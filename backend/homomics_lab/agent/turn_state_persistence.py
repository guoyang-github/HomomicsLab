"""TurnStatePersistence — run the turn pipeline with retry and persist state.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes). The collaborator holds a back-reference to the runner for the core
pipeline (``_run_turn_once``), result assembly (``_build_error_result``) and
the persistence/trace services (``memory_manager``,
``project_state_manager``, ``_trace_store``).
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any, Dict, Optional

from homomics_lab.agent.errors import ExecutionError, TurnError
from homomics_lab.config import settings
from homomics_lab.workspace.context import current_workspace
from homomics_lab.workspace.manager import WorkspaceManager

if TYPE_CHECKING:
    from homomics_lab.agent.turn_runner import TurnResult, TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory
    from homomics_lab.plan.store import PlanStore
    from homomics_lab.tasks.task_tree import TaskTree

logger = logging.getLogger(__name__)


class TurnStatePersistence:
    """Run the turn pipeline once (with retries) and persist turn state.

    Persistence (long-term memory, project state, trace nodes) is best-effort
    and runs as a background task so it stays off the HTTP critical path.
    Tasks are chained per ``session_id`` so two turns of the same session can
    never write session state concurrently.
    """

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner
        # session_id -> latest scheduled persistence task (strong refs keep
        # fire-and-forget tasks alive; entries are removed on completion).
        self._background_tasks: Dict[str, asyncio.Task] = {}

    async def drain(self) -> None:
        """Await all currently scheduled background persistence tasks.

        Intended for tests and graceful shutdown; production request handling
        never waits on persistence.
        """
        tasks = list(self._background_tasks.values())
        if not tasks:
            return
        await asyncio.gather(*tasks, return_exceptions=True)

    async def run_with_state(
        self,
        session_id: str,
        user_message: str,
        working_memory: "WorkingMemory",
        project_id: str,
        task_tree: Optional["TaskTree"] = None,
        job_service=None,
        enqueue_skills: bool = False,
        plan_store: Optional["PlanStore"] = None,
        debate_response: Optional[Dict[str, Any]] = None,
        plan_mode: bool = False,
        trace_id: Optional[str] = None,
    ) -> "TurnResult":
        """Run the turn pipeline once and persist state."""
        runner = self._runner
        turn_result: Optional[TurnResult] = None
        workspace_token = None
        if project_id:
            workspace = WorkspaceManager(settings.data_dir, project_id)
            workspace_token = current_workspace.set(workspace)
        try:
            turn_result = await runner._run_turn_once(
                session_id=session_id,
                user_message=user_message,
                working_memory=working_memory,
                project_id=project_id,
                task_tree=task_tree,
                job_service=job_service,
                enqueue_skills=enqueue_skills,
                plan_store=plan_store,
                debate_response=debate_response,
                plan_mode=plan_mode,
            )
        except TurnError as exc:
            if exc.retryable:
                max_retries = 2
                for attempt in range(max_retries):
                    backoff = (2**attempt) * 0.5 + random.uniform(0, 0.25)
                    logger.warning(
                        "Retryable turn error, retrying in %.2fs: %s",
                        backoff,
                        exc,
                    )
                    await asyncio.sleep(backoff)
                    try:
                        turn_result = await runner._run_turn_once(
                            session_id=session_id,
                            user_message=user_message,
                            working_memory=working_memory,
                            project_id=project_id,
                            task_tree=task_tree,
                            job_service=job_service,
                            enqueue_skills=enqueue_skills,
                            plan_store=plan_store,
                            debate_response=debate_response,
                            plan_mode=plan_mode,
                        )
                        break
                    except TurnError as exc2:
                        exc = exc2
                        if not exc2.retryable or attempt == max_retries - 1:
                            turn_result = runner._build_error_result(
                                exc2, working_memory
                            )
                            break
                else:
                    turn_result = runner._build_error_result(exc, working_memory)
            else:
                turn_result = runner._build_error_result(exc, working_memory)
        except Exception as exc:
            # Wrap unexpected errors as ExecutionError for structured reporting.
            turn_result = runner._build_error_result(
                ExecutionError(
                    str(exc), context={"exception_type": type(exc).__name__}
                ),
                working_memory,
            )
        finally:
            if workspace_token is not None:
                current_workspace.reset(workspace_token)

        turn_result = turn_result or runner._build_error_result(
            ExecutionError("Turn produced no result"), working_memory
        )

        # Persist state off the critical path (fire-and-forget, best-effort).
        self._schedule_background_persistence(
            session_id=session_id,
            project_id=project_id,
            user_message=user_message,
            turn_result=turn_result,
            working_memory=working_memory,
            trace_id=trace_id,
        )

        return turn_result

    def _schedule_background_persistence(
        self,
        *,
        session_id: str,
        project_id: str,
        user_message: str,
        turn_result: "TurnResult",
        working_memory: "WorkingMemory",
        trace_id: Optional[str],
    ) -> None:
        """Schedule persistence as a background task chained per session.

        Chaining on the previous task for the same session guarantees
        in-order, non-concurrent writes of session state across turns.
        """
        prev = self._background_tasks.get(session_id)

        async def _chained() -> None:
            if prev is not None:
                try:
                    await prev
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
            try:
                await self._persist_state(
                    session_id=session_id,
                    project_id=project_id,
                    user_message=user_message,
                    turn_result=turn_result,
                    working_memory=working_memory,
                    trace_id=trace_id,
                )
            except Exception:
                logger.warning("Background turn persistence failed", exc_info=True)

        task = asyncio.create_task(_chained())
        self._background_tasks[session_id] = task

        def _cleanup(done: asyncio.Task) -> None:
            # Only pop when this task is still the latest for the session.
            if self._background_tasks.get(session_id) is done:
                self._background_tasks.pop(session_id, None)

        task.add_done_callback(_cleanup)

    async def _persist_state(
        self,
        *,
        session_id: str,
        project_id: str,
        user_message: str,
        turn_result: "TurnResult",
        working_memory: "WorkingMemory",
        trace_id: Optional[str],
    ) -> None:
        """Persist turn state (memory, project state, trace). Best-effort."""
        runner = self._runner

        # 5. Persist turn to long-term memory (best-effort)
        if runner.memory_manager is not None and turn_result is not None:
            try:
                await runner.memory_manager.persist_turn(
                    session_id=session_id,
                    project_id=project_id,
                    user_message=user_message,
                    turn_result=turn_result,
                    working_memory=working_memory,
                    task_tree=turn_result.task_tree,
                )
            except Exception:
                logger.warning(
                    "Failed to persist turn to memory", exc_info=True
                )

        # 6. Update structured project state (best-effort)
        if runner.project_state_manager is not None and turn_result is not None:
            try:
                project_state = runner.project_state_manager.load(project_id)
                project_state = runner.project_state_manager.update_from_turn(
                    project_state,
                    task_tree=getattr(turn_result, "task_tree", None),
                    turn_result=turn_result,
                )
                runner.project_state_manager.save(project_state)
            except Exception:
                logger.warning(
                    "Failed to update project state", exc_info=True
                )

        # Record a lightweight summary node in the execution trace.
        # add_node -> update_node has an ordering dependency, so both stay
        # sequential inside this single background task.
        if runner._trace_store is not None and trace_id is not None:
            try:
                await runner._trace_store.add_node(
                    trace_id=trace_id,
                    node_type="turn",
                    name="chat_turn",
                    metadata={
                        "mode": str(
                            turn_result.mode.value
                            if hasattr(turn_result.mode, "value")
                            else turn_result.mode
                        ),
                        "response_length": len(turn_result.response_text or ""),
                        "has_error": turn_result.error is not None,
                        "job_id": turn_result.job_id,
                        "plan_id": turn_result.plan_id,
                    },
                )
                await runner._trace_store.update_node(
                    trace_id=trace_id,
                    node_id="root",
                    status="completed" if not turn_result.error else "failed",
                    outputs={
                        "response_preview": (turn_result.response_text or "")[:200]
                    },
                )
            except Exception:
                logger.warning("Failed to record turn trace node", exc_info=True)
