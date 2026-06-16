"""Tests for the checkpoint repository."""

import pytest

from homomics_lab.jobs.checkpoint import CheckpointRepository


@pytest.fixture
def repo(tmp_path):
    return CheckpointRepository(db_path=tmp_path / "checkpoints.db")


class TestCheckpointRepository:
    def test_record_and_get(self, repo):
        cp = repo.record(
            checkpoint_id="cp_1",
            job_id="job_1",
            task_id="task_1",
            phase="qc",
            payload={"adata": "path/to/adata.h5ad"},
        )
        assert cp.job_id == "job_1"
        assert cp.task_id == "task_1"
        assert cp.phase == "qc"

        fetched = repo.get("cp_1")
        assert fetched is not None
        assert fetched.payload["adata"] == "path/to/adata.h5ad"

    def test_get_latest(self, repo):
        repo.record("cp_1", "job_1", "task_1", payload={"step": 1})
        repo.record("cp_2", "job_1", "task_2", payload={"step": 2})
        repo.record("cp_3", "job_2", "task_1", payload={"step": 3})

        latest = repo.get_latest("job_1")
        assert latest is not None
        assert latest.checkpoint_id == "cp_2"

    def test_list_by_job(self, repo):
        repo.record("cp_1", "job_1", "task_1", status="success", payload={})
        repo.record("cp_2", "job_1", "task_2", status="failure", payload={})
        repo.record("cp_3", "job_1", "task_1", status="success", payload={})

        all_cps = repo.list_by_job("job_1")
        assert len(all_cps) == 3

        task_cps = repo.list_by_job("job_1", task_id="task_1")
        assert len(task_cps) == 2

        success_cps = repo.list_by_job("job_1", status="success")
        assert len(success_cps) == 2

    def test_delete(self, repo):
        repo.record("cp_1", "job_1", "task_1", payload={})
        assert repo.delete("cp_1") is True
        assert repo.get("cp_1") is None
        assert repo.delete("cp_1") is False
