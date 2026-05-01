"""README-contract tests for capture_context / retrieve / reflect and the cli.py shim."""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from totalreclaw.core import MemoryStore
from totalreclaw.capture import capture_context
from totalreclaw.retrieval import retrieve
from totalreclaw.reflection import reflect


def _temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def _cleanup(path):
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(path + suffix)
        except FileNotFoundError:
            pass


def test_memorystore_accepts_db_path_as_first_positional():
    db = _temp_db()
    try:
        store = MemoryStore(db)
        assert store.db_path == db
        assert store.agent_id  # non-empty default
        store.save_episode("hello", goal_tag="onboarding")
        assert store.count() == 1
    finally:
        _cleanup(db)


def test_capture_context_creates_memory():
    db = _temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_context(store, action="transfer", outcome="success", amount=150.00)
        assert mid is not None
        mem = store.get_by_id(mid)
        assert mem is not None
        assert "transfer" in mem.content
        assert "150" in mem.content
    finally:
        _cleanup(db)


def test_retrieve_finds_by_keyword_and_limit():
    db = _temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        capture_context(store, action="transfer", outcome="success", amount=150)
        capture_context(store, action="transfer", outcome="success", amount=200)
        capture_context(store, action="login", outcome="success")
        results = retrieve(store, query="transfer", limit=2)
        assert len(results) <= 2
        assert all("transfer" in r.content for r in results)
    finally:
        _cleanup(db)


def test_reflect_writes_a_reflection_entry():
    db = _temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        capture_context(store, action="transfer", outcome="success", amount=150)
        ids = reflect(store)
        assert len(ids) >= 1
        last = store.get_last_reflection()
        assert last is not None
    finally:
        _cleanup(db)


def test_cli_shim_capture_then_retrieve_then_stats():
    db = _temp_db()
    try:
        cli_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "cli.py",
        )

        capture_req = {
            "op": "capture",
            "db": db,
            "agent_id": "shim-test",
            "action": "transfer",
            "outcome": "success",
            "details": {"amount": 150},
        }
        result = subprocess.run(
            [sys.executable, cli_path],
            input=json.dumps(capture_req),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip())
        assert payload["ok"] is True
        assert payload["memory_id"]

        stats_req = {"op": "stats", "db": db, "agent_id": "shim-test"}
        result = subprocess.run(
            [sys.executable, cli_path],
            input=json.dumps(stats_req),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
        stats = json.loads(result.stdout.strip())
        assert stats["ok"] is True
        assert stats["stats"]["total_active_memories"] == 1
    finally:
        _cleanup(db)
