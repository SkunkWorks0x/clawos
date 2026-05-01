import chalk from "chalk";
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT_FROM_CLI = resolve(HERE, "..", "..", "..", "..");

interface ClawosConfig {
  name?: string;
  threshold?: number;
  publicKeyPath?: string;
  policyPath?: string;
  memoryDb?: string;
}

interface PolicyJson {
  maxTransactionAmount?: number;
  dailySpendingLimit?: number;
  allowedCounterparties?: string[];
  multiSigThreshold?: number;
  restrictedHours?: { block?: boolean; outside?: string };
}

/** Print the local agent status. Returns process exit code. */
export async function runStatus(opts: { cwd?: string } = {}): Promise<number> {
  const cwd = opts.cwd ?? process.cwd();
  const configPath = resolve(cwd, "clawos.config.json");
  if (!existsSync(configPath)) {
    console.log(chalk.yellow("No agent found. Run `clawos init` first."));
    return 1;
  }

  const config = JSON.parse(readFileSync(configPath, "utf8")) as ClawosConfig;
  const pubPath = resolve(cwd, config.publicKeyPath ?? ".clawos/agent.pub");
  const policyPath = resolve(cwd, config.policyPath ?? "policies/default.json");
  const dbPath = resolve(cwd, config.memoryDb ?? ".clawos/memory.db");

  const pubkey = existsSync(pubPath) ? truncatePub(readFileSync(pubPath, "utf8")) : "(missing)";
  const policy: PolicyJson = existsSync(policyPath)
    ? (JSON.parse(readFileSync(policyPath, "utf8")) as PolicyJson)
    : {};

  console.log("");
  console.log(chalk.bold(`ClawOS agent — ${config.name ?? "(unnamed)"}`));
  console.log(`  pubkey:        ${pubkey}`);
  console.log(`  threshold:     ${config.threshold ?? 60}`);
  console.log(`  policy:`);
  console.log(`    max tx:        ${policy.maxTransactionAmount ?? "—"}`);
  console.log(`    daily limit:   ${policy.dailySpendingLimit ?? "—"}`);
  console.log(`    multi-sig at:  ${policy.multiSigThreshold ?? "—"}`);
  console.log(
    `    counterparties: ${(policy.allowedCounterparties?.length ?? 0) === 0 ? "(open)" : (policy.allowedCounterparties ?? []).join(", ")}`,
  );

  const memStats = await readMemoryStats(dbPath, config.name ?? "default");
  if (memStats === null) {
    console.log(`  memory:        ${chalk.gray("no DB yet")}  (${dbPath})`);
  } else {
    console.log(`  memory:        ${memStats.totalActive} entries`);
    if (memStats.lastReflection) {
      console.log(`    last reflection: ${memStats.lastReflection}`);
    }
  }
  console.log("");
  return 0;
}

function truncatePub(pem: string): string {
  // Take the base64 body, hash a short fingerprint look-alike.
  const body = pem
    .replace(/-----BEGIN [^-]+-----/g, "")
    .replace(/-----END [^-]+-----/g, "")
    .replace(/\s/g, "");
  if (body.length < 20) return body;
  return `${body.slice(0, 16)}…${body.slice(-8)}`;
}

interface MemoryStatsResponse {
  ok: boolean;
  stats?: {
    total_active_memories?: number;
    by_type?: Record<string, number>;
  };
  memories?: Array<Record<string, unknown>>;
  error?: string;
}

interface MemorySummary {
  totalActive: number;
  lastReflection: string | null;
}

async function readMemoryStats(dbPath: string, agentId: string): Promise<MemorySummary | null> {
  if (!existsSync(dbPath)) return null;
  const shim = findShim();
  if (!shim) return { totalActive: -1, lastReflection: null };

  const stats = await runShim(shim, { op: "stats", db: dbPath, agent_id: agentId });
  if (!stats.ok || !stats.stats) return null;
  const total = stats.stats.total_active_memories ?? 0;

  const reflections = await runShim(shim, {
    op: "retrieve",
    db: dbPath,
    agent_id: agentId,
    query: "",
    limit: 1,
  });
  let lastReflection: string | null = null;
  if (reflections.ok && reflections.memories && reflections.memories.length > 0) {
    const memory = reflections.memories[0]!;
    if (memory["type"] === "reflection") {
      const created = memory["created_at"];
      if (typeof created === "number") {
        lastReflection = new Date(created * 1000).toISOString();
      }
    }
  }
  return { totalActive: total, lastReflection };
}

interface ShimLocation {
  cliPath: string;
  pythonPath: string;
}

function findShim(): ShimLocation | null {
  const candidates = [
    process.env.CLAWOS_MEMORY_CLI,
    resolve(REPO_ROOT_FROM_CLI, "packages", "memory", "cli.py"),
  ].filter((p): p is string => Boolean(p));
  for (const c of candidates) {
    if (existsSync(c)) {
      const venvPython = resolve(c, "..", ".venv", "bin", "python3");
      const pythonPath = existsSync(venvPython) ? venvPython : process.env.CLAWOS_PYTHON ?? "python3";
      return { cliPath: c, pythonPath };
    }
  }
  return null;
}

function runShim(loc: ShimLocation, payload: unknown): Promise<MemoryStatsResponse> {
  return new Promise((resolveP) => {
    const child = spawn(loc.pythonPath, [loc.cliPath], { stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      resolveP({ ok: false, error: "timeout" });
    }, 5_000);
    child.stdout.on("data", (d: Buffer) => {
      stdout += d.toString("utf8");
    });
    child.on("error", () => {
      clearTimeout(timer);
      resolveP({ ok: false, error: "spawn error" });
    });
    child.on("close", () => {
      clearTimeout(timer);
      try {
        resolveP(JSON.parse(stdout.trim()) as MemoryStatsResponse);
      } catch {
        resolveP({ ok: false, error: "invalid response" });
      }
    });
    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
  });
}
