"""Execution monitoring endpoints (SSE + Nextflow webhook)."""

import asyncio
import hmac
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from homomics_lab.api.auth import require_analyst_or_admin, require_auth
from homomics_lab.api.deps import (
    get_execution_pubsub,
    get_job_service,
    get_trace_store,
)
from homomics_lab.api.rate_limit import rate_limit_dependency
from homomics_lab.api.responses import StatusResponse
from homomics_lab.config import settings

from homomics_lab.hpc.state import ExecutionState
from homomics_lab.jobs import JobService
from homomics_lab.observability.trace_store import ExecutionTrace, TraceStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["execution"])


class _TaskProgress(BaseModel):
    total: int
    pending: int
    running: int
    completed: int
    failed: int
    awaiting_human: int
    percent: int


class _ExecutionStatusResponse(BaseModel):
    job_id: str
    status: str
    mode: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    error_message: Optional[str] = None
    latest_state: Optional[Dict[str, Any]] = None


class _ExecutionTasksResponse(BaseModel):
    job_id: str
    status: str
    tasks: List[Dict[str, Any]] = Field(default_factory=list)
    progress: _TaskProgress


class _CancelJobResponse(BaseModel):
    job_id: str
    status: str
    cancelled: bool


def _format_sse(data: str, event: Optional[str] = None) -> str:
    """Format a message as a Server-Sent Event."""
    message = ""
    if event:
        message += f"event: {event}\n"
    for line in data.splitlines():
        message += f"data: {line}\n"
    message += "\n"
    return message


@router.get(
    "/{job_id}/status",
    response_model=_ExecutionStatusResponse,
    dependencies=[Depends(rate_limit_dependency), Depends(require_auth)],
)
async def execution_status(
    job_id: str,
    request: Request,
    job_service: JobService = Depends(get_job_service),
) -> Dict[str, Any]:
    """Return the current status of a background job."""
    job = await job_service.get_job(job_id)
    if job is None:
        return {"job_id": job_id, "status": "not_found"}

    latest = await job_service.pubsub.latest(job_id)
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "mode": job.mode.value,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "error_message": job.error_message,
        "latest_state": latest.to_dict() if latest else None,
    }


@router.get(
    "/{job_id}/tasks",
    response_model=_ExecutionTasksResponse,
    dependencies=[Depends(rate_limit_dependency), Depends(require_auth)],
)
async def execution_tasks(
    job_id: str,
    request: Request,
    job_service: JobService = Depends(get_job_service),
) -> Dict[str, Any]:
    """Return the current task tree snapshot for a background job."""
    job = await job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    tasks = []
    if job.task_tree is not None:
        tasks = [t.model_dump(mode="json") for t in job.task_tree.tasks]
    progress = _job_progress(job.task_tree)
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "tasks": tasks,
        "progress": progress,
    }


def _job_progress(tree: Optional[Any]) -> Dict[str, Any]:
    total = len(tree.tasks) if tree else 0
    if total == 0:
        return {
            "total": 0,
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "awaiting_human": 0,
            "percent": 0,
        }

    counts = {
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "awaiting_human": 0,
    }
    for task in tree.tasks:
        status = task.status.value
        if status in counts:
            counts[status] += 1
    counts["total"] = total
    counts["percent"] = int((counts["completed"] / total) * 100)
    return counts


@router.post(
    "/{job_id}/cancel",
    response_model=_CancelJobResponse,
    dependencies=[Depends(rate_limit_dependency), Depends(require_analyst_or_admin)],
)
async def cancel_job(
    job_id: str,
    request: Request,
    job_service: JobService = Depends(get_job_service),
) -> Dict[str, Any]:
    """Cancel a queued or running background job."""
    job = await job_service.cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "cancelled": job.status.value == "cancelled",
    }


@router.get(
    "/{job_id}/trace",
    response_model=ExecutionTrace,
    dependencies=[Depends(rate_limit_dependency), Depends(require_auth)],
)
async def get_job_trace(
    job_id: str,
    request: Request,
    trace_store: TraceStore = Depends(get_trace_store),
) -> Dict[str, Any]:
    """Return the persisted execution trace for a job."""
    trace = await trace_store.get_trace(job_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace for job '{job_id}' not found")
    return trace.model_dump(mode="json")


@router.get(
    "/{job_id}/events",
    dependencies=[Depends(rate_limit_dependency), Depends(require_auth)],
)
async def execution_events(
    job_id: str,
    request: Request,
    pubsub=Depends(get_execution_pubsub),
) -> StreamingResponse:
    """Stream execution state updates for a job via SSE."""
    async def event_stream():
        # Replay historical states so late-connecting clients can see live logs
        # and intermediate progress that was published before the SSE handshake.
        for state in pubsub.history(job_id):
            yield _format_sse(json.dumps(state.to_dict()), event="state")

        # Short-circuit for tests: emit history and exit when requested.
        if request.headers.get("x-test-disconnect") == "1":
            return

        async with pubsub.subscribe(job_id) as subscription:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    state: ExecutionState = await asyncio.wait_for(
                        subscription.__anext__(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Send a keep-alive comment and re-check disconnect
                    yield ":keep-alive\n\n"
                    continue
                yield _format_sse(json.dumps(state.to_dict()), event="state")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/webhook/nextflow", response_model=StatusResponse)
async def nextflow_webhook(
    payload: Dict[str, Any],
    request: Request,
    x_nextflow_webhook_secret: Optional[str] = Header(None, alias="X-Nextflow-Webhook-Secret"),
    pubsub=Depends(get_execution_pubsub),
) -> Dict[str, str]:
    """Receive Nextflow weblog events and forward them to the pubsub bus.

    When ``settings.auth_enabled`` is true or ``nextflow_webhook_secret`` is set,
    the request must include the ``X-Nextflow-Webhook-Secret`` header and its value
    must match the configured secret. This prevents external actors from forging
    execution state updates.
    """
    secret = settings.nextflow_webhook_secret
    if secret:
        if x_nextflow_webhook_secret is None:
            raise HTTPException(status_code=401, detail="Missing X-Nextflow-Webhook-Secret header")
        if not hmac.compare_digest(x_nextflow_webhook_secret, secret):
            raise HTTPException(status_code=403, detail="Invalid Nextflow webhook secret")
    elif settings.auth_enabled:
        raise HTTPException(
            status_code=503,
            detail="Nextflow webhook secret is not configured. Set HOMOMICS_NEXTFLOW_WEBHOOK_SECRET.",
        )
    else:
        logger.warning(
            "Accepting unauthenticated Nextflow webhook; configure HOMOMICS_NEXTFLOW_WEBHOOK_SECRET in production."
        )

    pubsub = request.app.state.execution_pubsub

    run_name = payload.get("runName") or payload.get("runId") or "unknown"
    event = payload.get("event", "UNKNOWN")
    trace = payload.get("trace", {}) or {}
    job_id = trace.get("name") or run_name

    status_map = {
        "started": "RUNNING",
        "process_submitted": "RUNNING",
        "process_started": "RUNNING",
        "process_completed": "RUNNING",
        "completed": "COMPLETED",
        "error": "FAILED",
    }
    status = status_map.get(event, "RUNNING")

    state = ExecutionState(
        job_id=job_id,
        status=status,
        current_phase=trace.get("process") or run_name,
        progress_pct=100.0 if status == "COMPLETED" else 50.0,
        scheduler_type="nextflow",
        resource_usage={
            "event": event,
            "run_name": run_name,
            "trace": trace,
        },
    )
    pubsub.publish(job_id, state)
    return {"status": "ok"}
