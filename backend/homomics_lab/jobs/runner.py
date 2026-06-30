"""Background worker that consumes the job queue and executes jobs."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from homomics_lab.config import settings
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.jobs.backends.base import PubSubBackend, QueueBackend
from homomics_lab.logging_config import set_correlation_id
from homomics_lab.metrics import set_active_jobs
from homomics_lab.observability.trace_store import TraceStore
from homomics_lab.plan.models import PlanStatus
from homomics_lab.plan.store import PlanStore
from homomics_lab.reproducibility.engine import ReproducibilityEngine
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
    ):
        self._queue = queue
        self._repository = repository
        self._pubsub = pubsub
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
            runner = self._runner_factory(progress_callback)

            # Start reproducibility tracking for this job.
            repro_engine = self._create_repro_engine(job)

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
                    )
                else:
                    coro = runner.execute_tree(
                        tree=job.task_tree,
                        working_memory=job.working_memory,
                        project_id=job.project_id,
                        trace_id=job_id,
                    )
                result = await asyncio.wait_for(coro, timeout=timeout)

                # Persist mutated state
                job.task_tree = result.task_tree
                job.working_memory = job.working_memory  # TurnRunner mutates in place
                job.result = self._result_to_dict(result)
                job.status = self._mode_to_status(result.mode)
                job.error_message = result.error
                job.updated_at = datetime.now(timezone.utc)

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
                    self._publish_state(job_id, job.status, "Job finished")
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
                self._publish_state(job_id, JobStatus.FAILED, job.error_message)
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
                self._publish_state(job_id, JobStatus.FAILED, str(exc))
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

    def _publish_state(
        self,
        job_id: str,
        status: JobStatus,
        message: str,
        hitl_checkpoint: Optional[dict] = None,
    ) -> None:
        state = ExecutionState(
            job_id=job_id,
            status=status.value,
            current_phase=message,
            progress_pct=_status_to_progress(status),
            scheduler_type="agent",
            error_message=message if status == JobStatus.FAILED else None,
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
        progress_callback: Callable[[ExecutionState], None]
    ):
        # Local import to avoid a circular dependency between jobs.runner
        # and agent.turn_runner at module load time.
        from homomics_lab.agent.turn_runner import TurnRunner
        from homomics_lab.knowledge.cbkb import CBKB

        cbkb = CBKB(settings.data_dir)
        return TurnRunner(progress_callback=progress_callback, cbkb=cbkb)

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
        return {
            "mode": str(result.mode),
            "response_text": result.response_text,
            "progress": result.progress,
            "hitl_task_id": result.hitl_task_id,
            "error": result.error,
        }

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
