"""
TotalReclaw Capture — Event Filtering
Decides what agent events are worth storing as memories.
"""

from typing import Optional
from .core import MemoryStore


CAPTURE_RULES = {
    "api_call_success": {"capture": True, "type": "episode", "importance": 6},
    "api_call_error": {"capture": True, "type": "episode", "importance": 8},
    "file_write": {"capture": True, "type": "episode", "importance": 6},
    "file_create": {"capture": True, "type": "episode", "importance": 7},
    "db_mutation": {"capture": True, "type": "episode", "importance": 7},
    "external_request": {"capture": True, "type": "episode", "importance": 6},
    "api_response_data": {"capture": True, "type": "fact", "importance": 5},
    "config_discovered": {"capture": True, "type": "fact", "importance": 7},
    "credential_found": {"capture": True, "type": "fact", "importance": 8},
    "user_instruction": {"capture": True, "type": "directive", "importance": 9},
    "user_preference": {"capture": True, "type": "directive", "importance": 8},
    "user_correction": {"capture": True, "type": "directive", "importance": 9},
    "decision_made": {"capture": True, "type": "episode", "importance": 6},
    "file_read": {"capture": False, "type": None, "importance": 0},
    "search_query": {"capture": False, "type": None, "importance": 0},
    "status_check": {"capture": False, "type": None, "importance": 0},
    "log_output": {"capture": False, "type": None, "importance": 0},
}


def should_capture(event_type: str) -> bool:
    """Check if an event type should be captured as a memory."""
    rule = CAPTURE_RULES.get(event_type)
    if rule is None:
        return True
    return rule["capture"]


def capture_event(
    store: MemoryStore,
    event_type: str,
    content: str,
    goal_tag: Optional[str] = None,
    importance_override: Optional[int] = None,
) -> Optional[str]:
    """Process an agent event and store it as a memory if it passes filtering."""
    rule = CAPTURE_RULES.get(event_type, {
        "capture": True, "type": "episode", "importance": 5
    })
    
    if not rule["capture"]:
        return None
    if not content or not content.strip():
        return None
    
    memory_type = rule["type"]
    importance = importance_override if importance_override is not None else rule["importance"]
    
    mem = store.save(
        content=content.strip(),
        memory_type=memory_type,
        goal_tag=goal_tag,
        importance=importance,
    )
    return mem.id


def capture_context(
    store: MemoryStore,
    action: str,
    outcome: str = "success",
    goal_tag: Optional[str] = None,
    **details,
) -> Optional[str]:
    """Capture an agent action + outcome plus arbitrary structured details.

    README contract: capture_context(store, action="transfer", outcome="success", amount=150.00).
    Maps onto capture_event with an event_type derived from outcome.
    """
    import json
    event_type = "api_call_success" if outcome == "success" else "api_call_error"
    payload = {"action": action, "outcome": outcome, **details}
    content = json.dumps(payload, default=str, sort_keys=True)
    return capture_event(
        store=store,
        event_type=event_type,
        content=content,
        goal_tag=goal_tag or action,
    )


def capture_user_message(
    store: MemoryStore,
    message: str,
    goal_tag: Optional[str] = None,
) -> Optional[str]:
    """Analyze a user message for directives or preferences and store if found."""
    lower = message.lower().strip()
    directive_signals = [
        "always ", "never ", "don't ever ", "make sure to ",
        "i prefer ", "i want you to ", "from now on ", "remember to ",
        "important: ", "rule: ", "note: ",
    ]
    is_directive = any(lower.startswith(s) for s in directive_signals)
    if is_directive:
        return capture_event(
            store=store,
            event_type="user_instruction",
            content=message.strip(),
            goal_tag=goal_tag,
        )
    return None
