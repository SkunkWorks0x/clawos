"""
TotalReclaw Test Suite — Injection Module
Run: python -m totalreclaw.tests.test_injection
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from totalreclaw import format_memory_block, build_system_prompt_with_memory
from totalreclaw.core import Memory


def _make_memory(
    memory_type: str = "episode",
    content: str = "test content",
    importance: int = 5,
    memory_id: str = "test-id",
    agent_id: str = "test",
    session_id: str = "s1",
    created_at: float = 1000.0,
) -> Memory:
    """Helper to construct a Memory object with sensible defaults."""
    return Memory(
        id=memory_id,
        agent_id=agent_id,
        session_id=session_id,
        created_at=created_at,
        memory_type=memory_type,
        content=content,
        importance=importance,
    )


def test_empty_memory_list():
    result = format_memory_block([])
    assert "<agent_memory>" in result, "Should contain opening agent_memory tag"
    assert "</agent_memory>" in result, "Should contain closing agent_memory tag"
    assert "No previous session data available. This is a fresh start." in result, \
        "Empty list should produce fresh start message"
    print("✅ test_empty_memory_list passed")


def test_single_reflection():
    mem = _make_memory(memory_type="reflection", content="Session went well, completed payment integration.")
    result = format_memory_block([mem])
    assert "<last_session_summary>" in result, "Reflection should create last_session_summary section"
    assert "</last_session_summary>" in result, "Should close last_session_summary section"
    assert "Session went well, completed payment integration." in result, \
        "Reflection content should appear in output"
    assert "<standing_directives>" not in result, "No directives section when none provided"
    assert "<relevant_context>" not in result, "No facts section when none provided"
    assert "<recent_activity>" not in result, "No episodes section when none provided"
    print("✅ test_single_reflection passed")


def test_single_directive():
    mem = _make_memory(memory_type="directive", content="Always confirm before spending money")
    result = format_memory_block([mem])
    assert "<standing_directives>" in result, "Directive should create standing_directives section"
    assert "</standing_directives>" in result, "Should close standing_directives section"
    assert "- Always confirm before spending money" in result, \
        "Directive content should appear as a bullet point"
    assert "<last_session_summary>" not in result, "No reflection section when none provided"
    print("✅ test_single_directive passed")


def test_single_fact():
    mem = _make_memory(memory_type="fact", content="Stripe API key is sk_test_abc123")
    result = format_memory_block([mem])
    assert "<relevant_context>" in result, "Fact should create relevant_context section"
    assert "</relevant_context>" in result, "Should close relevant_context section"
    assert "- Stripe API key is sk_test_abc123" in result, \
        "Fact content should appear as a bullet point"
    assert "<last_session_summary>" not in result, "No reflection section when none provided"
    print("✅ test_single_fact passed")


def test_single_episode():
    mem = _make_memory(memory_type="episode", content="Called Stripe API, got 200 OK")
    result = format_memory_block([mem])
    assert "<recent_activity>" in result, "Episode should create recent_activity section"
    assert "</recent_activity>" in result, "Should close recent_activity section"
    assert "- Called Stripe API, got 200 OK" in result, \
        "Episode content should appear as a bullet point"
    assert "<last_session_summary>" not in result, "No reflection section when none provided"
    print("✅ test_single_episode passed")


def test_mixed_memory_types():
    memories = [
        _make_memory(memory_type="reflection", content="Completed auth module", memory_id="r1"),
        _make_memory(memory_type="directive", content="Use verbose logging", memory_id="d1"),
        _make_memory(memory_type="fact", content="DB is PostgreSQL 15", memory_id="f1"),
        _make_memory(memory_type="episode", content="Ran migration successfully", memory_id="e1"),
    ]
    result = format_memory_block(memories)

    # All four sections should be present
    assert "<last_session_summary>" in result, "Reflection section missing"
    assert "<standing_directives>" in result, "Directives section missing"
    assert "<relevant_context>" in result, "Facts section missing"
    assert "<recent_activity>" in result, "Episodes section missing"

    # Verify correct ordering: reflection -> directives -> facts -> episodes
    pos_reflection = result.index("<last_session_summary>")
    pos_directives = result.index("<standing_directives>")
    pos_facts = result.index("<relevant_context>")
    pos_episodes = result.index("<recent_activity>")
    assert pos_reflection < pos_directives < pos_facts < pos_episodes, \
        f"Sections not in correct order: reflection={pos_reflection}, directives={pos_directives}, facts={pos_facts}, episodes={pos_episodes}"

    # Content is in correct sections
    assert "Completed auth module" in result
    assert "- Use verbose logging" in result
    assert "- DB is PostgreSQL 15" in result
    assert "- Ran migration successfully" in result

    print("✅ test_mixed_memory_types passed")


def test_special_characters_in_content():
    test_cases = [
        ("Quotes: \"double\" and 'single'", "double quotes and single quotes"),
        ("Newline\nin content", "newline character"),
        ("XML-like <tag>value</tag> content", "angle brackets"),
        ("Ampersand & more & stuff", "ampersand characters"),
        ("All together: <b>bold</b> & \"quoted\" 'text'\nwith newlines", "all special chars combined"),
    ]
    for content, description in test_cases:
        mem = _make_memory(memory_type="fact", content=content)
        result = format_memory_block([mem])
        # The content should pass through verbatim -- injection module does no escaping
        assert content in result, \
            f"Content with {description} should appear in output verbatim"
    print("✅ test_special_characters_in_content passed")


def test_build_system_prompt_with_memory():
    base_prompt = "You are a helpful assistant."
    memories = [
        _make_memory(memory_type="reflection", content="Finished setting up the project", memory_id="r1"),
        _make_memory(memory_type="directive", content="Be concise", memory_id="d1"),
    ]
    result = build_system_prompt_with_memory(base_prompt, memories)

    # Base prompt should be at the start
    assert result.startswith("You are a helpful assistant."), \
        "Output should start with the base prompt"

    # Memory instructions should be present
    assert "--- PERSISTENT MEMORY ---" in result, \
        "Should contain persistent memory header"
    assert "check last_session_summary first" in result, \
        "Should contain instructions about using memory"
    assert "the current request takes priority" in result, \
        "Should contain conflict resolution instruction"

    # Memory block should be present
    assert "<agent_memory>" in result, "Should contain agent_memory block"
    assert "<last_session_summary>" in result, "Should contain reflection section"
    assert "Finished setting up the project" in result
    assert "<standing_directives>" in result, "Should contain directives section"
    assert "- Be concise" in result

    print("✅ test_build_system_prompt_with_memory passed")


def test_build_system_prompt_with_empty_memories():
    base_prompt = "You are a coding assistant."
    result = build_system_prompt_with_memory(base_prompt, [])

    # Base prompt should be at the start
    assert result.startswith("You are a coding assistant."), \
        "Output should start with the base prompt"

    # Memory instructions still present
    assert "--- PERSISTENT MEMORY ---" in result, \
        "Should contain persistent memory header even with empty memories"

    # Fresh start block
    assert "No previous session data available. This is a fresh start." in result, \
        "Empty memories should produce fresh start message"

    print("✅ test_build_system_prompt_with_empty_memories passed")


def test_large_memory_list():
    memories = []
    # Create 15 reflections, 15 directives, 15 facts, 15 episodes = 60 total
    for i in range(15):
        memories.append(_make_memory(
            memory_type="reflection",
            content=f"Reflection number {i}: completed task {i}",
            memory_id=f"r-{i}",
        ))
    for i in range(15):
        memories.append(_make_memory(
            memory_type="directive",
            content=f"Directive number {i}: always do thing {i}",
            memory_id=f"d-{i}",
        ))
    for i in range(15):
        memories.append(_make_memory(
            memory_type="fact",
            content=f"Fact number {i}: important detail {i}",
            memory_id=f"f-{i}",
        ))
    for i in range(15):
        memories.append(_make_memory(
            memory_type="episode",
            content=f"Episode number {i}: action taken {i}",
            memory_id=f"e-{i}",
        ))

    assert len(memories) == 60, f"Expected 60 memories, got {len(memories)}"

    # Should not crash
    result = format_memory_block(memories)

    # All sections should be present
    assert "<last_session_summary>" in result
    assert "<standing_directives>" in result
    assert "<relevant_context>" in result
    assert "<recent_activity>" in result

    # Only the first reflection is used for last_session_summary
    assert "Reflection number 0" in result, "First reflection should be in summary"

    # All 15 directives should appear as bullet points
    for i in range(15):
        assert f"Directive number {i}" in result, f"Directive {i} missing from output"

    # All 15 facts should appear as bullet points
    for i in range(15):
        assert f"Fact number {i}" in result, f"Fact {i} missing from output"

    # All 15 episodes should appear as bullet points
    for i in range(15):
        assert f"Episode number {i}" in result, f"Episode {i} missing from output"

    print(f"✅ test_large_memory_list passed ({len(memories)} entries, output length: {len(result)} chars)")


def test_multiple_directives():
    directives = [
        _make_memory(memory_type="directive", content="Always ask before deleting files", memory_id="d1"),
        _make_memory(memory_type="directive", content="Log all API calls", memory_id="d2"),
        _make_memory(memory_type="directive", content="Never commit secrets to git", memory_id="d3"),
        _make_memory(memory_type="directive", content="Use type hints everywhere", memory_id="d4"),
    ]
    result = format_memory_block(directives)

    assert "<standing_directives>" in result
    assert "- Always ask before deleting files" in result
    assert "- Log all API calls" in result
    assert "- Never commit secrets to git" in result
    assert "- Use type hints everywhere" in result

    # Verify they are each on separate lines with bullet points
    lines = result.split("\n")
    bullet_lines = [line for line in lines if line.startswith("- ")]
    assert len(bullet_lines) == 4, f"Expected 4 bullet lines, got {len(bullet_lines)}"

    print("✅ test_multiple_directives passed")


def test_multiple_facts():
    facts = [
        _make_memory(memory_type="fact", content="Database is SQLite with WAL mode", memory_id="f1"),
        _make_memory(memory_type="fact", content="API rate limit is 100 req/min", memory_id="f2"),
        _make_memory(memory_type="fact", content="Deploy target is AWS Lambda", memory_id="f3"),
        _make_memory(memory_type="fact", content="Auth uses JWT with RS256", memory_id="f4"),
        _make_memory(memory_type="fact", content="Frontend is React 18", memory_id="f5"),
    ]
    result = format_memory_block(facts)

    assert "<relevant_context>" in result
    assert "- Database is SQLite with WAL mode" in result
    assert "- API rate limit is 100 req/min" in result
    assert "- Deploy target is AWS Lambda" in result
    assert "- Auth uses JWT with RS256" in result
    assert "- Frontend is React 18" in result

    # Verify they are each on separate lines with bullet points
    lines = result.split("\n")
    bullet_lines = [line for line in lines if line.startswith("- ")]
    assert len(bullet_lines) == 5, f"Expected 5 bullet lines, got {len(bullet_lines)}"

    print("✅ test_multiple_facts passed")


if __name__ == "__main__":
    print("TotalReclaw Injection Tests")
    print("=" * 50)
    test_empty_memory_list()
    test_single_reflection()
    test_single_directive()
    test_single_fact()
    test_single_episode()
    test_mixed_memory_types()
    test_special_characters_in_content()
    test_build_system_prompt_with_memory()
    test_build_system_prompt_with_empty_memories()
    test_large_memory_list()
    test_multiple_directives()
    test_multiple_facts()
    print("\n" + "=" * 50)
    print("All tests passed ✅")
