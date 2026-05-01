"""
TotalReclaw Test Suite — Retrieval Edge Cases
Run: python -m totalreclaw.tests.test_retrieval
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from totalreclaw import MemoryStore, retrieve_memories, retrieval_stats, estimate_tokens


def get_temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def test_empty_store():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        memories = retrieve_memories(store)
        assert memories == [], f"Expected empty list, got {memories}"
        print("✅ test_empty_store passed")
    finally:
        os.unlink(db)


def test_reflection_loads_first():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_episode("Some episode", importance=10)
        store.save_reflection("Session summary: did stuff", importance=8)
        memories = retrieve_memories(store)
        assert memories[0].memory_type == "reflection", \
            f"First memory should be reflection, got {memories[0].memory_type}"
        print("✅ test_reflection_loads_first passed")
    finally:
        os.unlink(db)


def test_directives_always_load():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_directive("Always confirm before spending money")
        store.save_episode("Did something", goal_tag="unrelated-goal")
        memories = retrieve_memories(store, current_goal="my-goal")
        directive_found = any(m.memory_type == "directive" for m in memories)
        assert directive_found, "Directive should be present regardless of goal"
        print("✅ test_directives_always_load passed")
    finally:
        os.unlink(db)


def test_goal_filtering():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_fact("Stripe key is sk_test_123", goal_tag="payments")
        store.save_fact("Database URL is postgres://...", goal_tag="database")
        memories = retrieve_memories(store, current_goal="payments")
        payment_found = any("Stripe" in m.content for m in memories)
        assert payment_found, "Payment-related fact should be retrieved for payments goal"
        print("✅ test_goal_filtering passed")
    finally:
        os.unlink(db)


def test_token_budget_respected():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        for i in range(50):
            store.save_episode(f"Memory entry {i}: " + "x" * 500, importance=5)
        memories = retrieve_memories(store, token_budget=200)
        total_tokens = sum(estimate_tokens(m.content) for m in memories)
        assert total_tokens <= 200 + 150, \
            f"Token budget exceeded: {total_tokens} tokens"
        assert len(memories) < 50, \
            f"Should not load all 50 memories, loaded {len(memories)}"
        print(f"✅ test_token_budget_respected passed (loaded {len(memories)} memories, ~{total_tokens} tokens)")
    finally:
        os.unlink(db)


def test_no_duplicates():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_reflection("Summary of payments work", goal_tag="payments")
        store.save_episode("Did payment stuff", goal_tag="payments", importance=9)
        memories = retrieve_memories(store, current_goal="payments")
        ids = [m.id for m in memories]
        assert len(ids) == len(set(ids)), "Duplicate memory IDs found"
        print("✅ test_no_duplicates passed")
    finally:
        os.unlink(db)


def test_importance_ordering():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_fact("Low importance fact", goal_tag="test", importance=2)
        store.save_fact("High importance fact", goal_tag="test", importance=9)
        store.save_fact("Medium importance fact", goal_tag="test", importance=5)
        memories = retrieve_memories(store, current_goal="test")
        facts = [m for m in memories if m.memory_type == "fact"]
        if len(facts) >= 2:
            assert facts[0].importance >= facts[1].importance, \
                f"Importance ordering wrong: {facts[0].importance} < {facts[1].importance}"
        print("✅ test_importance_ordering passed")
    finally:
        os.unlink(db)


def test_access_tracking():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        mem = store.save_episode("Test memory")
        assert mem.access_count == 0
        retrieve_memories(store)
        updated = store.get_by_id(mem.id)
        assert updated.access_count == 1, f"Access count should be 1, got {updated.access_count}"
        print("✅ test_access_tracking passed")
    finally:
        os.unlink(db)


def test_reflection_decay():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        for i in range(7):
            store.save_reflection(f"Reflection {i}", importance=8)
        store.decay_old_reflections(keep_recent=5, importance_penalty=2)
        all_reflections = store.get_recent(limit=10, memory_type="reflection")
        old_reflections = all_reflections[-2:]
        for r in old_reflections:
            assert r.importance <= 6, \
                f"Old reflection should have decayed importance, got {r.importance}"
        print("✅ test_reflection_decay passed")
    finally:
        os.unlink(db)


def test_retrieval_stats_output():
    db = get_temp_db()
    try:
        store = MemoryStore(agent_id="test", db_path=db)
        store.save_reflection("Summary", goal_tag="test")
        store.save_directive("Be careful")
        store.save_fact("Important fact", goal_tag="test")
        memories = retrieve_memories(store, current_goal="test")
        stats = retrieval_stats(memories)
        assert stats["count"] > 0
        assert stats["total_tokens"] > 0
        assert isinstance(stats["by_type"], dict)
        print(f"✅ test_retrieval_stats_output passed (stats: {stats})")
    finally:
        os.unlink(db)


if __name__ == "__main__":
    print("TotalReclaw Retrieval Tests")
    print("=" * 50)
    test_empty_store()
    test_reflection_loads_first()
    test_directives_always_load()
    test_goal_filtering()
    test_token_budget_respected()
    test_no_duplicates()
    test_importance_ordering()
    test_access_tracking()
    test_reflection_decay()
    test_retrieval_stats_output()
    print("\n" + "=" * 50)
    print("All tests passed ✅")
