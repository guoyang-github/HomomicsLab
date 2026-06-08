from fastapi.testclient import TestClient
from homics_lab.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_app_info():
    response = client.get("/")
    assert response.status_code == 200
    assert "HomicsLab" in response.json()["name"]
