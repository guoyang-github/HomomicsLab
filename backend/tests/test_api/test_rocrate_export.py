"""Tests for the RO-Crate project export API endpoint."""

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


def test_export_rocrate_for_existing_project(client):
    _as_user(client, "owner")
    create_resp = client.post(
        "/api/projects",
        json={"name": "Exportable", "description": "test"},
    )
    assert create_resp.status_code == 200
    project_id = create_resp.json()["id"]

    export_resp = client.post(f"/api/projects/{project_id}/export/rocrate")
    assert export_resp.status_code == 200
    assert export_resp.headers["content-type"] == "application/zip"
    assert export_resp.headers["content-disposition"].endswith("_rocrate.zip\"")


def test_export_rocrate_not_found(client):
    _as_user(client, "owner")
    export_resp = client.post("/api/projects/nonexistent/export/rocrate")
    assert export_resp.status_code == 404
