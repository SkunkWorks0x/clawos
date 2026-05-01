"""
TotalReclaw — Basic Example
Get started in under 20 lines. Copy, paste, run.
"""

from totalreclaw import (
    MemoryStore,
    capture_event,
    retrieve_memories,
    format_memory_block,
    build_system_prompt_with_memory,
)

# ── SESSION 1: Agent does work ────────────────────────────────────────
store = MemoryStore(agent_id="demo-agent", db_path="./demo_memory.db")
print(f"Session 1 started: {store.session_id}\n")

capture_event(store, "api_call_success",
    "Created Stripe customer cus_abc123 for user john@example.com",
    goal_tag="payment-setup")

capture_event(store, "config_discovered",
    "Project uses Stripe API v2023-10-16, test mode enabled",
    goal_tag="payment-setup")

capture_event(store, "api_call_error",
    "Webhook endpoint creation failed: 403 Forbidden — API key may lack webhook permissions",
    goal_tag="payment-setup")

capture_event(store, "decision_made",
    "Chose to skip webhook setup and proceed with polling-based payment verification as fallback",
    goal_tag="payment-setup")

store.save_directive("Always confirm with the user before making API calls that cost money")

store.save_reflection(
    "Session summary: Set up Stripe payment flow. Created customer successfully. "
    "Webhook creation failed due to API key permissions. Fell back to polling. "
    "Goal: payment-setup\n"
    "Status: partial\n"
    "Next steps: Fix API key permissions for webhooks, then switch from polling to webhook-based verification.",
    goal_tag="payment-setup",
    importance=8,
)

print("Session 1 complete. Memories stored:")
stats = store.stats()
print(f"  Total memories: {stats['total_active_memories']}")
print(f"  By type: {stats['by_type']}\n")

# ── SESSION 2: Agent resumes work ─────────────────────────────────────
store.new_session()
print(f"Session 2 started: {store.session_id}\n")

memories = retrieve_memories(store, current_goal="payment-setup", token_budget=2000)
memory_block = format_memory_block(memories)
print("Memory block injected into agent context:")
print("=" * 60)
print(memory_block)
print("=" * 60)

base_prompt = "You are a helpful coding assistant that sets up payment infrastructure."
full_prompt = build_system_prompt_with_memory(base_prompt, memories)

print(f"\nFull system prompt length: {len(full_prompt)} characters")
print(f"Memories loaded: {len(memories)}")
print(f"\nThe agent now knows:")
print(f"  - What it did last session (Stripe customer created, webhook failed)")
print(f"  - Standing instructions (confirm before costly API calls)")
print(f"  - What to do next (fix API key permissions for webhooks)")
print(f"  - Relevant facts (Stripe API version, test mode status)")
print(f"\nNo repeated work. No forgotten context. No cold starts.")

# Clean up demo database
import os
os.remove("./demo_memory.db")
