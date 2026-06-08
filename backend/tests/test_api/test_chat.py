from fastapi.testclient import TestClient
from homics_lab.main import app

client = TestClient(app)


def test_send_message():
    response = client.post("/api/chat/send", json={
        "project_id": "proj_1",
        "session_id": "sess_1",
        "message": "帮我分析单细胞数据",
    })
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "task_tree" in data


def test_get_messages():
    response = client.get("/api/chat/messages?session_id=sess_1")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
