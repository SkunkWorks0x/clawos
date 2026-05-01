# @clawos/security — Sentinel

<p>
  <img src="https://img.shields.io/badge/tests-13%20passing-brightgreen" alt="tests" />
  <img src="https://img.shields.io/badge/language-TypeScript-blue" alt="typescript" />
  <img src="https://img.shields.io/badge/deps-zero-blue" alt="deps" />
</p>

Zero-dependency security scanner for AI agent configurations. Scores 0–100. Hard-blocks anything below threshold.

## What it does

Sentinel evaluates agent configurations across four dimensions:

- **API key exposure** — detects hardcoded secrets, overly broad scopes, leaked credentials.
- **Permission scope** — flags god-mode access patterns, missing least-privilege constraints.
- **Transport security** — checks TLS, endpoint validation, secure defaults.
- **Model access controls** — verifies model selection, rate limiting, output filtering.

Every scan is a pure function — stateless, deterministic, no side effects. Runs anywhere Node runs. This is the gate that caught a leaked Helius mainnet API key in production before it cost real money.

## Usage

```typescript
import { scan } from "@clawos/security";

const result = scan(agentConfig);

console.log(result.score);     // 0–100
console.log(result.findings);  // [{ severity, check, message, remediation }]

if (result.score < threshold) {
  // Hard block — agent cannot proceed
}
```

## Quick Start

```bash
cd packages/security
npm test  # 13 tests, 0 failures (node:test)
```

## Architecture

Sentinel is a core service in the ClawOS kernel. It never imports other core packages (memory, policy, credentials). The orchestrator calls Sentinel first in the execution pipeline — every agent action is scored before anything else runs.

## Project Structure

```
packages/security/
├── src/            # Scanner core, scoring engine, checks
└── test/           # sentinel.test.ts (10 cases)
```

> Full architecture + data flow: [ARCHITECTURE.md](../../ARCHITECTURE.md)
