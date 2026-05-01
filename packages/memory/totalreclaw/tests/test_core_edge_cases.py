"""
TotalReclaw Test Suite — Core Module Edge Cases
Tests for MemoryStore methods not covered by other test files:
  - save() validation, importance clamping, invalid types
  - get_by_id(), get_recent(), get_by_goal(), get_directives(), get_last_reflection()
  - count(), mark_accessed(), deactivate(), new_session(), stats()
  - Multi-agent isolation, concurrent sessions, empty DB edge cases
Run: python -m totalreclaw.tests.test_core_edge_cases
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from totalreclaw import MemoryStore


def get_temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def cleanup_db(path):
    """Remove DB and any SQLite WAL/SHM sidecar files."""
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(path + suffix)
        except FileNotFoundError:
            pass


# ── save() validation ─────────────────────────────────────────────

def test_save_invalid_memory_type():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        try:
            store.save("content", "invalid_type")
            assert False, "Should raise ValueError for invalid memory_type"
        except ValueError as e:
            assert "invalid_type" in str(e)
        print("✅ test_save_invalid_memory_type passed")
    finally:
        cleanup_db(db)


def test_save_importance_clamped_high():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save("test", "episode", importance=99)
        assert mem.importance == 10, f"Importance should clamp to 10, got {mem.importance}"
        print("✅ test_save_importance_clamped_high passed")
    finally:
        cleanup_db(db)


def test_save_importance_clamped_low():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save("test", "episode", importance=-5)
        assert mem.importance == 1, f"Importance should clamp to 1, got {mem.importance}"
        print("✅ test_save_importance_clamped_low passed")
    finally:
        cleanup_db(db)


def test_save_importance_zero_clamps_to_one():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save("test", "episode", importance=0)
        assert mem.importance == 1, f"Importance 0 should clamp to 1, got {mem.importance}"
        print("✅ test_save_importance_zero_clamps_to_one passed")
    finally:
        cleanup_db(db)


def test_save_importance_boundary_one():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save("test", "episode", importance=1)
        assert mem.importance == 1
        print("✅ test_save_importance_boundary_one passed")
    finally:
        cleanup_db(db)


def test_save_importance_boundary_ten():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save("test", "episode", importance=10)
        assert mem.importance == 10
        print("✅ test_save_importance_boundary_ten passed")
    finally:
        cleanup_db(db)


def test_save_returns_memory_with_correct_fields():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="agent-1", db_path=db)
        mem = store.save("hello world", "fact", goal_tag="my-goal", importance=7)
        assert mem.agent_id == "agent-1"
        assert mem.session_id == store.session_id
        assert mem.memory_type == "fact"
        assert mem.content == "hello world"
        assert mem.goal_tag == "my-goal"
        assert mem.importance == 7
        assert mem.access_count == 0
        assert mem.is_active is True
        assert len(mem.id) == 36  # UUID format
        print("✅ test_save_returns_memory_with_correct_fields passed")
    finally:
        cleanup_db(db)


def test_save_each_valid_type():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        for mtype in ("episode", "reflection", "fact", "directive"):
            mem = store.save(f"content for {mtype}", mtype)
            assert mem.memory_type == mtype
        assert store.count() == 4
        print("✅ test_save_each_valid_type passed")
    finally:
        cleanup_db(db)


# ── Convenience save methods ──────────────────────────────────────

def test_save_episode_defaults():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save_episode("ep content")
        assert mem.memory_type == "episode"
        assert mem.importance == 5
        assert mem.goal_tag is None
        print("✅ test_save_episode_defaults passed")
    finally:
        cleanup_db(db)


def test_save_reflection_defaults():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save_reflection("ref content")
        assert mem.memory_type == "reflection"
        assert mem.importance == 8
        print("✅ test_save_reflection_defaults passed")
    finally:
        cleanup_db(db)


def test_save_fact_defaults():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save_fact("fact content")
        assert mem.memory_type == "fact"
        assert mem.importance == 6
        print("✅ test_save_fact_defaults passed")
    finally:
        cleanup_db(db)


def test_save_directive_defaults():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save_directive("dir content")
        assert mem.memory_type == "directive"
        assert mem.importance == 9
        assert mem.goal_tag is None
        print("✅ test_save_directive_defaults passed")
    finally:
        cleanup_db(db)


# ── get_by_id() ───────────────────────────────────────────────────

def test_get_by_id_returns_none_for_missing():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        result = store.get_by_id("nonexistent-uuid")
        assert result is None, "Should return None for missing ID"
        print("✅ test_get_by_id_returns_none_for_missing passed")
    finally:
        cleanup_db(db)


def test_get_by_id_agent_isolation():
    db = get_temp_db()
    try:
        store_a = MemoryStore(agent_id="agent-a", db_path=db)
        store_b = MemoryStore(agent_id="agent-b", db_path=db)
        mem = store_a.save_episode("private to A")
        result = store_b.get_by_id(mem.id)
        assert result is None, "Agent B should not see Agent A's memories"
        print("✅ test_get_by_id_agent_isolation passed")
    finally:
        cleanup_db(db)


# ── get_recent() ──────────────────────────────────────────────────

def test_get_recent_respects_limit():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        for i in range(10):
            store.save_episode(f"Episode {i}")
        result = store.get_recent(limit=3)
        assert len(result) == 3, f"Expected 3, got {len(result)}"
        print("✅ test_get_recent_respects_limit passed")
    finally:
        cleanup_db(db)


def test_get_recent_filters_by_type():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_episode("ep1")
        store.save_fact("fact1")
        store.save_directive("dir1")
        result = store.get_recent(limit=10, memory_type="fact")
        assert len(result) == 1
        assert result[0].memory_type == "fact"
        print("✅ test_get_recent_filters_by_type passed")
    finally:
        cleanup_db(db)


def test_get_recent_excludes_inactive():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save_episode("will be deactivated")
        store.save_episode("still active")
        store.deactivate(mem.id)
        result = store.get_recent(limit=10)
        assert len(result) == 1
        assert result[0].content == "still active"
        print("✅ test_get_recent_excludes_inactive passed")
    finally:
        cleanup_db(db)


def test_get_recent_empty_store():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        result = store.get_recent()
        assert result == []
        print("✅ test_get_recent_empty_store passed")
    finally:
        cleanup_db(db)


def test_get_recent_orders_by_recency():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        m_old = store.save_episode("old")
        m_new = store.save_episode("new")
        # If timestamps collide, nudge them apart via direct DB update
        if m_old.created_at == m_new.created_at:
            with store._connect() as conn:
                conn.execute("UPDATE memories SET created_at = created_at - 1 WHERE id = ?", (m_old.id,))
        result = store.get_recent(limit=2)
        assert result[0].content == "new", "Most recent should be first"
        assert result[1].content == "old"
        print("✅ test_get_recent_orders_by_recency passed")
    finally:
        cleanup_db(db)


# ── get_by_goal() ─────────────────────────────────────────────────

def test_get_by_goal_empty_result():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_episode("no goal")
        result = store.get_by_goal("nonexistent-goal")
        assert result == []
        print("✅ test_get_by_goal_empty_result passed")
    finally:
        cleanup_db(db)


def test_get_by_goal_respects_limit():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        for i in range(10):
            store.save_episode(f"ep {i}", goal_tag="g1")
        result = store.get_by_goal("g1", limit=3)
        assert len(result) == 3
        print("✅ test_get_by_goal_respects_limit passed")
    finally:
        cleanup_db(db)


def test_get_by_goal_orders_by_importance():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_episode("low", goal_tag="g", importance=2)
        store.save_episode("high", goal_tag="g", importance=9)
        store.save_episode("mid", goal_tag="g", importance=5)
        result = store.get_by_goal("g")
        assert result[0].importance >= result[1].importance >= result[2].importance
        print("✅ test_get_by_goal_orders_by_importance passed")
    finally:
        cleanup_db(db)


# ── get_directives() ──────────────────────────────────────────────

def test_get_directives_empty():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        result = store.get_directives()
        assert result == []
        print("✅ test_get_directives_empty passed")
    finally:
        cleanup_db(db)


def test_get_directives_excludes_other_types():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_episode("ep")
        store.save_fact("fact")
        store.save_directive("dir1")
        result = store.get_directives()
        assert len(result) == 1
        assert result[0].memory_type == "directive"
        print("✅ test_get_directives_excludes_other_types passed")
    finally:
        cleanup_db(db)


# ── get_last_reflection() ─────────────────────────────────────────

def test_get_last_reflection_empty():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        result = store.get_last_reflection()
        assert result is None
        print("✅ test_get_last_reflection_empty passed")
    finally:
        cleanup_db(db)


def test_get_last_reflection_returns_most_recent():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        m_old = store.save_reflection("old reflection")
        m_new = store.save_reflection("new reflection")
        if m_old.created_at == m_new.created_at:
            with store._connect() as conn:
                conn.execute("UPDATE memories SET created_at = created_at - 1 WHERE id = ?", (m_old.id,))
        result = store.get_last_reflection()
        assert result.content == "new reflection"
        print("✅ test_get_last_reflection_returns_most_recent passed")
    finally:
        cleanup_db(db)


# ── count() ───────────────────────────────────────────────────────

def test_count_empty():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        assert store.count() == 0
        assert store.count(memory_type="episode") == 0
        print("✅ test_count_empty passed")
    finally:
        cleanup_db(db)


def test_count_by_type():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_episode("e1")
        store.save_episode("e2")
        store.save_fact("f1")
        assert store.count() == 3
        assert store.count(memory_type="episode") == 2
        assert store.count(memory_type="fact") == 1
        assert store.count(memory_type="directive") == 0
        print("✅ test_count_by_type passed")
    finally:
        cleanup_db(db)


def test_count_excludes_inactive():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save_episode("active")
        store.save_episode("also active")
        store.deactivate(mem.id)
        assert store.count() == 1
        print("✅ test_count_excludes_inactive passed")
    finally:
        cleanup_db(db)


# ── mark_accessed() ───────────────────────────────────────────────

def test_mark_accessed_empty_list():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        # Should not raise
        store.mark_accessed([])
        print("✅ test_mark_accessed_empty_list passed")
    finally:
        cleanup_db(db)


def test_mark_accessed_increments():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save_episode("test")
        store.mark_accessed([mem.id])
        store.mark_accessed([mem.id])
        updated = store.get_by_id(mem.id)
        assert updated.access_count == 2, f"Expected 2, got {updated.access_count}"
        assert updated.last_accessed is not None
        print("✅ test_mark_accessed_increments passed")
    finally:
        cleanup_db(db)


def test_mark_accessed_multiple_ids():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        m1 = store.save_episode("a")
        m2 = store.save_episode("b")
        store.mark_accessed([m1.id, m2.id])
        assert store.get_by_id(m1.id).access_count == 1
        assert store.get_by_id(m2.id).access_count == 1
        print("✅ test_mark_accessed_multiple_ids passed")
    finally:
        cleanup_db(db)


# ── deactivate() ──────────────────────────────────────────────────

def test_deactivate_makes_invisible():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save_episode("test")
        store.deactivate(mem.id)
        # get_by_id still returns deactivated memories (no is_active filter)
        found = store.get_by_id(mem.id)
        assert found is not None
        assert found.is_active is False
        recent = store.get_recent()
        assert len(recent) == 0
        print("✅ test_deactivate_makes_invisible passed")
    finally:
        cleanup_db(db)


def test_deactivate_nonexistent_id():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        # Should not raise
        store.deactivate("nonexistent-uuid")
        print("✅ test_deactivate_nonexistent_id passed")
    finally:
        cleanup_db(db)


# ── new_session() ─────────────────────────────────────────────────

def test_new_session_generates_uuid():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        old_session = store.session_id
        new_id = store.new_session()
        assert new_id != old_session
        assert store.session_id == new_id
        assert len(new_id) == 36
        print("✅ test_new_session_generates_uuid passed")
    finally:
        cleanup_db(db)


def test_new_session_custom_id():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        new_id = store.new_session(session_id="custom-session-42")
        assert new_id == "custom-session-42"
        assert store.session_id == "custom-session-42"
        print("✅ test_new_session_custom_id passed")
    finally:
        cleanup_db(db)


def test_new_session_memories_use_new_id():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_episode("old session")
        store.new_session(session_id="session-2")
        mem = store.save_episode("new session")
        assert mem.session_id == "session-2"
        print("✅ test_new_session_memories_use_new_id passed")
    finally:
        cleanup_db(db)


# ── stats() ───────────────────────────────────────────────────────

def test_stats_empty_store():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        s = store.stats()
        assert s["agent_id"] == "test"
        assert s["total_active_memories"] == 0
        assert s["by_type"] == {}
        assert s["total_sessions"] == 0
        assert s["db_path"] == db
        print("✅ test_stats_empty_store passed")
    finally:
        cleanup_db(db)


def test_stats_with_data():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_episode("e1")
        store.save_episode("e2")
        store.save_fact("f1")
        store.save_directive("d1")
        store.new_session()
        store.save_reflection("r1")
        s = store.stats()
        assert s["total_active_memories"] == 5
        assert s["by_type"]["episode"] == 2
        assert s["by_type"]["fact"] == 1
        assert s["by_type"]["directive"] == 1
        assert s["by_type"]["reflection"] == 1
        assert s["total_sessions"] == 2
        print("✅ test_stats_with_data passed")
    finally:
        cleanup_db(db)


def test_stats_excludes_inactive():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save_episode("active")
        store.save_episode("also active")
        store.deactivate(mem.id)
        s = store.stats()
        assert s["total_active_memories"] == 1
        print("✅ test_stats_excludes_inactive passed")
    finally:
        cleanup_db(db)


# ── Multi-agent isolation ─────────────────────────────────────────

def test_multi_agent_isolation():
    db = get_temp_db()
    try:
        store_a = MemoryStore(agent_id="agent-a", db_path=db)
        store_b = MemoryStore(agent_id="agent-b", db_path=db)
        store_a.save_episode("A's episode")
        store_a.save_directive("A's directive")
        store_b.save_episode("B's episode")
        assert store_a.count() == 2
        assert store_b.count() == 1
        assert store_a.get_directives()[0].content == "A's directive"
        assert store_b.get_directives() == []
        print("✅ test_multi_agent_isolation passed")
    finally:
        cleanup_db(db)


# ── Unicode and special content ───────────────────────────────────

def test_save_unicode_content():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        content = "Emoji test 🧠💾 and CJK: 你好世界 and Arabic: مرحبا"
        mem = store.save_episode(content)
        loaded = store.get_by_id(mem.id)
        assert loaded.content == content
        print("✅ test_save_unicode_content passed")
    finally:
        cleanup_db(db)


def test_save_very_long_content():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        content = "x" * 100_000
        mem = store.save_episode(content)
        loaded = store.get_by_id(mem.id)
        assert len(loaded.content) == 100_000
        print("✅ test_save_very_long_content passed")
    finally:
        cleanup_db(db)


def test_save_content_with_sql_injection_attempt():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        evil = "'; DROP TABLE memories; --"
        mem = store.save_episode(evil)
        loaded = store.get_by_id(mem.id)
        assert loaded.content == evil
        assert store.count() == 1, "Table should survive injection attempt"
        print("✅ test_save_content_with_sql_injection_attempt passed")
    finally:
        cleanup_db(db)


def test_save_content_with_newlines_and_tabs():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        content = "line1\nline2\n\ttabbed\n"
        mem = store.save_episode(content)
        loaded = store.get_by_id(mem.id)
        assert loaded.content == content
        print("✅ test_save_content_with_newlines_and_tabs passed")
    finally:
        cleanup_db(db)


# ── decay_old_reflections edge cases ──────────────────────────────

def test_decay_with_no_reflections():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        # Should not raise
        store.decay_old_reflections(keep_recent=5, importance_penalty=2)
        print("✅ test_decay_with_no_reflections passed")
    finally:
        cleanup_db(db)


def test_decay_with_fewer_than_keep_recent():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        for i in range(3):
            store.save_reflection(f"Reflection {i}", importance=8)
        store.decay_old_reflections(keep_recent=5, importance_penalty=2)
        # All should keep original importance since fewer than keep_recent
        for r in store.get_recent(limit=10, memory_type="reflection"):
            assert r.importance == 8
        print("✅ test_decay_with_fewer_than_keep_recent passed")
    finally:
        cleanup_db(db)


# ── Init with custom session_id ───────────────────────────────────

def test_init_with_custom_session_id():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db, session_id="my-session")
        assert store.session_id == "my-session"
        mem = store.save_episode("test")
        assert mem.session_id == "my-session"
        print("✅ test_init_with_custom_session_id passed")
    finally:
        cleanup_db(db)


if __name__ == "__main__":
    print("TotalReclaw Core Edge Case Tests")
    print("=" * 50)
    test_save_invalid_memory_type()
    test_save_importance_clamped_high()
    test_save_importance_clamped_low()
    test_save_importance_zero_clamps_to_one()
    test_save_importance_boundary_one()
    test_save_importance_boundary_ten()
    test_save_returns_memory_with_correct_fields()
    test_save_each_valid_type()
    test_save_episode_defaults()
    test_save_reflection_defaults()
    test_save_fact_defaults()
    test_save_directive_defaults()
    test_get_by_id_returns_none_for_missing()
    test_get_by_id_agent_isolation()
    test_get_recent_respects_limit()
    test_get_recent_filters_by_type()
    test_get_recent_excludes_inactive()
    test_get_recent_empty_store()
    test_get_recent_orders_by_recency()
    test_get_by_goal_empty_result()
    test_get_by_goal_respects_limit()
    test_get_by_goal_orders_by_importance()
    test_get_directives_empty()
    test_get_directives_excludes_other_types()
    test_get_last_reflection_empty()
    test_get_last_reflection_returns_most_recent()
    test_count_empty()
    test_count_by_type()
    test_count_excludes_inactive()
    test_mark_accessed_empty_list()
    test_mark_accessed_increments()
    test_mark_accessed_multiple_ids()
    test_deactivate_makes_invisible()
    test_deactivate_nonexistent_id()
    test_new_session_generates_uuid()
    test_new_session_custom_id()
    test_new_session_memories_use_new_id()
    test_stats_empty_store()
    test_stats_with_data()
    test_stats_excludes_inactive()
    test_multi_agent_isolation()
    test_save_unicode_content()
    test_save_very_long_content()
    test_save_content_with_sql_injection_attempt()
    test_save_content_with_newlines_and_tabs()
    test_decay_with_no_reflections()
    test_decay_with_fewer_than_keep_recent()
    test_init_with_custom_session_id()
    print("\n" + "=" * 50)
    print("All tests passed ✅")
