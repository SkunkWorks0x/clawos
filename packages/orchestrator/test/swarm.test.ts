// Swarm subsystem tests — registry, decomposer, full pipeline including the
// closed-loop reflection dispatch and memory persistence.

import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";

import { AgentRegistry, decompose, runSwarm } from "../src/swarm/index.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "..", "..", "..");
const MEMORY_CLI = resolve(REPO_ROOT, "packages", "memory", "cli.py");
const MEMORY_VENV = resolve(REPO_ROOT, "packages", "memory", ".venv", "bin", "python3");
const MEMORY_AVAILABLE = existsSync(MEMORY_CLI) && existsSync(MEMORY_VENV);

let workDir: string;

beforeAll(() => {
  workDir = resolve(tmpdir(), `clawos-swarm-test-${Date.now()}`);
  mkdirSync(workDir, { recursive: true });
});

afterAll(() => {
  if (workDir && existsSync(workDir)) rmSync(workDir, { recursive: true, force: true });
});

describe("swarm.registry", () => {
  it("registers 5 agents and returns each one by name", () => {
    const r = new AgentRegistry();
    const seed = [
      { name: "alpha", role: "lead", capabilities: ["plan"] },
      { name: "bravo", role: "builder", capabilities: ["scaffold"] },
      { name: "charlie", role: "scanner", capabilities: ["scan"] },
      { name: "delta", role: "policy", capabilities: ["evaluate"] },
      { name: "echo", role: "memory", capabilities: ["recall"] },
    ];
    for (const a of seed) r.register(a);
    expect(r.size()).toBe(5);
    for (const a of seed) {
      const got = r.get(a.name);
      expect(got).toBeDefined();
      expect(got!.name).toBe(a.name);
      expect(got!.role).toBe(a.role);
    }
    expect(r.list().map((a) => a.name).sort()).toEqual(["alpha", "bravo", "charlie", "delta", "echo"]);
  });
});

describe("swarm.decompose", () => {
  it("routes the demo task to forge → blade → masterchief in order", () => {
    const subtasks = decompose("demo: ship the v0.1 launch readiness checklist");
    expect(subtasks.length).toBeGreaterThanOrEqual(3);
    expect(subtasks[0]!.agent).toBe("forge");
    expect(subtasks[1]!.agent).toBe("blade");
    expect(subtasks[2]!.agent).toBe("masterchief");
    // exactly one elevated subtask trips the policy flag
    expect(subtasks.filter((s) => s.elevated).length).toBe(1);
    expect(subtasks.find((s) => s.elevated)?.agent).toBe("blade");
  });
});

describe("swarm.pipeline (memory-backed)", () => {
  it.skipIf(!MEMORY_AVAILABLE)(
    "runs the full swarm and persists at least one memory entry",
    async () => {
      const session = resolve(workDir, "pipeline");
      mkdirSync(session, { recursive: true });
      const result = await runSwarm({
        task: "demo: integration smoke",
        workDir: session,
        quiet: true,
        cadenceMs: 0,
      });

      // Pipeline succeeded across the chain
      expect(result.steps.length).toBe(3);
      expect(result.steps.every((s) => !s.blocked)).toBe(true);
      expect(result.followup.dispatched).toBe(true);
      expect(result.reflection.ok).toBe(true);
      expect(existsSync(result.dbPath)).toBe(true);

      // Independently query the memory shim and verify entries landed.
      const stats = spawnSync(
        MEMORY_VENV,
        [MEMORY_CLI],
        {
          input: JSON.stringify({
            op: "stats",
            db: result.dbPath,
            agent_id: "forge",
          }),
          encoding: "utf8",
          timeout: 10_000,
        },
      );
      expect(stats.status).toBe(0);
      const parsed = JSON.parse(stats.stdout.trim()) as {
        ok: boolean;
        stats?: { total_active_memories?: number };
      };
      expect(parsed.ok).toBe(true);
      // forge captured at least one memory from its dispatch.
      expect(parsed.stats?.total_active_memories ?? 0).toBeGreaterThan(0);
    },
    30_000,
  );
});
