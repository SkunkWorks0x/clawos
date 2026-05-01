# @clawos/memory — TotalReclaw

<p>
  <img src="https://img.shields.io/badge/tests-311%20passing-brightgreen" alt="tests" />
  <img src="https://img.shields.io/badge/language-Python%203.10%2B-blue" alt="python" />
  <img src="https://img.shields.io/badge/deps-zero%20(SQLite%20stdlib)-blue" alt="deps" />
</p>

Persistent memory + reflection engine for AI agents. Agents compound context over time — they don't just store what happened, they learn which memories matter.

## What it does

TotalReclaw gives agents four memory primitives:

- **Capture** — stores structured context from agent interactions (actions, outcomes, observations).
- **Retrieval** — semantic and temporal lookup across the full memory store.
- **Injection** — surfaces relevant memories into agent prompts at execution time.
- **Reflection** — periodic compression that synthesizes raw experience into reusable knowledge. Configurable by action count or idle timeout.

All state lives in a per-agent SQLite database. No external services, no infrastructure requirements. Memory DBs are single files — backup is `cp`.

## Usage

```python
from totalreclaw.core import MemoryStore
from totalreclaw.capture import capture_context
from totalreclaw.retrieval import retrieve
from totalreclaw.reflection import reflect

store = MemoryStore("agent_alpha.db")

# Capture an interaction
capture_context(store, action="transfer", outcome="success", amount=150.00)

# Retrieve relevant memories at prompt time
memories = retrieve(store, query="recent transfers", limit=5)

# Run reflection — compress raw experience into knowledge
reflect(store)  # synthesizes patterns, prunes low-signal entries
```

## Quick Start

```bash
cd packages/memory
python -m venv .venv
source .venv/bin/activate
pip install -e .
pytest  # 311 tests, 0 failures
```

## Architecture

TotalReclaw is a core service in the ClawOS kernel. It never imports other core packages (security, policy, credentials). The orchestrator calls into it — either in-process or via the stdio JSON shim (`cli.py`).

## Project Structure

```
packages/memory/
├── totalreclaw/
│   ├── core/           # Memory store, DB schema, lifecycle
│   ├── retrieval/      # Semantic + temporal lookup
│   ├── reflection/     # Periodic compression + synthesis
│   ├── capture/        # Structured context ingestion
│   ├── injection/      # Prompt-time memory surfacing
│   └── openclaw/       # OpenClaw skill integration
├── paid/               # Advanced reflection variants (open-source core is fully functional)
└── pyproject.toml
```

> Full architecture + data flow: [ARCHITECTURE.md](../../ARCHITECTURE.md)
