from fastapi.testclient import TestClient
from homics_lab.main import app

client = TestClient(app)


def test_create_project():
    response = client.post("/api/projects", json={
        "name": "PBMC Analysis",
        "description": "Single cell analysis of PBMC 3k",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "PBMC Analysis"
    assert "id" in data


def test_list_projects():
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
