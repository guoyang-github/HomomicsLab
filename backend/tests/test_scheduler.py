"""Tests for the APScheduler-based scheduled task integration."""

from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select

from homomics_lab.database import Base
from homomics_lab.database.connection import get_engine
from homomics_lab.database.connection import get_session_factory
from homomics_lab.database.models import ScheduledJobRun
from homomics_lab.knowledge.cbkb import CBKB, ExperimentNode
from homomics_lab.knowledge.curator import CBKBCurator
from homomics_lab.main import app
from homomics_lab.scheduler import (
    MIN_EXPERIMENTS_FOR_CURATION,
    MIN_EXPERIMENTS_FOR_EVOLUTION,
    MIN_EXPERIMENTS_FOR_NARRATIVE,
    MIN_EXPERIMENTS_FOR_SOP_PROPOSAL,
    HomomicsScheduler,
)

RESEARCH_JOBS = ("cbkb_full_curation", "narrative_report", "sop_proposal", "evolution_pass")


@pytest_asyncio.fixture(autouse=True)
async def _create_tables():
    async with get_engine().begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))
    yield
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


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
async def test_scheduler_registers_research_jobs_by_default():
    """All four research jobs register unconditionally (default awake).

    The scheduler no longer consults the legacy ``*_enabled`` settings
    (which default to False), so registration must happen under defaults.
    """
    sched = HomomicsScheduler()
    await sched.start()
    job_ids = {job.id for job in sched._scheduler.get_jobs()}
    for name in RESEARCH_JOBS:
        assert name in job_ids
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


# ── Data-volume gates ─────────────────────────────

GATED_JOBS = [
    ("cbkb_full_curation", "_run_full_curation", MIN_EXPERIMENTS_FOR_CURATION),
    ("narrative_report", "_run_narrative_report", MIN_EXPERIMENTS_FOR_NARRATIVE),
    ("sop_proposal", "_run_sop_proposal", MIN_EXPERIMENTS_FOR_SOP_PROPOSAL),
    ("evolution_pass", "_run_evolution_pass", MIN_EXPERIMENTS_FOR_EVOLUTION),
]


def _arm_job_dependencies(scheduler):
    """Give a non-started scheduler the attributes gated jobs touch."""
    scheduler._curator = SimpleNamespace(
        run_full_curation=lambda: None,
        generate_narrative=lambda *args: None,
        propose_sop_updates=lambda: None,
    )
    scheduler._evolution_engine = SimpleNamespace(run_evolution_pass=lambda: None)


@pytest.mark.asyncio
@pytest.mark.parametrize("job_name,runner_attr,minimum", GATED_JOBS)
async def test_gate_skips_below_threshold(scheduler, monkeypatch, job_name, runner_attr, minimum):
    """One experiment short of the minimum -> the job is skipped, not run."""
    monkeypatch.setattr(
        HomomicsScheduler, "_count_cbkb_experiments", lambda self: minimum - 1
    )
    _arm_job_dependencies(scheduler)
    calls = []

    async def fake_run_task(self, name, coro_fn, *args):
        calls.append(name)

    monkeypatch.setattr(HomomicsScheduler, "_run_task", fake_run_task)

    await getattr(scheduler, runner_attr)()
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("job_name,runner_attr,minimum", GATED_JOBS)
async def test_gate_allows_at_threshold(scheduler, monkeypatch, job_name, runner_attr, minimum):
    """Exactly at the minimum -> the job runs."""
    monkeypatch.setattr(
        HomomicsScheduler, "_count_cbkb_experiments", lambda self: minimum
    )
    _arm_job_dependencies(scheduler)
    calls = []

    async def fake_run_task(self, name, coro_fn, *args):
        calls.append(name)

    monkeypatch.setattr(HomomicsScheduler, "_run_task", fake_run_task)

    await getattr(scheduler, runner_attr)()
    assert calls == [job_name]


def _seed_experiments(cbkb, count):
    for i in range(count):
        cbkb.add_experiment_node(
            ExperimentNode(
                bundle_id=f"b{i}",
                project_id="p1",
                created_at="2024-01-01T00:00:00+00:00",
                skills_used=[],
                phases=[],
            )
        )


@pytest.mark.asyncio
async def test_gate_skip_writes_no_audit_record(scheduler, monkeypatch, tmp_path):
    """A gated skip is normal: no audit row, curator never invoked."""
    cbkb = CBKB(base_dir=tmp_path)
    _seed_experiments(cbkb, MIN_EXPERIMENTS_FOR_CURATION - 1)
    scheduler._curator = CBKBCurator(cbkb)
    calls = []

    async def fake_run_full_curation(self):
        calls.append("curation")

    monkeypatch.setattr(CBKBCurator, "run_full_curation", fake_run_full_curation)

    await scheduler._run_full_curation()

    assert calls == []
    async with get_session_factory()() as session:
        result = await session.execute(select(ScheduledJobRun))
        assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_gate_allows_run_and_records_audit(scheduler, monkeypatch, tmp_path):
    """With enough experiments the real count path runs the job and audits it."""
    cbkb = CBKB(base_dir=tmp_path)
    _seed_experiments(cbkb, MIN_EXPERIMENTS_FOR_CURATION)
    scheduler._curator = CBKBCurator(cbkb)

    async def fake_run_full_curation(self):
        return {"links_added": 1}

    monkeypatch.setattr(CBKBCurator, "run_full_curation", fake_run_full_curation)

    await scheduler._run_full_curation()

    async with get_session_factory()() as session:
        result = await session.execute(select(ScheduledJobRun))
        runs = result.scalars().all()
    assert len(runs) == 1
    assert runs[0].job_name == "cbkb_full_curation"
    assert runs[0].status == "completed"
