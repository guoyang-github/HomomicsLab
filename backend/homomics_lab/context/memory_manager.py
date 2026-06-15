"""Unified facade for session state and long-term memory."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from homomics_lab.context.semantic_memory import SemanticMemory
from homomics_lab.context.session_store import SessionState, SessionStore
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.tasks.task_tree import TaskTree

logger = logging.getLogger(__name__)


class MemoryManager:
    """Coordinates WorkingMemory, SemanticMemory, and CBKB for a session."""

    def __init__(
        self,
        session_store: SessionStore,
        semantic_memory: Optional[SemanticMemory] = None,
        cbkb: Optional[CBKB] = None,
    ) -> None:
        self.session_store = session_store
        self.semantic_memory = semantic_memory
        self.cbkb = cbkb

    async def load_session(
        self,
        session_id: str,
        project_id: str,
    ) -> Tuple[WorkingMemory, Optional[TaskTree]]:
        """Load a session from the store, or create a new one."""
        state = await self.session_store.get(session_id)
        if state is not None:
            return state.working_memory, state.task_tree
        return WorkingMemory(), None

    async def get_project_id(self, session_id: str) -> Optional[str]:
        state = await self.session_store.get(session_id)
        return state.project_id if state else None

    async def enrich_context(
        self,
        project_id: str,
        user_message: str,
        working_memory: WorkingMemory,
    ) -> Dict[str, Any]:
        """Retrieve relevant historical context for the current turn."""
        context: Dict[str, Any] = {"memory_snippets": [], "parameter_preferences": []}

        if self.semantic_memory is None:
            return context

        try:
            query = f"{user_message} project:{project_id}"
            results = await self.semantic_memory.search(query, top_k=5)
            context["memory_snippets"] = [r["text"] for r in results]
        except Exception:
            logger.warning("Semantic memory search failed; continuing without it", exc_info=True)

        if self.cbkb is not None:
            try:
                context["parameter_preferences"] = []
            except Exception:
                logger.warning("CBKB enrichment failed; continuing without it", exc_info=True)

        return context

    async def persist_turn(
        self,
        session_id: str,
        project_id: str,
        user_message: str,
        turn_result: Any,
        working_memory: WorkingMemory,
        task_tree: Optional[TaskTree],
    ) -> None:
        """Persist the current turn and update long-term memory."""
        if turn_result.agent_message is not None:
            working_memory.add_message(turn_result.agent_message)

        await self._save_session(session_id, project_id, working_memory, task_tree)
        await self._write_semantic_memory(
            project_id, user_message, turn_result, working_memory, task_tree
        )

    async def _save_session(
        self,
        session_id: str,
        project_id: str,
        working_memory: WorkingMemory,
        task_tree: Optional[TaskTree],
    ) -> None:
        state = SessionState(
            session_id=session_id,
            project_id=project_id,
            working_memory=working_memory,
            task_tree=task_tree,
            updated_at=datetime.now(timezone.utc),
        )
        try:
            await self.session_store.save(state)
        except Exception:
            logger.exception("Failed to persist session state for %s", session_id)

    async def _write_semantic_memory(
        self,
        project_id: str,
        user_message: str,
        turn_result: Any,
        working_memory: WorkingMemory,
        task_tree: Optional[TaskTree],
    ) -> None:
        if self.semantic_memory is None:
            return

        summary = self._summarize_turn(project_id, user_message, turn_result, task_tree)
        try:
            await self.semantic_memory.add(
                text=summary,
                memory_type="conversation",
                metadata={
                    "project_id": project_id,
                    "mode": str(turn_result.mode) if hasattr(turn_result, "mode") else None,
                },
            )
        except Exception:
            logger.warning("Failed to write semantic memory", exc_info=True)

    @staticmethod
    def _summarize_turn(
        project_id: str,
        user_message: str,
        turn_result: Any,
        task_tree: Optional[TaskTree],
    ) -> str:
        mode = str(turn_result.mode) if hasattr(turn_result, "mode") else "unknown"
        summary_parts = [
            f"Project {project_id}: user asked: '{user_message}'",
            f"Execution mode: {mode}.",
        ]
        if task_tree is not None and task_tree.tasks:
            task_names = ", ".join(t.name for t in task_tree.tasks)
            summary_parts.append(f"Tasks: {task_names}.")
        if hasattr(turn_result, "response_text") and turn_result.response_text:
            summary_parts.append(f"Response: {turn_result.response_text[:200]}")
        return " ".join(summary_parts)
