"""Tests for project-level RBAC."""

import pytest
from fastapi.testclient import TestClient

from homomics_lab.api.auth import get_current_user
from homomics_lab.config import settings
from homomics_lab.database import Base
from homomics_lab.database.connection import get_engine
from homomics_lab.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "auth_enabled", True)

    async def reset_db():
        async with get_engine().begin() as conn:
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


class TestProjectRbac:
    def test_owner_can_create_and_view(self, client):
        _as_user(client, "owner")
        response = client.post(
            "/api/projects",
            json={"name": "secret", "description": "x"},
        )
        assert response.status_code == 200
        project_id = response.json()["id"]

        response = client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "secret"

    def test_other_user_cannot_view(self, client):
        _as_user(client, "owner")
        response = client.post(
            "/api/projects",
            json={"name": "secret", "description": "x"},
        )
        project_id = response.json()["id"]

        _as_user(client, "other")
        response = client.get(f"/api/projects/{project_id}")
        assert response.status_code == 403

    def test_member_can_view_after_invite(self, client):
        _as_user(client, "owner")
        response = client.post(
            "/api/projects",
            json={"name": "shared", "description": "x"},
        )
        project_id = response.json()["id"]

        response = client.post(
            f"/api/projects/{project_id}/members",
            json={"user_id": "other", "role": "member"},
        )
        assert response.status_code == 200

        _as_user(client, "other")
        response = client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "shared"

    def test_list_projects_isolated(self, client):
        _as_user(client, "owner")
        client.post("/api/projects", json={"name": "p1", "description": "x"})

        response = client.get("/api/projects")
        assert response.status_code == 200
        assert len(response.json()) == 1

        _as_user(client, "other")
        response = client.get("/api/projects")
        assert response.status_code == 200
        assert len(response.json()) == 0
