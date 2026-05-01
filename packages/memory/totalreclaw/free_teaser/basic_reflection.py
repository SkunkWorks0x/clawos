"""
TotalReclaw Free Teaser — Standalone Reflection Prompt

This is a free, standalone reflection prompt you can use with any LLM.

WHAT THIS DOESN'T DO (that the full TotalReclaw does):
- No persistent storage
- No retrieval algorithm
- No token budgeting
- No importance scoring
- No capture filtering
- No multi-session continuity

Get the full system: https://skunkworks0x.gumroad.com/l/totalreclaw-core
"""

REFLECTION_PROMPT = """You are a session reflection engine for an AI agent. Your job is to analyze a completed work session and extract structured knowledge.

Respond with ONLY valid JSON. No markdown, no explanation, no preamble.

Required format:
{
    "session_summary": "2-3 sentences: what happened and what was accomplished",
    "goal_status": "completed | partial | blocked | failed",
    "key_facts": ["Important facts to remember (API keys, URLs, decisions, etc.)"],
    "lessons_learned": ["What went wrong or could be improved"],
    "next_session_primer": "What the agent should do FIRST next session"
}"""


def generate_reflection_messages(session_transcript: str) -> list[dict]:
    """Build the messages array for any LLM API."""
    return [
        {"role": "system", "content": REFLECTION_PROMPT},
        {"role": "user", "content": f"<session_transcript>\n{session_transcript}\n</session_transcript>"},
    ]


if __name__ == "__main__":
    example_transcript = """
    User: Set up a Stripe payment flow for my SaaS app.
    Agent: Creating Stripe customer... Done. ID: cus_abc123
    Agent: Creating payment intent for $29.99... Done. ID: pi_xyz789
    Agent: Setting up webhook... Error 403 — Forbidden.
    Agent: Falling back to polling-based verification.
    """
    messages = generate_reflection_messages(example_transcript)
    print("Send these messages to your LLM API:")
    print(f"System prompt: {len(messages[0]['content'])} chars")
    print(f"User message: {len(messages[1]['content'])} chars")
    print("\nWant automatic storage, retrieval, and multi-session continuity?")
    print("Get TotalReclaw: https://skunkworks0x.gumroad.com/l/totalreclaw-core")
