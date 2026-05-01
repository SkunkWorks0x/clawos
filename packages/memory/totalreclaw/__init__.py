"""
TotalReclaw — Persistent Memory + Reflection for OpenClaw Agents
Stop your agents from forgetting.

Quick start:
    from totalreclaw import MemoryStore, retrieve_memories, format_memory_block
    
    store = MemoryStore(agent_id="my-agent")
    store.save_episode("Called Stripe API, customer created", goal_tag="payments")
    
    memories = retrieve_memories(store, current_goal="payments")
    context_block = format_memory_block(memories)
"""

from .config import VERSION
from .core import Memory, MemoryStore
from .retrieval import retrieve_memories, retrieval_stats, estimate_tokens
from .reflection import (
    build_reflection_prompt,
    parse_reflection,
    store_reflection,
    fallback_store_summary,
)
from .injection import format_memory_block, build_system_prompt_with_memory
from .capture import capture_event, capture_user_message, should_capture
try:
    from .openclaw import TotalReclawPlugin
except ImportError:
    TotalReclawPlugin = None

__version__ = VERSION

__all__ = [
    "Memory", "MemoryStore",
    "retrieve_memories", "retrieval_stats", "estimate_tokens",
    "build_reflection_prompt", "parse_reflection", "store_reflection", "fallback_store_summary",
    "format_memory_block", "build_system_prompt_with_memory",
    "capture_event", "capture_user_message", "should_capture",
    "TotalReclawPlugin",
]
