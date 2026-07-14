"""API tests for the Waiting Orchestrator endpoints (/api/waiting)."""

import pytest

from homomics_lab.api.deps import get_waiting_service
from homomics_lab.jobs.waiting import WaitingService
from homomics_lab.main import app


@pytest.fixture(autouse=True)
def _isolated_waiting_service(tmp_path):
    """Route the waiting service to a temp DB for this test module.

    The app's default WaitingService persists to ``settings.data_dir``,
    which the global conftest resolves before ``HOMOMICS_DATA_DIR`` is set —
    without this override, test conditions would accumulate in the real
    ``data/waiting.db`` and break repeat runs.
    """
    service = WaitingService(db_path=tmp_path / "waiting.db")
    original = getattr(app.state, "waiting_service", None)
    app.state.waiting_service = service
    app.dependency_overrides[get_waiting_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_waiting_service, None)
    if original is not None:
        app.state.waiting_service = original


def _waiting():
    return app.state.waiting_service


def test_get_wait_condition(client):
    cond = _waiting().register("job_api_get", "manual", {"note": "hold"})

    resp = client.get(f"/api/waiting/{cond.wait_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["wait_id"] == cond.wait_id
    assert body["job_id"] == "job_api_get"
    assert body["condition_type"] == "manual"
    assert body["status"] == "pending"
    assert body["payload"] == {"note": "hold"}

    resp = client.get("/api/waiting/wait_does_not_exist")
    assert resp.status_code == 404


def test_list_wait_conditions_filtered_by_job(client):
    cond = _waiting().register("job_api_list", "manual")
    _waiting().register("job_api_other", "manual")

    resp = client.get("/api/waiting", params={"job_id": "job_api_list"})
    assert resp.status_code == 200
    items = resp.json()
    assert [item["wait_id"] for item in items] == [cond.wait_id]


def test_resume_webhook_token_flow(client):
    cond = _waiting().register("job_api_webhook", "webhook", {})
    token = cond.payload["token"]

    # Wrong token is rejected and the condition stays pending.
    resp = client.post(f"/api/waiting/{cond.wait_id}/resume", json={"token": "wrong"})
    assert resp.status_code == 403
    assert _waiting().get(cond.wait_id).status == "pending"

    # Correct token resolves the condition and carries resume_data.
    resp = client.post(
        f"/api/waiting/{cond.wait_id}/resume",
        json={"token": token, "data": {"run_id": "r1"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["wait"]["status"] == "resumed"
    assert body["wait"]["resume_data"] == {"run_id": "r1"}
    assert body["job_id"] == "job_api_webhook"

    # A resolved condition cannot be resumed again.
    resp = client.post(f"/api/waiting/{cond.wait_id}/resume", json={"token": token})
    assert resp.status_code == 409


def test_resume_manual_condition_without_token(client):
    cond = _waiting().register("job_api_manual", "manual")
    resp = client.post(f"/api/waiting/{cond.wait_id}/resume", json={})
    assert resp.status_code == 200
    assert resp.json()["wait"]["status"] == "resumed"

    resp = client.post("/api/waiting/wait_nope/resume", json={})
    assert resp.status_code == 404


def test_cancel_wait_condition(client):
    cond = _waiting().register("job_api_cancel", "manual")

    resp = client.post(f"/api/waiting/{cond.wait_id}/cancel")
    assert resp.status_code == 200
    assert resp.json() == {"cancelled": True}
    assert _waiting().get(cond.wait_id).status == "cancelled"

    # Cancelling again is a no-op.
    resp = client.post(f"/api/waiting/{cond.wait_id}/cancel")
    assert resp.status_code == 200
    assert resp.json() == {"cancelled": False}

    resp = client.post("/api/waiting/wait_nope/cancel")
    assert resp.status_code == 404
