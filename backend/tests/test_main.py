from fastapi.testclient import TestClient
from homomics_lab.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.5.0"
    assert "llm_configured" in data
    assert "llm_provider" in data
    assert "llm_model" in data

def test_app_info():
    response = client.get("/")
    assert response.status_code == 200
    assert "HomomicsLab" in response.json()["name"]


def test_memory_health():
    response = client.get("/health/memory")
    assert response.status_code == 200
    data = response.json()
    assert data["session_store"] in ("ok", "error", "not_configured")
    assert data["semantic_memory"] in ("ok", "disabled", "not_configured")
