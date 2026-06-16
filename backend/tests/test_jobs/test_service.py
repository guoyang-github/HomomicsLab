"""Tests for JobService recovery, cancel, and worker integration."""

import pytest
import pytest_asyncio

from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.database import Base, async_engine
from homomics_lab.jobs import Job, JobMode, JobRepository, JobService, JobStatus
from homomics_lab.jobs.backends import MemoryPubSubBackend, MemoryQueueBackend
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def queue():
    return MemoryQueueBackend()


@pytest.fixture
def pubsub():
    return MemoryPubSubBackend()


@pytest.fixture
def repository():
    return JobRepository()


@pytest.fixture
def job_service(queue, repository, pubsub):
    return JobService(queue=queue, repository=repository, pubsub=pubsub)


@pytest.mark.asyncio
async def test_create_job_persists_and_enqueues(job_service, queue):
    tree = TaskTree([TaskNode(id="t1", name="qc", description="QC")])
    wm = WorkingMemory()

    job = await job_service.create_job(
        session_id="sess_1",
        project_id="proj_1",
        working_memory=wm,
        task_tree=tree,
        mode=JobMode.WORKFLOW,
    )

    assert job.status == JobStatus.QUEUED
    persisted = await job_service.get_job(job.job_id)
    assert persisted is not None
    assert persisted.status == JobStatus.QUEUED

    # The job id should be in the memory queue.
    queued_id = await queue.dequeue(timeout=0.1)
    assert queued_id == job.job_id


@pytest.mark.asyncio
async def test_cancel_job_removes_from_queue_and_updates_status(job_service, queue):
    tree = TaskTree([TaskNode(id="t1", name="qc", description="QC")])
    wm = WorkingMemory()

    job = await job_service.create_job(
        session_id="sess_1",
        project_id="proj_1",
        working_memory=wm,
        task_tree=tree,
        mode=JobMode.WORKFLOW,
    )

    cancelled = await job_service.cancel_job(job.job_id)
    assert cancelled is not None
    assert cancelled.status == JobStatus.CANCELLED

    # The job should no longer be in the queue.
    queued_id = await queue.dequeue(timeout=0.1)
    assert queued_id is None

    persisted = await job_service.get_job(job.job_id)
    assert persisted.status == JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_start_worker_recovers_queued_jobs(job_service, repository):
    # Simulate a job that was queued before a restart.
    job = Job(
        session_id="sess_1",
        project_id="proj_1",
        status=JobStatus.QUEUED,
        mode=JobMode.WORKFLOW,
        task_tree=TaskTree([TaskNode(id="t1", name="qc", description="QC")]),
        working_memory=WorkingMemory(),
    )
    await repository.create(job)

    # Starting the worker should recover the queued job back into the queue.
    await job_service.start_worker()
    queued_id = await job_service.queue.dequeue(timeout=0.1)
    assert queued_id == job.job_id

    await job_service.stop_worker()


@pytest.mark.asyncio
async def test_cancel_completed_job_is_noop(job_service):
    tree = TaskTree([TaskNode(id="t1", name="qc", description="QC")])
    job = Job(
        session_id="sess_1",
        project_id="proj_1",
        status=JobStatus.COMPLETED,
        mode=JobMode.WORKFLOW,
        task_tree=tree,
        working_memory=WorkingMemory(),
    )
    await job_service.repository.create(job)

    cancelled = await job_service.cancel_job(job.job_id)
    assert cancelled.status == JobStatus.COMPLETED
