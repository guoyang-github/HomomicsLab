"""Tests that schedulers publish ExecutionState updates."""

import pytest

from homomics_lab.hpc.pubsub import ExecutionPubSub
from homomics_lab.hpc.scheduler import LocalScheduler, NextflowRunner, SlurmScheduler
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.skills.models import SkillDefinition, SkillResources, SkillRuntime


@pytest.fixture
def sample_skill():
    return SkillDefinition(
        id="test_skill",
        name="Test Skill",
        version="1.0",
        category="test",
        author="test",
        description="A test skill",
        runtime=SkillRuntime(
            type="python",
            resources=SkillResources(memory="1GB", cpu=1, time="5m"),
        ),
    )


@pytest.fixture
def sample_python_skill():
    return SkillDefinition(
        id="py_skill",
        name="Python Skill",
        version="1.0",
        category="test",
        author="test",
        description="A python test skill",
        runtime=SkillRuntime(
            type="python",
            resources=SkillResources(memory="1GB", cpu=1, time="5m"),
        ),
    )


@pytest.mark.asyncio
async def test_local_scheduler_publishes_progress(tmp_path, sample_python_skill):
    pubsub = ExecutionPubSub()
    received: list[ExecutionState] = []

    def callback(state: ExecutionState) -> None:
        received.append(state)

    scheduler = LocalScheduler(
        working_dir=tmp_path,
        progress_callback=callback,
        pubsub=pubsub,
    )

    result = await scheduler.execute(
        skill=sample_python_skill,
        code="result = {'value': 42}",
        inputs={},
        timeout_seconds=10.0,
    )

    statuses = {s.status for s in received}
    assert "PENDING" in statuses
    assert "RUNNING" in statuses
    assert "COMPLETED" in statuses
    assert result.get("value") == 42
    assert await pubsub.latest(received[-1].job_id) is not None


@pytest.mark.asyncio
async def test_local_scheduler_reports_failure(tmp_path, sample_python_skill):
    pubsub = ExecutionPubSub()
    received: list[ExecutionState] = []

    def callback(state: ExecutionState) -> None:
        received.append(state)

    scheduler = LocalScheduler(
        working_dir=tmp_path,
        progress_callback=callback,
        pubsub=pubsub,
    )

    with pytest.raises(Exception):
        await scheduler.execute(
            skill=sample_python_skill,
            code="raise ValueError('boom')",
            inputs={},
            timeout_seconds=10.0,
        )

    statuses = [s.status for s in received]
    assert "FAILED" in statuses


def test_scheduler_constructors_accept_progress_callback(tmp_path):
    pubsub = ExecutionPubSub()
    def callback(state):
        pass

    local = LocalScheduler(working_dir=tmp_path, progress_callback=callback, pubsub=pubsub)
    assert local._progress_callback is callback
    assert local._pubsub is pubsub

    slurm = SlurmScheduler(
        working_dir=tmp_path,
        progress_callback=callback,
        pubsub=pubsub,
    )
    assert slurm._progress_callback is callback

    nf = NextflowRunner(
        working_dir=tmp_path,
        progress_callback=callback,
        pubsub=pubsub,
    )
    assert nf._progress_callback is callback
