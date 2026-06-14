"""Background worker that consumes the job queue and executes jobs."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from homomics_lab.hpc.state import ExecutionState
from homomics_lab.jobs.backends.base import PubSubBackend, QueueBackend
from homomics_lab.plan.models import PlanStatus
from homomics_lab.plan.store import PlanStore

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

        try:
            job = await self._repository.get(job_id)
            if job is None:
                logger.error("Job %s not found in repository", job_id)
                return

            # The job may have been cancelled while sitting in the queue.
            if job.status == JobStatus.CANCELLED:
                return

            job.status = JobStatus.RUNNING
            job.updated_at = datetime.now(timezone.utc)
            await self._repository.update(job)
            if job.plan_id:
                await self._update_plan_status(job.plan_id, PlanStatus.EXECUTING)
            self._publish_state(job_id, JobStatus.RUNNING, "Job started")

            progress_callback = self._make_progress_callback(job_id)
            runner = self._runner_factory(progress_callback)

            try:
                if job.mode == JobMode.RESUME_HITL:
                    result = await runner.resume_hitl(
                        session_id=job.session_id,
                        task_id=job.resume_task_id,
                        choice=job.resume_choice,
                        parameters=job.resume_parameters or {},
                        working_memory=job.working_memory,
                        task_tree=job.task_tree,
                    )
                else:
                    result = await runner.execute_tree(
                        tree=job.task_tree,
                        working_memory=job.working_memory,
                        project_id=job.project_id,
                    )

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

                if job.status == JobStatus.AWAITING_HUMAN:
                    self._publish_state(
                        job_id,
                        JobStatus.AWAITING_HUMAN,
                        "Waiting for human input",
                        hitl_checkpoint=result.hitl_checkpoint,
                    )
                else:
                    self._publish_state(job_id, job.status, "Job finished")

            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                job.status = JobStatus.FAILED
                job.error_message = str(exc)
                job.updated_at = datetime.now(timezone.utc)
                await self._repository.update(job)
                if job.plan_id:
                    await self._update_plan_status(job.plan_id, PlanStatus.FAILED)
                self._publish_state(job_id, JobStatus.FAILED, str(exc))
        finally:
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

        return TurnRunner(progress_callback=progress_callback)

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
