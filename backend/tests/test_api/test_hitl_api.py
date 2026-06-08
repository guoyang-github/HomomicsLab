from fastapi.testclient import TestClient
from homics_lab.main import app

client = TestClient(app)


def test_hitl_response():
    # First send a message that triggers single-cell pipeline with HITL
    response = client.post("/api/chat/send", json={
        "project_id": "proj_1",
        "session_id": "sess_hitl",
        "message": "帮我分析这组单细胞数据",
    })
    assert response.status_code == 200

    # Find a task that is awaiting human input
    tasks = response.json()["task_tree"]["tasks"]
    hitl_task = None
    for task in tasks:
        if task.get("status") == "awaiting_human":
            hitl_task = task
            break

    # The clustering task should have HITL checkpoint
    assert hitl_task is not None, "Expected a task awaiting human input"
    assert hitl_task["name"] == "clustering"

    # Respond to HITL
    response = client.post("/api/chat/hitl/respond", json={
        "session_id": "sess_hitl",
        "task_id": hitl_task["id"],
        "choice": "ok",
        "parameters": {"n_neighbors": 20},
    })
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
