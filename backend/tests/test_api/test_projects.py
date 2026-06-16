from fastapi.testclient import TestClient
import pytest

from homomics_lab.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_create_project(client):
    response = client.post("/api/projects", json={
        "name": "PBMC Analysis",
        "description": "Single cell analysis of PBMC 3k",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "PBMC Analysis"
    assert "id" in data


def test_list_projects(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
