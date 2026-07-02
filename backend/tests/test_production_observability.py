"""Production observability smoke tests."""

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

from homomics_lab.config import settings
from homomics_lab.doctor import HealthChecker
from homomics_lab.logging_config import configure_logging, JsonFormatter
from homomics_lab.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_live_endpoint(client):
    """Liveness probe returns immediately without touching dependencies."""
    response = client.get("/api/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["version"] == "0.5.0"


def test_metrics_endpoint_returns_prometheus_text(client):
    """The /metrics endpoint exposes Prometheus-formatted metrics."""
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "homomicslab_info" in body or "Prometheus client not installed" in body


def test_trace_store_exposed_on_app_state(client):
    """TraceStore is initialized and attached to app.state."""
    assert hasattr(app.state, "trace_store")
    assert app.state.trace_store is not None


def test_log_level_and_format_settings_exist():
    """Log settings are part of the application config."""
    assert hasattr(settings, "log_level")
    assert hasattr(settings, "log_json_format")
    assert settings.log_level.upper() in {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }


def test_configure_logging_applies_level_and_format():
    """configure_logging replaces handlers and sets the requested level."""
    configure_logging(level="ERROR", json_format=False)
    root = logging.getLogger()
    assert root.level == logging.ERROR
    assert len(root.handlers) == 1
    formatter = root.handlers[0].formatter
    # Text formatter should not be the JSON formatter.
    assert not isinstance(formatter, JsonFormatter)


@pytest.mark.asyncio
async def test_health_checker_respects_timeout(monkeypatch):
    """A check that exceeds timeout_seconds is reported as an error."""

    async def _slow_check(self):
        await asyncio.sleep(10)
        return None  # pragma: no cover

    monkeypatch.setattr(HealthChecker, "_check_database", _slow_check)
    checker = HealthChecker(skill_executor=None)
    report = await checker.run_all_checks(timeout_seconds=0.1)
    db_check = next((c for c in report.checks if c.name == "database"), None)
    assert db_check is not None
    assert db_check.status == "error"
    assert "timed out" in db_check.message
