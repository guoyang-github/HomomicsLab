import time

from fastapi.testclient import TestClient
from homomics_lab.main import app


def _poll_job(client: TestClient, job_id: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/execution/{job_id}/status")
        data = response.json()
        if data["status"] not in ("queued", "pending", "running"):
            return data
        time.sleep(0.1)
    return response.json()


def test_hitl_response():
    with TestClient(app) as client:
        # First send a message that triggers single-cell pipeline with HITL
        response = client.post("/api/chat/send", json={
            "project_id": "proj_1",
            "session_id": "sess_hitl",
            "message": "帮我分析这组单细胞数据",
        })
        assert response.status_code == 200
        send_data = response.json()
        assert send_data["status"] == "queued"
        job_id = send_data["job_id"]

        # Wait for the job to hit a HITL checkpoint
        final = _poll_job(client, job_id)
        assert final["status"] == "awaiting_human"

        # Retrieve the persisted task tree from the job record
        job_response = client.get(f"/api/execution/{job_id}/status")
        job_data = job_response.json()
        assert "latest_state" in job_data

        # Load task tree snapshot from the original response preview
        tasks = send_data["task_tree"]["tasks"]
        hitl_task = None
        for task in tasks:
            if task.get("status") == "awaiting_human" or task.get("name") == "clustering":
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
        resume_data = response.json()
        assert resume_data["status"] == "queued"
        assert "job_id" in resume_data

        resume_job_id = resume_data["job_id"]
        resumed_final = _poll_job(client, resume_job_id)
        assert resumed_final["status"] in ("completed", "failed")
