"""Tests for /api/execution/{job_id}/status endpoint."""

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from homomics_lab.api.execution import router
from homomics_lab.database import Base, async_engine
from homomics_lab.jobs import Job, JobMode, JobRepository, JobService, JobStatus


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def repo():
    return JobRepository()


@pytest_asyncio.fixture
async def client():
    from fastapi import FastAPI
    from homomics_lab.observability.trace_store import TraceStore

    app = FastAPI()
    job_service = JobService()
    app.state.job_service = job_service
    app.state.trace_store = TraceStore()
    app.state.execution_pubsub = job_service.pubsub
    app.include_router(router, prefix="/api/execution")
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_status_not_found(client):
    response = await client.get("/api/execution/job_missing/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "not_found"


@pytest.mark.asyncio
async def test_status_existing_job(client, repo):
    job = await repo.create(
        Job(
            session_id="sess_1",
            project_id="proj_1",
            status=JobStatus.RUNNING,
            mode=JobMode.WORKFLOW,
        )
    )

    response = await client.get(f"/api/execution/{job.job_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job.job_id
    assert data["status"] == "running"
    assert data["mode"] == "workflow"
