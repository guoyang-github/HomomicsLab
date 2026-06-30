"""Reproducibility bundle download endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from homomics_lab.api.auth import require_auth
from homomics_lab.api.rate_limit import rate_limit_dependency
from homomics_lab.config import settings
from homomics_lab.jobs import JobService
from homomics_lab.workspace.manager import WorkspaceManager

router = APIRouter(tags=["reproducibility"])


def _bundle_paths(project_id: str, job_id: str) -> list[Path]:
    """Return candidate bundle paths for a job, preferring the job-scoped file."""
    workspace = WorkspaceManager(base_dir=settings.data_dir, project_id=project_id)
    return [
        workspace.get_path(f".metadata/reproducibility_bundle_{job_id}.json"),
        workspace.get_path(".metadata/reproducibility_bundle.json"),
    ]


@router.get(
    "/{job_id}/bundle",
    response_model=None,
    dependencies=[Depends(rate_limit_dependency), Depends(require_auth)],
)
async def get_reproducibility_bundle(
    job_id: str,
    request: Request,
    download: bool = Query(False, description="Return the bundle as a downloadable file."),
):
    """Return the reproducibility bundle for a completed background job.

    When ``download=true`` the bundle is returned as a JSON attachment.
    """
    job_service: JobService = getattr(
        request.app.state, "job_service", None
    ) or JobService()
    job = await job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    project_id = job.project_id or "default"
    for path in _bundle_paths(project_id, job_id):
        if path.exists():
            if download:
                return FileResponse(
                    path=path,
                    media_type="application/json",
                    filename=f"reproducibility_bundle_{job_id}.json",
                    content_disposition_type="attachment",
                )
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Bundle file is not valid JSON: {exc}",
                ) from exc

    raise HTTPException(
        status_code=404,
        detail=f"Reproducibility bundle for job '{job_id}' not found",
    )
