# @clawos/policy — ClawSteward

<p>
  <img src="https://img.shields.io/badge/tests-478%20passing%20(+20%20devnet)-brightgreen" alt="tests" />
  <img src="https://img.shields.io/badge/language-TypeScript-blue" alt="typescript" />
  <img src="https://img.shields.io/badge/runner-vitest-blue" alt="vitest" />
</p>

Pre-signing policy enforcement for AI agent transactions. Declarative rules in JSON — no code changes to update policy.

## What it does

ClawSteward evaluates every agent transaction against a policy set before the signature happens:

- **Spending limits** — per-transaction and rolling caps.
- **Counterparty allowlists** — restrict which addresses or APIs an agent can interact with.
- **Time-of-day restrictions** — block high-value actions outside business hours.
- **Multi-sig thresholds** — require additional approval above configurable limits.

Policies are JSON files in `policies/` — hot-reloadable, no redeploy required. Policy denial returns structured `{allow: false, reason, remediation}`. Audit logs stored in SQLite.

The 20 devnet tests self-skip without `SOLANA_RPC_URL` — they validate on-chain policy enforcement against a live Solana devnet.

## Usage

**Example policy** (`policies/default.json`):

```json
{
  "maxTransactionAmount": 500,
  "dailySpendingLimit": 2000,
  "allowedCounterparties": ["0xABC...", "0xDEF..."],
  "restrictedHours": { "block": true, "outside": "09:00-17:00" },
  "multiSigThreshold": 1000
}
```

**Evaluate a transaction:**

```typescript
import { evaluate } from "@clawos/policy";

const result = evaluate(transaction, policySet);

if (!result.allow) {
  console.log(result.reason);       // "Exceeds daily spending limit"
  console.log(result.remediation);  // "Request multi-sig approval"
}
```

## Quick Start

```bash
cd packages/policy
pnpm install
pnpm test  # 478 passing, 20 devnet skipped without SOLANA_RPC_URL
```

## Architecture

ClawSteward is a core service in the ClawOS kernel. It never imports other core packages (memory, security, credentials). The orchestrator calls it after Sentinel scoring and credential verification — policy is the final gate before execution.

Includes an MCP (Model Context Protocol) server for integration with AI development tools (e.g., Cursor, Claude Code).

## Project Structure

```
packages/policy/
├── src/
│   ├── core/       # Policy engine, evaluation logic
│   ├── chain/      # On-chain policy enforcement (Solana)
│   ├── mcp/        # MCP server integration
│   ├── db/         # SQLite audit log
│   └── cli/        # Policy CLI commands
├── policies/       # Default + example policy sets (JSON)
├── config/
├── dashboard/      # Next.js dashboard (slated for apps/dashboard/)
└── test/           # 16 vitest suites
```

> **Note:** `dashboard/` is a nested Next.js sub-package. It will be extracted to `apps/dashboard/` in a future cleanup.

> Full architecture + data flow: [ARCHITECTURE.md](../../ARCHITECTURE.md)
