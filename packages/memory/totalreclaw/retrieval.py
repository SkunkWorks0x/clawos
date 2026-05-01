"""
TotalReclaw Retrieval — The Core IP
Layered retrieval algorithm with token budgeting.
This is what people are paying for.
"""

from typing import Optional
from .core import Memory, MemoryStore
from .config import DEFAULT_TOKEN_BUDGET, MAX_MEMORIES_PER_LAYER


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate. 1 token ≈ 4 characters for English text.
    Intentionally over-counts by ~15% — safer to load fewer memories
    than to blow the context window.
    """
    return int(len(text) / 3.5)


def retrieve_memories(
    store: MemoryStore,
    current_goal: Optional[str] = None,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> list[Memory]:
    """
    Retrieve the most relevant memories for injection into agent context.
    
    Strategy: Layered retrieval with strict priority ordering.
    
    Layer 1 (ALWAYS):  Most recent reflection summary
    Layer 2 (ALWAYS):  All active directives
    Layer 3 (IF GOAL): Memories tagged with current goal, ranked by importance then recency
    Layer 4 (FILL):    Most recent episodic memories regardless of goal
    
    Token budget prevents context window bloat.
    """
    memories: list[Memory] = []
    seen_ids: set[str] = set()
    remaining_tokens = token_budget

    def _add_memory(mem: Memory) -> bool:
        nonlocal remaining_tokens
        if mem.id in seen_ids:
            return False
        cost = estimate_tokens(mem.content)
        if cost > remaining_tokens:
            return False
        memories.append(mem)
        seen_ids.add(mem.id)
        remaining_tokens -= cost
        return True

    # LAYER 1: Last Reflection
    last_reflection = store.get_last_reflection()
    if last_reflection:
        _add_memory(last_reflection)

    # LAYER 2: All Active Directives
    if remaining_tokens > 0:
        directives = store.get_directives()
        for d in directives:
            if remaining_tokens <= 0:
                break
            _add_memory(d)

    # LAYER 3: Goal-Relevant Memories
    if current_goal and remaining_tokens > 0:
        goal_memories = store.get_by_goal(current_goal, limit=MAX_MEMORIES_PER_LAYER)
        for m in goal_memories:
            if remaining_tokens <= 0:
                break
            _add_memory(m)

    # LAYER 4: Recent Episodic Backfill
    if remaining_tokens > 0:
        recent = store.get_recent(limit=MAX_MEMORIES_PER_LAYER, memory_type="episode")
        for m in recent:
            if remaining_tokens <= 0:
                break
            _add_memory(m)

    # Update Access Tracking
    retrieved_ids = [m.id for m in memories]
    if retrieved_ids:
        store.mark_accessed(retrieved_ids)

    return memories


def retrieve(
    store: MemoryStore,
    query: Optional[str] = None,
    limit: int = 5,
) -> list[Memory]:
    """Lightweight retrieval matching the README contract.

    README usage: retrieve(store, query="recent transfers", limit=5).
    Tries goal_tag exact match first, then falls back to keyword filter over
    recent memories, then to plain recency.
    """
    if not query:
        return store.get_recent(limit=limit)
    by_goal = store.get_by_goal(query, limit=limit)
    if by_goal:
        return by_goal[:limit]
    pool = store.get_recent(limit=max(limit * 4, 20))
    keywords = [k for k in query.lower().split() if k]
    if keywords:
        matched = [m for m in pool if any(k in m.content.lower() for k in keywords)]
        if matched:
            return matched[:limit]
    return pool[:limit]


def retrieval_stats(memories: list[Memory]) -> dict:
    """Generate statistics about a retrieval result."""
    if not memories:
        return {"count": 0, "total_tokens": 0, "by_type": {}, "goals_covered": []}

    by_type: dict[str, int] = {}
    goals: set[str] = set()
    total_tokens = 0

    for m in memories:
        by_type[m.memory_type] = by_type.get(m.memory_type, 0) + 1
        total_tokens += estimate_tokens(m.content)
        if m.goal_tag:
            goals.add(m.goal_tag)

    return {
        "count": len(memories),
        "total_tokens": total_tokens,
        "by_type": by_type,
        "goals_covered": sorted(goals),
        "importance_range": (
            min(m.importance for m in memories),
            max(m.importance for m in memories),
        ),
    }
