"""API endpoints for job checkpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from homomics_lab.api.auth import require_auth
from homomics_lab.jobs.checkpoint import CheckpointRepository

router = APIRouter(dependencies=[Depends(require_auth)])


def get_checkpoint_repository() -> CheckpointRepository:
    return CheckpointRepository()


class CheckpointCreate(BaseModel):
    checkpoint_id: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    phase: Optional[str] = None
    status: str = Field(default="success")
    payload: Dict[str, Any] = Field(default_factory=dict)


class CheckpointOut(BaseModel):
    checkpoint_id: str
    job_id: str
    task_id: str
    phase: Optional[str]
    status: str
    payload: Dict[str, Any]
    created_at: str


class DeleteCheckpointResponse(BaseModel):
    deleted: bool


class ResumeFromCheckpointResponse(BaseModel):
    new_job_id: str
    checkpoint_id: str


@router.post("/{job_id}/checkpoints", response_model=CheckpointOut)
async def record_checkpoint(
    job_id: str,
    body: CheckpointCreate,
    repo: CheckpointRepository = Depends(get_checkpoint_repository),
) -> CheckpointOut:
    cp = repo.record(
        checkpoint_id=body.checkpoint_id,
        job_id=job_id,
        task_id=body.task_id,
        phase=body.phase,
        status=body.status,
        payload=body.payload,
    )
    return _to_out(cp)


@router.get("/{job_id}/checkpoints/latest", response_model=CheckpointOut)
async def get_latest_checkpoint(
    job_id: str,
    status: Optional[str] = None,
    repo: CheckpointRepository = Depends(get_checkpoint_repository),
) -> CheckpointOut:
    cp = repo.get_latest(job_id, status=status)
    if cp is None:
        raise HTTPException(status_code=404, detail="No checkpoint found")
    return _to_out(cp)


@router.get("/{job_id}/checkpoints", response_model=List[CheckpointOut])
async def list_checkpoints(
    job_id: str,
    task_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    repo: CheckpointRepository = Depends(get_checkpoint_repository),
) -> List[CheckpointOut]:
    checkpoints = repo.list_by_job(job_id, task_id=task_id, status=status, limit=limit)
    return [_to_out(cp) for cp in checkpoints]


@router.get("/{job_id}/checkpoints/{checkpoint_id}", response_model=CheckpointOut)
async def get_checkpoint(
    job_id: str,
    checkpoint_id: str,
    repo: CheckpointRepository = Depends(get_checkpoint_repository),
) -> CheckpointOut:
    cp = repo.get(checkpoint_id)
    if cp is None or cp.job_id != job_id:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return _to_out(cp)


@router.delete(
    "/{job_id}/checkpoints/{checkpoint_id}", response_model=DeleteCheckpointResponse
)
async def delete_checkpoint(
    job_id: str,
    checkpoint_id: str,
    repo: CheckpointRepository = Depends(get_checkpoint_repository),
) -> DeleteCheckpointResponse:
    cp = repo.get(checkpoint_id)
    if cp is None or cp.job_id != job_id:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    repo.delete(checkpoint_id)
    return DeleteCheckpointResponse(deleted=True)


@router.post("/{job_id}/resume", response_model=ResumeFromCheckpointResponse)
async def resume_from_checkpoint(
    job_id: str,
    repo: CheckpointRepository = Depends(get_checkpoint_repository),
) -> ResumeFromCheckpointResponse:
    """Enqueue a checkpoint-resume job for the given job_id."""
    from homomics_lab.jobs.service import JobService

    cp = repo.get_latest(job_id, status="success")
    if cp is None:
        raise HTTPException(status_code=404, detail="No success checkpoint found")

    service = JobService()
    new_job = await service.create_checkpoint_resume_job(
        session_id=cp.payload.get("session_id", "resume"),
        project_id=cp.payload.get("project_id", "default"),
        checkpoint_payload=cp.payload,
        plan_id=cp.payload.get("plan_id"),
    )
    return ResumeFromCheckpointResponse(
        new_job_id=new_job.job_id, checkpoint_id=cp.checkpoint_id
    )


def _to_out(cp) -> CheckpointOut:
    return CheckpointOut(
        checkpoint_id=cp.checkpoint_id,
        job_id=cp.job_id,
        task_id=cp.task_id,
        phase=cp.phase,
        status=cp.status,
        payload=cp.payload,
        created_at=cp.created_at.isoformat(),
    )
