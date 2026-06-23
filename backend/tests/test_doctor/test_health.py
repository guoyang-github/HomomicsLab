"""Tests for health check / doctor diagnostics."""

import pytest
from fastapi.testclient import TestClient

from homomics_lab.doctor import HealthChecker, HealthReport
from homomics_lab.main import app


client = TestClient(app)


def test_basic_health_endpoint():
    """Basic /health endpoint returns quickly and publicly."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.5.0"


def test_health_ready_endpoint():
    """Readiness endpoint returns diagnostics and a valid HTTP status."""
    response = client.get("/api/health/ready")
    assert response.status_code in {200, 503}
    data = response.json()
    assert data["overall"] in {"healthy", "degraded", "unhealthy"}
    assert data["version"] == "0.5.0"
    assert data["timestamp"]
    assert data["checks"]
    for check in data["checks"]:
        assert "name" in check
        assert "status" in check
        assert check["status"] in {"ok", "warning", "error"}
        assert "message" in check


def test_detailed_health_endpoint():
    """Detailed /api/health/detail returns full diagnostics."""
    response = client.get("/api/health/detail")
    assert response.status_code == 200
    data = response.json()
    assert data["overall"] in {"healthy", "degraded", "unhealthy"}
    assert data["checks"]
    assert data["timestamp"]
    assert data["version"] == "0.5.0"


@pytest.mark.asyncio
async def test_health_checker_without_executor():
    """HealthChecker works without skill executor."""
    checker = HealthChecker(skill_executor=None)
    report = await checker.run_all_checks()
    assert isinstance(report, HealthReport)
    assert report.overall in {"healthy", "degraded", "unhealthy"}
    assert len(report.checks) >= 4
    check_names = {c.name for c in report.checks}
    assert check_names >= {"database", "redis", "storage", "skill_system"}


@pytest.mark.asyncio
async def test_database_check():
    checker = HealthChecker()
    result = await checker._check_database()
    assert result.status in {"ok", "error"}
    assert "Database" in result.message


@pytest.mark.asyncio
async def test_redis_check_when_not_enabled():
    from homomics_lab.config import settings

    original = settings.queue_backend
    try:
        settings.queue_backend = "memory"
        checker = HealthChecker()
        result = await checker._check_redis()
        assert result.status == "ok"
        assert "not enabled" in result.message
    finally:
        settings.queue_backend = original


@pytest.mark.asyncio
async def test_storage_check():
    checker = HealthChecker()
    result = await checker._check_storage()
    assert result.status in {"ok", "error"}


def test_url_masking_strips_credentials():
    masked = HealthChecker._mask_url("postgresql://user:secret@localhost:5432/db")
    assert "secret" not in masked
    assert "user@" not in masked
    assert masked == "postgresql://localhost:5432/db"
