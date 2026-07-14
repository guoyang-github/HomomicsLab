"""Background worker that consumes the job queue and executes jobs."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
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

            job.status = JobStatus.RUNNING
            job.updated_at = datetime.now(timezone.utc)
            await self._repository.update(job)
            if job.plan_id:
                await self._update_plan_status(job.plan_id, PlanStatus.EXECUTING)
            self._publish_state(job_id, JobStatus.RUNNING, "Job started")
            await self._update_active_jobs()

            progress_callback = self._make_progress_callback(job_id)
            runner = self._runner_factory(progress_callback, self._skill_executor, job_id=job_id)

            # Start reproducibility tracking for this job.
            repro_engine = self._create_repro_engine(job)

            cognify_handled = False
            try:
                timeout = settings.default_job_timeout_seconds
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
                    workspace.create_git_snapshot("pre-run", job_id)
                    if self._skill_executor is not None and hasattr(self._skill_executor, "set_workspace"):
                        self._skill_executor.set_workspace(workspace)
                    with workspace_context(workspace):
                        result = await asyncio.wait_for(coro, timeout=timeout)
                    workspace.create_git_snapshot("post-run", job_id)

                    # Persist mutated state
                    job.task_tree = result.task_tree
                    job.working_memory = job.working_memory  # TurnRunner mutates in place
                    job.result = self._result_to_dict(result)
                    job.status = self._mode_to_status(result.mode)
                    job.error_message = result.error
                    job.updated_at = datetime.now(timezone.utc)

                    # Update the original TODO_LIST chat message with the final
                    # result so that reloading the session still shows the outcome.
                    await self._update_queued_todo_message(job, result)

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
                        )
                        await trace_store.finish_trace(
                            job_id,
                            "completed" if job.status == JobStatus.COMPLETED else "failed",
                            job.error_message,
                        )

            except asyncio.TimeoutError:
                logger.error("Job %s timed out after %ss", job_id, settings.default_job_timeout_seconds)
                job.status = JobStatus.FAILED
                job.error_message = f"Timeout after {settings.default_job_timeout_seconds}s"
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

    async def _update_queued_todo_message(self, job: Job, result) -> None:
        """Embed the final skill result into the queued TODO_LIST message.

        Mutates both the in-job working memory (for the current process) and the
        persisted session state so that reloading the conversation shows the
        outcome.
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
                return

            tree = getattr(result, "task_tree", None) or job.task_tree
            summary_text, envelopes = self._compose_result_message(
                task_result, tree, job.status
            )
            if job.status == JobStatus.COMPLETED:
                todo_text = "分析已完成，详细结果见下一条消息。"
            else:
                err = str(task_result.get("error", ""))[:120] if isinstance(task_result, dict) else ""
                todo_text = f"执行失败，详细原因见下一条消息。{err}"
            todo_type = {MessageType.TODO_LIST, MessageType.TODO_LIST.value, "todo_list"}

            def _apply_update(messages):
                fallback_msg = None
                updated = False
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
                        if envelopes:
                            content["artifacts"] = envelopes
                        updated = True
                        break
                    # Remember the most recent pending todo as a fallback target.
                    if fallback_msg is None and content.get("status") in (None, "pending", "running"):
                        fallback_msg = msg
                if not updated and fallback_msg is not None:
                    content = fallback_msg.content
                    content["result"] = task_result
                    content["status"] = "completed" if job.status == JobStatus.COMPLETED else "failed"
                    content["text"] = todo_text
                    if envelopes:
                        content["artifacts"] = envelopes
                    updated = True
                return updated

            def _append_result_text(messages):
                related = [e.get("path") for e in envelopes if e.get("path")]
                messages.append(
                    ChatMessage(
                        id=f"msg_{len(messages)}",
                        type=MessageType.TEXT,
                        content=summary_text,
                        sender="agent",
                        related_files=related,
                    )
                )

            # Update the in-memory copy carried by the job.
            in_memory_messages = getattr(job.working_memory, "messages", [])
            if _apply_update(in_memory_messages):
                _append_result_text(in_memory_messages)

            # Persist the update so reloads / other processes see the summary.
            if self._memory_manager is not None and job.session_id:
                try:
                    working_memory, task_tree = await self._memory_manager.load_session(
                        job.session_id, job.project_id or "default"
                    )
                    if _apply_update(working_memory.messages):
                        _append_result_text(working_memory.messages)
                        await self._memory_manager._save_session(
                            job.session_id,
                            job.project_id or "default",
                            working_memory,
                            task_tree,
                        )
                except Exception:
                    logger.warning("Failed to persist TODO summary", exc_info=True)
        except Exception:
            logger.warning("Failed to update queued TODO message", exc_info=True)

    @staticmethod
    def _collect_artifact_envelopes(
        task_result: Any, tree: Any
    ) -> List[Dict[str, Any]]:
        """Harvest frontend-ready artifact envelopes from a skill result/tree.

        Accepts already-built envelopes (dicts with ``path``), plain path strings,
        or ``output_files``/``output_paths`` lists. Re-running ``build_artifact``
        normalizes everything to full ``{kind, mime, name, path, size}`` envelopes
        so the chat can render inline tables/images instead of bare file links.
        """
        from pathlib import Path

        from homomics_lab.artifacts import build_artifact

        raw_paths: List[str] = []

        def harvest(obj: Any) -> None:
            if not isinstance(obj, dict):
                return
            arts = obj.get("artifacts")
            if isinstance(arts, list):
                for a in arts:
                    if isinstance(a, dict) and a.get("path"):
                        raw_paths.append(str(a["path"]))
                    elif isinstance(a, str):
                        raw_paths.append(a)
            for key in ("output_files", "output_paths"):
                val = obj.get(key)
                if isinstance(val, (list, tuple)):
                    raw_paths.extend(str(x) for x in val if x)
                elif isinstance(val, str):
                    raw_paths.append(val)

        harvest(task_result)
        for task in getattr(tree, "tasks", []) or []:
            harvest(getattr(task, "result", None))

        envelopes: List[Dict[str, Any]] = []
        seen: set = set()
        for p in raw_paths:
            if not p or p in seen:
                continue
            seen.add(p)
            env = build_artifact(Path(p))
            if env:
                envelopes.append(env)
        return envelopes

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
    def _compose_result_message(
        cls, task_result: Any, tree: Any, status: JobStatus
    ) -> tuple:
        """Build ``(text, envelopes)`` for the queued TODO message.

        On success with artifacts, the text is the deterministic, sourced
        markdown from :mod:`homomics_lab.result_summary` (inline tables,
        findings, interpretation, next steps). Falls back to the legacy one-line
        summary when nothing richer is available, so the chat is never empty.
        """
        envelopes = cls._collect_artifact_envelopes(task_result, tree)
        text = ""
        is_partial = isinstance(task_result, dict) and task_result.get("partial")
        has_error = isinstance(task_result, dict) and task_result.get("error")
        if (status == JobStatus.COMPLETED or is_partial or has_error) and envelopes:
            try:
                from homomics_lab.result_summary import summarize_artifacts

                text = summarize_artifacts(
                    envelopes,
                    skill_id=cls._derive_skill_id(tree),
                    user_message=cls._derive_user_message(tree),
                ).to_markdown()
                if is_partial:
                    text = (
                        "⚠️ 执行未完全成功，但已生成部分结果，仍可参考：\n\n" + text
                    )
                elif has_error:
                    err = str(task_result.get("error", ""))[:300]
                    text = f"❌ 执行失败：{err}\n\n已生成的部分结果仍可参考：\n\n{text}"
            except Exception:
                logger.debug("rich result summary failed", exc_info=True)
                text = ""
        if not text:
            text = cls._format_result_summary(task_result, status)
        return text, envelopes

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
        output_csv = task_result.get("output_csv")
        if output_csv:
            parts.append("。详细结果已保存到输出文件，可点击下方链接查看。")
        else:
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

    def _make_progress_callback(self, job_id: str) -> Callable[[ExecutionState], None]:
        def callback(state: ExecutionState) -> None:
            state.job_id = job_id
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
        # Surface the first successful task result so clients can render
        # a concise result summary without walking the whole task tree.
        task_result = None
        tree = getattr(result, "task_tree", None)
        if tree and getattr(tree, "tasks", None):
            for task in tree.tasks:
                if getattr(task, "status", None) == "completed" and getattr(task, "result", None):
                    task_result = task.result
                    break
        data["task_result"] = task_result
        return data

    async def _acquire_lock(self, job_id: str) -> bool:
        """Acquire a distributed lock for this job when using Redis."""
        from homomics_lab.config import settings
        from homomics_lab.jobs.backends.redis import RedisQueueBackend

        if not isinstance(self._queue, RedisQueueBackend):
            return True
        acquired = await self._queue.acquire_lock(
            job_id, self._worker_id, ttl=settings.worker_lock_ttl
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
        from homomics_lab.config import settings
        from homomics_lab.jobs.backends.redis import RedisQueueBackend

        if not isinstance(self._queue, RedisQueueBackend):
            await self._shutdown_event.wait()
            return

        while not self._shutdown_event.is_set():
            try:
                await self._queue.heartbeat(self._worker_id, ttl=settings.worker_heartbeat_ttl)
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
    }.get(status, 0.0)
