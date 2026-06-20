"""Tests for the project-level audit log endpoint."""

import json

import pytest
from fastapi.testclient import TestClient

from homomics_lab.api.auth import get_current_user
from homomics_lab.config import settings
from homomics_lab.database import Base
from homomics_lab.database.connection import async_engine
from homomics_lab.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "auth_enabled", True)

    async def reset_db():
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    import asyncio

    asyncio.run(reset_db())

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _as_user(client: TestClient, user_id: str):
    app.dependency_overrides[get_current_user] = lambda: user_id


def test_audit_log_endpoint_returns_entries(client, tmp_path, monkeypatch):
    _as_user(client, "owner")
    create_resp = client.post(
        "/api/projects",
        json={"name": "Audited", "description": "test"},
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["id"]

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "audit.log"
    log_file.write_text(
        json.dumps({"project_id": project_id, "method": "GET", "path": "/test"})
        + "\n"
    )

    monkeypatch.setattr(settings, "audit_log_enabled", True)
    monkeypatch.setattr(settings, "audit_log_path", log_file)

    response = client.get(f"/api/projects/{project_id}/audit")
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == project_id
    assert len(data["entries"]) == 1
    assert data["entries"][0]["method"] == "GET"


def test_audit_log_disabled_returns_empty(client, tmp_path, monkeypatch):
    _as_user(client, "owner")
    create_resp = client.post("/api/projects", json={"name": "NoAudit"})
    assert create_resp.status_code == 200
    project_id = create_resp.json()["id"]

    monkeypatch.setattr(settings, "audit_log_enabled", False)

    response = client.get(f"/api/projects/{project_id}/audit")
    assert response.status_code == 200
    assert response.json()["entries"] == []
