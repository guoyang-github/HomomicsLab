"""Health check API endpoints."""

from fastapi import APIRouter, Request

from homomics_lab.doctor import HealthChecker

router = APIRouter()


@router.get("/health")
async def health_basic():
    """Basic health check — returns quickly, no deep diagnostics."""
    return {"status": "ok", "version": "0.5.0"}


@router.get("/health/ready")
async def health_ready(request: Request):
    """Readiness probe: verifies critical dependencies are reachable."""
    skill_executor = getattr(request.app.state, "skill_executor", None)
    checker = HealthChecker(skill_executor=skill_executor)
    report = await checker.run_all_checks()
    # A readiness check should return a non-2xx status when not ready.
    from fastapi.responses import JSONResponse

    status_code = 200 if report.overall == "healthy" else 503
    return JSONResponse(content=report.to_dict(), status_code=status_code)


@router.get("/health/detail")
async def health_detail(request: Request):
    """Detailed health check with full system diagnostics."""
    skill_executor = getattr(request.app.state, "skill_executor", None)
    checker = HealthChecker(skill_executor=skill_executor)
    report = await checker.run_all_checks()
    return report.to_dict()
