"""
TotalReclaw Test Suite — OpenClaw Integration Plugin
Run: python -m totalreclaw.tests.test_openclaw
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from totalreclaw import MemoryStore, TotalReclawPlugin


def get_temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


# ── Mock LLM helpers ────────────────────────────────────────────────

def make_mock_llm(response: str):
    """Return a callable that mimics an LLM API call."""
    def mock_llm(messages: list[dict]) -> str:
        return response
    return mock_llm


VALID_REFLECTION_JSON = json.dumps({
    "session_summary": "Set up Stripe integration and created test customer.",
    "goal_status": "partial",
    "current_goal": "payment-setup",
    "key_facts": [
        {"fact": "Stripe API version is 2024-01-01", "importance": 7},
    ],
    "lessons_learned": [
        {"lesson": "Always check webhook permissions first", "importance": 6},
    ],
    "next_session_primer": "Create webhook endpoint and configure event types.",
})


def make_failing_llm():
    """Return a callable that raises an exception."""
    def failing_llm(messages: list[dict]) -> str:
        raise ConnectionError("API timeout")
    return failing_llm


# ── Tests ───────────────────────────────────────────────────────────

def test_start_session_creates_store():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db)
        plugin.start_session()
        assert plugin.session_active, "Session should be active after start"
        assert plugin.store is not None, "Store should be initialized"
        assert plugin.store.agent_id == "test-agent"
        plugin.end_session()
        print("✅ test_start_session_creates_store passed")
    finally:
        os.unlink(db)


def test_context_manager_lifecycle():
    db = get_temp_db()
    try:
        with TotalReclawPlugin("test-agent", db_path=db) as plugin:
            assert plugin.session_active, "Session should be active inside with"
            assert plugin.store is not None
        assert not plugin.session_active, "Session should be inactive after with"
        print("✅ test_context_manager_lifecycle passed")
    finally:
        os.unlink(db)


def test_get_system_prompt_includes_memories():
    db = get_temp_db()
    try:
        # Session 1: create some memories
        store = MemoryStore(agent_id="test-agent", db_path=db)
        store.save_directive("Always confirm before spending money")
        store.save_reflection("Session summary: set up payments", importance=8)

        # Session 2: plugin retrieves them
        plugin = TotalReclawPlugin("test-agent", db_path=db)
        plugin.start_session()
        prompt = plugin.get_system_prompt("You are a helper.")
        assert "always confirm" in prompt.lower(), \
            "Directive should appear in system prompt"
        assert "set up payments" in prompt.lower(), \
            "Reflection should appear in system prompt"
        plugin.end_session()
        print("✅ test_get_system_prompt_includes_memories passed")
    finally:
        os.unlink(db)


def test_capture_stores_event():
    db = get_temp_db()
    try:
        with TotalReclawPlugin("test-agent", db_path=db) as plugin:
            mid = plugin.capture("api_call_success", "Created customer cus_123")
            assert mid is not None, "Captured event should return a memory ID"
            mem = plugin.store.get_by_id(mid)
            assert "cus_123" in mem.content
        print("✅ test_capture_stores_event passed")
    finally:
        os.unlink(db)


def test_capture_filters_read_only():
    db = get_temp_db()
    try:
        with TotalReclawPlugin("test-agent", db_path=db) as plugin:
            mid = plugin.capture("file_read", "Read config.json")
            assert mid is None, "file_read should be filtered out"
        print("✅ test_capture_filters_read_only passed")
    finally:
        os.unlink(db)


def test_capture_message_detects_directive():
    db = get_temp_db()
    try:
        with TotalReclawPlugin("test-agent", db_path=db) as plugin:
            mid = plugin.capture_message("Always use UTC timestamps")
            assert mid is not None, "Directive signal should be captured"
            mem = plugin.store.get_by_id(mid)
            assert mem.memory_type == "directive"
        print("✅ test_capture_message_detects_directive passed")
    finally:
        os.unlink(db)


def test_capture_accumulates_transcript():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db)
        plugin.start_session()
        plugin.capture("api_call_success", "Called Stripe")
        plugin.capture("file_write", "Wrote config.yaml")
        plugin.capture_message("Remember to check logs")
        assert len(plugin._transcript) == 3, \
            f"Expected 3 transcript entries, got {len(plugin._transcript)}"
        assert "[api_call_success]" in plugin._transcript[0]
        assert "[user]" in plugin._transcript[2]
        plugin.end_session()
        print("✅ test_capture_accumulates_transcript passed")
    finally:
        os.unlink(db)


def test_end_session_with_llm_call():
    db = get_temp_db()
    try:
        mock_llm = make_mock_llm(VALID_REFLECTION_JSON)
        plugin = TotalReclawPlugin(
            "test-agent", db_path=db, llm_call=mock_llm,
            current_goal="payment-setup",
        )
        plugin.start_session()
        plugin.capture("api_call_success", "Created customer")
        result = plugin.end_session()

        assert result["reflection_status"] == "full", \
            f"Expected full reflection, got {result['reflection_status']}"
        assert result["memories_created"] >= 1, \
            "Should create at least a reflection memory"
        assert len(result["memory_ids"]) >= 1
        print(f"✅ test_end_session_with_llm_call passed "
              f"(created {result['memories_created']} memories)")
    finally:
        os.unlink(db)


def test_end_session_fallback_without_llm():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db)
        plugin.start_session()
        plugin.capture("api_call_success", "Did something")
        result = plugin.end_session()

        assert result["reflection_status"] == "fallback", \
            f"Expected fallback, got {result['reflection_status']}"
        assert result["memories_created"] == 1
        print("✅ test_end_session_fallback_without_llm passed")
    finally:
        os.unlink(db)


def test_end_session_fallback_on_llm_error():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin(
            "test-agent", db_path=db, llm_call=make_failing_llm(),
        )
        plugin.start_session()
        plugin.capture("api_call_success", "Did work")
        result = plugin.end_session()

        assert result["reflection_status"] == "fallback", \
            f"Expected fallback on LLM error, got {result['reflection_status']}"
        assert result["memories_created"] == 1
        print("✅ test_end_session_fallback_on_llm_error passed")
    finally:
        os.unlink(db)


def test_end_session_skips_empty_transcript():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db)
        plugin.start_session()
        # No captures — transcript is empty
        result = plugin.end_session()
        assert result["reflection_status"] == "skipped", \
            f"Expected skipped for empty transcript, got {result['reflection_status']}"
        assert result["memories_created"] == 0
        print("✅ test_end_session_skips_empty_transcript passed")
    finally:
        os.unlink(db)


def test_double_start_session_ends_previous():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db)
        plugin.start_session()
        plugin.capture("api_call_success", "First session work")

        # Start again without explicit end — should auto-end
        plugin.start_session(current_goal="new-goal")
        assert plugin.session_active
        assert plugin.current_goal == "new-goal"
        # Transcript should be reset for new session
        assert len(plugin._transcript) == 0, \
            "Transcript should reset after auto-end + new start"
        plugin.end_session()
        print("✅ test_double_start_session_ends_previous passed")
    finally:
        os.unlink(db)


def test_capture_before_start_returns_none():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db)
        # No start_session called
        mid = plugin.capture("api_call_success", "This should not crash")
        assert mid is None, "Capture before start should return None"
        mid2 = plugin.capture_message("Always do X")
        assert mid2 is None, "capture_message before start should return None"
        print("✅ test_capture_before_start_returns_none passed")
    finally:
        os.unlink(db)


def test_set_goal_mid_session():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin(
            "test-agent", db_path=db, current_goal="goal-a",
        )
        plugin.start_session()
        plugin.capture("api_call_success", "Work for goal A")

        plugin.set_goal("goal-b")
        assert plugin.current_goal == "goal-b"
        plugin.capture("file_write", "Work for goal B", goal_tag="goal-b")

        plugin.end_session()
        print("✅ test_set_goal_mid_session passed")
    finally:
        os.unlink(db)


def test_never_crashes_host():
    """Plugin should absorb all internal errors without raising."""
    db = get_temp_db()
    try:
        # Use a bogus db path that can't be written to
        plugin = TotalReclawPlugin("test-agent", db_path="/dev/null/impossible.db")
        # These should all return safe defaults, never raise
        memories = plugin.start_session()
        assert isinstance(memories, list)

        prompt = plugin.get_system_prompt("Base prompt")
        assert prompt == "Base prompt" or isinstance(prompt, str)

        mid = plugin.capture("api_call_success", "test")
        # mid may be None if store is None

        result = plugin.end_session()
        assert isinstance(result, dict)
        print("✅ test_never_crashes_host passed")
    finally:
        os.unlink(db)


def test_end_session_without_start():
    db = get_temp_db()
    try:
        plugin = TotalReclawPlugin("test-agent", db_path=db)
        result = plugin.end_session()
        assert result["reflection_status"] == "skipped", \
            f"Expected skipped, got {result['reflection_status']}"
        print("✅ test_end_session_without_start passed")
    finally:
        os.unlink(db)


def test_transcript_override():
    db = get_temp_db()
    try:
        mock_llm = make_mock_llm(VALID_REFLECTION_JSON)
        plugin = TotalReclawPlugin("test-agent", db_path=db, llm_call=mock_llm)
        plugin.start_session()
        result = plugin.end_session(
            transcript_override="Custom transcript: did some work on payments"
        )
        assert result["reflection_status"] == "full", \
            f"Expected full with override, got {result['reflection_status']}"
        print("✅ test_transcript_override passed")
    finally:
        os.unlink(db)


if __name__ == "__main__":
    print("TotalReclaw OpenClaw Integration Tests")
    print("=" * 50)
    test_start_session_creates_store()
    test_context_manager_lifecycle()
    test_get_system_prompt_includes_memories()
    test_capture_stores_event()
    test_capture_filters_read_only()
    test_capture_message_detects_directive()
    test_capture_accumulates_transcript()
    test_end_session_with_llm_call()
    test_end_session_fallback_without_llm()
    test_end_session_fallback_on_llm_error()
    test_end_session_skips_empty_transcript()
    test_double_start_session_ends_previous()
    test_capture_before_start_returns_none()
    test_set_goal_mid_session()
    test_never_crashes_host()
    test_end_session_without_start()
    test_transcript_override()
    print("\n" + "=" * 50)
    print("All tests passed ✅")
