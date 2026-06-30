"""Tests for /api/reproducibility/{job_id}/bundle endpoint."""

import json

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from homomics_lab.api.reproducibility import router as reproducibility_router
from homomics_lab.config import settings
from homomics_lab.database import Base, async_engine
from homomics_lab.jobs import Job, JobMode, JobRepository, JobStatus
from homomics_lab.workspace.manager import WorkspaceManager


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_key", "test-api-key")
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(reproducibility_router, prefix="/api/reproducibility")
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture
async def repo():
    return JobRepository()


class TestReproducibilityBundleApi:
    def test_bundle_not_found_for_missing_job(self, client):
        response = client.get(
            "/api/reproducibility/job_missing/bundle",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_bundle_returns_json(self, client, tmp_path, monkeypatch, repo):
        monkeypatch.setattr(settings, "data_dir", tmp_path)
        job = await repo.create(
            Job(
                session_id="sess_1",
                project_id="proj_1",
                status=JobStatus.COMPLETED,
                mode=JobMode.WORKFLOW,
            )
        )
        workspace = WorkspaceManager(base_dir=tmp_path, project_id="proj_1")
        bundle_path = workspace.get_path(
            f".metadata/reproducibility_bundle_{job.job_id}.json"
        )
        bundle_payload = {
            "project_id": "proj_1",
            "random_seed": 42,
            "execution_snapshot": {"task_tree": {"tasks": []}},
        }
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_text(json.dumps(bundle_payload), encoding="utf-8")

        response = client.get(
            f"/api/reproducibility/{job.job_id}/bundle",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["project_id"] == "proj_1"
        assert data["random_seed"] == 42

    @pytest.mark.asyncio
    async def test_bundle_download_returns_attachment(self, client, tmp_path, monkeypatch, repo):
        monkeypatch.setattr(settings, "data_dir", tmp_path)
        job = await repo.create(
            Job(
                session_id="sess_2",
                project_id="proj_2",
                status=JobStatus.COMPLETED,
                mode=JobMode.WORKFLOW,
            )
        )
        workspace = WorkspaceManager(base_dir=tmp_path, project_id="proj_2")
        bundle_path = workspace.get_path(
            f".metadata/reproducibility_bundle_{job.job_id}.json"
        )
        bundle_payload = {"project_id": "proj_2", "random_seed": 7}
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_text(json.dumps(bundle_payload), encoding="utf-8")

        response = client.get(
            f"/api/reproducibility/{job.job_id}/bundle?download=true",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/json"
        content_disposition = response.headers["content-disposition"]
        assert "attachment" in content_disposition
        assert f"reproducibility_bundle_{job.job_id}.json" in content_disposition
        assert response.json()["random_seed"] == 7

    @pytest.mark.asyncio
    async def test_bundle_falls_back_to_project_bundle(self, client, tmp_path, monkeypatch, repo):
        monkeypatch.setattr(settings, "data_dir", tmp_path)
        job = await repo.create(
            Job(
                session_id="sess_3",
                project_id="proj_3",
                status=JobStatus.COMPLETED,
                mode=JobMode.WORKFLOW,
            )
        )
        workspace = WorkspaceManager(base_dir=tmp_path, project_id="proj_3")
        bundle_path = workspace.get_path(".metadata/reproducibility_bundle.json")
        bundle_payload = {"project_id": "proj_3", "random_seed": 99}
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        bundle_path.write_text(json.dumps(bundle_payload), encoding="utf-8")

        response = client.get(
            f"/api/reproducibility/{job.job_id}/bundle",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["random_seed"] == 99
