"""Cloud batch schedulers: AWS Batch, GCP Life Sciences, Azure Batch.

These schedulers wrap cloud-native batch services so HomomicsLab can offload
long-running skills to elastic compute. Each scheduler is optional; it only
requires its cloud SDK when actually instantiated.
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict, Optional
from uuid import uuid4

from homomics_lab.hpc.scheduler import BaseScheduler, ExecutionResult
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.skills.models import SkillDefinition


class AWSBatchScheduler(BaseScheduler):
    """Submit skills as AWS Batch jobs."""

    def __init__(self, *args, job_queue: Optional[str] = None, job_definition: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_queue = job_queue or os.environ.get("HOMOMICS_AWS_BATCH_JOB_QUEUE")
        self.job_definition = job_definition or os.environ.get("HOMOMICS_AWS_BATCH_JOB_DEFINITION")
        self._client = None

    @classmethod
    def is_available(cls) -> bool:
        return bool(
            shutil.which("aws") or os.environ.get("HOMOMICS_AWS_BATCH_JOB_QUEUE")
        )

    def _get_client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("batch")
        return self._client

    async def terminate(self, job_id: str) -> bool:
        """Cancel a running AWS Batch job."""
        try:
            self._get_client().terminate_job(jobId=job_id, reason="HomomicsLab user cancellation")
            return True
        except Exception:
            return False

    async def execute(
        self,
        skill: SkillDefinition,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
    ) -> Dict[str, Any]:
        if not self.job_queue or not self.job_definition:
            raise RuntimeError("AWS Batch job_queue and job_definition must be configured")

        job_name = f"homomics-{skill.id}-{uuid4().hex[:8]}"
        payload = json.dumps({"code": code, "inputs": inputs, "skill_id": skill.id})

        try:
            response = self._get_client().submit_job(
                jobName=job_name,
                jobQueue=self.job_queue,
                jobDefinition=self.job_definition,
                parameters={"payload": payload},
                containerOverrides={
                    "resourceRequirements": [
                        {"type": "VCPU", "value": "2"},
                        {"type": "MEMORY", "value": "4096"},
                    ]
                },
            )
            job_id = response["jobId"]
        except Exception as exc:
            return ExecutionResult(
                status="failed",
                output={},
                error_message=f"AWS Batch submit failed: {exc}",
            ).to_dict()

        # Poll until completion.
        return await self._poll_aws_batch(job_id, timeout_seconds)

    async def _poll_aws_batch(self, job_id: str, timeout_seconds: float) -> Dict[str, Any]:
        import asyncio
        client = self._get_client()
        waited = 0.0
        interval = 10.0
        while waited < timeout_seconds:
            response = client.describe_jobs(jobs=[job_id])
            status = response["jobs"][0]["status"]
            self._report_progress(
                ExecutionState(
                    job_id=job_id,
                    status=status,
                    current_phase="aws_batch",
                    scheduler_type="aws_batch",
                )
            )
            if status == "SUCCEEDED":
                return ExecutionResult(status="completed", output={"job_id": job_id}).to_dict()
            if status == "FAILED":
                reason = response["jobs"][0].get("statusReason", "unknown")
                return ExecutionResult(
                    status="failed",
                    output={},
                    error_message=reason,
                    job_id=job_id,
                ).to_dict()
            await asyncio.sleep(interval)
            waited += interval
        return ExecutionResult(
            status="timeout",
            output={},
            error_message="AWS Batch job did not complete within timeout",
            job_id=job_id,
        ).to_dict()


class GCPLifeSciencesScheduler(BaseScheduler):
    """Submit skills as Google Cloud Life Sciences pipelines."""

    def __init__(self, *args, location: Optional[str] = None, project: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project or os.environ.get("HOMOMICS_GCP_PROJECT")
        self.location = location or os.environ.get("HOMOMICS_GCP_LOCATION", "us-central1")
        self._client = None

    @classmethod
    def is_available(cls) -> bool:
        return bool(
            shutil.which("gcloud") or os.environ.get("HOMOMICS_GCP_PROJECT")
        )

    def _get_client(self):
        if self._client is None:
            from google.cloud import lifesciences_v2beta
            self._client = lifesciences_v2beta.WorkflowsServiceV2BetaClient()
        return self._client

    async def terminate(self, job_id: str) -> bool:
        """Cancel a running GCP Life Sciences operation."""
        try:
            client = self._get_client()
            client.transport.operations_client.cancel_operation(job_id)
            return True
        except Exception:
            return False

    async def execute(
        self,
        skill: SkillDefinition,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
    ) -> Dict[str, Any]:
        if not self.project:
            raise RuntimeError("HOMOMICS_GCP_PROJECT must be configured")

        run_id = f"homomics-{skill.id}-{uuid4().hex[:8]}"
        # Minimal pipeline: run a container that executes the skill code.
        # Real usage would stage inputs/outputs to GCS.
        pipeline = {
            "pipeline": {
                "actions": [
                    {
                        "image_uri": "python:3.11-slim",
                        "commands": ["python", "-c", code],
                    }
                ],
                "resources": {"cpu_cores": 2, "ram_gb": 4},
            },
            "labels": {"homomics-skill": skill.id, "homomics-run": run_id},
        }

        try:
            response = self._get_client().run_pipeline(
                parent=f"projects/{self.project}/locations/{self.location}",
                pipeline=pipeline["pipeline"],
                labels=pipeline["labels"],
            )
            operation_name = response.operation.name
        except Exception as exc:
            return ExecutionResult(
                status="failed",
                output={},
                error_message=f"GCP Life Sciences submit failed: {exc}",
            ).to_dict()

        return await self._poll_gcp(operation_name, timeout_seconds)

    async def _poll_gcp(self, operation_name: str, timeout_seconds: float) -> Dict[str, Any]:
        import asyncio
        client = self._get_client()
        waited = 0.0
        interval = 10.0
        while waited < timeout_seconds:
            operation = client.transport.operations_client.get_operation(operation_name)
            self._report_progress(
                ExecutionState(
                    job_id=operation_name,
                    status="RUNNING" if not operation.done else "SUCCEEDED" if operation.response else "FAILED",
                    current_phase="gcp_lifesciences",
                    scheduler_type="gcp_lifesciences",
                )
            )
            if operation.done:
                if operation.error:
                    return ExecutionResult(
                        status="failed",
                        output={},
                        error_message=str(operation.error),
                        job_id=operation_name,
                    ).to_dict()
                return ExecutionResult(status="completed", output={"operation": operation_name}).to_dict()
            await asyncio.sleep(interval)
            waited += interval
        return ExecutionResult(
            status="timeout",
            output={},
            error_message="GCP Life Sciences job did not complete within timeout",
            job_id=operation_name,
        ).to_dict()


class AzureBatchScheduler(BaseScheduler):
    """Submit skills to Azure Batch."""

    def __init__(
        self,
        *args,
        account_url: Optional[str] = None,
        pool_id: Optional[str] = None,
        job_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.account_url = account_url or os.environ.get("HOMOMICS_AZURE_BATCH_ACCOUNT_URL")
        self.pool_id = pool_id or os.environ.get("HOMOMICS_AZURE_BATCH_POOL_ID")
        self.batch_job_id = job_id or os.environ.get("HOMOMICS_AZURE_BATCH_JOB_ID", "homomics-job")
        self._client = None

    @classmethod
    def is_available(cls) -> bool:
        return bool(
            shutil.which("az") or os.environ.get("HOMOMICS_AZURE_BATCH_ACCOUNT_URL")
        )

    def _get_client(self):
        if self._client is None:
            from azure.batch import BatchServiceClient
            from azure.identity import DefaultAzureCredential
            cred = DefaultAzureCredential()
            self._client = BatchServiceClient(credential=cred, batch_url=self.account_url)
        return self._client

    async def terminate(self, job_id: str) -> bool:
        """Cancel a running Azure Batch task."""
        try:
            self._get_client().task.terminate(job_id=self.batch_job_id, task_id=job_id)
            return True
        except Exception:
            return False

    async def execute(
        self,
        skill: SkillDefinition,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
    ) -> Dict[str, Any]:
        if not self.account_url or not self.pool_id:
            raise RuntimeError("Azure Batch account_url and pool_id must be configured")

        task_id = f"homomics-{skill.id}-{uuid4().hex[:8]}"
        command = f"python -c {json.dumps(code)}"

        try:
            from azure.batch.models import TaskAddParameter

            self._get_client().task.add(
                job_id=self.batch_job_id,
                task=TaskAddParameter(
                    id=task_id,
                    command_line=command,
                    pool_info={"pool_id": self.pool_id},
                ),
            )
        except Exception as exc:
            return ExecutionResult(
                status="failed",
                output={},
                error_message=f"Azure Batch submit failed: {exc}",
            ).to_dict()

        return await self._poll_azure(task_id, timeout_seconds)

    async def _poll_azure(self, task_id: str, timeout_seconds: float) -> Dict[str, Any]:
        import asyncio
        client = self._get_client()
        waited = 0.0
        interval = 10.0
        while waited < timeout_seconds:
            task = client.task.get(job_id=self.batch_job_id, task_id=task_id)
            status = task.state.value if task.state else "unknown"
            self._report_progress(
                ExecutionState(
                    job_id=task_id,
                    status=status,
                    current_phase="azure_batch",
                    scheduler_type="azure_batch",
                )
            )
            if status == "completed":
                return ExecutionResult(status="completed", output={"task_id": task_id}).to_dict()
            if status == "failed":
                return ExecutionResult(
                    status="failed",
                    output={},
                    error_message=task.execution_information.failure_information.message if task.execution_information else "unknown",
                    job_id=task_id,
                ).to_dict()
            await asyncio.sleep(interval)
            waited += interval
        return ExecutionResult(
            status="timeout",
            output={},
            error_message="Azure Batch task did not complete within timeout",
            job_id=task_id,
        ).to_dict()
