# @clawos/cli

<p>
  <img src="https://img.shields.io/badge/status-scaffold-yellow" alt="status" />
  <img src="https://img.shields.io/badge/language-TypeScript-blue" alt="typescript" />
</p>

CLI entry point for ClawOS. Delegates everything to the orchestrator.

**Status:** Scaffold — command delegation in active development. Full end-to-end demo works via root `pnpm demo`.

## Commands

| Command | What it does |
|---------|-------------|
| `clawos init` | Generate Ed25519 keypair, scaffold default policies + Sentinel config, register agent with orchestrator. 30 seconds to first signed transaction. |
| `clawos scan` | Run Sentinel security scan on current agent config. Returns 0–100 score + findings. |
| `clawos status` | Show agent registration, credential status, memory stats, last policy evaluation. |
| `clawos demo` | End-to-end: init → scan → policy-approved transaction → memory reflection. |

## Usage

```bash
# From monorepo root
pnpm clawos init        # scaffold a new agent
pnpm clawos scan        # score your config
pnpm clawos demo        # full pipeline end-to-end
```

## Architecture

The CLI talks to the orchestrator and nothing else. It has no direct dependency on any core package. This is enforced by `package.json` — the only listed dependency from the monorepo is `@clawos/orchestrator`.

## Project Structure

```
packages/cli/
└── src/
    └── index.ts    # commander + chalk, delegates to orchestrator
```

> Full architecture + data flow: [ARCHITECTURE.md](../../ARCHITECTURE.md)
