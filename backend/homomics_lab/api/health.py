"""Health check API endpoints."""

from fastapi import APIRouter, Request

from homomics_lab.doctor import HealthChecker

router = APIRouter()


@router.get("/health")
async def health_basic():
    """Basic health check — returns quickly, no deep diagnostics."""
    return {"status": "ok", "version": "0.1.0"}


@router.get("/health/detail")
async def health_detail(request: Request):
    """Detailed health check with full system diagnostics."""
    skill_executor = getattr(request.app.state, "skill_executor", None)
    checker = HealthChecker(skill_executor=skill_executor)
    report = checker.run_all_checks()
    return report.to_dict()
