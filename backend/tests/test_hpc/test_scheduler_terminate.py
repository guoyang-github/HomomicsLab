"""Tests for scheduler terminate/cancel support."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homomics_lab.hpc.cloud_schedulers import AWSBatchScheduler, AzureBatchScheduler, GCPLifeSciencesScheduler
from homomics_lab.hpc.scheduler import LocalScheduler, NextflowRunner, SlurmScheduler
from homomics_lab.skills.sandbox import LocalSandbox


@pytest.mark.asyncio
async def test_local_scheduler_terminate_delegates_to_sandbox(tmp_path):
    sandbox = LocalSandbox(working_dir=tmp_path)
    scheduler = LocalScheduler(working_dir=tmp_path, sandbox=sandbox)

    proc = MagicMock()
    proc.returncode = None
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    sandbox._running["job_1"] = proc

    terminated = await scheduler.terminate("job_1")
    assert terminated is True
    proc.kill.assert_called_once()
    proc.wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_slurm_scheduler_terminate_calls_scancel():
    scheduler = SlurmScheduler(working_dir=Path("/tmp"))
    with patch("shutil.which", return_value="/usr/bin/scancel"):
        with patch(
            "asyncio.create_subprocess_exec",
            return_value=AsyncMock(
                communicate=AsyncMock(return_value=(b"", b"")),
                returncode=0,
            ),
        ) as mock_exec:
            terminated = await scheduler.terminate("12345")
            assert terminated is True
            mock_exec.assert_called_once_with(
                "scancel", "12345",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )


@pytest.mark.asyncio
async def test_nextflow_runner_terminate_kills_running_process(tmp_path):
    scheduler = NextflowRunner(working_dir=tmp_path)
    proc = MagicMock()
    proc.returncode = None
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    scheduler._running["nf_job"] = proc

    terminated = await scheduler.terminate("nf_job")
    assert terminated is True
    proc.kill.assert_called_once()
    proc.wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_aws_batch_terminate_calls_client():
    scheduler = AWSBatchScheduler(job_queue="queue", job_definition="def")
    scheduler._client = MagicMock()
    scheduler._client.terminate_job = MagicMock()
    terminated = await scheduler.terminate("job_id")
    assert terminated is True
    scheduler._client.terminate_job.assert_called_once_with(
        jobId="job_id", reason="HomomicsLab user cancellation"
    )


@pytest.mark.asyncio
async def test_gcp_lifesciences_terminate_calls_client():
    scheduler = GCPLifeSciencesScheduler(project="proj", location="loc")
    scheduler._client = MagicMock()
    scheduler._client.transport.operations_client.cancel_operation = MagicMock()
    terminated = await scheduler.terminate("op_name")
    assert terminated is True
    scheduler._client.transport.operations_client.cancel_operation.assert_called_once_with("op_name")


@pytest.mark.asyncio
async def test_azure_batch_terminate_calls_client():
    scheduler = AzureBatchScheduler(
        account_url="https://test.batch.core.windows.net",
        pool_id="pool",
        job_id="batch_job",
    )
    scheduler._client = MagicMock()
    terminated = await scheduler.terminate("task_id")
    assert terminated is True
    scheduler._client.task.terminate.assert_called_once_with(
        job_id="batch_job", task_id="task_id"
    )
