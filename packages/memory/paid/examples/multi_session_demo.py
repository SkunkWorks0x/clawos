"""
TotalReclaw — Multi-Session Demo
Simulates 3 full agent sessions with persistent memory.
Watch the agent remember, learn, and build on prior work.

Run: python -m totalreclaw.examples.multi_session_demo
"""

import json
import os
import time

from totalreclaw import TotalReclawPlugin, format_memory_block

DB_PATH = "./demo_multi_session.db"

# ── Visual helpers ──────────────────────────────────────────────────

def banner(text: str) -> None:
    width = 64
    print("\n")
    print("=" * width)
    print(f"  {text}")
    print("=" * width)


def sub_banner(text: str) -> None:
    print(f"\n--- {text} {'─' * (56 - len(text))}")


def show_memory_block(plugin: TotalReclawPlugin) -> None:
    """Display the formatted memory block the agent sees at session start."""
    block = format_memory_block(plugin._memories)
    print()
    for line in block.split("\n"):
        print(f"  {line}")
    print()


def show_result(result: dict) -> None:
    """Show end-of-session reflection result."""
    status_label = {
        "full": "Structured reflection stored",
        "fallback": "Fallback summary stored",
        "skipped": "No reflection (empty session)",
    }
    print(f"\n  Reflection:       {status_label.get(result['reflection_status'], result['reflection_status'])}")
    print(f"  Memories created: {result['memories_created']}")
    print(f"  Session duration: {result['duration_seconds']}s")


def pause() -> None:
    time.sleep(0.3)


# ── Mock LLM ────────────────────────────────────────────────────────
# In production, this would be your OpenAI / Anthropic / local LLM call.
# Here we return canned structured reflections to show the full flow.

SESSION_REFLECTIONS = [
    # Session 1 reflection
    json.dumps({
        "session_summary": (
            "Started competitive analysis for TaskFlow project management tool. "
            "Identified 3 key competitors (Asana, Monday, Linear) and collected "
            "pricing data. Hit a rate limit on the Crunchbase API while gathering "
            "funding data. User requested all findings cite their sources."
        ),
        "goal_status": "partial",
        "current_goal": "competitor-analysis",
        "key_facts": [
            {"fact": "Asana pricing: Free tier, Premium $10.99/user/mo, Business $24.99/user/mo", "importance": 8},
            {"fact": "Monday.com has 225,000+ customers as of 2024 10-K filing", "importance": 7},
            {"fact": "Linear focuses on engineering teams — 10,000+ companies, $52M Series B", "importance": 7},
            {"fact": "Crunchbase API rate limit: 200 requests/min on free tier", "importance": 6},
        ],
        "lessons_learned": [
            {"lesson": "Cache API responses locally before hitting rate limits — lost 10 min of work", "importance": 7},
        ],
        "next_session_primer": (
            "Resume competitor analysis: gather feature comparison matrix for "
            "Asana vs Monday vs Linear. Use cached Crunchbase data instead of "
            "live API calls. Still need market size estimates."
        ),
    }),
    # Session 2 reflection
    json.dumps({
        "session_summary": (
            "Continued competitor analysis. Built feature comparison matrix "
            "covering task management, integrations, and reporting. Found total "
            "addressable market for project management SaaS is $9.81B (2024). "
            "Identified key differentiator: none of the 3 competitors offer "
            "built-in time estimation powered by historical velocity data."
        ),
        "goal_status": "partial",
        "current_goal": "competitor-analysis",
        "key_facts": [
            {"fact": "PM SaaS TAM: $9.81B in 2024, projected $15.08B by 2028 (Grand View Research)", "importance": 9},
            {"fact": "Key gap: no competitor offers AI-powered time estimation from historical velocity", "importance": 9},
            {"fact": "Asana has 200+ integrations, Monday has 200+, Linear has 50+ (developer-focused)", "importance": 6},
            {"fact": "Feature comparison matrix saved to ./research/competitor_matrix.csv", "importance": 5},
        ],
        "lessons_learned": [
            {"lesson": "Cross-referencing multiple sources (10-K filings + press releases) gives more reliable numbers", "importance": 6},
        ],
        "next_session_primer": (
            "Complete the analysis: write executive summary with market opportunity, "
            "competitive positioning, and recommended pricing strategy for TaskFlow. "
            "All data is collected — this is a synthesis and writing session."
        ),
    }),
    # Session 3 reflection
    json.dumps({
        "session_summary": (
            "Completed competitor analysis report. Wrote executive summary with "
            "market sizing ($9.81B TAM), competitive landscape (Asana/Monday/Linear), "
            "and recommended positioning for TaskFlow: AI-first project management "
            "targeting mid-market engineering teams at $12/user/mo. Report saved "
            "and delivered to stakeholders."
        ),
        "goal_status": "completed",
        "current_goal": "competitor-analysis",
        "key_facts": [
            {"fact": "Recommended TaskFlow pricing: $12/user/mo for Pro, $22/user/mo for Business", "importance": 8},
            {"fact": "Target segment: mid-market engineering teams (50-500 employees)", "importance": 8},
            {"fact": "Final report saved to ./research/competitor_analysis_final.pdf", "importance": 7},
        ],
        "lessons_learned": [
            {"lesson": "Starting with data collection before synthesis avoids back-and-forth — clean 3-session arc", "importance": 5},
        ],
        "next_session_primer": (
            "Competitor analysis is complete. Next project: use the findings to "
            "build TaskFlow's landing page copy and positioning statement."
        ),
    }),
]

_reflection_index = 0

def mock_llm(messages: list[dict]) -> str:
    """Simulate an LLM reflection call with pre-built responses."""
    global _reflection_index
    response = SESSION_REFLECTIONS[_reflection_index]
    _reflection_index += 1
    return response


# ── Session 1 ───────────────────────────────────────────────────────

def run_session_1(plugin: TotalReclawPlugin) -> dict:
    banner("SESSION 1: Initial Research")
    memories = plugin.start_session(current_goal="competitor-analysis")

    sub_banner("AGENT MEMORY AT START")
    if not memories:
        print("\n  (empty — this is the agent's first session)")
        print("  The agent has no prior context. Starting from scratch.\n")
    else:
        show_memory_block(plugin)

    pause()
    sub_banner("AGENT WORKING")

    print("  Researching competitor: Asana...")
    plugin.capture("api_call_success",
        "Scraped Asana pricing page — Free, Premium $10.99/user/mo, Business $24.99/user/mo")
    pause()

    print("  Researching competitor: Monday.com...")
    plugin.capture("api_call_success",
        "Retrieved Monday.com 10-K filing — 225,000+ customers, $0.6B ARR")
    pause()

    print("  Researching competitor: Linear...")
    plugin.capture("api_call_success",
        "Gathered Linear data — engineering-focused, 10K+ companies, $52M Series B")
    pause()

    print("  Querying Crunchbase for funding rounds...")
    plugin.capture("api_call_error",
        "Crunchbase API returned 429 Too Many Requests — rate limited at 200 req/min on free tier")
    pause()

    print("  User directive received.")
    plugin.capture_message("Always cite sources when presenting competitor data")
    pause()

    sub_banner("END OF SESSION")
    print("  Reflection engine running...")
    result = plugin.end_session()
    show_result(result)
    return result


# ── Session 2 ───────────────────────────────────────────────────────

def run_session_2(plugin: TotalReclawPlugin) -> dict:
    banner("SESSION 2: Deep Dive")
    memories = plugin.start_session(current_goal="competitor-analysis")

    sub_banner("AGENT MEMORY AT START")
    print(f"  Loaded {len(memories)} memories from Session 1:")
    show_memory_block(plugin)

    print("  The agent now knows:")
    print("  -> Asana, Monday, and Linear pricing/stats from last session")
    print("  -> Crunchbase API is rate-limited (will avoid it)")
    print("  -> Must cite all sources (user directive)")
    print("  -> Next step: feature comparison + market size")

    pause()
    sub_banner("AGENT WORKING")

    print("  Building feature comparison matrix (using cached data)...")
    plugin.capture("file_create",
        "Created ./research/competitor_matrix.csv with feature comparison across Asana, Monday, Linear")
    pause()

    print("  Researching market size...")
    plugin.capture("api_call_success",
        "Retrieved Grand View Research report — PM SaaS TAM $9.81B in 2024, projected $15.08B by 2028")
    pause()

    print("  Analyzing competitive gaps...")
    plugin.capture("decision_made",
        "Key differentiator identified: no competitor offers AI-powered time estimation from historical velocity data")
    pause()

    print("  Gathering integration counts...")
    plugin.capture("api_call_success",
        "Asana: 200+ integrations, Monday: 200+, Linear: 50+ (developer-focused ecosystem)")
    pause()

    sub_banner("END OF SESSION")
    print("  Reflection engine running...")
    result = plugin.end_session()
    show_result(result)
    return result


# ── Session 3 ───────────────────────────────────────────────────────

def run_session_3(plugin: TotalReclawPlugin) -> dict:
    banner("SESSION 3: Final Report")
    memories = plugin.start_session(current_goal="competitor-analysis")

    sub_banner("AGENT MEMORY AT START")
    print(f"  Loaded {len(memories)} memories from Sessions 1 AND 2:")
    show_memory_block(plugin)

    print("  The agent now knows EVERYTHING from both prior sessions:")
    print("  -> Session 1 findings: competitor pricing, Crunchbase rate limit")
    print("  -> Session 2 findings: $9.81B TAM, competitive gap, feature matrix")
    print("  -> Standing directive: cite all sources")
    print("  -> Ready to synthesize and write the final report")

    pause()
    sub_banner("AGENT WORKING")

    print("  Writing executive summary...")
    plugin.capture("file_create",
        "Created executive summary: $9.81B market, 3 key competitors, AI time estimation as differentiator")
    pause()

    print("  Defining pricing recommendation...")
    plugin.capture("decision_made",
        "Recommended TaskFlow pricing: Pro $12/user/mo, Business $22/user/mo — "
        "positioned between Linear ($8) and Monday ($12-24) with AI features")
    pause()

    print("  Finalizing report...")
    plugin.capture("file_create",
        "Saved final report to ./research/competitor_analysis_final.pdf — "
        "all sources cited per user directive")
    pause()

    sub_banner("END OF SESSION")
    print("  Reflection engine running...")
    result = plugin.end_session()
    show_result(result)
    return result


# ── Main ────────────────────────────────────────────────────────────

def main() -> None:
    # Clean slate
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    banner("TotalReclaw Multi-Session Demo")
    print("  Scenario: Agent performs a 3-session competitor analysis")
    print("  Watch how memories persist, accumulate, and guide each session.")
    print("  In production, each session could be hours or days apart.")

    plugin = TotalReclawPlugin(
        agent_id="research-agent",
        db_path=DB_PATH,
        llm_call=mock_llm,
        current_goal="competitor-analysis",
    )

    r1 = run_session_1(plugin)
    r2 = run_session_2(plugin)
    r3 = run_session_3(plugin)

    # ── Final Summary ───────────────────────────────────────────────
    banner("RESULTS")

    total_memories = r1["memories_created"] + r2["memories_created"] + r3["memories_created"]
    stats = plugin.store.stats()

    print(f"  Sessions completed:    3")
    print(f"  Total memories stored: {stats['total_active_memories']}")
    print(f"  Memories by type:      {stats['by_type']}")
    print(f"  Reflections generated: {r1['reflection_status']}, {r2['reflection_status']}, {r3['reflection_status']}")
    print()
    print("  What TotalReclaw did:")
    print("  -> Session 1: Captured research + error + directive. Reflected.")
    print("  -> Session 2: Loaded Session 1 context. Avoided rate limit.")
    print("     Built on prior work. Reflected.")
    print("  -> Session 3: Loaded ALL context. Synthesized 2 sessions of")
    print("     research into a final report. No repeated work.")
    print()
    print("  Without TotalReclaw: 3 cold starts. Repeated API calls.")
    print("  Forgotten directives. No continuity.")
    print()
    print("  With TotalReclaw: One continuous arc of work across sessions.")
    print("  Zero context lost. Zero repeated work.")

    # Clean up
    os.remove(DB_PATH)


if __name__ == "__main__":
    main()
