"""Integration tests for the background job worker."""

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from homomics_lab.agent.turn_runner import ExecutionMode
from homomics_lab.config import settings
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.jobs import Job, JobMode, JobRepository, JobStatus
from homomics_lab.jobs.backends import MemoryPubSubBackend, MemoryQueueBackend
from homomics_lab.jobs.runner import BackgroundJobRunner
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


class _FakeTurnResult:
    """Minimal stand-in for ``TurnResult`` returned by ``execute_tree``."""

    def __init__(
        self,
        mode: ExecutionMode,
        response_text: str,
        task_tree: Optional[TaskTree] = None,
        progress: Optional[Dict[str, Any]] = None,
        hitl_task_id: Optional[str] = None,
        hitl_checkpoint: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.mode = mode
        self.response_text = response_text
        self.task_tree = task_tree
        self.progress = progress
        self.hitl_task_id = hitl_task_id
        self.hitl_checkpoint = hitl_checkpoint
        self.error = error


class _FakeRunner:
    """Deterministic runner that returns a completed result."""

    def __init__(self, progress_callback: Any = None):
        self._progress_callback = progress_callback

    async def execute_tree(
        self,
        tree: TaskTree,
        working_memory: WorkingMemory,
        project_id: str,
        trace_id: str,
        session_id: Optional[str] = None,
        plan_id: Optional[str] = None,
    ) -> _FakeTurnResult:
        if self._progress_callback:
            self._progress_callback(
                ExecutionState(
                    job_id=trace_id,
                    status="running",
                    current_phase="fake_step",
                    progress_pct=25.0,
                    scheduler_type="agent",
                )
            )
        # Yield control so the worker loop stays responsive.
        await asyncio.sleep(0)
        return _FakeTurnResult(
            mode=ExecutionMode.DIRECT_RESPONSE,
            response_text="done",
            task_tree=tree,
            progress={"steps": 1},
        )


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Route filesystem side effects (workspace, CBKB) into a temp directory."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    return tmp_path


@pytest.fixture
def queue() -> MemoryQueueBackend:
    return MemoryQueueBackend()


@pytest.fixture
def pubsub() -> MemoryPubSubBackend:
    return MemoryPubSubBackend()


@pytest.fixture
def repository() -> JobRepository:
    return JobRepository()


@pytest.fixture
def runner_factory():
    return lambda progress_callback=None, skill_executor=None, job_id=None: _FakeRunner(progress_callback)


@pytest.fixture
def runner(
    queue: MemoryQueueBackend,
    repository: JobRepository,
    pubsub: MemoryPubSubBackend,
    runner_factory,
    data_dir: Path,
) -> BackgroundJobRunner:
    return BackgroundJobRunner(
        queue=queue,
        repository=repository,
        pubsub=pubsub,
        runner_factory=runner_factory,
        poll_timeout=0.1,
    )


@pytest.mark.asyncio
async def test_worker_executes_job_to_completion(
    runner: BackgroundJobRunner,
    queue: MemoryQueueBackend,
    repository: JobRepository,
    pubsub: MemoryPubSubBackend,
) -> None:
    job = Job(
        session_id="sess_1",
        project_id="proj_1",
        status=JobStatus.QUEUED,
        mode=JobMode.WORKFLOW,
        task_tree=TaskTree([TaskNode(id="t1", name="qc", description="QC")]),
        working_memory=WorkingMemory(),
    )
    await repository.create(job)
    await queue.enqueue(job.job_id)

    runner.start()

    # Wait for the worker to process the job, with a generous timeout.
    for _ in range(100):
        await asyncio.sleep(0.05)
        persisted = await repository.get(job.job_id)
        if persisted.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break

    await runner.stop(timeout=2.0)

    persisted = await repository.get(job.job_id)
    assert persisted.status == JobStatus.COMPLETED
    assert persisted.result is not None
    assert persisted.result["response_text"] == "done"
    assert persisted.result["mode"] == str(ExecutionMode.DIRECT_RESPONSE)

    latest = await pubsub.latest(job.job_id)
    assert latest is not None
    assert latest.status == JobStatus.COMPLETED.value
