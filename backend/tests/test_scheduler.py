"""Tests for the APScheduler-based scheduled task integration."""

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from homomics_lab.database import Base, async_engine
from homomics_lab.main import app
from homomics_lab.scheduler import HomomicsScheduler


@pytest_asyncio.fixture(autouse=True)
async def _create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
def scheduler():
    return HomomicsScheduler()


@pytest.mark.asyncio
async def test_run_now_unknown_job(scheduler):
    with pytest.raises(ValueError, match="Unknown scheduled job"):
        await scheduler.run_now("unknown_job")


@pytest.mark.asyncio
async def test_run_now_curation_records_audit(scheduler, monkeypatch):
    calls = []

    async def fake_run_full_curation(*args, **kwargs):
        calls.append("curation")
        return {"links_added": 3}

    monkeypatch.setattr(
        "homomics_lab.scheduler.HomomicsScheduler._run_full_curation",
        fake_run_full_curation,
    )

    run = await scheduler.run_now("cbkb_full_curation")
    assert run.status == "completed"
    assert run.job_name == "cbkb_full_curation"
    assert calls == ["curation"]


@pytest.mark.asyncio
async def test_run_now_failure_records_failed(scheduler, monkeypatch):
    async def fake_run_full_curation(*args, **kwargs):
        raise RuntimeError("curator exploded")

    monkeypatch.setattr(
        "homomics_lab.scheduler.HomomicsScheduler._run_full_curation",
        fake_run_full_curation,
    )

    run = await scheduler.run_now("cbkb_full_curation")
    assert run.status == "failed"
    assert "curator exploded" in run.error_message


@pytest.mark.asyncio
async def test_scheduler_start_shutdown_with_no_jobs(monkeypatch):
    monkeypatch.setattr("homomics_lab.config.settings.curation_enabled", False)
    monkeypatch.setattr("homomics_lab.config.settings.narrative_report_enabled", False)
    monkeypatch.setattr("homomics_lab.config.settings.sop_proposal_enabled", False)
    monkeypatch.setattr("homomics_lab.config.settings.evolution_enabled", False)

    sched = HomomicsScheduler()
    await sched.start()
    assert len(sched._scheduler.get_jobs()) == 0
    await sched.shutdown()


@pytest.mark.asyncio
async def test_scheduler_registers_jobs_when_enabled(monkeypatch):
    monkeypatch.setattr("homomics_lab.config.settings.curation_enabled", True)
    monkeypatch.setattr("homomics_lab.config.settings.narrative_report_enabled", True)
    monkeypatch.setattr("homomics_lab.config.settings.sop_proposal_enabled", True)
    monkeypatch.setattr("homomics_lab.config.settings.evolution_enabled", True)
    monkeypatch.setattr("homomics_lab.config.settings.scheduler_run_at_startup", False)

    sched = HomomicsScheduler()
    await sched.start()
    job_ids = {job.id for job in sched._scheduler.get_jobs()}
    assert "cbkb_full_curation" in job_ids
    assert "narrative_report" in job_ids
    assert "sop_proposal" in job_ids
    assert "evolution_pass" in job_ids
    await sched.shutdown()


def test_api_run_scheduled_job(monkeypatch):
    """Manual trigger endpoint executes the scheduled job and returns audit."""
    executed = []

    async def fake_run_now(self, job_name):
        executed.append(job_name)
        run = type("Run", (), {
            "id": 1,
            "job_name": job_name,
            "trigger_time": None,
            "start_time": None,
            "end_time": None,
            "status": "completed",
            "result_json": '{"ok": true}',
            "error_message": None,
        })()
        return run

    monkeypatch.setattr(HomomicsScheduler, "run_now", fake_run_now)

    with TestClient(app) as client:
        response = client.post("/api/scheduler/jobs/cbkb_full_curation/run")
        assert response.status_code == 200
        data = response.json()
        assert data["job_name"] == "cbkb_full_curation"
        assert data["status"] == "completed"
        assert executed == ["cbkb_full_curation"]


def test_api_list_scheduled_runs(monkeypatch):
    async def fake_recent_runs(self, job_name=None, limit=20):
        return [
            type("Run", (), {
                "id": 1,
                "job_name": "cbkb_full_curation",
                "trigger_time": None,
                "start_time": None,
                "end_time": None,
                "status": "completed",
                "result_json": None,
                "error_message": None,
            })(),
        ]

    monkeypatch.setattr(HomomicsScheduler, "recent_runs", fake_recent_runs)

    with TestClient(app) as client:
        response = client.get("/api/scheduler/runs")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["job_name"] == "cbkb_full_curation"
