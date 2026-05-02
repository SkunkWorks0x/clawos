// Cross-package integration tests — these actually exercise @clawos/security,
// @clawos/policy, and the Python @clawos/memory shim through the orchestrator.
// Distinct from pipeline.test.ts (which leaves memory disabled): tests 3 and 5
// here spawn the real Python shim and verify the captured record exists.

import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { generateKeyPairSync, sign as cryptoSign } from "node:crypto";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";

import { execute, type AgentRequest, type ClawosPolicySet } from "../src/index.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "..", "..", "..");
const MEMORY_CLI = resolve(REPO_ROOT, "packages", "memory", "cli.py");
const MEMORY_VENV_PYTHON = resolve(REPO_ROOT, "packages", "memory", ".venv", "bin", "python3");
const MEMORY_AVAILABLE = existsSync(MEMORY_CLI) && existsSync(MEMORY_VENV_PYTHON);

interface TestKeys {
  privatePem: string;
  publicPem: string;
}

interface AgentContext {
  cwd: string;
  keys: TestKeys;
  policy: ClawosPolicySet;
  dbPath: string;
}

const DEFAULT_POLICY: ClawosPolicySet = {
  maxTransactionAmount: 500,
  dailySpendingLimit: 2000,
  allowedCounterparties: [],
  restrictedHours: { block: false },
  multiSigThreshold: 1000,
};

function freshKeys(): TestKeys {
  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  return {
    privatePem: privateKey.export({ type: "pkcs8", format: "pem" }) as string,
    publicPem: publicKey.export({ type: "spki", format: "pem" }) as string,
  };
}

function scaffoldAgent(parent: string, name: string, leaky = false): AgentContext {
  const cwd = resolve(parent, name);
  mkdirSync(cwd, { recursive: true });
  writeFileSync(resolve(cwd, "package.json"), JSON.stringify({ name }));
  writeFileSync(resolve(cwd, ".gitignore"), ".env\n*.key\n*.pem\nnode_modules/\n");
  writeFileSync(resolve(cwd, "package-lock.json"), '{"lockfileVersion":3}');
  if (leaky) {
    // Same runtime-concatenated pattern used in pipeline.test.ts to satisfy
    // GitHub push protection while still tripping Sentinel's credential rules.
    writeFileSync(
      resolve(cwd, "config.js"),
      [
        "const OPENAI_API_KEY = " + "'sk-proj-' + 'A'.repeat(48);",
        "const ANTHROPIC_API_KEY = " + "'sk-ant-api03-' + 'A'.repeat(95);",
        "const HELIUS_KEY = 'helius-' + 'A'.repeat(40);",
        "const AWS_KEY = 'AKIAIOSFODNN7EXAMPLE';",
      ].join("\n"),
    );
  }
  return {
    cwd,
    keys: freshKeys(),
    policy: { ...DEFAULT_POLICY },
    dbPath: resolve(cwd, "memory.db"),
  };
}

function buildRequest(
  ctx: AgentContext,
  options: { amount?: number; useMemory?: boolean; agentId?: string } = {},
): AgentRequest {
  const tx = {
    to: "0xABC",
    amount: options.amount ?? 100,
    action: "transfer",
  };
  const payload = JSON.stringify(tx);
  const signature = cryptoSign(null, Buffer.from(payload, "utf8"), ctx.keys.privatePem);
  const agentId = options.agentId ?? "integration-test";
  return {
    agentConfig: { name: agentId, scanPath: ctx.cwd },
    agentPublicKeyPem: ctx.keys.publicPem,
    policySet: ctx.policy,
    transaction: tx,
    signature,
    signedPayload: payload,
    threshold: 60,
    scanPath: ctx.cwd,
    memory:
      options.useMemory && MEMORY_AVAILABLE
        ? {
            enabled: true,
            cliPath: MEMORY_CLI,
            pythonPath: MEMORY_VENV_PYTHON,
            dbPath: ctx.dbPath,
            agentId,
          }
        : { enabled: false, cliPath: "/nonexistent", dbPath: "/nonexistent.db", agentId },
    execute: async () => ({ txHash: "0xMOCK_INTEGRATION", recordedAt: Date.now() }),
  };
}

interface ShimMemory {
  id: string;
  type: string;
  content: string;
  goal_tag: string | null;
  importance: number;
  created_at: number;
}

function memShimRetrieve(ctx: AgentContext, agentId: string, query?: string): ShimMemory[] {
  const result = spawnSync(MEMORY_VENV_PYTHON, [MEMORY_CLI], {
    input: JSON.stringify({
      op: "retrieve",
      db: ctx.dbPath,
      agent_id: agentId,
      query: query ?? "",
      limit: 10,
    }),
    encoding: "utf8",
    timeout: 10_000,
  });
  if (result.status !== 0) {
    throw new Error(`memory shim retrieve exited ${result.status}: ${result.stderr}`);
  }
  const parsed = JSON.parse(result.stdout.trim()) as { ok: boolean; memories?: ShimMemory[]; error?: string };
  if (!parsed.ok) throw new Error(`memory shim retrieve failed: ${parsed.error}`);
  return parsed.memories ?? [];
}

let workDir: string;

beforeAll(() => {
  workDir = resolve(tmpdir(), `clawos-integration-${Date.now()}`);
  mkdirSync(workDir, { recursive: true });
});

afterAll(() => {
  if (workDir && existsSync(workDir)) rmSync(workDir, { recursive: true, force: true });
});

describe("integration: cross-package coordination through @clawos/orchestrator", () => {
  it("1. agent init → Sentinel scan → score above threshold → proceed", async () => {
    const ctx = scaffoldAgent(workDir, "scenario-1-clean");
    const result = await execute(buildRequest(ctx));
    expect(result.blocked).toBe(false);
    expect(result.scan?.score).toBeGreaterThanOrEqual(60);
    expect(result.credential?.verified).toBe(true);
    expect(result.policy?.allow).toBe(true);
    expect(result.outcome).toMatchObject({ txHash: "0xMOCK_INTEGRATION" });
  });

  it("2. agent init → Sentinel scan → score below threshold → blocked", async () => {
    const ctx = scaffoldAgent(workDir, "scenario-2-leaky", true);
    const result = await execute(buildRequest(ctx));
    expect(result.blocked).toBe(true);
    expect(result.scan?.score).toBeLessThan(60);
    expect(result.reason).toMatch(/below threshold/);
    // Steps after scan must not have run.
    expect(result.credential).toBeUndefined();
    expect(result.policy).toBeUndefined();
    expect(result.memory).toBeUndefined();
  });

  it.skipIf(!MEMORY_AVAILABLE)(
    "3. full pipeline → memory stores the result after execution",
    async () => {
      const ctx = scaffoldAgent(workDir, "scenario-3-memory");
      const result = await execute(buildRequest(ctx, { useMemory: true, agentId: "scenario-3" }));
      expect(result.blocked).toBe(false);
      expect(result.memory?.captured).toBe(true);
      expect(result.memory?.error).toBeUndefined();
      // The Python shim is responsible for creating the SQLite file.
      expect(existsSync(ctx.dbPath)).toBe(true);
    },
  );

  it("4. policy enforcement blocks a transaction that exceeds spending limit", async () => {
    const ctx = scaffoldAgent(workDir, "scenario-4-overlimit");
    // 600 > maxTransactionAmount=500 but < multiSigThreshold=1000 → trips max-tx rule specifically.
    const result = await execute(buildRequest(ctx, { amount: 600 }));
    expect(result.blocked).toBe(true);
    expect(result.scan?.score).toBeGreaterThanOrEqual(60); // scan passed
    expect(result.credential?.verified).toBe(true); // cred passed
    expect(result.policy?.allow).toBe(false); // policy denied
    expect(result.reason).toMatch(/exceeds max transaction/i);
    expect(result.remediation?.length ?? 0).toBeGreaterThan(0);
  });

  it.skipIf(!MEMORY_AVAILABLE)(
    "5. end-to-end → init → scan → policy → execute → memory captures the execution record",
    async () => {
      const ctx = scaffoldAgent(workDir, "scenario-5-e2e");
      const agentId = "scenario-5";
      const result = await execute(
        buildRequest(ctx, { amount: 250, useMemory: true, agentId }),
      );

      // Pipeline state at every stage:
      expect(result.blocked).toBe(false);
      expect(result.scan?.score).toBeGreaterThanOrEqual(60);
      expect(result.credential?.verified).toBe(true);
      expect(result.policy?.allow).toBe(true);
      expect(result.memory?.captured).toBe(true);

      // Then independently query the memory shim to confirm the record landed.
      const memories = memShimRetrieve(ctx, agentId);
      expect(memories.length).toBeGreaterThan(0);

      const captured = memories.find((m) => m.content.includes("transfer"));
      expect(captured, `expected a memory whose content contains 'transfer', got ${JSON.stringify(memories)}`).toBeDefined();
      expect(captured!.content).toContain("250"); // tx amount
      expect(captured!.content).toContain("0xABC"); // tx counterparty
      expect(captured!.type).toBe("episode"); // capture_event maps api_call_success → episode
    },
  );
});
