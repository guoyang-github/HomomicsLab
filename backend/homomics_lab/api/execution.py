"""Execution monitoring endpoints (SSE + Nextflow webhook)."""

import asyncio
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from homomics_lab.hpc.pubsub import get_default_pubsub
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.jobs import JobService
from homomics_lab.observability.trace_store import TraceStore

router = APIRouter(tags=["execution"])


def _format_sse(data: str, event: Optional[str] = None) -> str:
    """Format a message as a Server-Sent Event."""
    message = ""
    if event:
        message += f"event: {event}\n"
    for line in data.splitlines():
        message += f"data: {line}\n"
    message += "\n"
    return message


@router.get("/{job_id}/status")
async def execution_status(
    job_id: str,
    request: Request,
) -> Dict[str, Any]:
    """Return the current status of a background job."""
    job_service: JobService = getattr(
        request.app.state, "job_service", None
    ) or JobService()
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


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    request: Request,
) -> Dict[str, Any]:
    """Cancel a queued or running background job."""
    job_service: JobService = getattr(
        request.app.state, "job_service", None
    ) or JobService()
    job = await job_service.cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "cancelled": job.status.value == "cancelled",
    }


@router.get("/{job_id}/trace")
async def get_job_trace(
    job_id: str,
    request: Request,
) -> Dict[str, Any]:
    """Return the persisted execution trace for a job."""
    trace = await TraceStore().get_trace(job_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace for job '{job_id}' not found")
    return trace.model_dump(mode="json")


@router.get("/{job_id}/events")
async def execution_events(
    job_id: str,
    request: Request,
) -> StreamingResponse:
    """Stream execution state updates for a job via SSE."""
    pubsub = getattr(request.app.state, "execution_pubsub", None) or get_default_pubsub()
    latest = await pubsub.latest(job_id)

    async def event_stream():
        # Send latest state immediately if available
        if latest is not None:
            yield _format_sse(json.dumps(latest.to_dict()), event="state")

        # Short-circuit for tests: emit latest state and exit when requested.
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


@router.post("/webhook/nextflow")
async def nextflow_webhook(
    payload: Dict[str, Any],
    request: Request,
) -> Dict[str, str]:
    """Receive Nextflow weblog events and forward them to the pubsub bus."""
    pubsub = getattr(request.app.state, "execution_pubsub", None) or get_default_pubsub()

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
