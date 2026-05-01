#!/usr/bin/env python3
"""TotalReclaw stdio JSON shim for the @clawos/orchestrator pipeline.

Reads a single JSON request from stdin, performs the requested op, and
writes a single JSON response to stdout. Errors are returned as
{"ok": false, "error": "..."} with a non-zero exit code.

Supported ops: capture, retrieve, reflect, stats.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from totalreclaw.core import MemoryStore
from totalreclaw.capture import capture_context
from totalreclaw.retrieval import retrieve
from totalreclaw.reflection import reflect


def _serialize_memory(mem: Any) -> dict[str, Any]:
    return {
        "id": mem.id,
        "type": mem.memory_type,
        "content": mem.content,
        "goal_tag": mem.goal_tag,
        "importance": mem.importance,
        "created_at": mem.created_at,
    }


def _handle(req: dict[str, Any]) -> dict[str, Any]:
    op = req.get("op", "stats")
    db_path = req.get("db", "./.clawos/memory.db")
    agent_id = req.get("agent_id", "default")
    store = MemoryStore(agent_id=agent_id, db_path=db_path)

    if op == "capture":
        details = req.get("details", {}) or {}
        memory_id = capture_context(
            store,
            action=req.get("action", "unknown"),
            outcome=req.get("outcome", "success"),
            goal_tag=req.get("goal_tag"),
            **details,
        )
        return {"ok": True, "memory_id": memory_id}

    if op == "retrieve":
        memories = retrieve(store, query=req.get("query"), limit=int(req.get("limit", 5)))
        return {"ok": True, "memories": [_serialize_memory(m) for m in memories]}

    if op == "reflect":
        ids = reflect(store)
        return {"ok": True, "reflection_ids": ids}

    if op == "stats":
        return {"ok": True, "stats": store.stats()}

    return {"ok": False, "error": f"unknown op: {op}"}


def main() -> int:
    raw = sys.stdin.read()
    try:
        req = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        sys.stdout.write(json.dumps({"ok": False, "error": f"invalid JSON: {exc}"}) + "\n")
        return 1

    try:
        response = _handle(req)
    except Exception as exc:
        sys.stdout.write(json.dumps({"ok": False, "error": str(exc)}) + "\n")
        return 1

    sys.stdout.write(json.dumps(response) + "\n")
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
