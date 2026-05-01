# TotalReclaw — Persistent Memory + Reflection for OpenClaw Agents

## What This Is
A commercial .claw plugin that gives OpenClaw agents persistent memory across sessions.
Solves context drift, goal forgetting, and redundant work in long-running agents.
Shipping in 7 days. Revenue target: $15k in 30-60 days.

## Tech Stack
- Python 3.10+ (no external dependencies beyond stdlib for v1)
- SQLite with WAL mode for memory storage
- Structured JSON reflection via LLM API calls
- Target runtime: OpenClaw agent framework

## Project Structure
```
totalreclaw/
├── core.py          # MemoryStore class — SQLite CRUD, schema, session management
├── retrieval.py     # 4-layer retrieval algorithm (THE CORE IP)
├── reflection.py    # End-of-session structured reflection engine
├── capture.py       # Event filtering — decides what becomes a memory
├── injection.py     # Formats memories into XML context block for agent prompts
├── config.py        # All tuneable defaults
├── openclaw.py      # OpenClaw integration hooks (TO BUILD)
├── examples/        # Runnable demos (basic_agent.py, multi_session_demo.py)
├── tests/           # Edge case tests for all modules
└── free_teaser/     # Standalone reflection prompt (email capture funnel)
```

## Key Commands
- Run tests: `python -m totalreclaw.tests.test_retrieval`
- Run basic demo: `python -m totalreclaw.examples.basic_agent`

## Architecture Decisions (LOCKED — Do Not Change)
- **Storage:** SQLite only. No vector stores, no Chroma, no Pinecone, no embeddings.
- **Retrieval:** 4-layer priority: reflection → directives → goal-tagged → recent episodes. Token-budgeted.
- **Reflection:** End-of-session ONLY for v1. No mid-session reflection.
- **Capture:** Filtered. Side effects captured, read-only skipped, errors elevated, user directives highest priority.
- **Scope:** Memory + reflection ONLY. No cost governor, no dashboard, no vector search in v1.

## Code Conventions
- Type hints on all function signatures
- Docstrings on all public functions (Google style)
- Error handling: never let a database error crash the host agent
- All SQL uses parameterized queries (no f-strings in SQL)

## What NOT to Do
- Do not add external dependencies (no pip installs for v1)
- Do not suggest vector stores or embedding-based retrieval
- Do not build features marked as v2 (cost governor, replay dashboard, mid-session reflection)
- Do not refactor existing working code unless explicitly asked
- Do not over-engineer — shipping speed > architectural perfection
