"""Background worker that consumes the job queue and executes jobs."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.jobs.backends.base import PubSubBackend, QueueBackend
from homomics_lab.logging_config import set_correlation_id
from homomics_lab.metrics import set_active_jobs
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.observability.trace_store import TraceStore
from homomics_lab.plan.models import PlanStatus
from homomics_lab.plan.store import PlanStore
from homomics_lab.reproducibility.engine import ReproducibilityEngine
from homomics_lab.workspace.context import workspace_context
from homomics_lab.workspace.manager import WorkspaceManager

from .checkpoint import CheckpointRepository
from .models import Job, JobMode, JobStatus
from .repository import JobRepository

logger = logging.getLogger(__name__)

# Job/worker guardrails (formerly HOMOMICS_* config fields; defaults kept).
DEFAULT_JOB_TIMEOUT_SECONDS = 3600.0
WORKER_HEARTBEAT_TTL = 30  # seconds
WORKER_LOCK_TTL = 600  # seconds
# Hypothesis-driven exploration post-processing (always on; the routing gate
# upstream decides whether a job is an exploration run).
EXPLORATION_ENABLED = True


class BackgroundJobRunner:
    """Long-running worker that dequeues jobs and executes them via TurnRunner."""

    def __init__(
        self,
        queue: QueueBackend,
        repository: JobRepository,
        pubsub: PubSubBackend,
        runner_factory: Optional[Callable] = None,
        poll_timeout: float = 1.0,
        worker_id: Optional[str] = None,
        heartbeat_interval: float = 10.0,
        skill_executor: Optional[Any] = None,
        memory_manager: Optional[MemoryManager] = None,
    ):
        self._queue = queue
        self._repository = repository
        self._pubsub = pubsub
        self._skill_executor = skill_executor
        self._memory_manager = memory_manager
        self._runner_factory = runner_factory or self._default_runner_factory
        self._poll_timeout = poll_timeout
        self._worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
        self._heartbeat_interval = heartbeat_interval
        self._shutdown_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self, timeout: float = 10.0) -> None:
        self._shutdown_event.set()
        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self._task is not None and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

    async def _run_loop(self) -> None:
        while not self._shutdown_event.is_set():
            job_id = await self._queue.dequeue(timeout=self._poll_timeout)
            if job_id is None:
                continue
            try:
                await self._execute_job(job_id)
            except Exception:
                logger.exception("Unexpected error executing job %s", job_id)
            finally:
                try:
                    self._queue.task_done()
                except ValueError:
                    pass

    async def _execute_job(self, job_id: str) -> None:
        if not await self._acquire_lock(job_id):
            logger.info("Job %s is already being processed by another worker", job_id)
            return

        # All logs for this job share the same correlation id.
        set_correlation_id(job_id)
        trace_store = TraceStore()
        await trace_store.start_trace(
            trace_id=job_id,
            session_id=None,
            project_id=None,
            root_name=f"job:{job_id}",
        )

        try:
            job = await self._repository.get(job_id)
            if job is None:
                logger.error("Job %s not found in repository", job_id)
                await trace_store.finish_trace(job_id, "failed", "Job not found in repository")
                return

            # Update trace with actual session/project now that the job is loaded.
            trace = await trace_store.get_trace(job_id)
            if trace is not None:
                trace.session_id = job.session_id
                trace.project_id = job.project_id
                await trace_store._save(trace)

            # The job may have been cancelled while sitting in the queue.
            if job.status == JobStatus.CANCELLED:
                await trace_store.finish_trace(job_id, "cancelled")
                return

            # The job may have been suspended for an external event while queued;
            # it will be re-enqueued once the wait condition resolves.
            if job.status == JobStatus.AWAITING_EVENT:
                logger.info("Job %s is awaiting an external event; skipping execution", job_id)
                await trace_store.finish_trace(job_id, "running")
                return

            job.status = JobStatus.RUNNING
            job.updated_at = datetime.now(timezone.utc)
            await self._repository.update(job)
            if job.plan_id:
                await self._update_plan_status(job.plan_id, PlanStatus.EXECUTING)
            self._publish_state(job_id, JobStatus.RUNNING, "Job started")
            await self._update_active_jobs()

            progress_callback = self._make_progress_callback(job_id, session_id=job.session_id)
            runner = self._runner_factory(progress_callback, self._skill_executor, job_id=job_id)

            # Start reproducibility tracking for this job.
            repro_engine = self._create_repro_engine(job)

            cognify_handled = False
            try:
                timeout = DEFAULT_JOB_TIMEOUT_SECONDS
                if job.mode == JobMode.CHECKPOINT_RESUME:
                    cp = CheckpointRepository().get_latest(job_id, status="success")
                    if cp is None:
                        raise RuntimeError(f"No success checkpoint found for job {job_id}")
                    job.working_memory = cp.payload.get("working_memory")
                    job.task_tree = cp.payload.get("task_tree")
                    self._publish_state(job_id, JobStatus.RUNNING, f"Resumed from checkpoint {cp.checkpoint_id}")
                    coro = runner.execute_tree(
                        tree=job.task_tree,
                        working_memory=job.working_memory,
                        project_id=job.project_id,
                        trace_id=job_id,
                    )
                elif job.mode == JobMode.RESUME_HITL:
                    coro = runner.resume_hitl(
                        session_id=job.session_id,
                        task_id=job.resume_task_id,
                        choice=job.resume_choice,
                        parameters=job.resume_parameters or {},
                        working_memory=job.working_memory,
                        task_tree=job.task_tree,
                        project_id=job.project_id,
                    )
                elif job.mode == JobMode.COGNIFY:
                    cognify_result = await self._execute_cognify_job(job)
                    job.result = cognify_result
                    job.status = JobStatus.COMPLETED if not cognify_result.get("error") else JobStatus.FAILED
                    job.error_message = cognify_result.get("error")
                    job.updated_at = datetime.now(timezone.utc)
                    await self._repository.update(job)
                    self._publish_state(job_id, job.status, "Cognify finished")
                    await trace_store.finish_trace(
                        job_id,
                        "completed" if job.status == JobStatus.COMPLETED else "failed",
                        job.error_message,
                    )
                    cognify_handled = True
                else:
                    coro = runner.execute_tree(
                        tree=job.task_tree,
                        working_memory=job.working_memory,
                        project_id=job.project_id,
                        trace_id=job_id,
                        session_id=job.session_id,
                        plan_id=job.plan_id,
                    )

                if not cognify_handled:
                    project_id = job.project_id or "default"
                    workspace = WorkspaceManager(settings.data_dir, project_id)
                    await workspace.create_git_snapshot("pre-run", job_id)
                    if self._skill_executor is not None and hasattr(self._skill_executor, "set_workspace"):
                        self._skill_executor.set_workspace(workspace)
                    with workspace_context(workspace):
                        result = await asyncio.wait_for(coro, timeout=timeout)
                        # Hypothesis-driven exploration post-processing:
                        # critique each verified hypothesis branch, chase
                        # depth-limited follow-ups, and synthesize the
                        # exploration report. Best-effort; never changes the
                        # job outcome.
                        exploration_message = (
                            await self._maybe_run_exploration_postprocess(
                                job, result, runner
                            )
                        )
                    await workspace.create_git_snapshot("post-run", job_id)

                    # Persist mutated state
                    job.task_tree = result.task_tree
                    job.working_memory = job.working_memory  # TurnRunner mutates in place
                    job.result = self._result_to_dict(result)
                    job.status = self._mode_to_status(result.mode)
                    job.error_message = result.error
                    job.updated_at = datetime.now(timezone.utc)

                    # Update the original TODO_LIST chat message with the final
                    # result so that reloading the session still shows the outcome.
                    # Also capture the new result message for real-time broadcast.
                    result_messages = await self._update_queued_todo_message(job, result)
                    if exploration_message is not None:
                        result_messages = list(result_messages or [])
                        result_messages.append(exploration_message)

                    # Update plan status before persisting the job so that callers
                    # observing a completed job also see a completed plan.
                    if job.plan_id:
                        plan_status = PlanStatus.COMPLETED if job.status == JobStatus.COMPLETED else PlanStatus.FAILED
                        if job.status == JobStatus.AWAITING_HUMAN:
                            plan_status = PlanStatus.EXECUTING
                        await self._update_plan_status(job.plan_id, plan_status)

                    await self._repository.update(job)
                    await self._ingest_to_cbkb(job)

                    if job.status == JobStatus.AWAITING_HUMAN:
                        self._publish_state(
                            job_id,
                            JobStatus.AWAITING_HUMAN,
                            "Waiting for human input",
                            hitl_checkpoint=result.hitl_checkpoint,
                        )
                        await trace_store.finish_trace(job_id, "running")
                    else:
                        task_result = job.result.get("task_result") if job.result else None
                        # The task result wrapper contains metadata and a nested
                        # "result" key with the actual skill output.
                        skill_result = (
                            task_result.get("result")
                            if isinstance(task_result, dict) and "result" in task_result
                            else task_result
                        )
                        self._publish_state(
                            job_id,
                            job.status,
                            "Job finished",
                            result=skill_result,
                            logs=["Job finished"],
                            messages=result_messages,
                        )
                        await trace_store.finish_trace(
                            job_id,
                            "completed" if job.status == JobStatus.COMPLETED else "failed",
                            job.error_message,
                        )

            except asyncio.TimeoutError:
                logger.error("Job %s timed out after %ss", job_id, DEFAULT_JOB_TIMEOUT_SECONDS)
                job.status = JobStatus.FAILED
                job.error_message = f"Timeout after {DEFAULT_JOB_TIMEOUT_SECONDS}s"
                job.updated_at = datetime.now(timezone.utc)
                await self._repository.update(job)
                await self._ingest_to_cbkb(job)
                if job.plan_id:
                    await self._update_plan_status(job.plan_id, PlanStatus.FAILED)
                self._publish_state(job_id, JobStatus.FAILED, job.error_message, result=job.result)
                await trace_store.finish_trace(job_id, "failed", job.error_message)
            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                job.status = JobStatus.FAILED
                job.error_message = str(exc)
                job.updated_at = datetime.now(timezone.utc)
                await self._repository.update(job)
                await self._ingest_to_cbkb(job)
                if job.plan_id:
                    await self._update_plan_status(job.plan_id, PlanStatus.FAILED)
                self._publish_state(job_id, JobStatus.FAILED, str(exc), result=job.result)
                await trace_store.finish_trace(job_id, "failed", str(exc))
            finally:
                # Finalize reproducibility bundle regardless of outcome.
                try:
                    cbkb = self._get_cbkb()
                    repro_engine.finalize(cbkb=cbkb, job_id=job_id)
                    logger.info("Reproducibility bundle finalized for job %s", job_id)
                except Exception:
                    logger.exception("Failed to finalize reproducibility bundle for job %s", job_id)
        finally:
            await self._update_active_jobs()
            await self._release_lock(job_id)

    async def _update_queued_todo_message(
        self, job: Job, result
    ) -> Optional[List[Dict[str, Any]]]:
        """Embed the final skill result into the queued TODO_LIST message.

        Mutates both the in-job working memory (for the current process) and the
        persisted session state so that reloading the conversation shows the
        outcome.  Also appends a fresh result message to the conversation and
        returns it so the runner can broadcast it to connected clients in real
        time.
        """
        try:
            task_result = None
            if job.result and isinstance(job.result, dict):
                task_result = job.result.get("task_result")
                if isinstance(task_result, dict) and "result" in task_result:
                    task_result = task_result["result"]
            if not task_result:
                tree = getattr(result, "task_tree", None)
                if tree:
                    for task in getattr(tree, "tasks", []):
                        status = getattr(task, "status", None)
                        if status in ("completed", "failed") and getattr(task, "result", None):
                            task_result = task.result
                            break
            if not task_result:
                return None

            tree = getattr(result, "task_tree", None) or job.task_tree
            summary, envelopes = await self._compose_result_message(
                task_result, tree, job.status
            )
            summary_text = summary.to_markdown()
            # Keep the TODO card concise; the detailed summary goes into a
            # separate chat message so the conversation reads naturally.
            todo_text = self._format_result_summary(task_result, job.status)
            todo_type = {MessageType.TODO_LIST, MessageType.TODO_LIST.value, "todo_list"}
            # Plot images and ready-made Plotly figures are already streamed as
            # dedicated PLOT/PLOT_DATA messages by TurnRunner; keep them out of
            # the TODO card to avoid duplicate inline cards.
            display_envelopes = [
                env for env in envelopes if env.get("kind") not in {"image", "plotly"}
            ]

            def _apply_update(messages):
                fallback_msg = None
                updated_msg = None
                for msg in reversed(messages):
                    msg_type = getattr(msg, "type", None)
                    if isinstance(msg_type, str):
                        msg_type = msg_type.lower()
                    content = getattr(msg, "content", None)
                    if msg_type not in todo_type or not isinstance(content, dict):
                        continue
                    # Exact match first.
                    if content.get("job_id") == job.job_id:
                        content["result"] = task_result
                        content["status"] = "completed" if job.status == JobStatus.COMPLETED else "failed"
                        content["text"] = todo_text
                        if display_envelopes:
                            content["artifacts"] = display_envelopes
                        elif "artifacts" in content:
                            content["artifacts"] = []
                        tasks = content.get("tasks", []) or []
                        for task in tasks:
                            if isinstance(task, dict):
                                task["status"] = content["status"]
                        progress = content.get("progress") or {}
                        if isinstance(progress, dict):
                            total = len(tasks)
                            completed = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "completed")
                            progress["total"] = total
                            progress["pending"] = total - completed
                            progress["running"] = 0
                            progress["completed"] = completed
                            progress["failed"] = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "failed")
                            progress["awaiting_human"] = 0
                            progress["percent"] = int((completed / total) * 100) if total else 0
                        updated_msg = msg
                        break
                    # Remember the most recent pending todo as a fallback target.
                    if fallback_msg is None and content.get("status") in (None, "pending", "running"):
                        fallback_msg = msg
                if updated_msg is None and fallback_msg is not None:
                    content = fallback_msg.content
                    content["result"] = task_result
                    content["status"] = "completed" if job.status == JobStatus.COMPLETED else "failed"
                    content["text"] = todo_text
                    if display_envelopes:
                        content["artifacts"] = display_envelopes
                    elif "artifacts" in content:
                        content["artifacts"] = []
                    tasks = content.get("tasks", []) or []
                    for task in tasks:
                        if isinstance(task, dict):
                            task["status"] = content["status"]
                    progress = content.get("progress") or {}
                    if isinstance(progress, dict):
                        total = len(tasks)
                        completed = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "completed")
                        progress["total"] = total
                        progress["pending"] = total - completed
                        progress["running"] = 0
                        progress["completed"] = completed
                        progress["failed"] = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "failed")
                        progress["awaiting_human"] = 0
                        progress["percent"] = int((completed / total) * 100) if total else 0
                    updated_msg = fallback_msg
                return updated_msg

            # Update the in-memory copy carried by the job.
            in_memory_messages = getattr(job.working_memory, "messages", [])
            updated_in_memory = _apply_update(in_memory_messages)

            # Persist the update so reloads / other processes see the summary.
            updated_persisted = None
            if self._memory_manager is not None and job.session_id:
                try:
                    working_memory, task_tree = await self._memory_manager.load_session(
                        job.session_id, job.project_id or "default"
                    )
                    updated_persisted = _apply_update(working_memory.messages)
                    if updated_persisted is not None:
                        await self._memory_manager._save_session(
                            job.session_id,
                            job.project_id or "default",
                            working_memory,
                            task_tree,
                        )
                except Exception:
                    logger.warning("Failed to persist TODO summary", exc_info=True)

            # Broadcast the updated TODO card (same id as the original) so the
            # frontend replaces it in place instead of appending a duplicate.
            broadcast_messages: List[Dict[str, Any]] = []
            broadcast_msg = updated_persisted or updated_in_memory
            if broadcast_msg is not None:
                broadcast_messages.append(broadcast_msg.model_dump(mode="json"))

            # Append a separate rich summary message to the conversation when
            # the job produced a meaningful result. This keeps the TODO card as
            # a lightweight progress indicator and puts the detailed answer in
            # the chat stream where the user expects it.
            if summary_text and job.status == JobStatus.COMPLETED:
                try:
                    summary_chat = ChatMessage(
                        id=f"msg_result_{job.job_id}",
                        type=MessageType.TEXT,
                        content=summary_text,
                        sender="agent",
                        related_files=[env.get("path") for env in envelopes if env.get("path")],
                    )
                    summary_id = summary_chat.id
                    # Guard against appending the same summary twice when the
                    # in-memory and persisted WorkingMemory share state.
                    in_memory_ids = {getattr(m, "id", None) for m in in_memory_messages}
                    if summary_id not in in_memory_ids:
                        in_memory_messages.append(summary_chat)
                        broadcast_messages.append(summary_chat.model_dump(mode="json"))
                    if self._memory_manager is not None and job.session_id:
                        working_memory, task_tree = await self._memory_manager.load_session(
                            job.session_id, job.project_id or "default"
                        )
                        persisted_ids = {getattr(m, "id", None) for m in working_memory.messages}
                        if summary_id not in persisted_ids:
                            working_memory.messages.append(summary_chat)
                        await self._memory_manager._save_session(
                            job.session_id,
                            job.project_id or "default",
                            working_memory,
                            task_tree,
                        )
                except Exception:
                    logger.warning("Failed to append result summary message", exc_info=True)

            return broadcast_messages
        except Exception:
            logger.warning("Failed to update queued TODO message", exc_info=True)
            return None
        except Exception:
            logger.warning("Failed to update queued TODO message", exc_info=True)
            return None

    async def _maybe_run_exploration_postprocess(
        self, job: Job, result, runner
    ) -> Optional[Dict[str, Any]]:
        """Critique + synthesize for hypothesis-driven exploration jobs.

        When the job's plan carries an exploration blueprint (stored by the
        intent router's exploration branch), each hypothesis branch result is
        critiqued by the ExplorationEngine, depth-limited follow-up hypotheses
        are executed through the same runner (i.e. the existing Orchestrator /
        CodeAct stack), and a Markdown exploration report is appended to the
        conversation. Returns the report message dict for broadcast, or None
        when the job is not an exploration job or post-processing is
        unavailable. Never raises.
        """
        try:
            if not EXPLORATION_ENABLED or not job.plan_id:
                return None
            plan = await PlanStore().get(job.plan_id)
            blueprint_data = None
            if plan is not None:
                blueprint_data = (plan.metadata or {}).get("exploration_blueprint")
            if not blueprint_data:
                return None

            from homomics_lab.agent.exploration import (
                ExplorationBlueprint,
                ExplorationEngine,
            )
            from homomics_lab.context.working_memory import WorkingMemory
            from homomics_lab.llm_client import LLMClient
            from homomics_lab.tasks.task_tree import TaskTree

            llm_client = LLMClient()
            if not llm_client.is_configured():
                return None
            blueprint = ExplorationBlueprint.from_dict(blueprint_data)
            engine = ExplorationEngine(llm_client=llm_client)

            tree = getattr(result, "task_tree", None) or job.task_tree
            task_results: Dict[str, Any] = {}
            for task in getattr(tree, "tasks", []) or []:
                hypothesis_id = (task.parameters or {}).get("exploration_hypothesis_id")
                if hypothesis_id:
                    task_results[hypothesis_id] = task.result

            working_memory = job.working_memory or WorkingMemory()

            async def _execute_follow_up(task_node):
                """Run one follow-up hypothesis task via the existing stack."""
                sub_result = await runner.execute_tree(
                    tree=TaskTree(tasks=[task_node]),
                    working_memory=working_memory,
                    project_id=job.project_id or "default",
                    trace_id=f"{job.job_id}-explore",
                    session_id=job.session_id or "",
                )
                sub_tree = getattr(sub_result, "task_tree", None)
                sub_tasks = getattr(sub_tree, "tasks", []) or []
                return getattr(sub_tasks[0], "result", None) if sub_tasks else None

            await engine.run_blueprint(
                blueprint, task_results=task_results, executor=_execute_follow_up
            )
            report_md = engine.synthesize(
                blueprint.question, blueprint.all_hypotheses()
            )
            report_msg = ChatMessage(
                id=f"msg_exploration_{job.job_id}",
                type=MessageType.TEXT,
                content=report_md,
                sender="agent",
            )

            # Append to the in-job working memory and the persisted session so
            # the report survives reloads, mirroring the summary-message dance.
            in_memory_messages = getattr(working_memory, "messages", [])
            in_memory_ids = {getattr(m, "id", None) for m in in_memory_messages}
            if report_msg.id not in in_memory_ids:
                in_memory_messages.append(report_msg)
            if self._memory_manager is not None and job.session_id:
                try:
                    loaded = await self._memory_manager.load_session(
                        job.session_id, job.project_id or "default"
                    )
                    persisted_memory, task_tree = loaded
                    persisted_ids = {
                        getattr(m, "id", None) for m in persisted_memory.messages
                    }
                    if report_msg.id not in persisted_ids:
                        persisted_memory.messages.append(report_msg)
                    await self._memory_manager._save_session(
                        job.session_id,
                        job.project_id or "default",
                        persisted_memory,
                        task_tree,
                    )
                except Exception:
                    logger.warning(
                        "Failed to persist exploration report", exc_info=True
                    )

            return report_msg.model_dump(mode="json")
        except Exception:
            logger.warning("Exploration post-processing failed", exc_info=True)
            return None

    @staticmethod
    def _collect_artifact_envelopes(
        task_result: Any, tree: Any
    ) -> List[Dict[str, Any]]:
        """Harvest frontend-ready artifact envelopes from a skill result/tree.

        Accepts already-built envelopes (dicts with ``path``), plain path strings,
        or ``output_files``/``output_paths`` lists. Re-running ``build_artifact``
        normalizes everything to full ``{kind, mime, name, path, size}`` envelopes
        so the chat can render inline tables/images instead of bare file links.
        Any extra metadata already present in an artifact dict (e.g. ``report_id``,
        ``summary``, ``url``) is preserved.

        As a fallback, the project's workspace ``outputs/`` directory is scanned
        for recently created files so CodeAct/skills that write there are still
        surfaced in the chat even when they do not explicitly report paths.
        """
        from pathlib import Path

        from homomics_lab.artifacts import build_artifact

        raw_items: List[Dict[str, Any]] = []

        def harvest(obj: Any) -> None:
            if not isinstance(obj, dict):
                return
            arts = obj.get("artifacts")
            if isinstance(arts, list):
                for a in arts:
                    if isinstance(a, dict) and a.get("path"):
                        raw_items.append(dict(a))
                    elif isinstance(a, str):
                        raw_items.append({"path": a})
            for key in ("output_files", "output_paths"):
                val = obj.get(key)
                if isinstance(val, (list, tuple)):
                    raw_items.extend({"path": str(x)} for x in val if x)
                elif isinstance(val, dict):
                    raw_items.extend({"path": str(v)} for v in val.values() if v)
                elif isinstance(val, str):
                    raw_items.append({"path": val})

        harvest(task_result)
        for task in getattr(tree, "tasks", []) or []:
            harvest(getattr(task, "result", None))

        # Fallback: collect recent files from the workspace outputs directory.
        outputs_dir = BackgroundJobRunner._resolve_outputs_dir(tree)
        if outputs_dir is not None and outputs_dir.exists():
            try:
                candidates = [
                    p for p in outputs_dir.rglob("*")
                    if p.is_file() and p.stat().st_size > 0
                ]
                # Prefer recently modified files (last 10 minutes).
                import time
                now = time.time()
                recent = [p for p in candidates if (now - p.stat().st_mtime) < 600]
                for p in recent:
                    raw_items.append({"path": str(p)})
            except Exception:
                pass

        envelopes: List[Dict[str, Any]] = []
        seen: set = set()
        for item in raw_items:
            p = item.get("path")
            if not p or p in seen:
                continue
            seen.add(p)
            env = build_artifact(Path(p))
            if env:
                env.update({k: v for k, v in item.items() if k != "path" and v is not None})
                envelopes.append(env)
        return envelopes

    @staticmethod
    def _resolve_outputs_dir(tree: Any) -> Optional[Path]:
        """Return the workspace outputs directory inferred from task parameters."""
        from pathlib import Path

        for task in getattr(tree, "tasks", []) or []:
            params = getattr(task, "parameters", None) or {}
            if not isinstance(params, dict):
                continue
            project_id = params.get("project_id")
            if project_id:
                return Path(settings.data_dir) / "workspaces" / str(project_id) / "outputs"
            input_file = params.get("input_file") or params.get("file_path")
            if input_file:
                p = Path(input_file)
                # workspace/<project>/data/file -> workspace/<project>/outputs
                if "workspaces" in p.parts:
                    parts = list(p.parts)
                    try:
                        idx = parts.index("workspaces")
                        project_id = parts[idx + 1]
                        return Path(*parts[: idx + 2]) / "outputs"
                    except (ValueError, IndexError):
                        pass
        return None

    @staticmethod
    def _derive_user_message(tree: Any) -> str:
        for task in getattr(tree, "tasks", []) or []:
            params = getattr(task, "parameters", None) or {}
            if isinstance(params, dict):
                request = params.get("user_request")
                if request:
                    return str(request)
        return ""

    @staticmethod
    def _derive_skill_id(tree: Any) -> Optional[str]:
        ids = [
            task.skills_required[0]
            for task in getattr(tree, "tasks", []) or []
            if getattr(task, "skills_required", None)
        ]
        return ids[0] if len(ids) == 1 else None

    @classmethod
    async def _compose_result_message(
        cls, task_result: Any, tree: Any, status: JobStatus
    ) -> tuple:
        """Build ``(ResultSummary, envelopes)`` for the queued TODO message.

        On success with artifacts, returns the deterministic, sourced
        :class:`ResultSummary` from :mod:`homomics_lab.result_summary` (inline
        tables, findings, interpretation, next steps).  When an LLM is configured,
        the interpretation and next steps are enriched with a controlled,
        source-grounded rewrite so the chat reads naturally without hallucinating
        numbers.  Falls back to a legacy one-line summary when nothing richer is
        available, so the chat is never empty.
        """
        from homomics_lab.result_summary import (
            Finding,
            ResultSummary,
            enrich_summary_with_llm,
            summarize_artifacts,
        )

        envelopes = cls._collect_artifact_envelopes(task_result, tree)
        is_partial = isinstance(task_result, dict) and task_result.get("partial")
        has_error = isinstance(task_result, dict) and task_result.get("error")
        if (status == JobStatus.COMPLETED or is_partial or has_error) and envelopes:
            try:
                summary = summarize_artifacts(
                    envelopes,
                    skill_id=cls._derive_skill_id(tree),
                    user_message=cls._derive_user_message(tree),
                )
                if status == JobStatus.COMPLETED and not is_partial and not has_error:
                    try:
                        from homomics_lab.llm_client import LLMClient

                        summary = await enrich_summary_with_llm(
                            summary,
                            user_message=cls._derive_user_message(tree),
                            llm_client=LLMClient(),
                        )
                    except Exception:
                        logger.debug("LLM summary enrichment failed", exc_info=True)
                if is_partial:
                    summary.interpretation.insert(
                        0,
                        Finding(
                            text="⚠️ 执行未完全成功，但已生成部分结果，仍可参考：",
                            sources=[],
                        ),
                    )
                elif has_error:
                    err = str(task_result.get("error", ""))[:300]
                    summary.interpretation.insert(
                        0,
                        Finding(
                            text=f"❌ 执行失败：{err}\n\n已生成的部分结果仍可参考：",
                            sources=[],
                        ),
                    )
                return summary, envelopes
            except Exception:
                logger.debug("rich result summary failed", exc_info=True)
        fallback_summary = ResultSummary(
            skill_id=cls._derive_skill_id(tree),
            interpretation=[],
            sources=[],
        )
        # Return a lightweight summary whose markdown is the legacy one-liner.
        fallback_text = cls._format_result_summary(task_result, status)
        if fallback_text:
            fallback_summary.interpretation.append(
                Finding(text=fallback_text, sources=[])
            )
        return fallback_summary, envelopes

    @staticmethod
    def _format_result_summary(task_result: Dict[str, Any], status: JobStatus) -> str:
        """Build a concise, human-readable summary for the chat message."""
        has_error = isinstance(task_result, dict) and task_result.get("error")
        is_partial = isinstance(task_result, dict) and task_result.get("partial")

        if has_error:
            err = str(task_result.get("error", ""))[:300]
            prefix = "⚠️ 执行未完全成功，但已生成部分结果。" if is_partial else "❌ 执行失败："
            return f"{prefix}{err}"

        if status != JobStatus.COMPLETED:
            if is_partial:
                return "执行未完全成功，但已生成部分结果（见下方文件/表格）。"
            return "执行结束，结果概要如下。"
        if not isinstance(task_result, dict):
            return "分析已完成。"
        if is_partial:
            return "⚠️ 执行未完全成功，但已生成部分结果（见下方文件/表格）。"

        # Prefer an explicit summary/text payload when the skill provides one.
        explicit_summary = (
            task_result.get("summary")
            or task_result.get("text")
            or (task_result.get("final_output") or {}).get("summary")
            or (task_result.get("final_output") or {}).get("text")
        )
        if isinstance(explicit_summary, str) and explicit_summary.strip():
            return explicit_summary.strip()[:1200]

        parts = ["分析已完成"]
        cells = task_result.get("cells")
        genes = task_result.get("genes")
        if cells is not None and genes is not None:
            parts.append(f"：共 {cells} 个细胞、{genes} 个基因")
        model = task_result.get("model")
        if model:
            parts.append(f"，使用模型 {model}")
        comparison = task_result.get("comparison")
        if isinstance(comparison, dict):
            ari = comparison.get("adjusted_rand_index")
            acc = comparison.get("accuracy")
            if ari is not None:
                parts.append(f"；与现有标签的 Adjusted Rand Index 为 {ari:.3f}")
            elif acc is not None:
                parts.append(f"；与现有标签的准确率为 {acc:.3f}")

        # Generic artifact/output file detection.
        outputs: List[str] = []
        for key in ("artifacts", "output_files", "output_paths", "output_csv"):
            val = task_result.get(key)
            if isinstance(val, list):
                outputs.extend(str(v) for v in val if v)
            elif isinstance(val, str) and val:
                outputs.append(val)
        if outputs:
            names = [Path(o).name or o for o in outputs[:5]]
            suffix = "等" if len(outputs) > 5 else ""
            parts.append(f"，已生成 {len(outputs)} 个结果文件：{', '.join(names)}{suffix}")
        elif task_result.get("output_csv"):
            parts.append("，详细结果已保存到输出文件，可点击下方链接查看。")
        parts.append("。")
        return "".join(parts)

    def _publish_state(
        self,
        job_id: str,
        status: JobStatus,
        message: str,
        hitl_checkpoint: Optional[dict] = None,
        result: Optional[Dict[str, Any]] = None,
        logs: Optional[list] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        state = ExecutionState(
            job_id=job_id,
            status=status.value,
            current_phase=message,
            progress_pct=_status_to_progress(status),
            scheduler_type="agent",
            error_message=message if status == JobStatus.FAILED else None,
            result=result,
            logs=logs or [],
            messages=messages,
        )
        if hitl_checkpoint:
            state.error_message = None  # not an error
            state.current_phase = f"awaiting_human:{hitl_checkpoint.get('task_id')}"
        self._pubsub.publish(job_id, state)

    async def _update_active_jobs(self) -> None:
        """Refresh the active jobs gauge from the repository."""
        active_statuses = {
            JobStatus.QUEUED.value,
            JobStatus.PENDING.value,
            JobStatus.RUNNING.value,
            JobStatus.AWAITING_HUMAN.value,
            JobStatus.AWAITING_EVENT.value,
        }
        try:
            jobs = await self._repository.list_all()
            count = sum(1 for job in jobs if job.status.value in active_statuses)
            set_active_jobs(count)
        except Exception:
            pass

    @staticmethod
    async def _update_plan_status(plan_id: Optional[str], status: str) -> None:
        if not plan_id:
            return
        try:
            await PlanStore().update_status(plan_id, status)
            logger.info("Updated plan %s status to %s", plan_id, status)
        except Exception:
            logger.exception("Failed to update plan status for %s", plan_id)

    def _make_progress_callback(
        self, job_id: str, session_id: Optional[str] = None
    ) -> Callable[[ExecutionState], None]:
        def callback(state: ExecutionState) -> None:
            state.job_id = job_id
            if session_id and state.extra is not None:
                # Workflow DAG events carry session_id as a top-level payload
                # key (see the {"type": "progress", "event": ...} contract).
                state.extra.setdefault("session_id", session_id)
            self._pubsub.publish(job_id, state)

        return callback

    @staticmethod
    def _default_runner_factory(
        progress_callback: Callable[[ExecutionState], None],
        skill_executor: Optional[Any] = None,
        job_id: Optional[str] = None,
    ):
        # Local import to avoid a circular dependency between jobs.runner
        # and agent.turn_runner at module load time.
        from homomics_lab.agent.plan.template_store import AnalysisTemplateStore
        from homomics_lab.agent.turn_runner import TurnRunner
        from homomics_lab.knowledge.cbkb import CBKB
        from homomics_lab.skills.registry import get_default_registry
        from homomics_lab.skills.skill_dag import SkillDAG
        from homomics_lab.workflow.execution_service import WorkflowExecutionService

        cbkb = CBKB(settings.data_dir)
        analysis_template_store = AnalysisTemplateStore(settings.data_dir)
        # Wire the job-level progress publisher into the shared skill executor
        # so agentic skills stream live state updates to the frontend.
        if skill_executor is not None:
            skill_executor.set_progress_callback(progress_callback)
            skill_executor.set_parent_job_id(job_id)

        workflow_service = WorkflowExecutionService(
            progress_callback=progress_callback,
            skill_registry=skill_executor.registry if skill_executor is not None else None,
            tool_registry=skill_executor.tool_registry if skill_executor is not None else None,
            llm_client=skill_executor.llm_client if skill_executor is not None else None,
        )
        # Share the same persisted SkillDAG the API process uses, so
        # observations recorded during background jobs evolve the same graph.
        try:
            skill_dag = SkillDAG(
                registry=get_default_registry(),
                db_path=settings.data_dir / "skill_dag.db",
            )
        except Exception:
            logger.warning("Failed to init SkillDAG for job runner", exc_info=True)
            skill_dag = None
        return TurnRunner(
            progress_callback=progress_callback,
            cbkb=cbkb,
            analysis_template_store=analysis_template_store,
            workflow_execution_service=workflow_service,
            skill_executor=skill_executor,
            skill_dag=skill_dag,
        )

    @staticmethod
    def _create_repro_engine(job: Job) -> ReproducibilityEngine:
        """Create a ReproducibilityEngine for the job's project."""
        project_id = job.project_id or "default"
        workspace = WorkspaceManager(base_dir=settings.data_dir, project_id=project_id)
        repro_engine = ReproducibilityEngine(workspace)
        repro_engine.start_analysis(project_id=project_id)
        if job.task_tree is not None:
            task_tree_dict = {
                "tasks": [t.model_dump(mode="json") for t in job.task_tree.tasks]
            }
            repro_engine.record_plan(
                task_tree=task_tree_dict,
                plan_context={"job_id": job.job_id, "mode": job.mode.value},
            )
        return repro_engine

    @staticmethod
    def _get_cbkb():
        """Get the CBKB instance for reproducibility indexing."""
        from homomics_lab.knowledge.cbkb import CBKB

        return CBKB(settings.data_dir)

    @staticmethod
    def _mode_to_status(mode) -> JobStatus:
        from homomics_lab.agent.turn_runner import ExecutionMode

        mapping = {
            ExecutionMode.DIRECT_RESPONSE: JobStatus.COMPLETED,
            ExecutionMode.SINGLE_STEP: JobStatus.COMPLETED,
            ExecutionMode.WORKFLOW: JobStatus.COMPLETED,
            ExecutionMode.AWAITING_HITL: JobStatus.AWAITING_HUMAN,
            ExecutionMode.AWAITING_DEBATE: JobStatus.AWAITING_HUMAN,
            ExecutionMode.RESUME_HITL: JobStatus.COMPLETED,
            ExecutionMode.ERROR: JobStatus.FAILED,
        }
        return mapping.get(mode, JobStatus.COMPLETED)

    @staticmethod
    def _result_to_dict(result) -> dict:
        data = {
            "mode": str(result.mode),
            "response_text": result.response_text,
            "progress": result.progress,
            "hitl_task_id": result.hitl_task_id,
            "error": result.error,
        }
        # Surface the best successful task result so clients can render a concise
        # summary without walking the whole task tree. Prefer the last completed
        # task (usually the deliverable step) and, among completed tasks, the one
        # with the richest final_output (output files + non-empty summary/metrics).
        task_result = None
        tree = getattr(result, "task_tree", None)
        if tree and getattr(tree, "tasks", None):
            candidates = [
                task
                for task in tree.tasks
                if getattr(task, "status", None) == "completed" and getattr(task, "result", None)
            ]

            def _result_score(task):
                res = task.result
                if not isinstance(res, dict):
                    return 0
                inner = res.get("result") or res
                if not isinstance(inner, dict):
                    return 0
                final_output = inner.get("final_output") or {}
                score = 0
                if final_output.get("summary"):
                    score += 10
                if final_output.get("metrics"):
                    score += 10
                score += len(final_output.get("output_files", [])) * 2
                score += len(inner.get("output_files", [])) * 2
                score += len(inner.get("artifacts", [])) * 2
                return score

            if candidates:
                # Prefer the last completed task unless an earlier one has a much
                # richer final_output (score >= 2x).
                last = candidates[-1]
                best = max(candidates, key=_result_score)
                if best is last or _result_score(best) >= _result_score(last) * 2:
                    task_result = best.result
                else:
                    task_result = last.result
        data["task_result"] = task_result
        return data

    async def _acquire_lock(self, job_id: str) -> bool:
        """Acquire a distributed lock for this job when using Redis."""
        from homomics_lab.jobs.backends.redis import RedisQueueBackend

        if not isinstance(self._queue, RedisQueueBackend):
            return True
        acquired = await self._queue.acquire_lock(
            job_id, self._worker_id, ttl=WORKER_LOCK_TTL
        )
        return bool(acquired)

    async def _release_lock(self, job_id: str) -> None:
        """Release the distributed lock for this job when using Redis."""
        from homomics_lab.jobs.backends.redis import RedisQueueBackend

        if isinstance(self._queue, RedisQueueBackend):
            await self._queue.release_lock(job_id, self._worker_id)

    async def _execute_cognify_job(self, job: Job) -> Dict[str, Any]:
        """Run a knowledge ingestion (cognify) job in the background."""
        from homomics_lab.knowledge.ingestion import KnowledgeIndex
        from homomics_lab.llm_client import LLMClient

        payload = job.result or {}
        source_type = payload.get("source_type", "text")
        source = payload.get("source", "")

        try:
            knowledge_index = KnowledgeIndex(
                settings=settings,
                llm_client=LLMClient(),
            )
            if source_type == "file":
                from pathlib import Path
                path = Path(source)
                if not path.is_absolute():
                    path = (settings.data_dir / "raw" / job.project_id / source).resolve()
                result = await knowledge_index.ingest_file(path, project_id=job.project_id)
            elif source_type == "url":
                result = await knowledge_index.ingest_url(source, project_id=job.project_id)
            else:
                result = await knowledge_index.ingest_text(source, project_id=job.project_id)
            await knowledge_index.close()
            return {
                "document_id": result.document_id,
                "chunk_count": len(result.chunk_ids),
                "entity_count": len(result.entity_names),
                "relation_count": result.relation_count,
                "memory_id": result.memory_id,
                "data_source_id": result.data_source_id,
                "already_processed": result.already_processed,
            }
        except Exception as exc:
            logger.exception("Cognify job %s failed", job.job_id)
            return {"error": str(exc)}

    async def _ingest_to_cbkb(self, job: Job) -> None:
        """Archive the completed job outcome into CBKB for self-evolution."""
        if job.task_tree is None:
            return
        try:
            from homomics_lab.evolution.ingestion import CBKBIngestionService
            from homomics_lab.knowledge.cbkb import CBKB

            cbkb = CBKB(settings.data_dir)
            ingestion = CBKBIngestionService(cbkb)
            duration = None
            if job.updated_at and job.created_at:
                updated = (
                    job.updated_at.replace(tzinfo=timezone.utc)
                    if job.updated_at.tzinfo is None
                    else job.updated_at
                )
                created = (
                    job.created_at.replace(tzinfo=timezone.utc)
                    if job.created_at.tzinfo is None
                    else job.created_at
                )
                duration = (updated - created).total_seconds()
            ingestion.ingest_workflow(
                project_id=job.project_id,
                task_tree=job.task_tree,
                success=job.status == JobStatus.COMPLETED,
                duration_seconds=duration,
            )
        except Exception:
            logger.exception("CBKB ingestion failed for job %s", job.job_id)

    async def _heartbeat_loop(self) -> None:
        """Periodically refresh this worker's liveness key when using Redis."""
        from homomics_lab.jobs.backends.redis import RedisQueueBackend

        if not isinstance(self._queue, RedisQueueBackend):
            await self._shutdown_event.wait()
            return

        while not self._shutdown_event.is_set():
            try:
                await self._queue.heartbeat(self._worker_id, ttl=WORKER_HEARTBEAT_TTL)
            except Exception:
                logger.exception("Worker heartbeat failed")
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._heartbeat_interval,
                )
            except asyncio.TimeoutError:
                continue


def _status_to_progress(status: JobStatus) -> float:
    return {
        JobStatus.QUEUED: 0.0,
        JobStatus.PENDING: 0.0,
        JobStatus.RUNNING: 50.0,
        JobStatus.COMPLETED: 100.0,
        JobStatus.FAILED: 0.0,
        JobStatus.CANCELLED: 0.0,
        JobStatus.AWAITING_HUMAN: 50.0,
        JobStatus.AWAITING_EVENT: 50.0,
    }.get(status, 0.0)
