# @clawos/orchestrator

<p>
  <img src="https://img.shields.io/badge/tests-7%20passing-brightgreen" alt="tests" />
  <img src="https://img.shields.io/badge/language-TypeScript-blue" alt="typescript" />
</p>

Multi-agent swarm coordination with role-based access control. The only package that talks to multiple core services.

**Status:** Core coordination logic wired. 5-step pipeline (scan → cred → policy → execute → memory) runs end-to-end via root `pnpm demo`.

## What it does

The orchestrator is the cross-cutting layer in ClawOS. It wires together the four core services into a single execution pipeline:

```
Agent request
  → Sentinel scan (score 0–100, hard-block below threshold)
  → ClawU credential verification
  → ClawSteward policy evaluation (allow / deny / require approval)
  → Execute action
  → TotalReclaw memory capture + reflection
```

TypeScript packages are called via direct async calls (in-process, single Node event loop). Python memory is invoked via stdio JSON shim. No event bus or message queue in v0.1 — EventEmitter-based parallel coordination planned for v0.3.

## Architecture

The orchestrator enforces the ClawOS hard rule: core packages (memory, security, policy, credentials) never import each other. All cross-service communication goes through this layer.

## Project Structure

```
packages/orchestrator/
└── src/            # Coordination logic (in progress)
```

> Full architecture + data flow: [ARCHITECTURE.md](../../ARCHITECTURE.md)
