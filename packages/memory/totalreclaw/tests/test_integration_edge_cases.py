"""
TotalReclaw Test Suite — Integration & Cross-Module Edge Cases
Tests for retrieval edge cases, estimate_tokens, injection with deactivated
memories, end-to-end flows, openclaw plugin edge cases, and config values.
Run: python -m totalreclaw.tests.test_integration_edge_cases
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from totalreclaw import (
    MemoryStore,
    TotalReclawPlugin,
    retrieve_memories,
    retrieval_stats,
    estimate_tokens,
    format_memory_block,
    build_system_prompt_with_memory,
    capture_event,
    capture_user_message,
    should_capture,
    parse_reflection,
    build_reflection_prompt,
    store_reflection,
    fallback_store_summary,
)
from totalreclaw.core import Memory
from totalreclaw.config import (
    DEFAULT_TOKEN_BUDGET,
    MAX_MEMORIES_PER_LAYER,
    REFLECTION_KEEP_RECENT,
    REFLECTION_DECAY_PENALTY,
    DEFAULT_CAPTURE_IMPORTANCE,
    DEFAULT_DB_PATH,
    VERSION,
    PRODUCT_NAME,
)


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


# ── estimate_tokens edge cases ────────────────────────────────────

def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0
    print("✅ test_estimate_tokens_empty passed")


def test_estimate_tokens_short():
    result = estimate_tokens("hello!!")
    assert result == 2, f"Expected 2, got {result}"
    print("✅ test_estimate_tokens_short passed")


def test_estimate_tokens_long():
    text = "a" * 3500
    result = estimate_tokens(text)
    assert result == 1000, f"Expected 1000, got {result}"
    print("✅ test_estimate_tokens_long passed")


def test_estimate_tokens_unicode():
    result = estimate_tokens("🧠" * 10)
    expected = int(len("🧠" * 10) / 3.5)
    assert result == expected, f"Expected {expected}, got {result}"
    print("✅ test_estimate_tokens_unicode passed")


# ── retrieval_stats edge cases ────────────────────────────────────

def test_retrieval_stats_empty():
    stats = retrieval_stats([])
    assert stats["count"] == 0
    assert stats["total_tokens"] == 0
    assert stats["by_type"] == {}
    assert stats["goals_covered"] == []
    print("✅ test_retrieval_stats_empty passed")


def test_retrieval_stats_multiple_goals():
    memories = [
        Memory(id="1", agent_id="t", session_id="s", created_at=1.0,
               memory_type="episode", content="a", goal_tag="g1", importance=5),
        Memory(id="2", agent_id="t", session_id="s", created_at=1.0,
               memory_type="fact", content="b", goal_tag="g2", importance=5),
        Memory(id="3", agent_id="t", session_id="s", created_at=1.0,
               memory_type="episode", content="c", goal_tag=None, importance=3),
    ]
    stats = retrieval_stats(memories)
    assert stats["count"] == 3
    assert stats["by_type"]["episode"] == 2
    assert stats["by_type"]["fact"] == 1
    assert set(stats["goals_covered"]) == {"g1", "g2"}
    assert stats["importance_range"] == (3, 5)
    print("✅ test_retrieval_stats_multiple_goals passed")


# ── retrieval: token budget exhaustion ────────────────────────────

def test_retrieval_zero_budget():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_episode("content")
        store.save_reflection("reflection")
        memories = retrieve_memories(store, token_budget=0)
        assert memories == [], "Zero budget should return empty"
        print("✅ test_retrieval_zero_budget passed")
    finally:
        cleanup_db(db)


def test_retrieval_tiny_budget_skips_large_memories():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        # This reflection is about 42 tokens (150 chars / 3.5)
        store.save_reflection("x" * 150)  # ~42 tokens, exceeds budget
        store.save_episode("small", importance=5)  # ~1 token, fits
        memories = retrieve_memories(store, token_budget=5)
        assert all(m.content != "x" * 150 for m in memories), "Large reflection should be skipped"
        print("✅ test_retrieval_tiny_budget_skips_large_memories passed")
    finally:
        cleanup_db(db)


def test_retrieval_no_goal_skips_layer3():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_fact("fact with goal", goal_tag="specific-goal", importance=10)
        store.save_episode("ungrouped episode")
        memories = retrieve_memories(store, current_goal=None)
        types = [m.memory_type for m in memories]
        assert "episode" in types, "Episode should appear via layer 4 backfill"
        assert "fact" not in types, "Goal-tagged fact should not appear without a matching goal"
        print("✅ test_retrieval_no_goal_skips_layer3 passed")
    finally:
        cleanup_db(db)


# ── retrieval: all layers exercised ───────────────────────────────

def test_retrieval_all_four_layers():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_reflection("session summary")
        store.save_directive("be careful")
        store.save_fact("stripe key", goal_tag="pay", importance=7)
        store.save_episode("called api", goal_tag="pay")
        store.save_episode("untagged episode")
        memories = retrieve_memories(store, current_goal="pay", token_budget=5000)
        types = {m.memory_type for m in memories}
        assert "reflection" in types
        assert "directive" in types
        assert "fact" in types
        assert "episode" in types
        print("✅ test_retrieval_all_four_layers passed")
    finally:
        cleanup_db(db)


# ── injection: only reflections section shows first ───────────────

def test_injection_only_first_reflection_in_summary():
    m1 = Memory(id="r1", agent_id="t", session_id="s", created_at=2.0,
                memory_type="reflection", content="Second reflection", importance=8)
    m2 = Memory(id="r2", agent_id="t", session_id="s", created_at=1.0,
                memory_type="reflection", content="First reflection", importance=8)
    result = format_memory_block([m1, m2])
    # Only the first reflection in the list goes into last_session_summary
    assert "Second reflection" in result
    # The second reflection is not displayed separately as there's only one last_session_summary
    assert result.count("<last_session_summary>") == 1
    print("✅ test_injection_only_first_reflection_in_summary passed")


# ── capture: goal_tag=None explicitly ─────────────────────────────

def test_capture_event_no_goal():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "file_write", "wrote config", goal_tag=None)
        assert mid is not None
        mem = store.get_by_id(mid)
        assert mem.goal_tag is None
        print("✅ test_capture_event_no_goal passed")
    finally:
        cleanup_db(db)


# ── parse_reflection: nested JSON ─────────────────────────────────

def test_parse_reflection_nested_json_in_facts():
    data = {
        "session_summary": "Configured API.",
        "goal_status": "completed",
        "current_goal": "setup",
        "key_facts": [
            {"fact": 'Config: {"port": 8080, "host": "0.0.0.0"}', "importance": 7},
        ],
        "lessons_learned": [],
        "next_session_primer": "Deploy.",
    }
    result = parse_reflection(json.dumps(data))
    assert result is not None
    assert "port" in result["key_facts"][0]["fact"]
    print("✅ test_parse_reflection_nested_json_in_facts passed")


def test_parse_reflection_extra_fields_ignored():
    data = {
        "session_summary": "Did work.",
        "goal_status": "completed",
        "current_goal": "test",
        "key_facts": [],
        "lessons_learned": [],
        "next_session_primer": "Next.",
        "extra_field": "should be ignored",
        "another_extra": 42,
    }
    result = parse_reflection(json.dumps(data))
    assert result is not None
    assert result["session_summary"] == "Did work."
    print("✅ test_parse_reflection_extra_fields_ignored passed")


def test_parse_reflection_key_facts_not_list():
    data = {
        "session_summary": "Did work.",
        "goal_status": "completed",
        "next_session_primer": "Next.",
        "key_facts": "not a list",
        "lessons_learned": {"also": "not a list"},
    }
    result = parse_reflection(json.dumps(data))
    assert result is not None
    assert result["key_facts"] == [], "Non-list key_facts should default to []"
    assert result["lessons_learned"] == [], "Non-list lessons_learned should default to []"
    print("✅ test_parse_reflection_key_facts_not_list passed")


# ── store_reflection: lessons with empty strings ──────────────────

def test_store_reflection_lessons_with_empty_lesson_key():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        reflection = {
            "session_summary": "test.",
            "goal_status": "completed",
            "current_goal": "test",
            "key_facts": [],
            "lessons_learned": [
                {"lesson": "", "importance": 5},
                {"lesson": "  ", "importance": 5},
                {"lesson": "Real lesson", "importance": 7},
            ],
            "next_session_primer": "Next.",
        }
        ids = store_reflection(store, reflection)
        # 1 reflection + 1 real lesson = 2
        assert len(ids) == 2
        print("✅ test_store_reflection_lessons_with_empty_lesson_key passed")
    finally:
        cleanup_db(db)


# ── config values ─────────────────────────────────────────────────

def test_config_values():
    assert isinstance(DEFAULT_TOKEN_BUDGET, int) and DEFAULT_TOKEN_BUDGET > 0
    assert isinstance(MAX_MEMORIES_PER_LAYER, int) and MAX_MEMORIES_PER_LAYER > 0
    assert isinstance(REFLECTION_KEEP_RECENT, int) and REFLECTION_KEEP_RECENT > 0
    assert isinstance(REFLECTION_DECAY_PENALTY, int) and REFLECTION_DECAY_PENALTY > 0
    assert isinstance(DEFAULT_CAPTURE_IMPORTANCE, int)
    assert isinstance(DEFAULT_DB_PATH, str)
    assert isinstance(VERSION, str) and "." in VERSION
    assert isinstance(PRODUCT_NAME, str)
    print("✅ test_config_values passed")


# ── OpenClaw plugin: end_session result structure ─────────────────

def test_end_session_result_keys():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db)
        plugin.start_session()
        plugin.capture("file_write", "wrote file")
        result = plugin.end_session()
        assert "session_id" in result
        assert "duration_seconds" in result
        assert "memories_created" in result
        assert "reflection_status" in result
        assert "memory_ids" in result
        assert isinstance(result["duration_seconds"], float)
        assert result["duration_seconds"] >= 0
        print("✅ test_end_session_result_keys passed")
    finally:
        cleanup_db(db)


def test_plugin_llm_returns_unparseable():
    db = get_temp_db()
    try:
        def bad_llm(messages):
            return "I'm not JSON at all!"
        plugin = TotalReclawPlugin("test-agent", db_path=db, llm_call=bad_llm)
        plugin.start_session()
        plugin.capture("file_write", "wrote something")
        result = plugin.end_session()
        assert result["reflection_status"] == "fallback", \
            f"Unparseable LLM output should fall back, got {result['reflection_status']}"
        print("✅ test_plugin_llm_returns_unparseable passed")
    finally:
        cleanup_db(db)


def test_plugin_capture_uses_plugin_goal():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db, current_goal="my-goal")
        plugin.start_session()
        mid = plugin.capture("file_write", "wrote file")
        mem = plugin.store.get_by_id(mid)
        assert mem.goal_tag == "my-goal"
        plugin.end_session()
        print("✅ test_plugin_capture_uses_plugin_goal passed")
    finally:
        cleanup_db(db)


def test_plugin_capture_goal_override():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db, current_goal="default")
        plugin.start_session()
        mid = plugin.capture("file_write", "wrote file", goal_tag="override-goal")
        mem = plugin.store.get_by_id(mid)
        assert mem.goal_tag == "override-goal"
        plugin.end_session()
        print("✅ test_plugin_capture_goal_override passed")
    finally:
        cleanup_db(db)


def test_plugin_capture_message_goal_propagation():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db, current_goal="agent-goal")
        plugin.start_session()
        mid = plugin.capture_message("Always validate inputs")
        assert mid is not None
        mem = plugin.store.get_by_id(mid)
        assert mem.goal_tag == "agent-goal"
        plugin.end_session()
        print("✅ test_plugin_capture_message_goal_propagation passed")
    finally:
        cleanup_db(db)


def test_plugin_session_id_in_result():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db)
        plugin.start_session(session_id="known-session")
        plugin.capture("file_write", "test")
        result = plugin.end_session()
        assert result["session_id"] == "known-session"
        print("✅ test_plugin_session_id_in_result passed")
    finally:
        cleanup_db(db)


def test_plugin_context_manager_with_exception():
    db = get_temp_db()
    try:
        try:
            with TotalReclawPlugin("test-agent", db_path=db) as plugin:
                plugin.capture("file_write", "before crash")
                raise ValueError("simulated error")
        except ValueError:
            pass
        # Session should have been ended despite the exception
        assert not plugin.session_active
        print("✅ test_plugin_context_manager_with_exception passed")
    finally:
        cleanup_db(db)


# ── End-to-end: multi-session continuity ──────────────────────────

def test_multi_session_continuity():
    db = get_temp_db()
    try:
        valid_json = json.dumps({
            "session_summary": "Set up Stripe.",
            "goal_status": "partial",
            "current_goal": "payments",
            "key_facts": [{"fact": "Stripe key is sk_test_x", "importance": 7}],
            "lessons_learned": [],
            "next_session_primer": "Add webhook.",
        })
        mock_llm = lambda msgs: valid_json

        # Session 1
        p1 = TotalReclawPlugin("agent", db_path=db, llm_call=mock_llm, current_goal="payments")
        p1.start_session()
        p1.capture("api_call_success", "Created customer")
        p1.capture_message("Always check idempotency keys")
        r1 = p1.end_session()
        assert r1["reflection_status"] == "full"

        # Session 2: should retrieve session 1's memories
        p2 = TotalReclawPlugin("agent", db_path=db, current_goal="payments")
        memories = p2.start_session()
        assert len(memories) > 0, "Session 2 should retrieve Session 1 memories"
        contents = " ".join(m.content for m in memories)
        assert "stripe" in contents.lower() or "idempotency" in contents.lower(), \
            "Session 2 should see Session 1 data"
        prompt = p2.get_system_prompt("Base.")
        assert "PERSISTENT MEMORY" in prompt
        p2.end_session()

        print("✅ test_multi_session_continuity passed")
    finally:
        cleanup_db(db)


# ── build_system_prompt preserves base prompt exactly ─────────────

def test_build_system_prompt_base_unchanged():
    base = "You are a coding assistant.\nBe helpful."
    result = build_system_prompt_with_memory(base, [])
    assert result.startswith(base)
    print("✅ test_build_system_prompt_base_unchanged passed")


# ── Memory dataclass defaults ─────────────────────────────────────

def test_memory_dataclass_defaults():
    m = Memory(
        id="x", agent_id="a", session_id="s",
        created_at=1.0, memory_type="episode", content="c",
    )
    assert m.goal_tag is None
    assert m.importance == 5
    assert m.access_count == 0
    assert m.last_accessed is None
    assert m.is_active is True
    print("✅ test_memory_dataclass_defaults passed")


# ── capture_user_message edge: empty message ──────────────────────

def test_capture_user_message_empty():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "")
        assert mid is None
        print("✅ test_capture_user_message_empty passed")
    finally:
        cleanup_db(db)


def test_capture_user_message_whitespace_only():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "   \n\t  ")
        assert mid is None
        print("✅ test_capture_user_message_whitespace_only passed")
    finally:
        cleanup_db(db)


# ── should_capture for every defined rule ─────────────────────────

def test_should_capture_all_defined_types():
    from totalreclaw.capture import CAPTURE_RULES
    for event_type, rule in CAPTURE_RULES.items():
        result = should_capture(event_type)
        assert result == rule["capture"], \
            f"should_capture('{event_type}') returned {result}, expected {rule['capture']}"
    print("✅ test_should_capture_all_defined_types passed")


if __name__ == "__main__":
    print("TotalReclaw Integration & Edge Case Tests")
    print("=" * 50)
    test_estimate_tokens_empty()
    test_estimate_tokens_short()
    test_estimate_tokens_long()
    test_estimate_tokens_unicode()
    test_retrieval_stats_empty()
    test_retrieval_stats_multiple_goals()
    test_retrieval_zero_budget()
    test_retrieval_tiny_budget_skips_large_memories()
    test_retrieval_no_goal_skips_layer3()
    test_retrieval_all_four_layers()
    test_injection_only_first_reflection_in_summary()
    test_capture_event_no_goal()
    test_parse_reflection_nested_json_in_facts()
    test_parse_reflection_extra_fields_ignored()
    test_parse_reflection_key_facts_not_list()
    test_store_reflection_lessons_with_empty_lesson_key()
    test_config_values()
    test_end_session_result_keys()
    test_plugin_llm_returns_unparseable()
    test_plugin_capture_uses_plugin_goal()
    test_plugin_capture_goal_override()
    test_plugin_capture_message_goal_propagation()
    test_plugin_session_id_in_result()
    test_plugin_context_manager_with_exception()
    test_multi_session_continuity()
    test_build_system_prompt_base_unchanged()
    test_memory_dataclass_defaults()
    test_capture_user_message_empty()
    test_capture_user_message_whitespace_only()
    test_should_capture_all_defined_types()
    print("\n" + "=" * 50)
    print("All tests passed ✅")
