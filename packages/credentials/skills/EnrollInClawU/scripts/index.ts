import { ethers } from 'ethers';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';
import config from '../config.json';

const execAsync = promisify(exec);

// ---------------------------------------------------------------------------
//  ABIs — extracted from ~/clawu/out/ Foundry build artifacts
// ---------------------------------------------------------------------------

const REGISTRY_ABI = [
  'function isEnrolled(address agent) view returns (bool)',
  'function enrollments(address) view returns (uint256 bond, uint8 rank, uint64 enrolledAt, bytes32 transcriptHash, bool active)',
  'function enroll(uint256 bondAmount, string acpJobRef)',
  'function MIN_BOND() view returns (uint256)',
  'event Enrolled(address indexed agent, uint256 bondAmount)',
];

const USDC_ABI = [
  'function balanceOf(address account) view returns (uint256)',
  'function allowance(address owner, address spender) view returns (uint256)',
  'function approve(address spender, uint256 value) returns (bool)',
];

// ---------------------------------------------------------------------------
//  Types
// ---------------------------------------------------------------------------

interface SkillInput {
  agentName: string;
  acpJobRef: string;
}

interface SkillOutput {
  success: boolean;
  alreadyEnrolled: boolean;
  enrollmentTx: string | null;
  bond: number;
  rank: number;
  error: string | null;
}

interface UniversityState {
  enrolled: boolean;
  enrollment_tx?: string;
  bond_amount?: number;
  rank?: number;
  goal?: string;
}

// ---------------------------------------------------------------------------
//  Constants
// ---------------------------------------------------------------------------

const BOND_AMOUNT = BigInt(config.enrollment.bondAmount); // 10_000_000 (10 USDC)
const BRIDGE_PATH = '~/.openclaw/shared/reclaw-bridge.py';
const TX_TIMEOUT_MS = 25_000; // 25s — leaves 5s margin in 30s decision loop budget

// ---------------------------------------------------------------------------
//  PLAYBOOK.md helpers
// ---------------------------------------------------------------------------

function getPlaybookPath(agentName: string): string {
  const home = process.env.HOME || '/root';
  return `${home}/.openclaw/workspaces/${agentName}/PLAYBOOK.md`;
}

function readUniversityState(agentName: string): UniversityState {
  const path = getPlaybookPath(agentName);
  if (!existsSync(path)) return { enrolled: false };

  const content = readFileSync(path, 'utf-8');
  const match = content.match(/# University \(ClawU\)\n([\s\S]*?)(?=\n#|$)/);
  if (!match) return { enrolled: false };

  const section = match[1];
  return {
    enrolled: /^enrolled:\s*true/m.test(section),
    enrollment_tx: section.match(/^enrollment_tx:\s*(\S+)/m)?.[1],
    bond_amount: parseInt(section.match(/^bond_amount:\s*(\d+)/m)?.[1] || '0'),
    rank: parseInt(section.match(/^rank:\s*(\d+)/m)?.[1] || '0'),
    goal: section.match(/^goal:\s*(\S+)/m)?.[1],
  };
}

function updatePlaybook(agentName: string, txHash: string, bond: bigint, rank: number): void {
  const path = getPlaybookPath(agentName);
  if (!existsSync(path)) return;

  let content = readFileSync(path, 'utf-8');

  const universityBlock = [
    '# University (ClawU)',
    `enrolled: true`,
    `enrollment_tx: ${txHash}`,
    `bond_amount: ${bond.toString()}`,
    `rank: ${rank}`,
    `transcript_hashes:`,
    `current_credentials: 0`,
    `goal: academic_credential`,
    `next_class_priority: defi`,
  ].join('\n');

  // Replace existing University section or append
  const existingMatch = content.match(/# University \(ClawU\)\n[\s\S]*?(?=\n#|$)/);
  if (existingMatch) {
    content = content.replace(existingMatch[0], universityBlock);
  } else {
    content += '\n\n' + universityBlock + '\n';
  }

  writeFileSync(path, content, 'utf-8');
}

// ---------------------------------------------------------------------------
//  TotalReclaw helper
// ---------------------------------------------------------------------------

async function saveEnrollmentMemory(agentName: string, txHash: string): Promise<void> {
  const content = `Enrolled at ClawU on Base Sepolia. Bond: 10 USDC. Tx: ${txHash}. Rank: student (0). Ready for classes.`;
  const escaped = content.replace(/'/g, "'\\''");

  try {
    await execAsync(
      `python3 ${BRIDGE_PATH} save ${agentName} episode '${escaped}' --goal academic_credential --importance 9`,
      { timeout: 5_000 }
    );
  } catch (err) {
    // TotalReclaw failure is non-fatal — enrollment still succeeded on-chain
    console.error('[EnrollInClawU] TotalReclaw save failed (non-fatal):', (err as Error).message);
  }
}

// ---------------------------------------------------------------------------
//  Main execution
// ---------------------------------------------------------------------------

export async function execute(_ctx: unknown, input: SkillInput): Promise<SkillOutput> {
  const { agentName, acpJobRef } = input;

  if (!agentName || !acpJobRef) {
    return { success: false, alreadyEnrolled: false, enrollmentTx: null, bond: 0, rank: 0, error: 'Missing agentName or acpJobRef' };
  }

  // --- Setup provider + wallet ---
  const privateKey = process.env.AGENT_PRIVATE_KEY;
  if (!privateKey) {
    return { success: false, alreadyEnrolled: false, enrollmentTx: null, bond: 0, rank: 0, error: 'AGENT_PRIVATE_KEY not set' };
  }

  const provider = new ethers.JsonRpcProvider(config.rpcUrl);
  const wallet = new ethers.Wallet(privateKey, provider);
  const agentAddress = wallet.address;

  const registry = new ethers.Contract(config.contracts.registry, REGISTRY_ABI, wallet);
  const usdc = new ethers.Contract(config.contracts.usdc, USDC_ABI, wallet);

  // --- Step 1: Check on-chain enrollment (ground truth, not PLAYBOOK) ---
  try {
    const alreadyEnrolled: boolean = await registry.isEnrolled(agentAddress);
    if (alreadyEnrolled) {
      const enrollment = await registry.enrollments(agentAddress);
      return {
        success: true,
        alreadyEnrolled: true,
        enrollmentTx: null,
        bond: Number(enrollment.bond),
        rank: Number(enrollment.rank),
        error: null,
      };
    }
  } catch (err) {
    return { success: false, alreadyEnrolled: false, enrollmentTx: null, bond: 0, rank: 0, error: `Registry read failed: ${(err as Error).message}` };
  }

  // --- Step 2: Check USDC balance ---
  let balance: bigint;
  try {
    balance = await usdc.balanceOf(agentAddress);
  } catch (err) {
    return { success: false, alreadyEnrolled: false, enrollmentTx: null, bond: 0, rank: 0, error: `USDC balance check failed: ${(err as Error).message}` };
  }

  if (balance < BOND_AMOUNT) {
    return {
      success: false,
      alreadyEnrolled: false,
      enrollmentTx: null,
      bond: 0,
      rank: 0,
      error: `Insufficient USDC: have ${balance.toString()} (${Number(balance) / 1e6} USDC), need ${BOND_AMOUNT.toString()} (${Number(BOND_AMOUNT) / 1e6} USDC)`,
    };
  }

  // --- Step 3: Approve Registry to spend USDC ---
  try {
    const currentAllowance: bigint = await usdc.allowance(agentAddress, config.contracts.registry);
    if (currentAllowance < BOND_AMOUNT) {
      const approveTx = await usdc.approve(config.contracts.registry, ethers.MaxUint256);
      await approveTx.wait(1);
    }
  } catch (err) {
    return { success: false, alreadyEnrolled: false, enrollmentTx: null, bond: 0, rank: 0, error: `USDC approval failed: ${(err as Error).message}` };
  }

  // --- Step 4: Enroll ---
  let enrollTx: ethers.TransactionResponse;
  try {
    enrollTx = await registry.enroll(BOND_AMOUNT, acpJobRef, {
      gasLimit: 300_000n, // Base L2 gas is cheap, generous limit
    });
  } catch (err) {
    const msg = (err as Error).message;
    if (msg.includes('AlreadyEnrolled')) {
      // Race condition: enrolled between our check and our tx
      const enrollment = await registry.enrollments(agentAddress);
      return { success: true, alreadyEnrolled: true, enrollmentTx: null, bond: Number(enrollment.bond), rank: Number(enrollment.rank), error: null };
    }
    return { success: false, alreadyEnrolled: false, enrollmentTx: null, bond: 0, rank: 0, error: `enroll() tx failed: ${msg}` };
  }

  // --- Step 5: Wait for confirmation ---
  let receipt: ethers.TransactionReceipt | null;
  try {
    receipt = await Promise.race([
      enrollTx.wait(1),
      new Promise<null>((_, reject) => setTimeout(() => reject(new Error('Tx confirmation timeout')), TX_TIMEOUT_MS)),
    ]) as ethers.TransactionReceipt | null;

    if (!receipt || receipt.status !== 1) {
      return { success: false, alreadyEnrolled: false, enrollmentTx: enrollTx.hash, bond: 0, rank: 0, error: `Tx reverted on-chain: ${enrollTx.hash}` };
    }
  } catch (err) {
    return { success: false, alreadyEnrolled: false, enrollmentTx: enrollTx.hash, bond: 0, rank: 0, error: `Tx confirmation failed: ${(err as Error).message}` };
  }

  // --- Step 6: Read back enrollment to verify ---
  let bond: bigint;
  let rank: number;
  try {
    const enrollment = await registry.enrollments(agentAddress);
    bond = enrollment.bond as bigint;
    rank = Number(enrollment.rank);

    if (!enrollment.active) {
      return { success: false, alreadyEnrolled: false, enrollmentTx: enrollTx.hash, bond: 0, rank: 0, error: 'Enrollment not active after tx — unexpected state' };
    }
  } catch (err) {
    return { success: false, alreadyEnrolled: false, enrollmentTx: enrollTx.hash, bond: 0, rank: 0, error: `Post-enrollment verification failed: ${(err as Error).message}` };
  }

  // --- Step 7: Update PLAYBOOK.md ---
  try {
    updatePlaybook(agentName, enrollTx.hash, bond, rank);
  } catch (err) {
    // Non-fatal: on-chain enrollment succeeded, PLAYBOOK update failed
    console.error('[EnrollInClawU] PLAYBOOK update failed (non-fatal):', (err as Error).message);
  }

  // --- Step 8: Save to TotalReclaw ---
  await saveEnrollmentMemory(agentName, enrollTx.hash);

  // --- Done ---
  return {
    success: true,
    alreadyEnrolled: false,
    enrollmentTx: enrollTx.hash,
    bond: Number(bond),
    rank,
    error: null,
  };
}
