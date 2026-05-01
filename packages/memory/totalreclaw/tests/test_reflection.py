"""
TotalReclaw Test Suite — Reflection Engine Edge Cases
Run: python -m totalreclaw.tests.test_reflection
"""

import os
import sys
import json
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from totalreclaw import (
    MemoryStore,
    build_reflection_prompt,
    parse_reflection,
    store_reflection,
    fallback_store_summary,
)


def get_temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


# ── VALID REFLECTION FIXTURE ─────────────────────────────────────────

VALID_REFLECTION = json.dumps({
    "session_summary": "Set up Stripe integration and processed first test payment.",
    "goal_status": "completed",
    "current_goal": "payment-setup",
    "key_facts": [
        {"fact": "Stripe test key is sk_test_abc123", "importance": 7},
        {"fact": "Webhook endpoint is /api/stripe/hooks", "importance": 5},
    ],
    "lessons_learned": [
        {"lesson": "Always check idempotency key before retrying charges", "importance": 8},
    ],
    "next_session_primer": "Verify webhook signatures and add production key rotation.",
})


# ── TEST: parse_reflection with valid JSON ────────────────────────────

def test_parse_valid_json():
    db = get_temp_db()
    try:
        result = parse_reflection(VALID_REFLECTION)
        assert result is not None, "parse_reflection returned None for valid JSON"
        assert result["session_summary"] == "Set up Stripe integration and processed first test payment."
        assert result["goal_status"] == "completed"
        assert result["current_goal"] == "payment-setup"
        assert len(result["key_facts"]) == 2
        assert len(result["lessons_learned"]) == 1
        assert result["next_session_primer"] == "Verify webhook signatures and add production key rotation."
        print("✅ test_parse_valid_json passed")
    finally:
        os.unlink(db)


# ── TEST: malformed JSON — missing closing brace ──────────────────────

def test_parse_malformed_missing_brace():
    db = get_temp_db()
    try:
        # Completely broken JSON with no extractable object
        broken = '{"session_summary": "Did stuff", "goal_status": "completed"'
        result = parse_reflection(broken)
        # Missing closing brace — rfind("}") will find nothing useful, should return None
        assert result is None, "Should return None for JSON missing closing brace"
        print("✅ test_parse_malformed_missing_brace passed")
    finally:
        os.unlink(db)


# ── TEST: trailing text after valid JSON ──────────────────────────────

def test_parse_trailing_text():
    db = get_temp_db()
    try:
        trailing = VALID_REFLECTION + "\n\nHope that helps! Let me know if you need anything else."
        result = parse_reflection(trailing)
        assert result is not None, "Should extract JSON despite trailing text"
        assert result["session_summary"] == "Set up Stripe integration and processed first test payment."
        assert result["goal_status"] == "completed"
        print("✅ test_parse_trailing_text passed")
    finally:
        os.unlink(db)


# ── TEST: markdown fences around JSON ─────────────────────────────────

def test_parse_markdown_json_fences():
    db = get_temp_db()
    try:
        fenced = f"```json\n{VALID_REFLECTION}\n```"
        result = parse_reflection(fenced)
        assert result is not None, "Should handle ```json ... ``` fences"
        assert result["goal_status"] == "completed"
        assert len(result["key_facts"]) == 2
        print("✅ test_parse_markdown_json_fences passed")
    finally:
        os.unlink(db)


# ── TEST: bare markdown fences (no json tag) ──────────────────────────

def test_parse_bare_markdown_fences():
    db = get_temp_db()
    try:
        fenced = f"```\n{VALID_REFLECTION}\n```"
        result = parse_reflection(fenced)
        assert result is not None, "Should handle bare ``` ... ``` fences"
        assert result["session_summary"] == "Set up Stripe integration and processed first test payment."
        print("✅ test_parse_bare_markdown_fences passed")
    finally:
        os.unlink(db)


# ── TEST: preamble text before JSON ───────────────────────────────────

def test_parse_preamble_before_json():
    db = get_temp_db()
    try:
        preamble = "Here is my analysis of the session:\n\n" + VALID_REFLECTION
        result = parse_reflection(preamble)
        assert result is not None, "Should extract JSON despite preamble text"
        assert result["goal_status"] == "completed"
        print("✅ test_parse_preamble_before_json passed")
    finally:
        os.unlink(db)


# ── TEST: missing required field — no session_summary ─────────────────

def test_parse_missing_session_summary():
    db = get_temp_db()
    try:
        data = {
            "goal_status": "completed",
            "current_goal": "test",
            "key_facts": [],
            "lessons_learned": [],
            "next_session_primer": "Do the next thing.",
        }
        result = parse_reflection(json.dumps(data))
        assert result is None, "Should return None when session_summary is missing"
        print("✅ test_parse_missing_session_summary passed")
    finally:
        os.unlink(db)


# ── TEST: missing required field — no goal_status ─────────────────────

def test_parse_missing_goal_status():
    db = get_temp_db()
    try:
        data = {
            "session_summary": "Did some work.",
            "current_goal": "test",
            "key_facts": [],
            "lessons_learned": [],
            "next_session_primer": "Continue tomorrow.",
        }
        result = parse_reflection(json.dumps(data))
        assert result is None, "Should return None when goal_status is missing"
        print("✅ test_parse_missing_goal_status passed")
    finally:
        os.unlink(db)


# ── TEST: missing required field — no next_session_primer ─────────────

def test_parse_missing_next_session_primer():
    db = get_temp_db()
    try:
        data = {
            "session_summary": "Did some work.",
            "goal_status": "partial",
            "current_goal": "test",
            "key_facts": [],
            "lessons_learned": [],
        }
        result = parse_reflection(json.dumps(data))
        assert result is None, "Should return None when next_session_primer is missing"
        print("✅ test_parse_missing_next_session_primer passed")
    finally:
        os.unlink(db)


# ── TEST: invalid goal_status defaults to "partial" ───────────────────

def test_parse_invalid_goal_status_defaults():
    db = get_temp_db()
    try:
        data = {
            "session_summary": "Did some work.",
            "goal_status": "in_progress",
            "current_goal": "test",
            "key_facts": [],
            "lessons_learned": [],
            "next_session_primer": "Keep going.",
        }
        result = parse_reflection(json.dumps(data))
        assert result is not None, "Should still parse with invalid goal_status"
        assert result["goal_status"] == "partial", \
            f"Invalid goal_status should default to 'partial', got '{result['goal_status']}'"
        print("✅ test_parse_invalid_goal_status_defaults passed")
    finally:
        os.unlink(db)


# ── TEST: all four valid goal_status values accepted ──────────────────

def test_parse_all_valid_goal_statuses():
    db = get_temp_db()
    try:
        for status in ["completed", "partial", "blocked", "failed"]:
            data = {
                "session_summary": "Work session.",
                "goal_status": status,
                "current_goal": "test",
                "key_facts": [],
                "lessons_learned": [],
                "next_session_primer": "Next steps.",
            }
            result = parse_reflection(json.dumps(data))
            assert result is not None, f"Should parse with goal_status='{status}'"
            assert result["goal_status"] == status, \
                f"goal_status should remain '{status}', got '{result['goal_status']}'"
        print("✅ test_parse_all_valid_goal_statuses passed")
    finally:
        os.unlink(db)


# ── TEST: missing key_facts/lessons_learned get defaulted to [] ───────

def test_parse_missing_optional_lists():
    db = get_temp_db()
    try:
        data = {
            "session_summary": "Quick session.",
            "goal_status": "completed",
            "next_session_primer": "Nothing to do.",
        }
        result = parse_reflection(json.dumps(data))
        assert result is not None, "Should parse even without key_facts/lessons_learned"
        assert result["key_facts"] == [], \
            f"Missing key_facts should default to [], got {result['key_facts']}"
        assert result["lessons_learned"] == [], \
            f"Missing lessons_learned should default to [], got {result['lessons_learned']}"
        print("✅ test_parse_missing_optional_lists passed")
    finally:
        os.unlink(db)


# ── TEST: build_reflection_prompt with empty transcript ───────────────

def test_build_prompt_empty_transcript():
    db = get_temp_db()
    try:
        messages = build_reflection_prompt("")
        assert isinstance(messages, list), "Should return a list of message dicts"
        assert len(messages) == 2, f"Expected 2 messages (system + user), got {len(messages)}"
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "<session_transcript>" in messages[1]["content"]
        assert "</session_transcript>" in messages[1]["content"]
        print("✅ test_build_prompt_empty_transcript passed")
    finally:
        os.unlink(db)


# ── TEST: build_reflection_prompt with very long transcript ───────────

def test_build_prompt_long_transcript():
    db = get_temp_db()
    try:
        long_transcript = "Step {i}: Performed action and observed result. " * 500
        assert len(long_transcript) > 10000, "Transcript should be 10k+ characters"
        messages = build_reflection_prompt(long_transcript)
        assert len(messages) == 2
        assert long_transcript in messages[1]["content"]
        print(f"✅ test_build_prompt_long_transcript passed (transcript length: {len(long_transcript)} chars)")
    finally:
        os.unlink(db)


# ── TEST: build_reflection_prompt with agent_context ──────────────────

def test_build_prompt_with_agent_context():
    db = get_temp_db()
    try:
        messages = build_reflection_prompt(
            "User asked to set up payments.",
            agent_context="Agent is a backend developer focused on Stripe integration.",
        )
        assert len(messages) == 2
        user_content = messages[1]["content"]
        assert "<agent_context>" in user_content
        assert "backend developer" in user_content
        assert "<session_transcript>" in user_content
        # agent_context should appear before session_transcript
        ctx_pos = user_content.index("<agent_context>")
        transcript_pos = user_content.index("<session_transcript>")
        assert ctx_pos < transcript_pos, "agent_context should appear before session_transcript"
        print("✅ test_build_prompt_with_agent_context passed")
    finally:
        os.unlink(db)


# ── TEST: build_reflection_prompt without agent_context ───────────────

def test_build_prompt_without_agent_context():
    db = get_temp_db()
    try:
        messages = build_reflection_prompt("Simple session.")
        user_content = messages[1]["content"]
        assert "<agent_context>" not in user_content, \
            "Should not include agent_context tags when no context provided"
        print("✅ test_build_prompt_without_agent_context passed")
    finally:
        os.unlink(db)


# ── TEST: store_reflection creates correct memory types ───────────────

def test_store_reflection_creates_correct_types():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        reflection = json.loads(VALID_REFLECTION)
        ids = store_reflection(store, reflection)

        # 1 reflection + 2 facts + 1 lesson = 4 total
        assert len(ids) == 4, f"Expected 4 memory IDs, got {len(ids)}"

        # Verify the first one is a reflection
        first = store.get_by_id(ids[0])
        assert first is not None, "First memory should exist"
        assert first.memory_type == "reflection", \
            f"First memory should be 'reflection', got '{first.memory_type}'"
        assert "Session summary:" in first.content
        assert "payment-setup" in first.content

        # Verify the facts
        fact1 = store.get_by_id(ids[1])
        assert fact1.memory_type == "fact", f"Second memory should be 'fact', got '{fact1.memory_type}'"
        assert "Stripe test key" in fact1.content
        assert fact1.importance == 7

        fact2 = store.get_by_id(ids[2])
        assert fact2.memory_type == "fact", f"Third memory should be 'fact', got '{fact2.memory_type}'"
        assert "Webhook endpoint" in fact2.content
        assert fact2.importance == 5

        # Verify the lesson (stored as fact with "LESSON:" prefix)
        lesson = store.get_by_id(ids[3])
        assert lesson.memory_type == "fact", f"Lesson should be stored as 'fact', got '{lesson.memory_type}'"
        assert lesson.content.startswith("LESSON:"), \
            f"Lesson content should start with 'LESSON:', got '{lesson.content[:20]}'"
        assert "idempotency" in lesson.content
        assert lesson.importance == 8

        print("✅ test_store_reflection_creates_correct_types passed")
    finally:
        os.unlink(db)


# ── TEST: store_reflection with empty facts and lessons ───────────────

def test_store_reflection_empty_facts_lessons():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        reflection = {
            "session_summary": "Short uneventful session.",
            "goal_status": "partial",
            "current_goal": "maintenance",
            "key_facts": [],
            "lessons_learned": [],
            "next_session_primer": "Continue where we left off.",
        }
        ids = store_reflection(store, reflection)

        # Only 1 reflection, no facts or lessons
        assert len(ids) == 1, f"Expected 1 memory ID, got {len(ids)}"
        mem = store.get_by_id(ids[0])
        assert mem.memory_type == "reflection"
        assert mem.importance == 8
        print("✅ test_store_reflection_empty_facts_lessons passed")
    finally:
        os.unlink(db)


# ── TEST: store_reflection goal_tag propagates to all memories ────────

def test_store_reflection_goal_tag_propagation():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        reflection = json.loads(VALID_REFLECTION)
        ids = store_reflection(store, reflection)

        for mid in ids:
            mem = store.get_by_id(mid)
            assert mem.goal_tag == "payment-setup", \
                f"Memory {mid} should have goal_tag 'payment-setup', got '{mem.goal_tag}'"

        print("✅ test_store_reflection_goal_tag_propagation passed")
    finally:
        os.unlink(db)


# ── TEST: store_reflection with no current_goal ──────────────────────

def test_store_reflection_no_goal():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        reflection = {
            "session_summary": "Explored some ideas.",
            "goal_status": "partial",
            "key_facts": [{"fact": "Python 3.12 has new typing features", "importance": 4}],
            "lessons_learned": [],
            "next_session_primer": "Pick a direction.",
        }
        ids = store_reflection(store, reflection)
        assert len(ids) == 2, f"Expected 2 memory IDs, got {len(ids)}"

        for mid in ids:
            mem = store.get_by_id(mid)
            assert mem.goal_tag is None, \
                f"Memory {mid} should have goal_tag None, got '{mem.goal_tag}'"

        print("✅ test_store_reflection_no_goal passed")
    finally:
        os.unlink(db)


# ── TEST: store_reflection handles string-only facts/lessons ──────────

def test_store_reflection_string_facts():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        reflection = {
            "session_summary": "Did work.",
            "goal_status": "completed",
            "current_goal": "test",
            "key_facts": ["API rate limit is 100/min", "Timeout is 30s"],
            "lessons_learned": ["Always validate inputs"],
            "next_session_primer": "Deploy.",
        }
        ids = store_reflection(store, reflection)

        # 1 reflection + 2 facts + 1 lesson = 4
        assert len(ids) == 4, f"Expected 4 memory IDs for string entries, got {len(ids)}"

        fact1 = store.get_by_id(ids[1])
        assert fact1.content == "API rate limit is 100/min"
        assert fact1.importance == 6, "String facts should default to importance 6"

        lesson = store.get_by_id(ids[3])
        assert lesson.content.startswith("LESSON:")
        assert lesson.importance == 6, "String lessons should default to importance 6"

        print("✅ test_store_reflection_string_facts passed")
    finally:
        os.unlink(db)


# ── TEST: store_reflection skips whitespace-only facts ────────────────

def test_store_reflection_skips_blank_facts():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        reflection = {
            "session_summary": "Did work.",
            "goal_status": "completed",
            "current_goal": "test",
            "key_facts": [
                {"fact": "Real fact", "importance": 7},
                {"fact": "   ", "importance": 5},
                {"fact": "", "importance": 3},
            ],
            "lessons_learned": [
                {"lesson": "", "importance": 4},
            ],
            "next_session_primer": "Continue.",
        }
        ids = store_reflection(store, reflection)

        # 1 reflection + 1 real fact (blanks skipped) + 0 lessons = 2
        assert len(ids) == 2, f"Expected 2 memory IDs (blanks skipped), got {len(ids)}"
        print("✅ test_store_reflection_skips_blank_facts passed")
    finally:
        os.unlink(db)


# ── TEST: store_reflection skips non-dict/non-str entries ─────────────

def test_store_reflection_skips_invalid_entries():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        reflection = {
            "session_summary": "Did work.",
            "goal_status": "completed",
            "current_goal": "test",
            "key_facts": [
                {"fact": "Valid fact", "importance": 7},
                42,
                None,
                True,
            ],
            "lessons_learned": [
                123,
                {"lesson": "Valid lesson", "importance": 6},
            ],
            "next_session_primer": "Next.",
        }
        ids = store_reflection(store, reflection)

        # 1 reflection + 1 valid fact + 1 valid lesson = 3
        assert len(ids) == 3, f"Expected 3 memory IDs (invalid entries skipped), got {len(ids)}"
        print("✅ test_store_reflection_skips_invalid_entries passed")
    finally:
        os.unlink(db)


# ── TEST: fallback_store_summary stores with correct type/importance ──

def test_fallback_store_summary():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = fallback_store_summary(store, "Agent spent time debugging a timeout issue.")

        assert isinstance(mid, str), "Should return a memory ID string"
        mem = store.get_by_id(mid)
        assert mem is not None, "Stored memory should be retrievable"
        assert mem.memory_type == "reflection", \
            f"Fallback should store as 'reflection', got '{mem.memory_type}'"
        assert mem.importance == 6, \
            f"Fallback importance should be 6, got {mem.importance}"
        assert mem.content.startswith("[Fallback summary]"), \
            f"Content should start with '[Fallback summary]', got '{mem.content[:30]}'"
        assert "debugging a timeout" in mem.content
        print("✅ test_fallback_store_summary passed")
    finally:
        os.unlink(db)


# ── TEST: fallback_store_summary with goal_tag ────────────────────────

def test_fallback_store_summary_with_goal():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = fallback_store_summary(store, "Worked on payments.", goal_tag="payments")

        mem = store.get_by_id(mid)
        assert mem.goal_tag == "payments", \
            f"Fallback should preserve goal_tag, got '{mem.goal_tag}'"
        print("✅ test_fallback_store_summary_with_goal passed")
    finally:
        os.unlink(db)


# ── TEST: fallback_store_summary without goal_tag ─────────────────────

def test_fallback_store_summary_no_goal():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mid = fallback_store_summary(store, "General session summary.")

        mem = store.get_by_id(mid)
        assert mem.goal_tag is None, \
            f"Fallback without goal should have None goal_tag, got '{mem.goal_tag}'"
        print("✅ test_fallback_store_summary_no_goal passed")
    finally:
        os.unlink(db)


# ── TEST: reflection decay reduces old reflection importance ──────────

def test_reflection_decay_after_store():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)

        # Create 7 reflections with small delays to ensure ordering
        for i in range(7):
            store.save_reflection(f"Old reflection {i}", importance=8)
            time.sleep(0.01)

        # Now store a new structured reflection, which calls decay internally
        reflection = {
            "session_summary": "Latest session.",
            "goal_status": "completed",
            "current_goal": "test",
            "key_facts": [],
            "lessons_learned": [],
            "next_session_primer": "Next.",
        }
        store_reflection(store, reflection)

        # After store_reflection, decay_old_reflections(keep_recent=5) was called.
        # The 8th reflection (just created) plus 4 of the original 7 = 5 kept.
        # The 3 oldest should have decayed importance.
        all_reflections = store.get_recent(limit=20, memory_type="reflection")

        # Sort by created_at ascending to identify oldest
        all_reflections.sort(key=lambda m: m.created_at)
        oldest_three = all_reflections[:3]

        for r in oldest_three:
            assert r.importance <= 6, \
                f"Old reflection should have decayed importance <= 6, got {r.importance} for '{r.content}'"

        # The most recent 5 should remain at importance 8
        newest_five = all_reflections[-5:]
        for r in newest_five:
            assert r.importance == 8, \
                f"Recent reflection should keep importance 8, got {r.importance} for '{r.content}'"

        print("✅ test_reflection_decay_after_store passed")
    finally:
        os.unlink(db)


# ── TEST: multiple decays stack — importance floors at 1 ──────────────

def test_reflection_decay_floors_at_one():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)

        # Create one old reflection
        store.save_reflection("Ancient reflection", importance=3)
        time.sleep(0.01)

        # Create 5 more recent ones to push the old one out of keep_recent
        for i in range(5):
            store.save_reflection(f"Recent reflection {i}", importance=8)
            time.sleep(0.01)

        # Decay multiple times
        store.decay_old_reflections(keep_recent=5, importance_penalty=2)
        store.decay_old_reflections(keep_recent=5, importance_penalty=2)
        store.decay_old_reflections(keep_recent=5, importance_penalty=2)

        all_reflections = store.get_recent(limit=20, memory_type="reflection")
        all_reflections.sort(key=lambda m: m.created_at)
        oldest = all_reflections[0]

        # importance 3 - 2 - 2 - 2 = -3, but floored at MAX(1, ...) in SQL
        assert oldest.importance >= 1, \
            f"Importance should floor at 1, got {oldest.importance}"
        assert oldest.importance <= 1, \
            f"After heavy decay from 3, importance should be 1, got {oldest.importance}"

        print("✅ test_reflection_decay_floors_at_one passed")
    finally:
        os.unlink(db)


# ── TEST: completely garbage input to parse_reflection ────────────────

def test_parse_total_garbage():
    db = get_temp_db()
    try:
        result = parse_reflection("this is not json at all, just random text")
        assert result is None, "Should return None for total garbage input"

        result = parse_reflection("")
        assert result is None, "Should return None for empty string"

        result = parse_reflection("   \n\n  ")
        assert result is None, "Should return None for whitespace-only input"

        print("✅ test_parse_total_garbage passed")
    finally:
        os.unlink(db)


# ── TEST: store_reflection returns list of valid UUIDs ────────────────

def test_store_reflection_returns_valid_ids():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        reflection = json.loads(VALID_REFLECTION)
        ids = store_reflection(store, reflection)

        assert isinstance(ids, list), "store_reflection should return a list"
        for mid in ids:
            assert isinstance(mid, str), f"Each ID should be a string, got {type(mid)}"
            assert len(mid) == 36, f"UUID should be 36 chars, got {len(mid)} for '{mid}'"
            # Verify each ID is retrievable
            mem = store.get_by_id(mid)
            assert mem is not None, f"Memory with ID {mid} should exist in store"

        print("✅ test_store_reflection_returns_valid_ids passed")
    finally:
        os.unlink(db)


# ── TEST: reflection content format ──────────────────────────────────

def test_store_reflection_content_format():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        reflection = json.loads(VALID_REFLECTION)
        ids = store_reflection(store, reflection)

        mem = store.get_by_id(ids[0])
        assert "Session summary:" in mem.content
        assert "Goal: payment-setup" in mem.content
        assert "Status: completed" in mem.content
        assert "Next steps:" in mem.content
        assert "webhook signatures" in mem.content

        print("✅ test_store_reflection_content_format passed")
    finally:
        os.unlink(db)


if __name__ == "__main__":
    print("TotalReclaw Reflection Tests")
    print("=" * 50)
    test_parse_valid_json()
    test_parse_malformed_missing_brace()
    test_parse_trailing_text()
    test_parse_markdown_json_fences()
    test_parse_bare_markdown_fences()
    test_parse_preamble_before_json()
    test_parse_missing_session_summary()
    test_parse_missing_goal_status()
    test_parse_missing_next_session_primer()
    test_parse_invalid_goal_status_defaults()
    test_parse_all_valid_goal_statuses()
    test_parse_missing_optional_lists()
    test_build_prompt_empty_transcript()
    test_build_prompt_long_transcript()
    test_build_prompt_with_agent_context()
    test_build_prompt_without_agent_context()
    test_store_reflection_creates_correct_types()
    test_store_reflection_empty_facts_lessons()
    test_store_reflection_goal_tag_propagation()
    test_store_reflection_no_goal()
    test_store_reflection_string_facts()
    test_store_reflection_skips_blank_facts()
    test_store_reflection_skips_invalid_entries()
    test_fallback_store_summary()
    test_fallback_store_summary_with_goal()
    test_fallback_store_summary_no_goal()
    test_reflection_decay_after_store()
    test_reflection_decay_floors_at_one()
    test_parse_total_garbage()
    test_store_reflection_returns_valid_ids()
    test_store_reflection_content_format()
    print("\n" + "=" * 50)
    print("All tests passed ✅")
