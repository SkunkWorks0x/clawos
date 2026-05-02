// Memory shim lifecycle wrapper. The @clawos/memory cli.py is one-shot
// (read one request → write one response → exit), and the orchestrator
// is forbidden from modifying memory's package, so init/dispose are
// scaffold for future persistent IPC. Each call() spawns its own python
// process with a 5s timeout — fail fast, never hang the demo.

import { spawnSync } from "node:child_process";

export interface ShimConfig {
  cliPath: string;
  pythonPath: string;
  dbPath: string;
  agentId: string;
}

export interface ShimResponse {
  ok: boolean;
  error?: string;
  memory_id?: string;
  reflection_ids?: string[];
  memories?: Array<Record<string, unknown>>;
  stats?: Record<string, unknown>;
}

const TIMEOUT_MS = 5000;

export class SwarmShim {
  private cfg: ShimConfig | null = null;
  private disposed = false;
  private readonly exitHandler = (): void => {
    this.dispose();
  };

  init(cfg: ShimConfig): void {
    this.cfg = cfg;
    this.disposed = false;
    process.on("exit", this.exitHandler);
    process.on("SIGINT", this.exitHandler);
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    process.off("exit", this.exitHandler);
    process.off("SIGINT", this.exitHandler);
    this.cfg = null;
  }

  call(payload: Record<string, unknown>): ShimResponse {
    if (!this.cfg) {
      return { ok: false, error: "shim not initialized" };
    }
    const merged: Record<string, unknown> = {
      db: this.cfg.dbPath,
      agent_id: this.cfg.agentId,
      ...payload,
    };
    const result = spawnSync(this.cfg.pythonPath, [this.cfg.cliPath], {
      input: JSON.stringify(merged),
      encoding: "utf8",
      timeout: TIMEOUT_MS,
    });
    if (result.status !== 0) {
      return { ok: false, error: result.stderr.trim() || `exit ${result.status}` };
    }
    try {
      return JSON.parse(result.stdout.trim()) as ShimResponse;
    } catch (err) {
      return { ok: false, error: `invalid shim response: ${(err as Error).message}` };
    }
  }
}
