"""API endpoints for scheduled tasks."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from homomics_lab.scheduler import HomomicsScheduler

router = APIRouter(tags=["scheduler"])


def _run_to_dict(run) -> Dict[str, Any]:
    return {
        "id": run.id,
        "job_name": run.job_name,
        "trigger_time": run.trigger_time.isoformat() if run.trigger_time else None,
        "start_time": run.start_time.isoformat() if run.start_time else None,
        "end_time": run.end_time.isoformat() if run.end_time else None,
        "status": run.status,
        "result_json": run.result_json,
        "error_message": run.error_message,
    }


def _get_scheduler(request: Request) -> HomomicsScheduler:
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    return scheduler


@router.post("/jobs/{job_name}/run")
async def run_scheduled_job(
    job_name: str,
    request: Request,
) -> Dict[str, Any]:
    """Manually trigger a scheduled job immediately."""
    scheduler = _get_scheduler(request)
    try:
        run = await scheduler.run_now(job_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _run_to_dict(run)


@router.get("/runs")
async def list_scheduled_runs(
    request: Request,
    job_name: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Return recent scheduled task execution history."""
    scheduler = _get_scheduler(request)
    runs = await scheduler.recent_runs(job_name=job_name, limit=limit)
    return [_run_to_dict(r) for r in runs]
