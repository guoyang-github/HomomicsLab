"""High-level facade for creating and managing background jobs."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from homomics_lab.config import settings
from homomics_lab.context.memory_manager import MemoryManager
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.jobs.backends import create_backends
from homomics_lab.jobs.backends.base import PubSubBackend, QueueBackend
from homomics_lab.metrics import set_active_jobs
from homomics_lab.tasks.task_tree import TaskTree

from .models import Job, JobMode, JobStatus
from .repository import JobRepository
from .runner import BackgroundJobRunner


class JobService:
    """Coordinates job creation, queueing, persistence, and execution."""

    def __init__(
        self,
        queue: Optional[QueueBackend] = None,
        repository: Optional[JobRepository] = None,
        pubsub: Optional[PubSubBackend] = None,
        skill_executor: Optional[Any] = None,
        memory_manager: Optional[MemoryManager] = None,
    ):
        queue_backend, pubsub_backend = create_backends()
        self._queue = queue or queue_backend
        self._repository = repository or JobRepository()
        self._pubsub = pubsub or pubsub_backend
        self._skill_executor = skill_executor
        self._memory_manager = memory_manager
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
        await self._update_active_jobs()
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
        await self._update_active_jobs()
        return job

    async def create_cognify_job(
        self,
        session_id: str,
        project_id: str,
        source_type: str,
        source: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Job:
        job = Job(
            session_id=session_id,
            project_id=project_id,
            status=JobStatus.QUEUED,
            mode=JobMode.COGNIFY,
            result={
                "source_type": source_type,
                "source": source,
                "options": options or {},
            },
        )
        await self._repository.create(job)
        await self._queue.enqueue(job.job_id)
        await self._publish_state(job.job_id, JobStatus.QUEUED, "Cognify job queued")
        await self._update_active_jobs()
        return job

    async def create_checkpoint_resume_job(
        self,
        session_id: str,
        project_id: str,
        checkpoint_payload: Dict[str, Any],
        plan_id: Optional[str] = None,
    ) -> Job:
        job = Job(
            session_id=session_id,
            project_id=project_id,
            status=JobStatus.QUEUED,
            mode=JobMode.CHECKPOINT_RESUME,
            plan_id=plan_id,
        )
        await self._repository.create(job)
        await self._queue.enqueue(job.job_id)
        await self._publish_state(job.job_id, JobStatus.QUEUED, "Checkpoint resume job queued")
        await self._update_active_jobs()
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
        await self._update_active_jobs()
        return job

    async def _update_active_jobs(self) -> None:
        """Update the Prometheus gauge for active (non-terminal) jobs."""
        try:
            jobs = await self._repository.list_all()
            active_statuses = {
                JobStatus.QUEUED.value,
                JobStatus.PENDING.value,
                JobStatus.RUNNING.value,
                JobStatus.AWAITING_HUMAN.value,
            }
            count = sum(1 for job in jobs if job.status.value in active_statuses)
            set_active_jobs(count)
        except Exception:
            pass

    async def start_worker(self) -> None:
        if not settings.worker_mode:
            return
        if self._runner is None:
            self._runner = BackgroundJobRunner(
                queue=self._queue,
                repository=self._repository,
                pubsub=self._pubsub,
                skill_executor=self._skill_executor,
                memory_manager=self._memory_manager,
            )
        await self._recover_queued_jobs()
        self._runner.start()

    async def _recover_queued_jobs(self) -> None:
        """Re-enqueue jobs that were QUEUED when the previous process exited.

        Only safe for single-process/memory backend deployments. With Redis,
        multiple workers may recover concurrently; the runner's distributed
        lock ensures each job is executed by at most one worker.
        """
        try:
            queued = await self._repository.list_by_status(JobStatus.QUEUED.value)
        except Exception:
            return
        for job in queued:
            try:
                await self._queue.enqueue(job.job_id)
                await self._publish_state(job.job_id, JobStatus.QUEUED, "Job recovered after restart")
            except Exception:
                pass

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
