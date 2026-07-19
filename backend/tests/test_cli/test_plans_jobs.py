"""Tests for `homomics plans` and `homomics jobs` CLI commands."""

import argparse
import json
import uuid

import pytest
import pytest_asyncio

from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.cli.commands.jobs import _list_jobs
from homomics_lab.cli.commands.plans import _list_plans
from homomics_lab.database import Base
from homomics_lab.database.connection import get_engine
from homomics_lab.jobs import Job, JobMode, JobRepository, JobStatus
from homomics_lab.plan import Plan, PlanStatus, PlanStore
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


@pytest_asyncio.fixture(autouse=True, loop_scope="function")
async def _create_tables():
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def plan_store():
    return PlanStore()


@pytest_asyncio.fixture
async def job_repo():
    return JobRepository()


def _make_plan(project_id: str = "proj_1") -> Plan:
    tree = TaskTree([TaskNode(id="t1", name="qc", description="QC")])
    plan_result = PlanResult(
        phases=[Phase(phase_type="qc", description="QC")],
        strategy_name="test",
        data_state=DataState(),
    )
    return Plan(
        plan_id=f"plan_{uuid.uuid4().hex[:12]}",
        session_id="sess_1",
        project_id=project_id,
        status=PlanStatus.APPROVED,
        intent_analysis_type="test",
        plan_result=plan_result,
        task_tree=tree,
    )


class FakeCapsys:
    """Minimal capsys stand-in for the async CLI helpers."""

    def __init__(self):
        self._out = ""
        self._err = ""

    def write(self, text: str):
        self._out += text + "\n"

    @property
    def out(self):
        return self._out


@pytest.mark.asyncio
async def test_plans_json_output(plan_store, capsys):
    plan = _make_plan()
    await plan_store.create(plan)

    code = await _list_plans(argparse.Namespace(status=None, project_id=None, json_output=True))
    assert code == 0

    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["plan_id"] == plan.plan_id
    assert rows[0]["status"] == PlanStatus.APPROVED


@pytest.mark.asyncio
async def test_plans_status_filter(plan_store, capsys):
    plan = _make_plan()
    await plan_store.create(plan)

    code = await _list_plans(
        argparse.Namespace(status=PlanStatus.COMPLETED, project_id=None, json_output=True)
    )
    assert code == 0

    rows = json.loads(capsys.readouterr().out)
    assert rows == []


@pytest.mark.asyncio
async def test_plans_project_filter(plan_store, capsys):
    await plan_store.create(_make_plan(project_id="proj_a"))
    await plan_store.create(_make_plan(project_id="proj_b"))

    code = await _list_plans(
        argparse.Namespace(status=None, project_id="proj_a", json_output=True)
    )
    assert code == 0

    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["project_id"] == "proj_a"


@pytest.mark.asyncio
async def test_jobs_json_output(job_repo, capsys):
    job = Job(
        session_id="sess_1",
        project_id="proj_1",
        status=JobStatus.QUEUED,
        mode=JobMode.WORKFLOW,
        task_tree=TaskTree([]),
    )
    await job_repo.create(job)

    code = await _list_jobs(argparse.Namespace(project_id=None, status=None, json_output=True))
    assert code == 0

    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["job_id"] == job.job_id


@pytest.mark.asyncio
async def test_jobs_project_and_status_filter(job_repo, capsys):
    job_a = Job(
        session_id="sess_1",
        project_id="proj_a",
        status=JobStatus.QUEUED,
        mode=JobMode.WORKFLOW,
        task_tree=TaskTree([]),
    )
    job_b = Job(
        session_id="sess_1",
        project_id="proj_b",
        status=JobStatus.RUNNING,
        mode=JobMode.WORKFLOW,
        task_tree=TaskTree([]),
    )
    await job_repo.create(job_a)
    await job_repo.create(job_b)

    code = await _list_jobs(
        argparse.Namespace(project_id="proj_a", status=JobStatus.QUEUED, json_output=True)
    )
    assert code == 0

    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["job_id"] == job_a.job_id
