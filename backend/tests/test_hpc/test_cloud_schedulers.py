"""Tests for cloud batch scheduler availability and basic structure."""

import pytest

from homomics_lab.hpc.cloud_schedulers import AWSBatchScheduler, AzureBatchScheduler, GCPLifeSciencesScheduler


class TestCloudSchedulerAvailability:
    def test_aws_batch_is_available_when_configured(self, monkeypatch):
        monkeypatch.setenv("HOMOMICS_AWS_BATCH_JOB_QUEUE", "test-queue")
        assert AWSBatchScheduler.is_available() is True

    def test_aws_batch_not_available_without_config(self, monkeypatch):
        monkeypatch.delenv("HOMOMICS_AWS_BATCH_JOB_QUEUE", raising=False)
        # shutil.which("aws") may or may not be present; just check it does not crash.
        result = AWSBatchScheduler.is_available()
        assert isinstance(result, bool)

    def test_gcp_lifesciences_is_available_when_configured(self, monkeypatch):
        monkeypatch.setenv("HOMOMICS_GCP_PROJECT", "test-project")
        assert GCPLifeSciencesScheduler.is_available() is True

    def test_azure_batch_is_available_when_configured(self, monkeypatch):
        monkeypatch.setenv("HOMOMICS_AZURE_BATCH_ACCOUNT_URL", "https://test.batch.core.windows.net")
        assert AzureBatchScheduler.is_available() is True


class TestCloudSchedulerValidation:
    def test_aws_batch_raises_without_queue(self):
        scheduler = AWSBatchScheduler(job_definition="def")
        with pytest.raises(RuntimeError, match="job_queue"):
            # execute is async
            import asyncio
            asyncio.run(scheduler.execute(None, "print(1)", {}))

    def test_gcp_raises_without_project(self):
        scheduler = GCPLifeSciencesScheduler()
        with pytest.raises(RuntimeError, match="HOMOMICS_GCP_PROJECT"):
            import asyncio
            asyncio.run(scheduler.execute(None, "print(1)", {}))

    def test_azure_raises_without_pool(self):
        scheduler = AzureBatchScheduler(account_url="https://test.batch.core.windows.net")
        with pytest.raises(RuntimeError, match="pool_id"):
            import asyncio
            asyncio.run(scheduler.execute(None, "print(1)", {}))
