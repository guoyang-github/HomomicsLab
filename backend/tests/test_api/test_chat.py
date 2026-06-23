import time

from fastapi.testclient import TestClient
from homomics_lab.main import app


def _poll_job(client: TestClient, job_id: str, timeout: float = 30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/execution/{job_id}/status")
        data = response.json()
        if data["status"] not in ("queued", "pending", "running"):
            return data
        time.sleep(0.1)
    return response.json()


def test_send_message():
    with TestClient(app) as client:
        response = client.post("/api/chat/send", json={
            "project_id": "proj_1",
            "session_id": "sess_1",
            "message": "帮我分析单细胞数据",
        })
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "task_tree" in data
        assert "job_id" in data
        assert data["status"] in ("queued", "awaiting_plan_approval")

        if data["status"] == "queued":
            job_id = data["job_id"]
            final = _poll_job(client, job_id)
            assert final["status"] in ("awaiting_human", "completed", "failed")


def test_get_messages():
    with TestClient(app) as client:
        response = client.get("/api/chat/messages?session_id=sess_1")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_respond_to_debate():
    with TestClient(app) as client:
        session_id = "sess_debate_api"
        # Seed a session by sending a message that triggers a debate
        response = client.post("/api/chat/send", json={
            "project_id": "proj_1",
            "session_id": session_id,
            "message": "请帮我选择分析类型",
        })
        assert response.status_code == 200

        # Manually inject debate state for the test
        from homomics_lab.api import chat as chat_api
        chat_api._debates[session_id] = {
            "debate_id": "debate_1",
            "topic": "请选择您需要的分析类型",
            "options": [
                {"id": "qa", "label": "问题解答"},
                {"id": "single_cell_analysis", "label": "单细胞分析"},
            ],
            "recommendation": None,
        }

        response = client.post("/api/chat/debate/respond", json={
            "session_id": session_id,
            "debate_id": "debate_1",
            "choice_id": "qa",
            "parameters": {},
        })
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["status"] == "completed"
        assert data["result"]["task_tree"] is not None
