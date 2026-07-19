import asyncio

import pytest
from fastapi.testclient import TestClient

from homomics_lab.api.auth import get_current_user
from homomics_lab.context.working_memory import WorkingMemory
from homomics_lab.database import Base
from homomics_lab.database.connection import get_engine
from homomics_lab.jobs.models import JobMode, JobStatus
from homomics_lab.jobs.service import JobService
from homomics_lab.main import app
from homomics_lab.models.common import HITLCheckpoint, Option
from homomics_lab.tasks.models import TaskNode, TaskStatus
from homomics_lab.tasks.task_tree import TaskTree


@pytest.fixture
def client():
    async def reset_db():
        async with get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(reset_db())

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _as_user(client: TestClient, user_id: str):
    app.dependency_overrides[get_current_user] = lambda: user_id


def test_hitl_response(client):
    _as_user(client, "owner")

    # Seed a job in AWAITING_HUMAN status directly so the test does not
    # depend on the stochastic chat/intent pipeline.
    task = TaskNode(
        id="task_1",
        name="clustering",
        description="Run clustering",
        phase="clustering",
        status=TaskStatus.AWAITING_HUMAN,
        hitl_checkpoints=[
            HITLCheckpoint(
                id="chk_1",
                trigger_reason="policy",
                context_summary="Confirm clustering",
                options=[
                    Option(id="ok", label="OK"),
                    Option(id="cancel", label="Cancel"),
                ],
            )
        ],
    )
    tree = TaskTree(tasks=[task])
    wm = WorkingMemory()

    service = JobService()
    job = asyncio.run(
        service.create_job(
            session_id="sess_hitl",
            project_id="proj_1",
            working_memory=wm,
            task_tree=tree,
            mode=JobMode.AWAITING_HITL,
        )
    )
    job.status = JobStatus.AWAITING_HUMAN
    asyncio.run(service.repository.update(job))

    response = client.post("/api/chat/hitl/respond", json={
        "session_id": "sess_hitl",
        "task_id": "task_1",
        "choice": "ok",
        "parameters": {"n_neighbors": 20},
    })
    assert response.status_code == 200
    resume_data = response.json()
    assert resume_data["status"] == "queued"
    assert "job_id" in resume_data
