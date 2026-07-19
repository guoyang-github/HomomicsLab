"""Tests for the job repository and serialization."""

import pytest
import pytest_asyncio

from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.database import Base
from homomics_lab.database.connection import get_engine
from homomics_lab.jobs import Job, JobMode, JobRepository, JobStatus
from homomics_lab.models.common import ChatMessage, MessageType
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _create_tables():
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def repo():
    return JobRepository()


@pytest.mark.asyncio
async def test_create_and_get_job(repo):
    wm = WorkingMemory()
    wm.add_message(
        ChatMessage(
            id="msg_0",
            type=MessageType.TEXT,
            content="hello",
            sender="user",
        )
    )
    tree = TaskTree([TaskNode(id="t1", name="qc", description="QC")])

    job = Job(
        session_id="sess_1",
        project_id="proj_1",
        status=JobStatus.QUEUED,
        mode=JobMode.WORKFLOW,
        task_tree=tree,
        working_memory=wm,
    )

    created = await repo.create(job)
    assert created.job_id == job.job_id

    fetched = await repo.get(job.job_id)
    assert fetched is not None
    assert fetched.status == JobStatus.QUEUED
    assert fetched.mode == JobMode.WORKFLOW
    assert len(fetched.task_tree.tasks) == 1
    assert fetched.task_tree.tasks[0].name == "qc"
    assert len(fetched.working_memory.messages) == 1


@pytest.mark.asyncio
async def test_update_job_status(repo):
    job = Job(
        session_id="sess_1",
        project_id="proj_1",
        status=JobStatus.QUEUED,
        mode=JobMode.WORKFLOW,
    )
    await repo.create(job)

    job.status = JobStatus.RUNNING
    await repo.update(job)

    fetched = await repo.get(job.job_id)
    assert fetched.status == JobStatus.RUNNING


@pytest.mark.asyncio
async def test_get_latest_by_session(repo):
    job1 = Job(
        session_id="sess_1",
        project_id="proj_1",
        status=JobStatus.AWAITING_HUMAN,
        mode=JobMode.WORKFLOW,
    )
    job2 = Job(
        session_id="sess_1",
        project_id="proj_1",
        status=JobStatus.QUEUED,
        mode=JobMode.WORKFLOW,
    )
    await repo.create(job1)
    await repo.create(job2)

    latest = await repo.get_latest_by_session("sess_1", statuses=[JobStatus.AWAITING_HUMAN.value])
    assert latest is not None
    assert latest.job_id == job1.job_id
