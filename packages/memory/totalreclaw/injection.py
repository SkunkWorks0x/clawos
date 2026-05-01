"""
TotalReclaw Injection — Context Formatter
Formats retrieved memories into a structured block for injection
into the agent's system prompt or context window.
"""

from .core import Memory


def format_memory_block(memories: list[Memory]) -> str:
    """Format a list of retrieved memories into the injection block."""
    if not memories:
        return "<agent_memory>\nNo previous session data available. This is a fresh start.\n</agent_memory>"

    reflections = [m for m in memories if m.memory_type == "reflection"]
    directives = [m for m in memories if m.memory_type == "directive"]
    facts = [m for m in memories if m.memory_type == "fact"]
    episodes = [m for m in memories if m.memory_type == "episode"]

    sections = []

    if reflections:
        latest = reflections[0]
        sections.append(
            f"<last_session_summary>\n{latest.content}\n</last_session_summary>"
        )

    if directives:
        directive_lines = [f"- {d.content}" for d in directives]
        sections.append(
            "<standing_directives>\n"
            + "\n".join(directive_lines)
            + "\n</standing_directives>"
        )

    if facts:
        fact_lines = [f"- {f.content}" for f in facts]
        sections.append(
            "<relevant_context>\n"
            + "\n".join(fact_lines)
            + "\n</relevant_context>"
        )

    if episodes:
        episode_lines = [f"- {e.content}" for e in episodes]
        sections.append(
            "<recent_activity>\n"
            + "\n".join(episode_lines)
            + "\n</recent_activity>"
        )

    return "<agent_memory>\n" + "\n\n".join(sections) + "\n</agent_memory>"


def build_system_prompt_with_memory(
    base_system_prompt: str,
    memories: list[Memory],
) -> str:
    """Combine the agent's base system prompt with the memory context block."""
    memory_block = format_memory_block(memories)
    
    memory_instructions = (
        "\n\n--- PERSISTENT MEMORY ---\n"
        "The following is your memory from previous sessions. Use this context to:\n"
        "1. Continue where you left off (check last_session_summary first)\n"
        "2. Follow all standing_directives at all times\n"
        "3. Reference relevant_context before re-doing past work\n"
        "4. Build on recent_activity rather than starting from scratch\n"
        "If information conflicts between your memory and the current user request, "
        "the current request takes priority.\n\n"
    )
    
    return base_system_prompt + memory_instructions + memory_block
