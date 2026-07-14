"""API endpoints for the Waiting Orchestrator (event-driven job suspend/resume)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from homomics_lab.api.auth import require_auth
from homomics_lab.api.deps import get_job_service, get_waiting_service
from homomics_lab.jobs import JobService
from homomics_lab.jobs.waiting import WaitingService

router = APIRouter(dependencies=[Depends(require_auth)])


class ResumeRequest(BaseModel):
    data: Optional[Dict[str, Any]] = None
    token: Optional[str] = None


class WaitConditionOut(BaseModel):
    wait_id: str
    job_id: str
    condition_type: str
    payload: Dict[str, Any]
    status: str
    created_at: str
    resume_data: Optional[Dict[str, Any]] = None


class ResumeResponse(BaseModel):
    wait: WaitConditionOut
    job_id: str
    job_status: Optional[str] = None


class CancelResponse(BaseModel):
    cancelled: bool


@router.get("", response_model=List[WaitConditionOut])
async def list_wait_conditions(
    job_id: Optional[str] = None,
    waiting: WaitingService = Depends(get_waiting_service),
) -> List[WaitConditionOut]:
    """List pending wait conditions, optionally filtered by job_id."""
    return [
        WaitConditionOut(**condition.to_dict())
        for condition in waiting.list_pending(job_id=job_id)
    ]


@router.get("/{wait_id}", response_model=WaitConditionOut)
async def get_wait_condition(
    wait_id: str,
    waiting: WaitingService = Depends(get_waiting_service),
) -> WaitConditionOut:
    condition = waiting.get(wait_id)
    if condition is None:
        raise HTTPException(status_code=404, detail="Wait condition not found")
    return WaitConditionOut(**condition.to_dict())


@router.post("/{wait_id}/resume", response_model=ResumeResponse)
async def resume_wait_condition(
    wait_id: str,
    body: ResumeRequest,
    waiting: WaitingService = Depends(get_waiting_service),
    job_service: JobService = Depends(get_job_service),
) -> ResumeResponse:
    """Resolve a wait condition; webhook conditions require their token.

    Resolving the condition re-queues the suspended job via the JobService
    resume callback (RESUME_HITL path).
    """
    condition = waiting.get(wait_id)
    if condition is None:
        raise HTTPException(status_code=404, detail="Wait condition not found")
    if condition.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"Wait condition already {condition.status}"
        )
    ok = await waiting.resume(wait_id, data=body.data, token=body.token)
    if not ok:
        raise HTTPException(status_code=403, detail="Invalid token")
    condition = waiting.get(wait_id)
    job = await job_service.get_job(condition.job_id)
    return ResumeResponse(
        wait=WaitConditionOut(**condition.to_dict()),
        job_id=condition.job_id,
        job_status=job.status.value if job is not None else None,
    )


@router.post("/{wait_id}/cancel", response_model=CancelResponse)
async def cancel_wait_condition(
    wait_id: str,
    waiting: WaitingService = Depends(get_waiting_service),
) -> CancelResponse:
    condition = waiting.get(wait_id)
    if condition is None:
        raise HTTPException(status_code=404, detail="Wait condition not found")
    return CancelResponse(cancelled=waiting.cancel(wait_id))
