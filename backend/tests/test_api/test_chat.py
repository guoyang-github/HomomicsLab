import time

from fastapi.testclient import TestClient


def _poll_job(client: TestClient, job_id: str, timeout: float = 30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/execution/{job_id}/status")
        data = response.json()
        if data["status"] not in ("queued", "pending", "running"):
            return data
        time.sleep(0.1)
    return response.json()


def test_send_message(client):
    response = client.post("/api/chat/send", json={
        "project_id": "proj_1",
        "session_id": "sess_1",
        "message": "帮我分析单细胞数据",
        "plan_mode": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "task_tree" in data
    assert "plan_id" in data
    assert data["status"] == "awaiting_plan_approval"


def test_get_messages(client):
    response = client.get("/api/chat/messages?session_id=sess_1")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_respond_to_debate(client):
    import asyncio

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
    asyncio.run(chat_api._debate_store.save(session_id, {
        "debate_id": "debate_1",
        "topic": "请选择您需要的分析类型",
        "options": [
            {"id": "qa", "label": "问题解答"},
            {"id": "single_cell_analysis", "label": "单细胞分析"},
        ],
        "recommendation": None,
    }))

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


def test_regenerate_message(client):
    session_id = "sess_regenerate_api"
    # Seed a session with a user message.
    response = client.post("/api/chat/send", json={
        "project_id": "proj_1",
        "session_id": session_id,
        "message": "什么是单细胞测序？",
    })
    assert response.status_code == 200
    original = response.json()

    # Regenerate the last assistant response.
    response = client.post("/api/chat/regenerate", json={
        "project_id": "proj_1",
        "session_id": session_id,
        "message": "",
    })
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "task_tree" in data
    assert "messages" in data
    assert len(data["messages"]) >= len(original["messages"]) - 1

    # Ensure the assistant response count stays the same (one reply for the last user message).
    assistant_messages = [m for m in data["messages"] if m.get("sender") == "agent"]
    original_assistant = [m for m in original["messages"] if m.get("sender") == "agent"]
    assert len(assistant_messages) == len(original_assistant)


def test_list_sessions(client):
    session_id = "sess_list_api"
    response = client.post("/api/chat/send", json={
        "project_id": "proj_1",
        "session_id": session_id,
        "message": "列出我的会话",
    })
    assert response.status_code == 200

    response = client.get("/api/chat/sessions?project_id=proj_1")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(s["id"] == session_id for s in data)
    session = next(s for s in data if s["id"] == session_id)
    assert session["project_id"] == "proj_1"
    assert "name" in session


def test_submit_feedback(client):
    session_id = "sess_feedback_api"
    response = client.post("/api/chat/send", json={
        "project_id": "proj_1",
        "session_id": session_id,
        "message": "hello",
    })
    assert response.status_code == 200
    data = response.json()
    agent_messages = [m for m in data["messages"] if m.get("sender") == "agent"]
    assert agent_messages
    message_id = agent_messages[0]["id"]

    response = client.post("/api/chat/feedback", json={
        "message_id": message_id,
        "rating": "positive",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
