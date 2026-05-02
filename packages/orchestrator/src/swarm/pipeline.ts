// Swarm pipeline — coordinates registry → decompose → per-subtask execute()
// → reflection → ONE closed-loop follow-up. The closed-loop step is the
// differentiator: agents improve their own dispatch through reflection.

import { generateKeyPairSync, sign as cryptoSign, randomUUID } from "node:crypto";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { performance } from "node:perf_hooks";

import { execute, type AgentRequest, type ClawosPolicySet } from "../index.js";
import { defaultRegistry, type AgentRegistry } from "./registry.js";
import { decompose, followupSubtask, type Subtask } from "./decompose.js";
import { SwarmShim } from "./shim.js";
import { SwarmLogger } from "./log.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "..", "..", "..", "..");
const MEMORY_CLI = resolve(REPO_ROOT, "packages", "memory", "cli.py");
const MEMORY_VENV = resolve(REPO_ROOT, "packages", "memory", ".venv", "bin", "python3");

const DEFAULT_TASK = "demo: ship the v0.1 launch readiness checklist";

const DEFAULT_POLICY: ClawosPolicySet = {
  maxTransactionAmount: 500,
  dailySpendingLimit: 10000,
  allowedCounterparties: [],
  restrictedHours: { block: false },
  multiSigThreshold: 1000,
};

export interface SwarmOptions {
  task?: string;
  workDir?: string;
  quiet?: boolean;
  cadenceMs?: number;
  registry?: AgentRegistry;
}

export interface SwarmStep {
  subtask: Subtask;
  blocked: boolean;
  score: number | null;
  durationMs: number;
  flagged: boolean;
}

export interface SwarmResult {
  sessionId: string;
  task: string;
  workDir: string;
  dbPath: string;
  steps: SwarmStep[];
  reflection: { ok: boolean; ids: string[] };
  followup: { dispatched: boolean; agent: string; durationMs: number };
  totalMs: number;
}

/** Run the full multi-agent swarm pipeline including the closed loop. */
export async function runSwarm(options: SwarmOptions = {}): Promise<SwarmResult> {
  const sessionId = randomUUID().slice(0, 8);
  const task = options.task ?? DEFAULT_TASK;
  const registry = options.registry ?? defaultRegistry();
  const log = new SwarmLogger({
    quiet: options.quiet ?? false,
    cadenceMs: options.cadenceMs ?? 90,
  });

  const workDir = options.workDir ?? resolve(tmpdir(), `clawos-swarm-${sessionId}`);
  mkdirSync(workDir, { recursive: true });
  scaffoldClean(workDir, sessionId);
  const dbPath = resolve(workDir, "swarm.db");

  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  const privatePem = privateKey.export({ type: "pkcs8", format: "pem" }) as string;
  const publicPem = publicKey.export({ type: "spki", format: "pem" }) as string;

  const shim = new SwarmShim();
  const shimAvailable = existsSync(MEMORY_CLI) && existsSync(MEMORY_VENV);
  if (shimAvailable) {
    shim.init({
      cliPath: MEMORY_CLI,
      pythonPath: MEMORY_VENV,
      dbPath,
      agentId: `swarm-${sessionId}`,
    });
  }

  await log.header(`ClawOS swarm — ${task}`, sessionId);

  const subtasks = decompose(task);
  const t0 = performance.now();
  const steps: SwarmStep[] = [];

  for (const sub of subtasks) {
    if (!registry.has(sub.agent)) {
      throw new Error(`agent ${sub.agent} is not registered`);
    }
    const tStart = performance.now();
    const req = buildRequest({
      sub,
      workDir,
      privatePem,
      publicPem,
      dbPath,
      shimAvailable,
    });
    const result = await execute(req);
    const durationMs = performance.now() - tStart;

    if (sub.elevated) {
      await log.flag("flagged: elevated scope — auto-approved under demo policy");
    }
    await log.step(
      sub.agent,
      `${sub.description}${result.blocked ? " — BLOCKED" : ""}`,
      durationMs,
    );
    steps.push({
      subtask: sub,
      blocked: result.blocked,
      score: result.scan?.score ?? null,
      durationMs,
      flagged: sub.elevated,
    });
  }

  let reflectionIds: string[] = [];
  let reflectionOk = false;
  if (shimAvailable) {
    const refl = shim.call({ op: "reflect" });
    reflectionOk = refl.ok;
    reflectionIds = refl.reflection_ids ?? [];
  }
  await log.step(
    "masterchief",
    `reflect (${reflectionIds.length} memo${reflectionIds.length === 1 ? "" : "s"})`,
  );

  const followup = followupSubtask();
  if (!registry.has(followup.agent)) {
    throw new Error(`followup agent ${followup.agent} not registered`);
  }
  const fStart = performance.now();
  const fReq = buildRequest({
    sub: followup,
    workDir,
    privatePem,
    publicPem,
    dbPath,
    shimAvailable,
  });
  const fResult = await execute(fReq);
  const fDurationMs = performance.now() - fStart;
  await log.followup("Self-directed iteration: 1 follow-up dispatched from reflection");
  await log.step(
    followup.agent,
    `${followup.description}${fResult.blocked ? " — BLOCKED" : ""}`,
    fDurationMs,
  );

  const totalMs = performance.now() - t0;
  await log.summary(
    `swarm complete — ${subtasks.length + 1} dispatches, ${reflectionIds.length} reflection${reflectionIds.length === 1 ? "" : "s"}, ${totalMs.toFixed(1)}ms`,
  );

  shim.dispose();

  return {
    sessionId,
    task,
    workDir,
    dbPath,
    steps,
    reflection: { ok: reflectionOk, ids: reflectionIds },
    followup: { dispatched: !fResult.blocked, agent: followup.agent, durationMs: fDurationMs },
    totalMs,
  };
}

function scaffoldClean(dir: string, sessionId: string): void {
  writeFileSync(resolve(dir, "package.json"), JSON.stringify({ name: `swarm-${sessionId}` }));
  writeFileSync(resolve(dir, ".gitignore"), ".env\n*.key\n*.pem\nnode_modules/\n");
  writeFileSync(resolve(dir, "package-lock.json"), '{"lockfileVersion":3}');
}

interface BuildArgs {
  sub: Subtask;
  workDir: string;
  privatePem: string;
  publicPem: string;
  dbPath: string;
  shimAvailable: boolean;
}

function buildRequest(args: BuildArgs): AgentRequest {
  const tx = { to: "0xSWARM", amount: args.sub.amount, action: args.sub.action };
  const payload = JSON.stringify(tx);
  const signature = cryptoSign(null, Buffer.from(payload, "utf8"), args.privatePem);
  return {
    agentConfig: { name: args.sub.agent, scanPath: args.workDir },
    agentPublicKeyPem: args.publicPem,
    policySet: DEFAULT_POLICY,
    transaction: tx,
    signature,
    signedPayload: payload,
    threshold: 60,
    scanPath: args.workDir,
    memory: args.shimAvailable
      ? {
          enabled: true,
          cliPath: MEMORY_CLI,
          pythonPath: MEMORY_VENV,
          dbPath: args.dbPath,
          agentId: args.sub.agent,
        }
      : { enabled: false, cliPath: "/none", dbPath: "/none.db", agentId: args.sub.agent },
    execute: async () => ({ subtask: args.sub.description }),
  };
}
