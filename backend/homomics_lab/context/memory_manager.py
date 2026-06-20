"""Unified facade for session state and long-term memory."""

import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from homomics_lab.context.semantic_memory import SemanticMemory
from homomics_lab.context.session_store import SessionState, SessionStore
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.knowledge.cbkb import CBKB
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
        context: Dict[str, Any] = {
            "memory_snippets": [],
            "recent_experiments": [],
            "recent_sops": [],
            "recent_anomalies": [],
            "parameter_preferences": [],
            "user_preferences": [],
        }

        if self.semantic_memory is not None:
            try:
                results = await self.semantic_memory.search(
                    user_message, top_k=5, project_id=project_id
                )
                context["memory_snippets"] = [r["text"] for r in results]

                # Retrieve explicit user preferences for this project.
                pref_results = await self.semantic_memory.search(
                    "preference",
                    memory_type="preference",
                    top_k=3,
                    project_id=project_id,
                )
                context["user_preferences"] = [r["text"] for r in pref_results]
            except Exception:
                logger.warning("Semantic memory search failed; continuing without it", exc_info=True)

        if self.cbkb is not None:
            try:
                experiments = self.cbkb.list_experiment_nodes_by_project(project_id, limit=5)
                context["recent_experiments"] = [
                    {
                        "bundle_id": n.bundle_id,
                        "summary": n.summary,
                        "skills_used": n.skills_used,
                        "phases": n.phases,
                    }
                    for n in experiments
                ]

                skills_used = {s for n in experiments for s in n.skills_used}
                parameter_preferences: List[Dict[str, Any]] = []
                for skill_id in skills_used:
                    entries = self.cbkb.query_parameter_lore(
                        skill_id=skill_id, project_id=project_id, limit=3
                    )
                    parameter_preferences.extend(
                        {
                            "skill_id": e.skill_id,
                            "param_name": e.param_name,
                            "param_value": e.param_value,
                            "outcome_metric": e.outcome_metric,
                            "outcome_value": e.outcome_value,
                            "context": e.context,
                        }
                        for e in entries
                    )
                context["parameter_preferences"] = parameter_preferences

                sops = self.cbkb.list_sops()[:5]
                context["recent_sops"] = [
                    {"id": s.id, "name": s.name, "category": s.category}
                    for s in sops
                ]

                anomalies = self.cbkb.query_anomalies(project_id=project_id, limit=5)
                context["recent_anomalies"] = [
                    {
                        "phase_type": a.phase_type,
                        "summary": a.summary,
                        "severity": a.severity,
                        "recommendations": a.recommendations,
                    }
                    for a in anomalies
                ]
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
            session_id, project_id, user_message, turn_result, working_memory, task_tree
        )
        await self._remember_preference(project_id, user_message, turn_result)
        await self._maintain_semantic_memory(session_id)

    async def _remember_preference(
        self,
        project_id: str,
        user_message: str,
        turn_result: Any,
    ) -> None:
        """Extract and store explicit user preferences expressed in a turn."""
        if self.semantic_memory is None:
            return

        preference = self._extract_preference(user_message)
        if preference is None:
            return

        # Only remember preferences on successful/direct turns.
        mode = getattr(turn_result, "mode", None)
        if mode is not None and "error" in str(mode).lower():
            return

        try:
            await self.semantic_memory.add(
                text=preference,
                memory_type="preference",
                metadata={"project_id": project_id, "source_message": user_message},
                importance=0.8,
                project_id=project_id,
            )
        except Exception:
            logger.warning("Failed to store preference", exc_info=True)

    async def _maintain_semantic_memory(self, session_id: str) -> None:
        """Run periodic grooming and consolidation on semantic memory."""
        if self.semantic_memory is None:
            return

        async def _await_if_needed(result: Any) -> Any:
            return await result if inspect.isawaitable(result) else result

        try:
            await _await_if_needed(self.semantic_memory.prune_stale_memories())
        except Exception:
            logger.warning("Memory pruning failed", exc_info=True)

        try:
            await _await_if_needed(
                self.semantic_memory.consolidate_conversation_chunks(session_id=session_id)
            )
        except Exception:
            logger.warning("Memory consolidation failed", exc_info=True)

    @staticmethod
    def _extract_preference(user_message: str) -> Optional[str]:
        """Detect explicit preference statements in user message."""
        text = user_message.lower()
        markers = [
            r"(?:always|总是|总|一直)\s+(?:use|用|选择|prefer|喜欢用)\s+(.+?)(?:\.|。|$)",
            r"(?:prefer|喜欢|偏好|倾向于)\s+(?:to use|using|用|使用)?\s*(.+?)(?:\.|。|$)",
            r"(?:用|使用)\s+(.+?)\s*(?:做|来分析|分析|跑|运行)",
            r"结果(?:要|需要|得|应该)(?:有|包含|带|出)(图|图片|可视化|报告|表格)",
        ]
        for pattern in markers:
            match = __import__("re").search(pattern, text)
            if match:
                return f"User preference: {match.group(1).strip()}"
        return None

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
        session_id: str,
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
                    "session_id": session_id,
                    "mode": str(turn_result.mode) if hasattr(turn_result, "mode") else None,
                },
                project_id=project_id,
                session_id=session_id,
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
