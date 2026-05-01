"""
TotalReclaw OpenClaw Integration
Drop-in persistent memory for OpenClaw agents. Add 2-3 lines, get full
session memory with retrieval, capture, and structured reflection.

Usage:
    from totalreclaw.openclaw import TotalReclawPlugin

    with TotalReclawPlugin("my-agent", llm_call=my_llm) as memory:
        prompt = memory.get_system_prompt("You are a helpful assistant.")
        # ... agent runs ...
        memory.capture("api_call_success", "Created Stripe customer")
"""

import logging
import time
from typing import Callable, Optional

from .core import Memory, MemoryStore
from .retrieval import retrieve_memories
from .reflection import (
    build_reflection_prompt,
    parse_reflection,
    store_reflection,
    fallback_store_summary,
)
from .capture import capture_event, capture_user_message
from .injection import build_system_prompt_with_memory
from .config import DEFAULT_TOKEN_BUDGET, DEFAULT_DB_PATH

logger = logging.getLogger("totalreclaw")

# Max characters of transcript to store as fallback summary
_FALLBACK_SUMMARY_LIMIT = 500


class TotalReclawPlugin:
    """OpenClaw integration plugin for persistent agent memory.

    Manages the full memory lifecycle: retrieval at session start,
    event capture during the session, and structured reflection at
    session end.

    Args:
        agent_id: Unique identifier for this agent. Memories are scoped
            to this ID.
        db_path: Path to the SQLite database file.
        llm_call: Optional callable for structured reflection. Signature:
            ``(messages: list[dict]) -> str``. If not provided, reflection
            falls back to storing a truncated transcript summary.
        token_budget: Maximum tokens of memory to inject into context.
        current_goal: Optional goal tag for retrieval and capture tagging.
    """

    def __init__(
        self,
        agent_id: str,
        db_path: str = DEFAULT_DB_PATH,
        llm_call: Optional[Callable[[list[dict]], str]] = None,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        current_goal: Optional[str] = None,
    ) -> None:
        self.agent_id = agent_id
        self.db_path = db_path
        self.llm_call = llm_call
        self.token_budget = token_budget
        self.current_goal = current_goal

        self._store: Optional[MemoryStore] = None
        self._memories: list[Memory] = []
        self._transcript: list[str] = []
        self._session_active: bool = False
        self._session_start_time: Optional[float] = None

    # ── Properties ───────────────────────────────────────────────────

    @property
    def store(self) -> Optional[MemoryStore]:
        """The underlying MemoryStore, or None if no session is active."""
        return self._store

    @property
    def session_active(self) -> bool:
        """Whether a session is currently in progress."""
        return self._session_active

    # ── Lifecycle ────────────────────────────────────────────────────

    def start_session(
        self,
        current_goal: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> list[Memory]:
        """Begin a new memory session.

        Initializes the memory store, starts a new session, and retrieves
        relevant memories from previous sessions.

        If a session is already active, it is ended first (auto-flush).

        Args:
            current_goal: Override the goal set at init time.
            session_id: Optional explicit session ID. Auto-generated
                if not provided.

        Returns:
            List of retrieved Memory objects for this session.
        """
        try:
            # Auto-close previous session if still active
            if self._session_active:
                self.end_session()

            if current_goal is not None:
                self.current_goal = current_goal

            self._store = MemoryStore(
                agent_id=self.agent_id,
                db_path=self.db_path,
                session_id=session_id,
            )
            self._memories = retrieve_memories(
                self._store,
                current_goal=self.current_goal,
                token_budget=self.token_budget,
            )
        except Exception:
            logger.exception("TotalReclaw: error during start_session")
            self._memories = []
            if self._store is None:
                # Store creation failed — create a bare one so capture
                # calls don't need to check for None everywhere
                try:
                    self._store = MemoryStore(
                        agent_id=self.agent_id,
                        db_path=self.db_path,
                        session_id=session_id,
                    )
                except Exception:
                    logger.exception("TotalReclaw: store creation failed")

        self._transcript = []
        self._session_active = True
        self._session_start_time = time.time()
        return list(self._memories)

    def end_session(
        self,
        transcript_override: Optional[str] = None,
        agent_context: Optional[str] = None,
    ) -> dict:
        """End the current session and run reflection.

        If an ``llm_call`` was provided at init, runs structured reflection.
        Otherwise, or on failure, falls back to storing a basic summary.

        Args:
            transcript_override: Use this transcript instead of the
                internally accumulated one.
            agent_context: Additional context for the reflection prompt.

        Returns:
            Dict with keys: ``session_id``, ``duration_seconds``,
            ``memories_created``, ``reflection_status``
            (``"full"`` | ``"fallback"`` | ``"skipped"`` | ``"error"``),
            and ``memory_ids``.
        """
        duration = (
            time.time() - self._session_start_time
            if self._session_start_time is not None
            else 0.0
        )
        session_id = self._store.session_id if self._store else ""

        result: dict = {
            "session_id": session_id,
            "duration_seconds": round(duration, 2),
            "memories_created": 0,
            "reflection_status": "skipped",
            "memory_ids": [],
        }

        if not self._session_active:
            return result

        self._session_active = False

        try:
            transcript = transcript_override or "\n".join(self._transcript)

            if not transcript.strip() or self._store is None:
                return result

            memory_ids: list[str] = []

            # Try structured reflection via LLM
            if self.llm_call is not None:
                try:
                    messages = build_reflection_prompt(
                        transcript, agent_context=agent_context
                    )
                    raw_response = self.llm_call(messages)
                    parsed = parse_reflection(raw_response)
                    if parsed is not None:
                        memory_ids = store_reflection(self._store, parsed)
                        result["reflection_status"] = "full"
                        result["memories_created"] = len(memory_ids)
                        result["memory_ids"] = memory_ids
                        return result
                except Exception:
                    logger.exception(
                        "TotalReclaw: LLM reflection failed, using fallback"
                    )

            # Fallback: store truncated transcript as summary
            summary = transcript[:_FALLBACK_SUMMARY_LIMIT]
            mid = fallback_store_summary(
                self._store, summary, goal_tag=self.current_goal
            )
            result["reflection_status"] = "fallback"
            result["memories_created"] = 1
            result["memory_ids"] = [mid]

        except Exception:
            logger.exception("TotalReclaw: error during end_session")
            result["reflection_status"] = "error"

        return result

    # ── Capture ──────────────────────────────────────────────────────

    def capture(
        self,
        event_type: str,
        content: str,
        goal_tag: Optional[str] = None,
        importance: Optional[int] = None,
    ) -> Optional[str]:
        """Capture an agent event as a potential memory.

        Events are filtered by type — read-only operations are skipped
        automatically. Also appends the event to the session transcript.

        Args:
            event_type: Event type (e.g. ``"api_call_success"``).
            content: Human-readable description of what happened.
            goal_tag: Override goal tag for this event.
            importance: Override importance (1-10).

        Returns:
            Memory ID if captured, None if filtered or on error.
        """
        if not self._session_active or self._store is None:
            logger.warning(
                "TotalReclaw: capture() called with no active session"
            )
            return None

        try:
            effective_goal = goal_tag or self.current_goal
            self._transcript.append(f"[{event_type}] {content}")
            return capture_event(
                self._store,
                event_type,
                content,
                goal_tag=effective_goal,
                importance_override=importance,
            )
        except Exception:
            logger.exception("TotalReclaw: error during capture")
            return None

    def capture_message(
        self,
        message: str,
        goal_tag: Optional[str] = None,
    ) -> Optional[str]:
        """Process a user message for potential directive capture.

        Analyzes the message for directive signals (e.g. "always...",
        "never...") and stores matches as high-priority directives.
        Also appends the message to the session transcript.

        Args:
            message: The user's message text.
            goal_tag: Override goal tag.

        Returns:
            Memory ID if a directive was captured, None otherwise.
        """
        if not self._session_active or self._store is None:
            logger.warning(
                "TotalReclaw: capture_message() called with no active session"
            )
            return None

        try:
            self._transcript.append(f"[user] {message}")
            return capture_user_message(
                self._store,
                message,
                goal_tag=goal_tag or self.current_goal,
            )
        except Exception:
            logger.exception("TotalReclaw: error during capture_message")
            return None

    # ── Prompt ───────────────────────────────────────────────────────

    def get_system_prompt(self, base_prompt: str) -> str:
        """Build a system prompt with injected memory context.

        Combines the base prompt with retrieved memories from previous
        sessions. Call after ``start_session()``.

        Args:
            base_prompt: The agent's original system prompt.

        Returns:
            The augmented system prompt. Returns ``base_prompt`` unchanged
            on error.
        """
        try:
            return build_system_prompt_with_memory(base_prompt, self._memories)
        except Exception:
            logger.exception("TotalReclaw: error building system prompt")
            return base_prompt

    # ── Goal ─────────────────────────────────────────────────────────

    def set_goal(self, goal: str) -> None:
        """Update the current goal mid-session.

        Affects retrieval filtering on next session start and capture
        tagging for subsequent events.

        Args:
            goal: The new goal tag string.
        """
        self.current_goal = goal

    # ── Context Manager ──────────────────────────────────────────────

    def __enter__(self) -> "TotalReclawPlugin":
        """Start a session on context manager entry."""
        self.start_session()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> bool:
        """End session on context manager exit. Never suppresses exceptions."""
        try:
            self.end_session()
        except Exception:
            logger.exception("TotalReclaw: error during session cleanup")
        return False
