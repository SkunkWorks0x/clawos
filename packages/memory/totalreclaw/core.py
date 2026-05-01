"""
TotalReclaw Core — Persistent Memory Store
SQLite-backed memory storage with typed entries and importance scoring.
"""

import sqlite3
import uuid
import time
import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class Memory:
    """A single memory entry."""
    id: str
    agent_id: str
    session_id: str
    created_at: float
    memory_type: str  # 'episode' | 'reflection' | 'fact' | 'directive'
    content: str
    goal_tag: Optional[str] = None
    importance: int = 5  # 1-10
    access_count: int = 0
    last_accessed: Optional[float] = None
    is_active: bool = True


class MemoryStore:
    """
    SQLite-backed persistent memory store for OpenClaw agents.
    
    Usage:
        store = MemoryStore(agent_id="my-agent", db_path="./memory.db")
        store.save_episode("Called Stripe API, got 200", goal_tag="payment-setup", importance=7)
        memories = store.get_recent(limit=10)
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS memories (
        id              TEXT PRIMARY KEY,
        agent_id        TEXT NOT NULL,
        session_id      TEXT NOT NULL,
        created_at      REAL NOT NULL,
        memory_type     TEXT NOT NULL CHECK(memory_type IN ('episode', 'reflection', 'fact', 'directive')),
        goal_tag        TEXT,
        content         TEXT NOT NULL,
        importance      INTEGER DEFAULT 5 CHECK(importance BETWEEN 1 AND 10),
        access_count    INTEGER DEFAULT 0,
        last_accessed   REAL,
        is_active       INTEGER DEFAULT 1
    );

    CREATE INDEX IF NOT EXISTS idx_agent_goal ON memories(agent_id, goal_tag);
    CREATE INDEX IF NOT EXISTS idx_agent_type ON memories(agent_id, memory_type);
    CREATE INDEX IF NOT EXISTS idx_agent_time ON memories(agent_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_agent_active ON memories(agent_id, is_active);
    """

    DEFAULT_DB_PATH = "./totalreclaw.db"

    def __init__(self, agent_id: str = "default", db_path: str = DEFAULT_DB_PATH, session_id: Optional[str] = None):
        # README convention: MemoryStore("agent_alpha.db") — single positional
        # ending in .db means the caller passed a db path, not an agent id.
        if agent_id.endswith(".db") and db_path == self.DEFAULT_DB_PATH:
            db_path = agent_id
            agent_id = os.path.splitext(os.path.basename(db_path))[0] or "default"
        self.agent_id = agent_id
        self.session_id = session_id or str(uuid.uuid4())
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database and create tables if they don't exist."""
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".", exist_ok=True)
        with self._connect() as conn:
            conn.executescript(self.SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        """Create a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert a database row to a Memory object."""
        return Memory(
            id=row["id"],
            agent_id=row["agent_id"],
            session_id=row["session_id"],
            created_at=row["created_at"],
            memory_type=row["memory_type"],
            content=row["content"],
            goal_tag=row["goal_tag"],
            importance=row["importance"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
            is_active=bool(row["is_active"]),
        )

    # ── WRITE OPERATIONS ──────────────────────────────────────────────

    def save(
        self,
        content: str,
        memory_type: str,
        goal_tag: Optional[str] = None,
        importance: int = 5,
    ) -> Memory:
        """
        Save a new memory entry.
        
        Args:
            content: The memory content text.
            memory_type: One of 'episode', 'reflection', 'fact', 'directive'.
            goal_tag: Optional goal/task this memory relates to.
            importance: 1-10 importance score (higher = more likely to be retrieved).
        
        Returns:
            The created Memory object.
        """
        if memory_type not in ("episode", "reflection", "fact", "directive"):
            raise ValueError(f"Invalid memory_type: {memory_type}. Must be one of: episode, reflection, fact, directive")
        
        importance = max(1, min(10, importance))
        
        memory = Memory(
            id=str(uuid.uuid4()),
            agent_id=self.agent_id,
            session_id=self.session_id,
            created_at=time.time(),
            memory_type=memory_type,
            content=content,
            goal_tag=goal_tag,
            importance=importance,
        )

        with self._connect() as conn:
            conn.execute(
                """INSERT INTO memories 
                   (id, agent_id, session_id, created_at, memory_type, goal_tag, content, importance, access_count, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1)""",
                (memory.id, memory.agent_id, memory.session_id, memory.created_at,
                 memory.memory_type, memory.goal_tag, memory.content, memory.importance),
            )

        return memory

    # ── CONVENIENCE WRITE METHODS ─────────────────────────────────────

    def save_episode(self, content: str, goal_tag: Optional[str] = None, importance: int = 5) -> Memory:
        """Save an episodic memory (action + outcome from a session)."""
        return self.save(content, "episode", goal_tag=goal_tag, importance=importance)

    def save_reflection(self, content: str, goal_tag: Optional[str] = None, importance: int = 8) -> Memory:
        """Save a reflection summary. Default high importance."""
        return self.save(content, "reflection", goal_tag=goal_tag, importance=importance)

    def save_fact(self, content: str, goal_tag: Optional[str] = None, importance: int = 6) -> Memory:
        """Save an extracted fact (persistent knowledge)."""
        return self.save(content, "fact", goal_tag=goal_tag, importance=importance)

    def save_directive(self, content: str, importance: int = 9) -> Memory:
        """Save a user directive/preference. Default very high importance. No goal tag (applies globally)."""
        return self.save(content, "directive", goal_tag=None, importance=importance)

    # ── READ OPERATIONS ───────────────────────────────────────────────

    def get_by_id(self, memory_id: str) -> Optional[Memory]:
        """Retrieve a single memory by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ? AND agent_id = ?",
                (memory_id, self.agent_id),
            ).fetchone()
        return self._row_to_memory(row) if row else None

    def get_recent(self, limit: int = 10, memory_type: Optional[str] = None) -> list[Memory]:
        """Get most recent active memories, optionally filtered by type."""
        query = "SELECT * FROM memories WHERE agent_id = ? AND is_active = 1"
        params: list = [self.agent_id]
        
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def get_by_goal(self, goal_tag: str, limit: int = 20) -> list[Memory]:
        """Get memories tagged with a specific goal, ranked by importance then recency."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM memories 
                   WHERE agent_id = ? AND goal_tag = ? AND is_active = 1
                   ORDER BY importance DESC, created_at DESC LIMIT ?""",
                (self.agent_id, goal_tag, limit),
            ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def get_directives(self) -> list[Memory]:
        """Get all active directives, ranked by importance."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM memories 
                   WHERE agent_id = ? AND memory_type = 'directive' AND is_active = 1
                   ORDER BY importance DESC""",
                (self.agent_id,),
            ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def get_last_reflection(self) -> Optional[Memory]:
        """Get the most recent reflection. This is the 'where was I?' anchor."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM memories 
                   WHERE agent_id = ? AND memory_type = 'reflection' AND is_active = 1
                   ORDER BY created_at DESC LIMIT 1""",
                (self.agent_id,),
            ).fetchone()
        return self._row_to_memory(row) if row else None

    def count(self, memory_type: Optional[str] = None) -> int:
        """Count active memories, optionally filtered by type."""
        query = "SELECT COUNT(*) as cnt FROM memories WHERE agent_id = ? AND is_active = 1"
        params: list = [self.agent_id]
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return row["cnt"]

    # ── UPDATE OPERATIONS ─────────────────────────────────────────────

    def mark_accessed(self, memory_ids: list[str]):
        """Update access count and timestamp for retrieved memories."""
        if not memory_ids:
            return
        now = time.time()
        with self._connect() as conn:
            placeholders = ",".join("?" * len(memory_ids))
            conn.execute(
                f"""UPDATE memories 
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE id IN ({placeholders}) AND agent_id = ?""",
                [now] + memory_ids + [self.agent_id],
            )

    def deactivate(self, memory_id: str):
        """Soft-delete a memory (set is_active = 0)."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE memories SET is_active = 0 WHERE id = ? AND agent_id = ?",
                (memory_id, self.agent_id),
            )

    def decay_old_reflections(self, keep_recent: int = 5, importance_penalty: int = 2):
        """
        Reduce importance of old reflections to prevent memory bloat.
        Keeps the most recent N reflections at full importance, reduces the rest.
        """
        with self._connect() as conn:
            recent_ids = conn.execute(
                """SELECT id FROM memories 
                   WHERE agent_id = ? AND memory_type = 'reflection' AND is_active = 1
                   ORDER BY created_at DESC LIMIT ?""",
                (self.agent_id, keep_recent),
            ).fetchall()
            keep_ids = [r["id"] for r in recent_ids]

            if keep_ids:
                placeholders = ",".join("?" * len(keep_ids))
                conn.execute(
                    f"""UPDATE memories 
                        SET importance = MAX(1, importance - ?)
                        WHERE agent_id = ? AND memory_type = 'reflection' AND is_active = 1
                        AND id NOT IN ({placeholders})""",
                    [importance_penalty, self.agent_id] + keep_ids,
                )

    # ── SESSION MANAGEMENT ────────────────────────────────────────────

    def new_session(self, session_id: Optional[str] = None) -> str:
        """Start a new session. Returns the new session ID."""
        self.session_id = session_id or str(uuid.uuid4())
        return self.session_id

    # ── STATS ─────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Get memory store statistics for this agent."""
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM memories WHERE agent_id = ? AND is_active = 1",
                (self.agent_id,),
            ).fetchone()["cnt"]
            
            by_type = {}
            for row in conn.execute(
                """SELECT memory_type, COUNT(*) as cnt FROM memories 
                   WHERE agent_id = ? AND is_active = 1 GROUP BY memory_type""",
                (self.agent_id,),
            ).fetchall():
                by_type[row["memory_type"]] = row["cnt"]
            
            sessions = conn.execute(
                "SELECT COUNT(DISTINCT session_id) as cnt FROM memories WHERE agent_id = ?",
                (self.agent_id,),
            ).fetchone()["cnt"]

        return {
            "agent_id": self.agent_id,
            "total_active_memories": total,
            "by_type": by_type,
            "total_sessions": sessions,
            "db_path": self.db_path,
        }
