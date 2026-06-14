"""High-level facade for creating and managing background jobs."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from homomics_lab.config import settings
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.jobs.backends import MemoryPubSubBackend, MemoryQueueBackend
from homomics_lab.jobs.backends.base import PubSubBackend, QueueBackend
from homomics_lab.jobs.backends.redis import create_redis_backends
from homomics_lab.tasks.task_tree import TaskTree

from .models import Job, JobMode, JobStatus
from .repository import JobRepository
from .runner import BackgroundJobRunner


def _create_backends():
    """Create queue + pub/sub backends according to configuration."""
    if settings.queue_backend == "redis":
        return create_redis_backends(settings.redis_url)
    return MemoryQueueBackend(), MemoryPubSubBackend()


class JobService:
    """Coordinates job creation, queueing, persistence, and execution."""

    def __init__(
        self,
        queue: Optional[QueueBackend] = None,
        repository: Optional[JobRepository] = None,
        pubsub: Optional[PubSubBackend] = None,
    ):
        self._queue = queue or _create_backends()[0]
        self._repository = repository or JobRepository()
        self._pubsub = pubsub or _create_backends()[1]
        self._runner: Optional[BackgroundJobRunner] = None

    @property
    def queue(self) -> QueueBackend:
        return self._queue

    @property
    def repository(self) -> JobRepository:
        return self._repository

    @property
    def pubsub(self) -> PubSubBackend:
        return self._pubsub

    async def create_job(
        self,
        session_id: str,
        project_id: str,
        working_memory: WorkingMemory,
        task_tree: TaskTree,
        mode: JobMode,
        plan_id: Optional[str] = None,
    ) -> Job:
        job = Job(
            session_id=session_id,
            project_id=project_id,
            status=JobStatus.QUEUED,
            mode=mode,
            task_tree=task_tree,
            working_memory=working_memory,
            plan_id=plan_id,
        )
        await self._repository.create(job)
        await self._queue.enqueue(job.job_id)
        await self._publish_state(job.job_id, JobStatus.QUEUED, "Job queued")
        return job

    async def create_resume_job(
        self,
        session_id: str,
        project_id: str,
        working_memory: WorkingMemory,
        task_tree: TaskTree,
        task_id: str,
        choice: str,
        parameters: Dict[str, Any],
    ) -> Job:
        job = Job(
            session_id=session_id,
            project_id=project_id,
            status=JobStatus.QUEUED,
            mode=JobMode.RESUME_HITL,
            task_tree=task_tree,
            working_memory=working_memory,
            resume_task_id=task_id,
            resume_choice=choice,
            resume_parameters=parameters,
        )
        await self._repository.create(job)
        await self._queue.enqueue(job.job_id)
        await self._publish_state(job.job_id, JobStatus.QUEUED, "Resume job queued")
        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        return await self._repository.get(job_id)

    async def get_latest_job(
        self,
        session_id: str,
        statuses: Optional[list] = None,
    ) -> Optional[Job]:
        return await self._repository.get_latest_by_session(
            session_id,
            statuses=[s.value for s in statuses] if statuses else None,
        )

    async def cancel_job(self, job_id: str) -> Optional[Job]:
        job = await self._repository.get(job_id)
        if job is None or job.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ):
            return job
        job.status = JobStatus.CANCELLED
        job.updated_at = datetime.now(timezone.utc)
        await self._repository.update(job)
        # Best-effort removal from the queue if it is still pending there.
        if hasattr(self._queue, "remove"):
            try:
                await self._queue.remove(job_id)
            except Exception:
                pass
        await self._publish_state(job_id, JobStatus.CANCELLED, "Job cancelled")
        return job

    def start_worker(self) -> None:
        if not settings.worker_mode:
            return
        if self._runner is None:
            self._runner = BackgroundJobRunner(
                queue=self._queue,
                repository=self._repository,
                pubsub=self._pubsub,
            )
        self._runner.start()

    async def stop_worker(self, timeout: float = 10.0) -> None:
        if self._runner is not None:
            await self._runner.stop(timeout=timeout)

    async def close(self) -> None:
        await self.stop_worker()
        await self._queue.close()
        await self._pubsub.close()

    async def _publish_state(
        self, job_id: str, status: JobStatus, message: str
    ) -> None:
        from .runner import _status_to_progress

        state = ExecutionState(
            job_id=job_id,
            status=status.value,
            current_phase=message,
            progress_pct=_status_to_progress(status),
            scheduler_type="agent",
        )
        self._pubsub.publish(job_id, state)
