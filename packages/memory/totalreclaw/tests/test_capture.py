"""
TotalReclaw Test Suite — Capture Module Edge Cases
Run: python -m totalreclaw.tests.test_capture
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from totalreclaw import MemoryStore, capture_event, capture_user_message, should_capture
from totalreclaw.capture import CAPTURE_RULES


def get_temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


# ── should_capture tests ─────────────────────────────────────────────


def test_should_capture_captured_types():
    captured_types = [
        "api_call_success", "api_call_error", "file_write", "file_create",
        "db_mutation", "external_request", "api_response_data",
        "config_discovered", "credential_found", "user_instruction",
        "user_preference", "user_correction", "decision_made",
    ]
    for event_type in captured_types:
        result = should_capture(event_type)
        assert result is True, f"should_capture('{event_type}') returned {result}, expected True"
    print("✅ test_should_capture_captured_types passed")


def test_should_capture_skipped_types():
    skipped_types = ["file_read", "search_query", "status_check", "log_output"]
    for event_type in skipped_types:
        result = should_capture(event_type)
        assert result is False, f"should_capture('{event_type}') returned {result}, expected False"
    print("✅ test_should_capture_skipped_types passed")


def test_should_capture_unknown_type():
    result = should_capture("totally_unknown_event")
    assert result is True, f"should_capture for unknown type returned {result}, expected True"
    print("✅ test_should_capture_unknown_type passed")


# ── capture_event tests for each captured event type ─────────────────


def test_capture_api_call_success():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "api_call_success", "Called /users endpoint, got 200")
        assert mid is not None, "api_call_success should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "episode"
        assert mem.importance == 6
        print("✅ test_capture_api_call_success passed")
    finally:
        os.unlink(db)


def test_capture_api_call_error():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "api_call_error", "Stripe API returned 500")
        assert mid is not None, "api_call_error should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "episode"
        assert mem.importance == 8
        print("✅ test_capture_api_call_error passed")
    finally:
        os.unlink(db)


def test_capture_file_write():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "file_write", "Wrote config to settings.json")
        assert mid is not None, "file_write should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "episode"
        assert mem.importance == 6
        print("✅ test_capture_file_write passed")
    finally:
        os.unlink(db)


def test_capture_file_create():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "file_create", "Created new module api_handler.py")
        assert mid is not None, "file_create should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "episode"
        assert mem.importance == 7
        print("✅ test_capture_file_create passed")
    finally:
        os.unlink(db)


def test_capture_db_mutation():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "db_mutation", "Inserted 5 rows into users table")
        assert mid is not None, "db_mutation should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "episode"
        assert mem.importance == 7
        print("✅ test_capture_db_mutation passed")
    finally:
        os.unlink(db)


def test_capture_external_request():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "external_request", "Sent webhook to Slack")
        assert mid is not None, "external_request should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "episode"
        assert mem.importance == 6
        print("✅ test_capture_external_request passed")
    finally:
        os.unlink(db)


def test_capture_api_response_data():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "api_response_data", "User has 3 active subscriptions")
        assert mid is not None, "api_response_data should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "fact"
        assert mem.importance == 5
        print("✅ test_capture_api_response_data passed")
    finally:
        os.unlink(db)


def test_capture_config_discovered():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "config_discovered", "Database port is 5432")
        assert mid is not None, "config_discovered should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "fact"
        assert mem.importance == 7
        print("✅ test_capture_config_discovered passed")
    finally:
        os.unlink(db)


def test_capture_credential_found():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "credential_found", "Found API key in .env file")
        assert mid is not None, "credential_found should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "fact"
        assert mem.importance == 8
        print("✅ test_capture_credential_found passed")
    finally:
        os.unlink(db)


def test_capture_user_instruction():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "user_instruction", "Always use TypeScript for new files")
        assert mid is not None, "user_instruction should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        assert mem.importance == 9
        print("✅ test_capture_user_instruction passed")
    finally:
        os.unlink(db)


def test_capture_user_preference():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "user_preference", "Prefers tabs over spaces")
        assert mid is not None, "user_preference should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        assert mem.importance == 8
        print("✅ test_capture_user_preference passed")
    finally:
        os.unlink(db)


def test_capture_user_correction():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "user_correction", "No, use port 8080 not 3000")
        assert mid is not None, "user_correction should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        assert mem.importance == 9
        print("✅ test_capture_user_correction passed")
    finally:
        os.unlink(db)


def test_capture_decision_made():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "decision_made", "Chose REST over GraphQL for simplicity")
        assert mid is not None, "decision_made should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "episode"
        assert mem.importance == 6
        print("✅ test_capture_decision_made passed")
    finally:
        os.unlink(db)


# ── capture_event tests for skipped event types ──────────────────────


def test_skip_file_read():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "file_read", "Read contents of config.json")
        assert mid is None, "file_read should be skipped"
        assert store.count() == 0, "No memory should be stored for file_read"
        print("✅ test_skip_file_read passed")
    finally:
        os.unlink(db)


def test_skip_search_query():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "search_query", "Searched for 'auth middleware'")
        assert mid is None, "search_query should be skipped"
        assert store.count() == 0, "No memory should be stored for search_query"
        print("✅ test_skip_search_query passed")
    finally:
        os.unlink(db)


def test_skip_status_check():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "status_check", "Server is running on port 3000")
        assert mid is None, "status_check should be skipped"
        assert store.count() == 0, "No memory should be stored for status_check"
        print("✅ test_skip_status_check passed")
    finally:
        os.unlink(db)


def test_skip_log_output():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "log_output", "INFO: Request handled in 42ms")
        assert mid is None, "log_output should be skipped"
        assert store.count() == 0, "No memory should be stored for log_output"
        print("✅ test_skip_log_output passed")
    finally:
        os.unlink(db)


# ── Unknown event types ──────────────────────────────────────────────


def test_unknown_event_type_captured():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "mystery_event", "Something unexpected happened")
        assert mid is not None, "Unknown event type should be captured"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "episode", \
            f"Unknown event should default to 'episode', got '{mem.memory_type}'"
        assert mem.importance == 5, \
            f"Unknown event should default to importance 5, got {mem.importance}"
        print("✅ test_unknown_event_type_captured passed")
    finally:
        os.unlink(db)


# ── Empty and whitespace content ─────────────────────────────────────


def test_empty_content_returns_none():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "api_call_success", "")
        assert mid is None, "Empty content should return None"
        assert store.count() == 0, "No memory should be stored for empty content"
        print("✅ test_empty_content_returns_none passed")
    finally:
        os.unlink(db)


def test_whitespace_only_content_returns_none():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "api_call_success", "   \t\n  ")
        assert mid is None, "Whitespace-only content should return None"
        assert store.count() == 0, "No memory should be stored for whitespace-only content"
        print("✅ test_whitespace_only_content_returns_none passed")
    finally:
        os.unlink(db)


# ── importance_override ──────────────────────────────────────────────


def test_importance_override():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        # api_call_success normally has importance 6
        mid = capture_event(store, "api_call_success", "Important API call", importance_override=10)
        assert mid is not None, "Should be captured with importance override"
        mem = store.get_by_id(mid)
        assert mem.importance == 10, \
            f"Importance should be overridden to 10, got {mem.importance}"
        print("✅ test_importance_override passed")
    finally:
        os.unlink(db)


def test_importance_override_low():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        # user_instruction normally has importance 9
        mid = capture_event(store, "user_instruction", "Minor instruction", importance_override=2)
        assert mid is not None, "Should be captured with low importance override"
        mem = store.get_by_id(mid)
        assert mem.importance == 2, \
            f"Importance should be overridden to 2, got {mem.importance}"
        print("✅ test_importance_override_low passed")
    finally:
        os.unlink(db)


# ── goal_tag propagation ─────────────────────────────────────────────


def test_goal_tag_stored():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "file_create", "Created handler.py", goal_tag="backend-api")
        assert mid is not None
        mem = store.get_by_id(mid)
        assert mem.goal_tag == "backend-api", \
            f"Goal tag should be 'backend-api', got '{mem.goal_tag}'"
        print("✅ test_goal_tag_stored passed")
    finally:
        os.unlink(db)


# ── Content stripping ────────────────────────────────────────────────


def test_content_stripped():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_event(store, "api_call_success", "  padded content  \n")
        assert mid is not None
        mem = store.get_by_id(mid)
        assert mem.content == "padded content", \
            f"Content should be stripped, got '{mem.content}'"
        print("✅ test_content_stripped passed")
    finally:
        os.unlink(db)


# ── capture_user_message directive detection ─────────────────────────


def test_directive_always():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "Always use dark mode")
        assert mid is not None, "'always ' should be detected as directive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        print("✅ test_directive_always passed")
    finally:
        os.unlink(db)


def test_directive_never():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "Never delete production data")
        assert mid is not None, "'never ' should be detected as directive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        print("✅ test_directive_never passed")
    finally:
        os.unlink(db)


def test_directive_dont_ever():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "Don't ever push to main directly")
        assert mid is not None, "'don't ever ' should be detected as directive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        print("✅ test_directive_dont_ever passed")
    finally:
        os.unlink(db)


def test_directive_make_sure_to():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "Make sure to run tests before committing")
        assert mid is not None, "'make sure to ' should be detected as directive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        print("✅ test_directive_make_sure_to passed")
    finally:
        os.unlink(db)


def test_directive_i_prefer():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "I prefer functional components over class components")
        assert mid is not None, "'i prefer ' should be detected as directive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        print("✅ test_directive_i_prefer passed")
    finally:
        os.unlink(db)


def test_directive_i_want_you_to():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "I want you to always explain your reasoning")
        assert mid is not None, "'i want you to ' should be detected as directive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        print("✅ test_directive_i_want_you_to passed")
    finally:
        os.unlink(db)


def test_directive_from_now_on():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "From now on use Python 3.12 features")
        assert mid is not None, "'from now on ' should be detected as directive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        print("✅ test_directive_from_now_on passed")
    finally:
        os.unlink(db)


def test_directive_remember_to():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "Remember to check for null values")
        assert mid is not None, "'remember to ' should be detected as directive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        print("✅ test_directive_remember_to passed")
    finally:
        os.unlink(db)


def test_directive_important():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "Important: the deploy key rotates weekly")
        assert mid is not None, "'important: ' should be detected as directive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        print("✅ test_directive_important passed")
    finally:
        os.unlink(db)


def test_directive_rule():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "Rule: no console.log in production code")
        assert mid is not None, "'rule: ' should be detected as directive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        print("✅ test_directive_rule passed")
    finally:
        os.unlink(db)


def test_directive_note():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "Note: the staging server is at 10.0.0.5")
        assert mid is not None, "'note: ' should be detected as directive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        print("✅ test_directive_note passed")
    finally:
        os.unlink(db)


# ── capture_user_message ignoring normal messages ────────────────────


def test_normal_message_ignored():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "Can you help me fix this bug?")
        assert mid is None, "Normal message should not be captured as directive"
        assert store.count() == 0, "No memory should be stored for normal message"
        print("✅ test_normal_message_ignored passed")
    finally:
        os.unlink(db)


def test_normal_message_with_keyword_midsentence():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "I think you should always test your code")
        assert mid is None, \
            "Message with 'always' mid-sentence should not be captured (signal must be at start)"
        assert store.count() == 0
        print("✅ test_normal_message_with_keyword_midsentence passed")
    finally:
        os.unlink(db)


def test_various_normal_messages_ignored():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        normal_messages = [
            "What does this function do?",
            "Show me the test results",
            "How does the retrieval algorithm work?",
            "Thanks, that looks good",
            "Can you refactor the database layer?",
        ]
        for msg in normal_messages:
            mid = capture_user_message(store, msg)
            assert mid is None, f"Normal message should not be captured: '{msg}'"
        assert store.count() == 0, "No memories should be stored for normal messages"
        print("✅ test_various_normal_messages_ignored passed")
    finally:
        os.unlink(db)


# ── capture_user_message case insensitivity ──────────────────────────


def test_directive_case_insensitive():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "ALWAYS use type hints")
        assert mid is not None, "Directive detection should be case-insensitive"
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive"
        assert mem.content == "ALWAYS use type hints", \
            "Original casing should be preserved in stored content"
        print("✅ test_directive_case_insensitive passed")
    finally:
        os.unlink(db)


# ── capture_user_message with goal_tag ───────────────────────────────


def test_directive_with_goal_tag():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "Always validate inputs", goal_tag="security")
        assert mid is not None
        mem = store.get_by_id(mid)
        assert mem.goal_tag == "security", \
            f"Goal tag should be 'security', got '{mem.goal_tag}'"
        print("✅ test_directive_with_goal_tag passed")
    finally:
        os.unlink(db)


# ── capture_user_message stores as user_instruction ──────────────────


def test_directive_stored_as_user_instruction():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = capture_user_message(store, "Never use eval() in production")
        assert mid is not None
        mem = store.get_by_id(mid)
        assert mem.memory_type == "directive", \
            f"Directive should be stored as 'directive' type, got '{mem.memory_type}'"
        assert mem.importance == 9, \
            f"user_instruction importance should be 9, got {mem.importance}"
        print("✅ test_directive_stored_as_user_instruction passed")
    finally:
        os.unlink(db)


if __name__ == "__main__":
    print("TotalReclaw Capture Tests")
    print("=" * 50)

    # should_capture tests
    test_should_capture_captured_types()
    test_should_capture_skipped_types()
    test_should_capture_unknown_type()

    # capture_event for each captured type
    test_capture_api_call_success()
    test_capture_api_call_error()
    test_capture_file_write()
    test_capture_file_create()
    test_capture_db_mutation()
    test_capture_external_request()
    test_capture_api_response_data()
    test_capture_config_discovered()
    test_capture_credential_found()
    test_capture_user_instruction()
    test_capture_user_preference()
    test_capture_user_correction()
    test_capture_decision_made()

    # capture_event for skipped types
    test_skip_file_read()
    test_skip_search_query()
    test_skip_status_check()
    test_skip_log_output()

    # unknown event types
    test_unknown_event_type_captured()

    # empty and whitespace content
    test_empty_content_returns_none()
    test_whitespace_only_content_returns_none()

    # importance override
    test_importance_override()
    test_importance_override_low()

    # goal tag propagation
    test_goal_tag_stored()

    # content stripping
    test_content_stripped()

    # capture_user_message directive signals
    test_directive_always()
    test_directive_never()
    test_directive_dont_ever()
    test_directive_make_sure_to()
    test_directive_i_prefer()
    test_directive_i_want_you_to()
    test_directive_from_now_on()
    test_directive_remember_to()
    test_directive_important()
    test_directive_rule()
    test_directive_note()

    # capture_user_message normal messages
    test_normal_message_ignored()
    test_normal_message_with_keyword_midsentence()
    test_various_normal_messages_ignored()

    # case insensitivity and original content preservation
    test_directive_case_insensitive()

    # goal tag on directives
    test_directive_with_goal_tag()

    # stored type and importance for user message directives
    test_directive_stored_as_user_instruction()

    print("\n" + "=" * 50)
    print("All tests passed ✅")
