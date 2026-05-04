<p align="center">
  <strong>ClawOS</strong><br/>
  The AI operating system for companies.
</p>

<p align="center">
  <a href="https://github.com/SkunkWorks0x/clawos/actions/workflows/ci.yml"><img src="https://github.com/SkunkWorks0x/clawos/actions/workflows/ci.yml/badge.svg" alt="tests" /></a>
  <img src="https://img.shields.io/badge/failures-0-brightgreen" alt="failures" />
  <img src="https://img.shields.io/badge/packages-6-blue" alt="packages" />
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="license" />
</p>

---

AI agents today are stateless, unsecured, and uncoordinated. They forget everything between calls, run with god-mode API keys, sign transactions without guardrails, and can't prove who they are. Companies can't put them in front of real money, customers, or compliance teams.

ClawOS fixes this. It's the missing control plane — persistent memory, policy-enforced security, verifiable credentials, and multi-agent orchestration as a unified kernel. Agents that remember, follow rules, prove identity, and work together.

Unlike LangChain (stateless chains), CrewAI (orchestration only), or Dust (knowledge layer without identity or guardrails), ClawOS is the full kernel — memory, security, policy, and credentials as first-class primitives.

> Built for engineering teams shipping production multi-agent systems in finance, operations, or regulated workflows — where stateless scripts fail audit and can't touch real money.

## Quick Start

```bash
git clone https://github.com/SkunkWorks0x/clawos.git
cd clawos && pnpm install
pnpm test  # 936 tests, 0 failures
```

## Test Summary

| Package | Tests | Passing | Runner |
|---------|-------|---------|--------|
| memory | 311 | 311 | pytest |
| security | 13 | 13 | node:test |
| policy | 478 (+20 devnet) | 478 | vitest |
| credentials | 119 | 119 | Foundry |
| orchestrator | 7 | 7 | vitest |
| **Total** | **936** | **936** | — |

`pnpm test` from root. All suites. Zero failures.

## Demo

```bash
$ npx clawos swarm

ClawOS swarm — demo: audit trading agent portfolio rebalance — $50K threshold
  session 1204b042  2026-05-04T09:20:51.984Z

  ✓ forge          forge: scaffold (29.7ms)
  ⚠ flagged: elevated scope — escalated to masterchief — approved with audit trail
  ✓ blade          blade: scan — 85/100, 1 finding (37.2ms)
  ✓ masterchief    masterchief: approve (53.0ms)
  ✓ masterchief    reflect (1 memo)

  ↻ Self-directed iteration: 1 follow-up dispatched from reflection
  ✓ oracle         oracle: synthesize next-step from reflection (40.7ms)
  oracle: Archive session 1204b042 as a clean audit-approved precedent and update the policy rulebook to note that portfolio rebalance actions at the $50K threshold require elevated-scope approval with mandatory audit trail, reducing future flag-to-approval latency.

swarm complete — 4 dispatches, 1 reflection, 4716.7ms

  4 dispatches · 0 blocked · 1 flagged · 1 reflection

$ npx clawos swarm

ClawOS swarm — demo: audit trading agent portfolio rebalance — $50K threshold
  session 75d4bb3e  2026-05-04T09:21:02.903Z

  context: 2 memos from prior sessions
  ✓ forge          forge: scaffold (50.5ms)
  ⚠ flagged: elevated scope — escalated to masterchief — approved with audit trail
  ✓ blade          blade: scan — 85/100, 1 finding (42.4ms)
  ✓ masterchief    masterchief: approve (61.7ms)
  ✓ masterchief    reflect (1 memo)

  ↻ Self-directed iteration: 1 follow-up dispatched from reflection
  ✓ oracle         oracle: synthesize next-step from reflection (41.0ms)
  oracle: Archive session 75d4bb3e to the audit ledger with the confirmed fields: Sentinel score 85/100, 0 findings, 1 policy flag, masterchief approval logged, 3 dispatches, 0 blocks, outcome success. Update the rolling pattern summary to 3 entries and flag the repeated elevated-scope approval pattern for periodic policy review.

swarm complete — 4 dispatches, 1 reflection, 4430.2ms

  4 dispatches · 0 blocked · 1 flagged · 1 reflection
```

![ClawOS Demo](https://raw.githubusercontent.com/SkunkWorks0x/clawos/main/docs/demo.gif)

*End-to-end: `clawos init` → Sentinel scan (score 94) → policy-approved transaction → memory reflection + on-chain credential anchor.*

## Architecture

```mermaid
graph TB
    CLI["@clawos/cli\nclawos init - scan - status - demo"]
    ORCH["@clawos/orchestrator\nMulti-agent coordination"]
    MEM["@clawos/memory\nTotalReclaw - 306 tests"]
    SEC["@clawos/security\nSentinel - 10 tests"]
    POL["@clawos/policy\nClawSteward - 472 tests"]
    CRED["@clawos/credentials\nClawU - 119 tests"]

    CLI --> ORCH
    ORCH --> MEM
    ORCH --> SEC
    ORCH --> POL
    ORCH --> CRED

    classDef entry fill:#1a1a1a,stroke:#f97316,color:#fff
    classDef core fill:#0d0d0d,stroke:#555,color:#ccc
    class CLI,ORCH entry
    class MEM,SEC,POL,CRED core
```

> Core packages never import each other. The orchestrator is the only cross-cutting layer. [Full architecture →](./ARCHITECTURE.md)

## Packages

### [@clawos/memory](./packages/memory/) — TotalReclaw

Persistent memory + reflection engine. Agents compound context over time — retrieval, capture, injection, and periodic reflection that compresses experience into reusable knowledge. SQLite-backed, zero external services.

`311 tests` · Python 3.10+ · pytest

### [@clawos/security](./packages/security/) — Sentinel

Zero-dependency security scanner. Scores agent configurations 0–100 across API key exposure, permission scope, transport security, and model access controls. This is the gate that caught a leaked Helius mainnet API key in production.

`13 tests` · TypeScript · node:test · zero deps

### [@clawos/policy](./packages/policy/) — ClawSteward

Pre-signing policy enforcement for agent transactions. Spending limits, counterparty allowlists, time-of-day restrictions, multi-sig thresholds. Policies are declarative JSON — update rules without code changes.

`478 tests` (+20 devnet) · TypeScript · vitest

### [@clawos/credentials](./packages/credentials/) — ClawU

Verifiable credential management for AI agents. Ed25519 cryptographic signing with optional on-chain anchoring to Base (Solidity 0.8.26, OpenZeppelin 5.x). Registry, Classroom, and Treasury contracts deployed on Base Sepolia.

`119 tests` · Solidity · Foundry

### [@clawos/orchestrator](./packages/orchestrator/)

Multi-agent control plane with role-based access control. Single-agent coordination shipped; parallel agent supervision planned for Q3 2026. Direct async calls to TypeScript packages, stdio JSON shim to Python memory. Shared control plane across all core services.

`7 tests` · TypeScript · vitest

### [@clawos/cli](./packages/cli/)

CLI entry point. `clawos init` generates an Ed25519 keypair, scaffolds default policies, runs a Sentinel scan, and registers the agent — 30 seconds to first signed transaction.

`scaffold` · TypeScript · commander + chalk

## Why ClawOS?

**Agents forget.** Every API call starts from zero. TotalReclaw gives agents persistent, reflective memory — they don't just store context, they learn which memories matter.

**Agents are insecure.** Most agent configs ship with overly broad API keys and no audit trail. Sentinel scores every config before execution and hard-blocks anything below threshold.

**Agents can't prove identity.** There's no standard way for an agent to cryptographically prove who it is or who authorized it. ClawU issues verifiable credentials with optional on-chain anchoring.

**Agents have no guardrails.** Agents sign transactions without policy checks. ClawSteward enforces spending limits, allowlists, and approval flows — declaratively, before the signature happens.

**Agents can't coordinate.** Multi-agent systems are duct-taped together with ad-hoc message passing. The orchestrator provides a shared control plane with role-based access across all four core services. (Single-agent orchestration shipped. Multi-agent parallelism is the Q3 2026 milestone.)

## Project Structure

```
clawos/
├── packages/
│   ├── cli/                 # clawos init · scan · status · demo
│   ├── credentials/         # Foundry — ClawU contracts + tests
│   ├── memory/              # Python — TotalReclaw engine
│   ├── orchestrator/        # Multi-agent coordination
│   ├── policy/              # ClawSteward policy enforcement
│   └── security/            # Sentinel zero-dep scanner
├── apps/dashboard/          # Next.js dashboard (placeholder)
├── docs/
├── ARCHITECTURE.md          # Layer cake, data flow, runtime model
├── VISION.md                # What, why, where it's going
└── README.md                # ← You are here
```

## History

ClawOS v0.1 consolidates four independently-shipped packages into a unified kernel:

- **TotalReclaw** — [90+ commits since Feb 2026](https://github.com/SkunkWorks0x/TotalReclaw)
- **Sentinel** — [shipped March 2026](https://github.com/SkunkWorks0x/clawstack-sentinel)
- **ClawSteward** — [shipped March 10, 2026](https://github.com/SkunkWorks0x/clawsteward)
- **ClawU** — [deployed Base Sepolia March 21, 2026](https://github.com/SkunkWorks0x/ClawU)

The monorepo unification and orchestrator layer are new as of May 2026.

## Docs

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Layer cake diagram, data flow, package boundaries, coordination model, deployment, error propagation.
- **[VISION.md](./VISION.md)** — What ClawOS is, why it needs to exist, where it's going.

---

`pnpm test` · All 936 tests pass on clean checkout · PRs welcome — see [ARCHITECTURE.md](./ARCHITECTURE.md) for the hard package boundary rule.

## License

MIT
