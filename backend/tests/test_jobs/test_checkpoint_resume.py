"""Tests for checkpoint-based job resume."""

import pytest

from homomics_lab.jobs.checkpoint import CheckpointRepository
from homomics_lab.jobs.constants import JobMode, JobStatus
from homomics_lab.jobs.service import JobService


@pytest.fixture
def repo(tmp_path):
    return CheckpointRepository(db_path=tmp_path / "checkpoints.db")


@pytest.mark.asyncio
async def test_checkpoint_resume_job_is_queued(repo, tmp_path, monkeypatch):
    monkeypatch.setattr("homomics_lab.config.settings.data_dir", tmp_path)

    repo.record(
        checkpoint_id="cp_1",
        job_id="job_1",
        task_id="task_1",
        status="success",
        payload={
            "session_id": "sess_1",
            "project_id": "proj_1",
            "working_memory": {"data": "state"},
            "task_tree": {"tasks": []},
            "plan_id": "plan_1",
        },
    )

    service = JobService()
    job = await service.create_checkpoint_resume_job(
        session_id="sess_1",
        project_id="proj_1",
        checkpoint_payload=repo.get_latest("job_1").payload,
        plan_id="plan_1",
    )

    assert job.status == JobStatus.QUEUED
    assert job.mode == JobMode.CHECKPOINT_RESUME
    assert job.plan_id == "plan_1"
