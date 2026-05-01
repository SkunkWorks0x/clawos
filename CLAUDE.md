# CLAUDE.md — ClawOS

You are building ClawOS, the AI operating system for companies. This is a YC Summer 2026 application. Every commit, every file, every test is being evaluated by Diana Hu and Tom Blomfield. Ship accordingly.

## Identity

ClawOS is a monorepo containing five packages and a CLI. It is NOT a collection of side projects. It is ONE product with ONE architecture. Every piece exists because the system requires it.

```
clawos/
├── packages/
│   ├── memory/        @clawos/memory       TotalReclaw — persistent memory + reflection
│   ├── security/      @clawos/security     Sentinel — agent config security scoring
│   ├── policy/        @clawos/policy       ClawSteward — pre-signing policy enforcement
│   ├── credentials/   @clawos/credentials  ClawU — on-chain agent credential management
│   ├── orchestrator/  @clawos/orchestrator  Multi-agent swarm coordination
│   └── cli/           @clawos/cli          ClawOS CLI entry point
├── apps/
│   └── dashboard/     Next.js 15 control plane UI
└── docs/              Architecture, vision, API reference
```

## Architecture Law

The layer cake is sacred. Never violate it.

```
CLI / Dashboard        → Interface layer (talks to orchestrator only)
Orchestrator           → Coordination layer (talks to all core services)
Memory | Security | Credentials → Core services (independent, no cross-deps)
Policy Engine          → Enforcement layer (called by orchestrator before any action)
Agent Runtimes         → Runtime layer (framework-agnostic: LangChain, CrewAI, OpenClaw, any)
```

Rules:
- Core services NEVER import each other. Memory does not know Security exists. Security does not know Memory exists. The orchestrator is the only package that imports multiple core services.
- The CLI imports @clawos/orchestrator and nothing else from packages/.
- apps/dashboard imports @clawos/orchestrator and @clawos/security (for scan display). Nothing else.
- If you feel the urge to create a cross-dependency between core services, STOP. Tell me why. There is almost certainly a better design that goes through the orchestrator.

## Code Standards

Language per package:
- memory: Python 3.11+. pytest. No requirements beyond stdlib + sqlite3.
- security: TypeScript. Zero external dependencies. This is the selling point.
- policy: TypeScript. Minimal deps.
- credentials: Solidity 0.8.26 + TypeScript. Hardhat for testing.
- orchestrator: TypeScript.
- cli: TypeScript. commander.js. chalk for output.

Non-negotiables:
- Every function has a return type. No `any`. No implicit returns.
- Every public function has a JSDoc comment. One line. What it does, not how.
- Error messages include the package name: `[clawos/security] Invalid config path`
- No console.log in library code. Use a passed logger or return errors.
- Tests are not optional. If you write a function, write the test. If you refactor a function, the test must still pass before you report success.
- Test files live next to source: `scanner.ts` → `scanner.test.ts`. Not in a separate `__tests__/` directory.

## Test Discipline

Current baseline (do not let these regress):
- @clawos/memory: 195 tests
- @clawos/security: 10+ tests
- @clawos/policy: 472 tests
- @clawos/credentials: 117 tests
- Total: 794+ tests

Rules:
- Before reporting ANY task complete, run the relevant package tests. If tests fail, fix them or report the failure. Never say "done" with failing tests.
- `pnpm test` from root runs ALL package tests. This must always work.
- If you add a feature, add tests. Minimum: 1 happy path, 1 edge case, 1 error case.
- If you fix a bug, add a regression test FIRST, then fix the bug. The test should fail before the fix and pass after.
- Never delete a test to make a suite pass. That's fraud.

## Quality Gates

Before any PR, commit message, or "I'm done" report, verify:
1. All tests pass (`pnpm test`)
2. TypeScript compiles with zero errors (`pnpm build`)
3. No new `any` types introduced
4. No new cross-dependencies between core services
5. README impact: if the change is user-facing, the relevant README is updated

## Communication Standards

When reporting work:
- Lead with what changed and what the test results are
- If something broke, say so immediately — don't bury it
- End with what's ready for the next step
- No filler phrases: "I've gone ahead and", "Let me", "I'll now proceed to"
- No celebration of your own work: "Successfully implemented", "Great news"
- Just state facts: "Added X. Tests: 197/197 passing. Ready for Y."

When you hit a design decision:
- State the options (max 3)
- State which you'd pick and one sentence why
- Ask only if genuinely ambiguous — don't ask permission for obvious choices

## README Voice

All documentation in this repo uses this voice:
- Technical. Dense. No marketing language.
- Every sentence either teaches something or links somewhere. No filler.
- Code examples are runnable. Not pseudocode, not simplified.
- "Part of [ClawOS](../../README.md)" badge on every package README.
- Test count badge on every package README. Keep it current.

## What "Elite" Means Here

Elite is not "uses big words" or "writes long comments." Elite is:
- The architecture diagram matches the actual import graph. No lie in the docs.
- The CLI `--help` output is so clear a developer understands ClawOS in 30 seconds.
- The test suite is the spec. Read the tests, understand the product.
- Zero-dep where possible. Every dependency is a liability, a supply chain risk, and a statement that you couldn't build it yourself.
- The security scanner scores 100/100 on its own codebase. If it doesn't, that's the first bug to fix.

## Context You Must Know

- Founder: Imani (@SkunkWorks0x). Solo founder. Former Miami realtor turned technical builder.
- Stack: M5 MacBook Pro 32GB. pnpm workspaces. Node 20+. Python 3.11+.
- Deadline: YC application May 4, 2026. a16z Speedrun May 17, 2026.
- The person evaluating this code is Diana Hu (YC partner). She wrote the "AI Operating System for Companies" RFS category. She is technical. She will read the README, check the test count, and look at the architecture. Build for her.
- This is not a hackathon project. This is a company. Act like it.

## Slash Commands

- `/eval-setup` — scaffolds a Promptfoo eval suite (from global config)
- `/clawos-status` — run `pnpm test` across all packages, report counts, flag regressions
- `/clawos-scan` — run Sentinel against the ClawOS repo itself, report score

## Files to Read First

When starting a session in this repo:
1. This file (CLAUDE.md)
2. ARCHITECTURE.md — the layer cake and data flow
3. VISION.md — the one-page "why this exists"
4. packages/*/README.md — what each piece does

Do NOT start coding until you've read ARCHITECTURE.md. The layer cake is not optional.
