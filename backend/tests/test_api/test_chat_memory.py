import time


def _poll_job(client, job_id, timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/execution/{job_id}/status")
        data = response.json()
        if data["status"] not in ("queued", "pending", "running"):
            return data
        time.sleep(0.1)
    return response.json()


def test_chat_persists_session_state(client):
    r1 = client.post("/api/chat/send", json={
        "project_id": "proj_1",
        "session_id": "sess_persist_api",
        "message": "帮我分析单细胞数据",
    })
    assert r1.status_code == 200
    data1 = r1.json()
    job_id = data1["job_id"]
    _poll_job(client, job_id)

    r2 = client.post("/api/chat/send", json={
        "project_id": "proj_1",
        "session_id": "sess_persist_api",
        "message": "继续",
    })
    assert r2.status_code == 200

    messages = client.get("/api/chat/messages?session_id=sess_persist_api").json()
    assert len(messages) >= 4
