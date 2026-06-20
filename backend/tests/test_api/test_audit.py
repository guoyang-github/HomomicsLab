"""Tests for the audit logging middleware."""

import json

import pytest
from fastapi.testclient import TestClient

from homomics_lab.config import settings
from homomics_lab.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def enable_audit(tmp_path, monkeypatch):
    from homomics_lab.api.audit import AuditLogger

    # Reset singleton so each test gets a fresh logger configuration.
    AuditLogger._instance = None

    log_path = tmp_path / "audit.log"
    monkeypatch.setattr(settings, "audit_log_enabled", True)
    monkeypatch.setattr(settings, "audit_log_path", log_path)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    yield log_path
    AuditLogger._instance = None


def test_audit_log_records_request(client, enable_audit):
    response = client.get("/api/skills/")
    assert response.status_code == 200

    log_path = enable_audit
    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) >= 1

    record = json.loads(lines[-1])
    assert record["method"] == "GET"
    assert "/api/skills/" in record["path"]
    assert record["status_code"] == 200
    assert "duration_ms" in record
    assert "correlation_id" in record


def test_audit_log_includes_user_when_auth_enabled(client, enable_audit, monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_key", "audit-test-key")

    response = client.get("/api/skills/", headers={"X-API-Key": "audit-test-key"})
    assert response.status_code == 200

    log_path = enable_audit
    lines = log_path.read_text().strip().splitlines()
    record = json.loads(lines[-1])
    assert record["user_id"] == "authenticated_user"


def test_audit_log_disabled_by_default(client, tmp_path, monkeypatch):
    log_path = tmp_path / "audit.log"
    monkeypatch.setattr(settings, "audit_log_enabled", False)
    monkeypatch.setattr(settings, "audit_log_path", log_path)

    response = client.get("/api/skills/")
    assert response.status_code == 200
    assert not log_path.exists()
