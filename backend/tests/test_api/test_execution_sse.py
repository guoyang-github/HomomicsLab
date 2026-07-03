"""Tests for execution monitoring API endpoints."""

import pytest
from fastapi.testclient import TestClient

from homomics_lab.api.execution import router
from homomics_lab.hpc.pubsub import ExecutionPubSub
from homomics_lab.hpc.state import ExecutionState


@pytest.fixture
def client(_isolate_pubsub):
    from fastapi import FastAPI

    app = FastAPI()
    app.state.execution_pubsub = _isolate_pubsub
    app.include_router(router, prefix="/api/execution")
    return TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_pubsub():
    """Use a fresh pubsub for every execution API test."""
    return ExecutionPubSub()


class TestExecutionAPI:
    @pytest.mark.asyncio
    async def test_sse_stream_existing_state(self, client, _isolate_pubsub):
        _isolate_pubsub.publish(
            "job_abc", ExecutionState(job_id="job_abc", status="RUNNING")
        )

        with client.stream(
            "GET",
            "/api/execution/job_abc/events",
            headers={"x-test-disconnect": "1"},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type")
            body = response.read().decode("utf-8")
            assert "RUNNING" in body

    @pytest.mark.asyncio
    async def test_nextflow_webhook_publishes_state(self, client, _isolate_pubsub):
        payload = {
            "runName": "nf_run_1",
            "event": "started",
            "trace": {"process": "qc", "name": "nf_run_1"},
        }
        response = client.post("/api/execution/webhook/nextflow", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        latest = await _isolate_pubsub.latest("nf_run_1")
        assert latest is not None
        assert latest.status == "RUNNING"
        assert latest.scheduler_type == "nextflow"
