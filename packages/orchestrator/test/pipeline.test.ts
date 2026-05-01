// @clawos/orchestrator pipeline tests — covers all five steps end-to-end:
// scan, credential verify, policy, execute callback, memory capture.

import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { generateKeyPairSync, sign as cryptoSign } from "node:crypto";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { tmpdir } from "node:os";

import { execute, verifyCredential, type AgentRequest } from "../src/index.js";

interface TestKeys {
  privatePem: string;
  publicPem: string;
}

function freshKeys(): TestKeys {
  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  return {
    privatePem: privateKey.export({ type: "pkcs8", format: "pem" }) as string,
    publicPem: publicKey.export({ type: "spki", format: "pem" }) as string,
  };
}

function signMessage(privatePem: string, message: string): Buffer {
  return cryptoSign(null, Buffer.from(message, "utf8"), privatePem);
}

let workDir: string;
let cleanProjectDir: string;
let leakyProjectDir: string;

beforeAll(() => {
  workDir = resolve(tmpdir(), `clawos-orch-${Date.now()}`);
  mkdirSync(workDir, { recursive: true });

  cleanProjectDir = resolve(workDir, "clean");
  mkdirSync(cleanProjectDir, { recursive: true });
  writeFileSync(
    resolve(cleanProjectDir, "package.json"),
    JSON.stringify({ name: "clean-agent" }),
  );
  writeFileSync(
    resolve(cleanProjectDir, ".gitignore"),
    ".env\n*.key\n*.pem\nnode_modules/\n",
  );
  writeFileSync(
    resolve(cleanProjectDir, "package-lock.json"),
    '{"lockfileVersion":3}',
  );

  leakyProjectDir = resolve(workDir, "leaky");
  mkdirSync(leakyProjectDir, { recursive: true });
  writeFileSync(
    resolve(leakyProjectDir, "package.json"),
    JSON.stringify({ name: "leaky-agent" }),
  );
  // Multiple critical findings to drive score below default threshold (60).
  writeFileSync(
    resolve(leakyProjectDir, "config.js"),
    [
      // Synthetic fixtures only — assembled at runtime to dodge platform secret scanners
      // while still matching Sentinel's credential patterns.
      "const OPENAI_API_KEY = " + "'sk-proj-' + 'A'.repeat(48);",
      "const ANTHROPIC_API_KEY = " + "'sk-ant-api03-' + 'A'.repeat(95);",
      "const HELIUS_KEY = 'helius-' + 'A'.repeat(40);",
      "const AWS_KEY = 'AKIAIOSFODNN7EXAMPLE';",
    ].join("\n"),
  );
});

afterAll(() => {
  if (workDir && existsSync(workDir)) rmSync(workDir, { recursive: true, force: true });
});

function buildRequest(overrides: Partial<AgentRequest> & { keys: TestKeys; cwd: string }): AgentRequest {
  const tx = { to: "0xABC", amount: 100, action: "transfer" };
  const payload = JSON.stringify(tx);
  const sig = signMessage(overrides.keys.privatePem, payload);
  return {
    agentConfig: { name: "test-agent", scanPath: overrides.cwd },
    agentPublicKeyPem: overrides.keys.publicPem,
    policySet: {
      maxTransactionAmount: 500,
      dailySpendingLimit: 2000,
      allowedCounterparties: [],
      restrictedHours: { block: false },
      multiSigThreshold: 1000,
    },
    transaction: tx,
    signature: sig,
    signedPayload: payload,
    threshold: 60,
    scanPath: overrides.cwd,
    memory: { enabled: false, cliPath: "/nonexistent", dbPath: "/nonexistent.db", agentId: "test" },
    execute: async () => ({ txHash: "mock" }),
    ...overrides,
  };
}

describe("execute() pipeline", () => {
  it("allows a clean request through every gate", async () => {
    const keys = freshKeys();
    const req = buildRequest({ keys, cwd: cleanProjectDir });
    const result = await execute(req);
    expect(result.blocked).toBe(false);
    expect(result.outcome).toEqual({ txHash: "mock" });
    expect(result.scan?.score).toBeGreaterThanOrEqual(60);
    expect(result.credential?.verified).toBe(true);
    expect(result.policy?.allow).toBe(true);
  });

  it("blocks when scan score is below threshold", async () => {
    const keys = freshKeys();
    const req = buildRequest({ keys, cwd: leakyProjectDir });
    const result = await execute(req);
    expect(result.blocked).toBe(true);
    expect(result.reason).toMatch(/below threshold/);
    expect(result.scan?.score).toBeLessThan(60);
  });

  it("blocks when credential signature does not verify", async () => {
    const keys = freshKeys();
    const wrongKeys = freshKeys();
    const req = buildRequest({ keys, cwd: cleanProjectDir });
    req.agentPublicKeyPem = wrongKeys.publicPem; // sig was made by `keys`, not `wrongKeys`
    const result = await execute(req);
    expect(result.blocked).toBe(true);
    expect(result.reason).toMatch(/credential/i);
  });

  it("blocks when policy denies", async () => {
    const keys = freshKeys();
    const req = buildRequest({ keys, cwd: cleanProjectDir });
    req.transaction = { to: "0xABC", amount: 5000, action: "transfer" };
    req.signedPayload = JSON.stringify(req.transaction);
    req.signature = signMessage(keys.privatePem, req.signedPayload as string);
    const result = await execute(req);
    expect(result.blocked).toBe(true);
    expect(result.policy?.allow).toBe(false);
  });

  it("treats memory shim failure as non-fatal", async () => {
    const keys = freshKeys();
    const req = buildRequest({ keys, cwd: cleanProjectDir });
    req.memory = {
      enabled: true,
      cliPath: "/nonexistent/cli.py",
      dbPath: "/tmp/clawos-orch-nope.db",
      agentId: "test",
    };
    const result = await execute(req);
    expect(result.blocked).toBe(false);
    expect(result.memory?.captured).toBe(false);
    expect(result.memory?.error).toBeTruthy();
  });
});

describe("verifyCredential", () => {
  it("verifies a valid signature", () => {
    const keys = freshKeys();
    const message = "hello clawos";
    const sig = signMessage(keys.privatePem, message);
    const result = verifyCredential({
      agentConfig: { name: "x" },
      agentPublicKeyPem: keys.publicPem,
      policySet: {},
      transaction: { amount: 0 },
      signature: sig,
      signedPayload: message,
      execute: async () => null,
    });
    expect(result.verified).toBe(true);
  });

  it("rejects a tampered payload", () => {
    const keys = freshKeys();
    const sig = signMessage(keys.privatePem, "original");
    const result = verifyCredential({
      agentConfig: { name: "x" },
      agentPublicKeyPem: keys.publicPem,
      policySet: {},
      transaction: { amount: 0 },
      signature: sig,
      signedPayload: "tampered",
      execute: async () => null,
    });
    expect(result.verified).toBe(false);
  });
});
