"""Tests for checkpoint API endpoints."""

import pytest
from fastapi.testclient import TestClient

from homomics_lab.config import settings
from homomics_lab.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_key", "test-api-key")
    with TestClient(app) as c:
        yield c


class TestCheckpointsApi:
    def test_record_and_list(self, client):
        response = client.post(
            "/api/jobs/job_1/checkpoints",
            json={
                "checkpoint_id": "cp_1",
                "task_id": "task_1",
                "phase": "qc",
                "status": "success",
                "payload": {"adata": "path.h5ad"},
            },
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job_1"
        assert data["checkpoint_id"] == "cp_1"

        response = client.get(
            "/api/jobs/job_1/checkpoints",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        checkpoints = response.json()
        assert len(checkpoints) == 1
        assert checkpoints[0]["payload"]["adata"] == "path.h5ad"

    def test_latest_checkpoint(self, client):
        client.post(
            "/api/jobs/job_1/checkpoints",
            json={"checkpoint_id": "cp_1", "task_id": "task_1", "payload": {"step": 1}},
            headers={"X-API-Key": "test-api-key"},
        )
        client.post(
            "/api/jobs/job_1/checkpoints",
            json={"checkpoint_id": "cp_2", "task_id": "task_2", "payload": {"step": 2}},
            headers={"X-API-Key": "test-api-key"},
        )

        response = client.get(
            "/api/jobs/job_1/checkpoints/latest",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        assert response.json()["checkpoint_id"] == "cp_2"

    def test_get_and_delete(self, client):
        client.post(
            "/api/jobs/job_1/checkpoints",
            json={"checkpoint_id": "cp_1", "task_id": "task_1", "payload": {}},
            headers={"X-API-Key": "test-api-key"},
        )

        response = client.get(
            "/api/jobs/job_1/checkpoints/cp_1",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        assert response.json()["checkpoint_id"] == "cp_1"

        response = client.delete(
            "/api/jobs/job_1/checkpoints/cp_1",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        assert response.json()["deleted"] is True

        response = client.get(
            "/api/jobs/job_1/checkpoints/cp_1",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 404

    def test_auth_required(self, client):
        response = client.get("/api/jobs/job_1/checkpoints")
        assert response.status_code == 401
