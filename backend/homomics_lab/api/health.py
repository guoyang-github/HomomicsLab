"""Health check API endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from homomics_lab.config import settings
from homomics_lab.doctor import HealthChecker

router = APIRouter()


@router.get("/health")
async def health_basic():
    """Basic health check — returns quickly, no deep diagnostics."""
    return {"status": "ok", "version": "0.5.0"}


@router.get("/health/live")
async def health_live():
    """Liveness probe: returns immediately; indicates the process is up."""
    return {"status": "alive", "version": "0.5.0"}


@router.get("/health/ready")
async def health_ready(request: Request):
    """Readiness probe: verifies critical dependencies are reachable."""
    skill_executor = getattr(request.app.state, "skill_executor", None)
    checker = HealthChecker(skill_executor=skill_executor)
    report = await checker.run_all_checks(
        timeout_seconds=settings.health_check_timeout_seconds
    )
    status_code = 200 if report.overall == "healthy" else 503
    return JSONResponse(content=report.to_dict(), status_code=status_code)


@router.get("/health/detail")
async def health_detail(request: Request):
    """Detailed health check with full system diagnostics."""
    skill_executor = getattr(request.app.state, "skill_executor", None)
    checker = HealthChecker(skill_executor=skill_executor)
    report = await checker.run_all_checks(
        timeout_seconds=settings.health_check_timeout_seconds
    )
    return report.to_dict()
