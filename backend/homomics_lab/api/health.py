"""Health check API endpoints."""

from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from homomics_lab.config import settings
from homomics_lab.doctor import HealthChecker
from homomics_lab.version import app_version

router = APIRouter()


class HealthStatusResponse(BaseModel):
    """Basic health / liveness response."""

    status: str
    version: str


class HealthCheckItem(BaseModel):
    """Single diagnostic check result."""

    name: str
    status: str
    message: str
    details: Dict[str, Any]


class HealthReportResponse(BaseModel):
    """Detailed health diagnostic report."""

    overall: str
    version: str
    timestamp: str
    checks: List[HealthCheckItem]


@router.get("/health", response_model=HealthStatusResponse)
async def health_basic():
    """Basic health check — returns quickly, no deep diagnostics."""
    return {"status": "ok", "version": app_version()}


@router.get("/health/live", response_model=HealthStatusResponse)
async def health_live():
    """Liveness probe: returns immediately; indicates the process is up."""
    return {"status": "alive", "version": app_version()}


@router.get("/health/ready", response_model=HealthReportResponse)
async def health_ready(request: Request):
    """Readiness probe: verifies critical dependencies are reachable."""
    skill_executor = getattr(request.app.state, "skill_executor", None)
    checker = HealthChecker(skill_executor=skill_executor)
    report = await checker.run_all_checks(
        timeout_seconds=settings.health_check_timeout_seconds
    )
    status_code = 200 if report.overall == "healthy" else 503
    return JSONResponse(content=report.to_dict(), status_code=status_code)


@router.get("/health/detail", response_model=HealthReportResponse)
async def health_detail(request: Request):
    """Detailed health check with full system diagnostics."""
    skill_executor = getattr(request.app.state, "skill_executor", None)
    checker = HealthChecker(skill_executor=skill_executor)
    report = await checker.run_all_checks(
        timeout_seconds=settings.health_check_timeout_seconds
    )
    return report.to_dict()
