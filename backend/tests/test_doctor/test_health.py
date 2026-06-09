"""Tests for health check / doctor diagnostics."""

from fastapi.testclient import TestClient
from homomics_lab.main import app
from homomics_lab.doctor import HealthChecker, HealthReport


client = TestClient(app)


def test_basic_health_endpoint():
    """Basic /health endpoint returns quickly."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_detailed_health_endpoint():
    """Detailed /api/health/detail returns full diagnostics."""
    response = client.get("/api/health/detail")
    assert response.status_code == 200
    data = response.json()

    assert "overall" in data
    assert data["overall"] in ("healthy", "degraded", "unhealthy")
    assert "checks" in data
    assert len(data["checks"]) > 0
    assert "timestamp" in data
    assert "version" in data


def test_health_checks_structure():
    """Each check has required fields."""
    response = client.get("/api/health/detail")
    data = response.json()

    for check in data["checks"]:
        assert "name" in check
        assert "status" in check
        assert check["status"] in ("ok", "warning", "error")
        assert "message" in check
        assert "details" in check


def test_health_checker_without_executor():
    """HealthChecker works without skill executor."""
    checker = HealthChecker(skill_executor=None)
    report = checker.run_all_checks()

    assert isinstance(report, HealthReport)
    assert report.overall in ("healthy", "degraded", "unhealthy")
    assert len(report.checks) >= 4

    # Skill system should warn when no executor
    skill_check = next(c for c in report.checks if c.name == "skill_system")
    assert skill_check.status == "warning"


def test_python_version_check():
    """Python version check passes on supported versions."""
    checker = HealthChecker()
    check = checker._check_python_version()
    assert check.status == "ok"
    assert "3." in check.message


def test_core_dependencies_check():
    """Core dependencies should all be present."""
    checker = HealthChecker()
    check = checker._check_core_dependencies()
    assert check.status == "ok"
    assert "fastapi" in check.details["versions"]


def test_hpc_schedulers_check():
    """At least local scheduler should be available."""
    checker = HealthChecker()
    check = checker._check_hpc_schedulers()
    assert check.status == "ok"
    assert "local" in check.details["available"]
