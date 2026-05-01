import chalk from "chalk";
import { sign as cryptoSign, createPrivateKey } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execute, type AgentRequest } from "@clawos/orchestrator";

import { runInit } from "./init.js";

const TICK = chalk.green("✓");
const CROSS = chalk.red("✗");

export interface DemoOptions {
  cwd?: string;
  threshold?: number;
}

// packages/cli/src/commands/demo.ts → up four = repo root.
const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT_FROM_CLI = resolve(HERE, "..", "..", "..", "..");

/** Run the end-to-end demo against the agent in cwd. */
export async function runDemo(opts: DemoOptions = {}): Promise<number> {
  const cwd = opts.cwd ?? process.cwd();
  const threshold = opts.threshold ?? 60;
  const t0 = Date.now();

  if (!existsSync(resolve(cwd, "clawos.config.json"))) {
    console.log(chalk.gray(`  …no agent found, running init first`));
    const init = await runInit({ cwd });
    console.log(`${TICK} Agent initialized (keypair + config + policies)`);
    console.log(chalk.gray(`     pubkey ${init.publicKeyHex.slice(0, 16)}…`));
  } else {
    console.log(`${TICK} Agent already initialized — using existing keypair`);
  }

  const config = JSON.parse(readFileSync(resolve(cwd, "clawos.config.json"), "utf8")) as {
    name?: string;
    threshold?: number;
    publicKeyPath?: string;
    policyPath?: string;
    memoryDb?: string;
  };
  const pubPath = resolve(cwd, config.publicKeyPath ?? ".clawos/agent.pub");
  const keyPath = resolve(cwd, ".clawos/agent.key");
  const policyPath = resolve(cwd, config.policyPath ?? "policies/default.json");

  const publicKeyPem = readFileSync(pubPath, "utf8");
  const privateKeyPem = readFileSync(keyPath, "utf8");
  const policySet = JSON.parse(readFileSync(policyPath, "utf8"));

  const transaction = { to: "0xDEAD" + "0".repeat(36), amount: 150, action: "transfer" };
  const signedPayload = JSON.stringify(transaction);
  const privateKey = createPrivateKey(privateKeyPem);
  const signature = cryptoSign(null, Buffer.from(signedPayload, "utf8"), privateKey);

  const memoryCli = findMemoryShim();
  const request: AgentRequest = {
    agentConfig: { name: config.name ?? "demo-agent", scanPath: cwd },
    agentPublicKeyPem: publicKeyPem,
    policySet,
    transaction,
    signature,
    signedPayload,
    threshold,
    scanPath: cwd,
    memory: memoryCli
      ? {
          enabled: true,
          cliPath: memoryCli.cliPath,
          pythonPath: memoryCli.pythonPath,
          dbPath: resolve(cwd, config.memoryDb ?? ".clawos/memory.db"),
          agentId: config.name ?? "demo-agent",
        }
      : undefined,
    execute: async () => ({ txHash: "0xMOCK" + Date.now().toString(16) }),
  };

  const result = await execute(request);

  if (result.scan) {
    const sevColor =
      result.scan.score >= 80 ? chalk.green : result.scan.score >= 50 ? chalk.yellow : chalk.red;
    const criticals = "?"; // detailed counts not exposed in summary
    void criticals;
    console.log(
      `${TICK} Sentinel scan: ${sevColor(String(result.scan.score))}/100 (${result.scan.findings} findings)`,
    );
  }

  if (result.blocked && result.scan && result.scan.score < threshold) {
    console.log(`${CROSS} Pipeline blocked: ${result.reason}`);
    return 1;
  }

  if (result.credential) {
    if (result.credential.verified) {
      console.log(`${TICK} Credential verified (Ed25519)`);
    } else {
      console.log(`${CROSS} Credential failed: ${result.reason}`);
      return 1;
    }
  }

  if (result.policy) {
    if (result.policy.allow) {
      console.log(
        `${TICK} Policy approved (amount ${transaction.amount} < limit ${policySet.maxTransactionAmount ?? "n/a"})`,
      );
    } else {
      console.log(`${CROSS} Policy denied: ${result.policy.reason}`);
      console.log(chalk.gray(`     remediation: ${result.policy.remediation}`));
      return 1;
    }
  }

  if (!result.blocked) {
    const outcome = result.outcome as { txHash?: string } | undefined;
    console.log(`${TICK} Transaction executed (mock)${outcome?.txHash ? ` ${chalk.gray(outcome.txHash)}` : ""}`);
  }

  if (result.memory) {
    if (result.memory.captured) {
      console.log(`${TICK} Memory captured (1 entry stored)`);
    } else {
      console.log(`${chalk.yellow("•")} Memory shim non-fatal warning: ${result.memory.error ?? "skipped"}`);
    }
  } else {
    console.log(`${chalk.yellow("•")} Memory step skipped (no shim configured)`);
  }

  // Reflection trigger — best-effort follow-up call to the same shim.
  if (memoryCli) {
    const reflectErr = await runReflect(memoryCli, resolve(cwd, config.memoryDb ?? ".clawos/memory.db"), config.name ?? "demo-agent");
    if (reflectErr === null) {
      console.log(`${TICK} Reflection triggered (deterministic pass)`);
    } else {
      console.log(`${chalk.yellow("•")} Reflection skipped: ${reflectErr}`);
    }
  }

  const elapsed = Date.now() - t0;
  console.log("");
  console.log(chalk.bold(`pipeline complete in ${elapsed}ms`));
  return 0;
}

interface MemoryShimLocation {
  cliPath: string;
  pythonPath: string;
}

function findMemoryShim(): MemoryShimLocation | null {
  const candidates = [
    process.env.CLAWOS_MEMORY_CLI,
    resolve(REPO_ROOT_FROM_CLI, "packages", "memory", "cli.py"),
    resolve(process.cwd(), "..", "memory", "cli.py"),
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

async function runReflect(loc: MemoryShimLocation, dbPath: string, agentId: string): Promise<string | null> {
  return new Promise((resolveP) => {
    import("node:child_process").then(({ spawn }) => {
      const child = spawn(loc.pythonPath, [loc.cliPath], { stdio: ["pipe", "pipe", "pipe"] });
      let stdout = "";
      let stderr = "";
      const timer = setTimeout(() => {
        child.kill("SIGKILL");
        resolveP("timeout");
      }, 8_000);
      child.stdout.on("data", (d: Buffer) => {
        stdout += d.toString("utf8");
      });
      child.stderr.on("data", (d: Buffer) => {
        stderr += d.toString("utf8");
      });
      child.on("error", (err) => {
        clearTimeout(timer);
        resolveP(`spawn error: ${err.message}`);
      });
      child.on("close", () => {
        clearTimeout(timer);
        try {
          const parsed = JSON.parse(stdout.trim());
          if (parsed.ok) resolveP(null);
          else resolveP(parsed.error ?? "shim error");
        } catch {
          resolveP(stderr.trim() || "invalid shim response");
        }
      });
      child.stdin.write(JSON.stringify({ op: "reflect", db: dbPath, agent_id: agentId }));
      child.stdin.end();
    });
  });
}
