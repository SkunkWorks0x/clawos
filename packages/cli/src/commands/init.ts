import chalk from "chalk";
import { generateKeyPairSync } from "node:crypto";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { basename, resolve } from "node:path";
import { scan } from "@clawos/security";

const DEFAULT_POLICY = {
  maxTransactionAmount: 500,
  dailySpendingLimit: 2000,
  allowedCounterparties: [] as string[],
  restrictedHours: { block: false },
  multiSigThreshold: 1000,
};

export interface InitArgs {
  cwd?: string;
  force?: boolean;
}

export interface InitResult {
  agentName: string;
  keyPath: string;
  pubPath: string;
  configPath: string;
  policyPath: string;
  publicKeyHex: string;
  score: number;
}

/** Scaffold a new ClawOS agent project in cwd. */
export async function runInit(args: InitArgs = {}): Promise<InitResult> {
  const cwd = args.cwd ?? process.cwd();
  const agentName = basename(cwd);

  const clawosDir = resolve(cwd, ".clawos");
  const policyDir = resolve(cwd, "policies");
  mkdirSync(clawosDir, { recursive: true });
  mkdirSync(policyDir, { recursive: true });

  const keyPath = resolve(clawosDir, "agent.key");
  const pubPath = resolve(clawosDir, "agent.pub");
  const configPath = resolve(cwd, "clawos.config.json");
  const policyPath = resolve(policyDir, "default.json");

  if (!args.force && existsSync(keyPath)) {
    throw new Error(`agent.key already exists at ${keyPath}; pass --force to overwrite`);
  }

  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  const privatePem = privateKey.export({ type: "pkcs8", format: "pem" }) as string;
  const publicPem = publicKey.export({ type: "spki", format: "pem" }) as string;
  const publicKeyHex = (publicKey.export({ type: "spki", format: "der" }) as Buffer)
    .subarray(-32)
    .toString("hex");

  writeFileSync(keyPath, privatePem, { mode: 0o600 });
  writeFileSync(pubPath, publicPem, "utf8");

  const config = {
    name: agentName,
    threshold: 60,
    publicKeyPath: ".clawos/agent.pub",
    policyPath: "policies/default.json",
    memoryDb: ".clawos/memory.db",
  };
  writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n", "utf8");
  writeFileSync(policyPath, JSON.stringify(DEFAULT_POLICY, null, 2) + "\n", "utf8");

  const ensureProjectMarker = resolve(cwd, "package.json");
  if (!existsSync(ensureProjectMarker)) {
    writeFileSync(
      ensureProjectMarker,
      JSON.stringify({ name: agentName, private: true }, null, 2) + "\n",
      "utf8",
    );
  }

  const gitignorePath = resolve(cwd, ".gitignore");
  if (!existsSync(gitignorePath)) {
    writeFileSync(
      gitignorePath,
      [".clawos/", "node_modules/", "*.key", "*.pem", ".env", ""].join("\n"),
      "utf8",
    );
  }
  const lockfilePath = resolve(cwd, "package-lock.json");
  if (!existsSync(lockfilePath)) {
    writeFileSync(lockfilePath, '{"lockfileVersion":3,"name":"' + agentName + '"}\n', "utf8");
  }

  let score = 100;
  try {
    const result = scan(cwd);
    score = result.score;
  } catch (err) {
    console.warn(chalk.yellow(`[clawos/cli] init scan skipped: ${(err as Error).message}`));
  }

  return {
    agentName,
    keyPath,
    pubPath,
    configPath,
    policyPath,
    publicKeyHex,
    score,
  };
}

export function printInitResult(result: InitResult, threshold = 60): void {
  console.log("");
  console.log(chalk.bold(`ClawOS agent initialized — ${result.agentName}`));
  console.log(`  keypair:    ${result.keyPath}`);
  console.log(`              ${result.pubPath}`);
  console.log(`  pubkey:     ${result.publicKeyHex.slice(0, 16)}…${result.publicKeyHex.slice(-8)}`);
  console.log(`  config:     ${result.configPath}`);
  console.log(`  policies:   ${result.policyPath}`);
  const scoreLine =
    result.score >= 80
      ? chalk.green(String(result.score))
      : result.score >= 50
        ? chalk.yellow(String(result.score))
        : chalk.red(String(result.score));
  const status = result.score >= threshold ? chalk.green("PASS") : chalk.red("FAIL");
  console.log(`  scan:       ${scoreLine} / 100   threshold ${threshold}   ${status}`);
  console.log("");
}
