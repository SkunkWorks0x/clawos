// @clawos/orchestrator — the only package that talks to multiple core services.
// Pipeline: Sentinel scan → Ed25519 cred verify → ClawSteward policy → execute → memory capture.

import { spawn } from "node:child_process";
import { createPublicKey, verify as cryptoVerify } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { scan, type AgentConfig, type PublicScanResult } from "@clawos/security";
import { evaluate, type ClawosPolicySet, type ClawosTransaction, type EvaluateResult } from "@clawos/policy";

export interface AgentRequest {
  agentConfig: AgentConfig;
  agentPublicKeyPem: string;
  policySet: ClawosPolicySet;
  transaction: ClawosTransaction;
  signature: Buffer | string;
  signedPayload: Buffer | string;
  threshold?: number;
  scanPath?: string;
  memory?: MemoryShimConfig;
  execute: () => Promise<unknown>;
}

export interface MemoryShimConfig {
  pythonPath?: string;
  cliPath: string;
  dbPath: string;
  agentId: string;
  enabled?: boolean;
}

export interface ExecutionResult {
  blocked: boolean;
  reason?: string;
  remediation?: string;
  outcome?: unknown;
  scan?: { score: number; findings: number };
  policy?: EvaluateResult;
  credential?: { verified: boolean };
  memory?: { captured: boolean; error?: string };
}

const DEFAULT_THRESHOLD = 60;

/** Run the full ClawOS pipeline against a single agent request. */
export async function execute(request: AgentRequest): Promise<ExecutionResult> {
  // Step 1 — Sentinel scan
  const threshold = request.threshold ?? DEFAULT_THRESHOLD;
  let scanResult: PublicScanResult;
  try {
    scanResult = scan(request.scanPath ?? request.agentConfig);
  } catch (err) {
    return {
      blocked: true,
      reason: `Security scan failed: ${(err as Error).message}`,
    };
  }
  const scanSummary = { score: scanResult.score, findings: scanResult.findings.length };
  if (scanResult.score < threshold) {
    return {
      blocked: true,
      reason: `Security score ${scanResult.score} below threshold ${threshold}`,
      scan: scanSummary,
    };
  }

  // Step 2 — Ed25519 credential verification (local only)
  const credential = verifyCredential(request);
  if (!credential.verified) {
    return {
      blocked: true,
      reason: "Invalid agent credential — signature did not verify against agent public key",
      scan: scanSummary,
      credential,
    };
  }

  // Step 3 — Policy evaluation
  const policy = evaluate(request.transaction, request.policySet);
  if (!policy.allow) {
    return {
      blocked: true,
      reason: policy.reason,
      remediation: policy.remediation,
      scan: scanSummary,
      credential,
      policy,
    };
  }

  // Step 4 — Execute action
  const outcome = await request.execute();

  // Step 5 — Memory capture (non-fatal)
  const memory = await captureToMemory(request, outcome);

  return {
    blocked: false,
    outcome,
    scan: scanSummary,
    credential,
    policy,
    memory,
  };
}

/** Verify an Ed25519 signature against the agent's PEM-encoded public key. */
export function verifyCredential(request: AgentRequest): { verified: boolean } {
  try {
    const publicKey = createPublicKey(request.agentPublicKeyPem);
    const sig = typeof request.signature === "string" ? Buffer.from(request.signature, "hex") : request.signature;
    const payload =
      typeof request.signedPayload === "string"
        ? Buffer.from(request.signedPayload, "utf8")
        : request.signedPayload;
    const ok = cryptoVerify(null, payload, publicKey, sig);
    return { verified: ok };
  } catch {
    return { verified: false };
  }
}

interface ShimResponse {
  ok: boolean;
  error?: string;
  memory_id?: string;
  reflection_ids?: string[];
  stats?: Record<string, unknown>;
  memories?: Array<Record<string, unknown>>;
}

async function captureToMemory(
  request: AgentRequest,
  outcome: unknown,
): Promise<{ captured: boolean; error?: string }> {
  if (request.memory?.enabled === false) {
    return { captured: false, error: "memory disabled" };
  }
  const memCfg = resolveMemoryConfig(request);
  if (!memCfg) {
    return { captured: false, error: "memory shim not configured" };
  }

  const payload = {
    op: "capture",
    db: memCfg.dbPath,
    agent_id: memCfg.agentId,
    action: request.transaction.action ?? "transfer",
    outcome: "success",
    details: {
      to: request.transaction.to,
      amount: request.transaction.amount,
      outcome_payload: outcome ?? null,
    },
  };

  const result = await runShim(memCfg, payload);
  if (!result.ok) {
    return { captured: false, error: result.error ?? "unknown error" };
  }
  return { captured: true };
}

function resolveMemoryConfig(request: AgentRequest): MemoryShimConfig | null {
  if (request.memory) return request.memory;
  // Best-effort default — only if the cli.py shim is present in the conventional location.
  const conventional = resolve(process.cwd(), "..", "memory", "cli.py");
  if (existsSync(conventional)) {
    return {
      pythonPath: "python3",
      cliPath: conventional,
      dbPath: resolve(process.cwd(), ".clawos", "memory.db"),
      agentId: request.agentConfig.name ?? "default",
    };
  }
  return null;
}

function runShim(memCfg: MemoryShimConfig, payload: unknown): Promise<ShimResponse> {
  return new Promise((resolveP) => {
    const python = memCfg.pythonPath ?? "python3";
    const child = spawn(python, [memCfg.cliPath], {
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let timer: NodeJS.Timeout | null = setTimeout(() => {
      child.kill("SIGKILL");
      resolveP({ ok: false, error: "memory shim timeout (>10s)" });
    }, 10_000);

    child.stdout.on("data", (d: Buffer) => {
      stdout += d.toString("utf8");
    });
    child.stderr.on("data", (d: Buffer) => {
      stderr += d.toString("utf8");
    });
    child.on("error", (err) => {
      if (timer) clearTimeout(timer);
      timer = null;
      resolveP({ ok: false, error: `spawn failed: ${err.message}` });
    });
    child.on("close", () => {
      if (timer) clearTimeout(timer);
      timer = null;
      const trimmed = stdout.trim();
      if (!trimmed) {
        resolveP({ ok: false, error: stderr.trim() || "empty response from shim" });
        return;
      }
      try {
        const parsed = JSON.parse(trimmed) as ShimResponse;
        resolveP(parsed);
      } catch (err) {
        resolveP({ ok: false, error: `invalid shim response: ${(err as Error).message}` });
      }
    });

    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
  });
}

/** Convenience helper: read a JSON file and parse it. */
export function readJsonFile<T = unknown>(path: string): T {
  const text = readFileSync(path, "utf8");
  return JSON.parse(text) as T;
}

export type { AgentConfig, PublicScanResult } from "@clawos/security";
export type { ClawosPolicySet, ClawosTransaction, EvaluateResult } from "@clawos/policy";
