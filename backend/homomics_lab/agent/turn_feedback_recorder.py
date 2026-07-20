"""FeedbackRecorder — record skill execution outcomes into feedback stores.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes). Unlike most turn collaborators this one does not hold a
back-reference to the runner: every dependency (``capability_index``,
``memory_backend``, ``skill_dag``) is constructor-injected because none of
them is reassigned after ``TurnRunner`` construction.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from homomics_lab.config import settings
from homomics_lab.context.feedback_store import FeedbackOutcome
from homomics_lab.knowledge.seed import record_observed_seed_edges
from homomics_lab.skills.capability_index import CapabilityType
from homomics_lab.tasks.models import TaskStatus

if TYPE_CHECKING:
    from homomics_lab.context.memory_backend import MemoryBackend
    from homomics_lab.skills.capability_index import CapabilityIndex
    from homomics_lab.tasks.task_tree import TaskTree

logger = logging.getLogger(__name__)

# Consecutive successful runs required for an observed skill transition to be
# promoted to a CONFIRMED SkillDAG edge (formerly
# HOMOMICS_SEED_OBSERVED_PROMOTION_THRESHOLD; default kept).
SEED_OBSERVED_PROMOTION_THRESHOLD = 3


async def _notify_genesis_crystallized(notification: Dict[str, Any]) -> None:
    """Persist a crystallization notice as an agent message in the session chat.

    The recorder only knows the ``project_id`` of the running turn, so the
    notice is appended to the most recently updated session of that project
    in the shared SessionStore — the same channel the job runner uses for
    result summaries (``jobs/runner.py``). Job-driven turns reload and
    re-save the persisted session when the job finishes
    (``_update_queued_todo_message``), so a notice written mid-job survives
    the final merge and shows up in the conversation history on next load.

    Best-effort: failures are logged here and also degrade to the log line
    in ``SkillGenesis._emit_notification``.
    """
    message = str(notification.get("message") or "").strip()
    if not message:
        return
    project_id = str(notification.get("project_id") or "default")
    skill_id = str(notification.get("skill_id") or "unknown")
    try:
        from homomics_lab.context.session_store import (
            create_session_store_from_settings,
        )
        from homomics_lab.models.common import ChatMessage, MessageType

        store = create_session_store_from_settings()
        await store.init()
        states = await store.list(project_id=project_id)
        if not states:
            logger.info(
                "Skill genesis notification has no session for project %s: %s",
                project_id,
                message,
            )
            return
        state = max(states, key=lambda s: s.updated_at)
        # Deterministic id: a skill is crystallized at most once, and this
        # guard keeps a redelivered notice from duplicating the message.
        message_id = f"msg_genesis_{skill_id}"
        existing_ids = {
            getattr(m, "id", None) for m in state.working_memory.messages
        }
        if message_id in existing_ids:
            return
        state.working_memory.add_message(
            ChatMessage(
                id=message_id,
                type=MessageType.TEXT,
                content=message,
                sender="agent",
            )
        )
        state.updated_at = datetime.now(timezone.utc)
        await store.save(state)
    except Exception:
        logger.warning("Failed to deliver skill genesis notification", exc_info=True)


class FeedbackRecorder:
    """Record skill execution feedback into CapabilityIndex, MemoryBackend and SkillDAG."""

    def __init__(
        self,
        capability_index: Optional["CapabilityIndex"] = None,
        memory_backend: Optional["MemoryBackend"] = None,
        skill_dag: Optional[Any] = None,
        skill_genesis: Optional[Any] = None,
    ):
        self._capability_index = capability_index
        self._memory_backend = memory_backend
        self._skill_dag = skill_dag
        # None means "not injected": lazily built on first use (genesis is
        # always on). False disables the hook.
        self._skill_genesis = skill_genesis
        self._genesis_checked = skill_genesis is not None

    def _get_skill_genesis(self) -> Optional[Any]:
        """Return the SkillGenesis service, lazily building the default one.

        The default build is lazy so turns pay nothing until the first
        CodeAct success is recorded, and no TurnRunner call site needs new
        wiring. Crystallization notifications are routed to the project's
        chat session via ``_notify_genesis_crystallized``.
        """
        if self._genesis_checked:
            return self._skill_genesis or None
        self._genesis_checked = True
        try:
            from homomics_lab.skills.genesis import SkillGenesis

            self._skill_genesis = SkillGenesis.from_settings(
                skill_dag=self._skill_dag,
                notify=_notify_genesis_crystallized,
            )
        except Exception:
            logger.warning("Failed to initialize SkillGenesis", exc_info=True)
            self._skill_genesis = None
        return self._skill_genesis

    async def record_execution_feedback(
        self,
        tree: "TaskTree",
        results: Dict[str, Any],
        project_id: str,
    ) -> None:
        """Record skill execution feedback into CapabilityIndex, MemoryBackend and SkillDAG.

        This is best-effort: failures are logged but never break the turn.
        """
        genesis = self._get_skill_genesis()
        if (
            self._capability_index is None
            and self._memory_backend is None
            and self._skill_dag is None
            and genesis is None
        ):
            return

        for task in tree.tasks:
            if not task.skills_required:
                continue
            skill_id = task.skills_required[0]
            if not skill_id:
                continue

            outcome = (
                FeedbackOutcome.SUCCESS
                if task.status == TaskStatus.COMPLETED
                else FeedbackOutcome.FAILURE
            )

            if self._capability_index is not None:
                try:
                    await self._capability_index.add_feedback(
                        capability_id=skill_id,
                        capability_type=CapabilityType.SKILL,
                        outcome=outcome,
                        project_id=project_id,
                        context={
                            "task_id": task.id,
                            "phase": task.phase,
                            "result_keys": (
                                list(results.get(task.id, {}).keys())
                                if isinstance(results.get(task.id), dict)
                                else []
                            ),
                        },
                    )
                except Exception:
                    logger.warning(
                        "Failed to record capability feedback for %s",
                        skill_id,
                        exc_info=True,
                    )

            if self._memory_backend is not None:
                try:
                    await self._memory_backend.add(
                        text=(
                            f"Executed skill '{skill_id}' for task '{task.name}' "
                            f"with outcome {outcome.value}."
                        ),
                        memory_type="task",
                        metadata={
                            "skill_id": skill_id,
                            "task_id": task.id,
                            "phase": task.phase,
                            "outcome": outcome.value,
                        },
                        importance=0.7 if outcome == FeedbackOutcome.SUCCESS else 0.9,
                        project_id=project_id,
                    )
                except Exception:
                    logger.warning(
                        "Failed to record task memory for %s", skill_id, exc_info=True
                    )

        if genesis is not None:
            await self._record_genesis_candidates(genesis, tree, results, project_id)

        if self._skill_dag is not None:
            # Record adjacent skill transitions so the SkillDAG evolves from
            # real executions instead of only offline mining.
            try:
                from homomics_lab.skills.skill_dag import EdgeType

                prev_skill: Optional[str] = None
                prev_ok = True
                observed_pairs: List[Tuple[str, str]] = []
                for task in tree.tasks:
                    if not task.skills_required:
                        continue
                    skill_id = task.skills_required[0]
                    if not skill_id:
                        continue
                    ok = task.status == TaskStatus.COMPLETED
                    if prev_skill is not None and prev_skill != skill_id:
                        self._skill_dag.record_observation(
                            prev_skill,
                            skill_id,
                            EdgeType.FOLLOWED_BY,
                            prev_ok and ok,
                            context=f"Turn execution in project {project_id}",
                        )
                        if prev_ok and ok:
                            observed_pairs.append((prev_skill, skill_id))
                    prev_skill = skill_id
                    prev_ok = ok

                # Promote high-confidence observed transitions to observed seed
                # edges (G4). This is best-effort and never blocks the turn.
                if observed_pairs:
                    record_observed_seed_edges(
                        self._skill_dag,
                        observed_pairs,
                        threshold=SEED_OBSERVED_PROMOTION_THRESHOLD,
                    )
            except Exception:
                logger.warning("Failed to record SkillDAG observations", exc_info=True)

    async def _record_genesis_candidates(
        self,
        genesis: Any,
        tree: "TaskTree",
        results: Dict[str, Any],
        project_id: str,
    ) -> None:
        """Feed successful CodeAct-generated scripts into SkillGenesis.

        A result carries a ``code`` key only when it came from the CodeAct
        path (``TaskExecutors._normalize_codeact_result``), so curated-skill
        executions are naturally excluded. Best-effort per task.
        """
        for task in tree.tasks:
            if task.status != TaskStatus.COMPLETED:
                continue
            result = results.get(task.id)
            if not isinstance(result, dict):
                continue
            code = result.get("code")
            if not isinstance(code, str) or not code.strip():
                continue

            input_types, paths = self._genesis_task_inputs(task, project_id)
            origin_skill = None
            if result.get("fallback") and task.skills_required:
                # The curated skill failed and CodeAct recovered the task: the
                # crystallized skill becomes its alternative in the SkillDAG.
                origin_skill = task.skills_required[0]
            try:
                await genesis.record_execution(
                    domain=task.phase or "general",
                    action=task.name,
                    input_types=input_types,
                    task_name=task.description or task.name,
                    code=code,
                    success=True,
                    fix_history=result.get("fix_history") or [],
                    project_id=project_id,
                    origin_skill=origin_skill,
                    paths=paths,
                )
            except Exception:
                logger.warning(
                    "SkillGenesis recording failed for task %s", task.id, exc_info=True
                )

    @staticmethod
    def _genesis_task_inputs(
        task: Any, project_id: str
    ) -> Tuple[List[str], Dict[str, str]]:
        """Extract normalized input types and concrete paths from task params.

        Mirrors the context building in ``TaskExecutors._run_codeact_for_task``
        so the paths seen by the generated script are the ones parameterized.
        """
        input_types: List[str] = []
        paths: Dict[str, str] = {}
        working_dir = settings.data_dir / "workspaces" / project_id
        paths["working_dir"] = str(working_dir)
        paths["output_dir"] = str(working_dir / "outputs")
        for key, value in (task.parameters or {}).items():
            candidate: Optional[str] = None
            if isinstance(value, (str, Path)):
                candidate = str(value)
            elif isinstance(value, dict) and isinstance(value.get("path"), str):
                candidate = value["path"]
            if not candidate:
                continue
            p = Path(candidate)
            if p.is_file():
                paths[key] = candidate
                if p.suffix:
                    input_types.append(p.suffix.lower())
            elif p.is_dir():
                paths[key] = candidate
                input_types.append("dir")
        return sorted(set(input_types)), paths
