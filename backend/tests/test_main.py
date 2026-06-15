from fastapi.testclient import TestClient
from homomics_lab.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_app_info():
    response = client.get("/")
    assert response.status_code == 200
    assert "HomomicsLab" in response.json()["name"]


def test_memory_health():
    from fastapi.testclient import TestClient
    from homomics_lab.main import app

    with TestClient(app) as client:
        response = client.get("/health/memory")
        assert response.status_code == 200
        data = response.json()
        assert data["session_store"] in ("ok", "error")
        assert data["semantic_memory"] in ("ok", "disabled")
