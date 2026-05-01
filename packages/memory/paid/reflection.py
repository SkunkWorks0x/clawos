"""
TotalReclaw Reflection Engine
End-of-session structured reflection that turns messy session transcripts
into organized, scored memories.
"""

import json
import time
from typing import Optional
from .core import MemoryStore


REFLECTION_SYSTEM_PROMPT = """You are a session reflection engine for an AI agent. Your job is to analyze a completed work session and extract structured knowledge that will help the agent perform better in future sessions.

You must respond with ONLY valid JSON. No markdown, no explanation, no preamble. Just the JSON object.

Required output format:
{
    "session_summary": "2-3 sentence summary of what happened and what was accomplished this session",
    "goal_status": "completed | partial | blocked | failed",
    "current_goal": "The primary goal the agent was working toward (short phrase)",
    "key_facts": [
        {"fact": "A specific piece of information worth remembering permanently", "importance": 7},
        {"fact": "Another fact (API keys, URLs, decisions, configurations, etc.)", "importance": 5}
    ],
    "lessons_learned": [
        {"lesson": "What went wrong or could be improved — specific and actionable", "importance": 6}
    ],
    "next_session_primer": "1-2 sentences describing exactly what the agent should do FIRST in the next session to maintain continuity"
}

Rules:
- importance scores range from 1 (trivial) to 10 (critical)
- key_facts should capture concrete, reusable information (not vague observations)
- lessons_learned should be specific enough to prevent the same mistake twice
- session_summary should be useful to someone who wasn't present for the session
- next_session_primer should be actionable
- If the session was short or uneventful, it's okay to have empty key_facts or lessons_learned arrays
- goal_status must be exactly one of: completed, partial, blocked, failed"""


def build_reflection_prompt(session_transcript: str, agent_context: Optional[str] = None) -> list[dict]:
    """Build the messages array for the reflection API call."""
    user_content = f"<session_transcript>\n{session_transcript}\n</session_transcript>"
    if agent_context:
        user_content = f"<agent_context>\n{agent_context}\n</agent_context>\n\n{user_content}"
    return [
        {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def parse_reflection(raw_response: str) -> Optional[dict]:
    """Parse and validate the reflection output from the LLM."""
    text = raw_response.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                return None
        else:
            return None
    
    required_fields = ["session_summary", "goal_status", "next_session_primer"]
    for field in required_fields:
        if field not in data:
            return None
    
    valid_statuses = {"completed", "partial", "blocked", "failed"}
    if data.get("goal_status") not in valid_statuses:
        data["goal_status"] = "partial"
    
    if "key_facts" not in data or not isinstance(data["key_facts"], list):
        data["key_facts"] = []
    if "lessons_learned" not in data or not isinstance(data["lessons_learned"], list):
        data["lessons_learned"] = []
    
    return data


def store_reflection(store: MemoryStore, reflection: dict) -> list[str]:
    """Process a parsed reflection and store all generated memories."""
    created_ids = []
    goal_tag = reflection.get("current_goal")
    
    reflection_content = (
        f"Session summary: {reflection['session_summary']}\n"
        f"Goal: {goal_tag or 'Not specified'}\n"
        f"Status: {reflection['goal_status']}\n"
        f"Next steps: {reflection['next_session_primer']}"
    )
    
    mem = store.save_reflection(reflection_content, goal_tag=goal_tag, importance=8)
    created_ids.append(mem.id)
    
    for fact_entry in reflection.get("key_facts", []):
        if isinstance(fact_entry, dict):
            fact_text = fact_entry.get("fact", "")
            importance = fact_entry.get("importance", 6)
        elif isinstance(fact_entry, str):
            fact_text = fact_entry
            importance = 6
        else:
            continue
        if fact_text.strip():
            mem = store.save_fact(fact_text.strip(), goal_tag=goal_tag, importance=importance)
            created_ids.append(mem.id)
    
    for lesson_entry in reflection.get("lessons_learned", []):
        if isinstance(lesson_entry, dict):
            lesson_text = lesson_entry.get("lesson", "")
            importance = lesson_entry.get("importance", 6)
        elif isinstance(lesson_entry, str):
            lesson_text = lesson_entry
            importance = 6
        else:
            continue
        if lesson_text.strip():
            mem = store.save_fact(
                f"LESSON: {lesson_text.strip()}", 
                goal_tag=goal_tag, 
                importance=importance,
            )
            created_ids.append(mem.id)
    
    store.decay_old_reflections(keep_recent=5, importance_penalty=2)
    return created_ids


FALLBACK_PROMPT = """Summarize this agent session in 2-3 sentences. Focus on: what was the goal, what was accomplished, and what should happen next. Respond with ONLY the summary text, nothing else.

<session_transcript>
{transcript}
</session_transcript>"""


def fallback_store_summary(store: MemoryStore, summary_text: str, goal_tag: Optional[str] = None) -> str:
    """Store a basic summary when structured reflection fails."""
    mem = store.save_reflection(
        f"[Fallback summary] {summary_text}",
        goal_tag=goal_tag,
        importance=6,
    )
    return mem.id
