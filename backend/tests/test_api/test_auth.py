"""Tests for authentication and authorization."""

import pytest
from fastapi.testclient import TestClient

from homomics_lab.config import settings
from homomics_lab.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def enable_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_key", "test-secret-key")


@pytest.fixture
def disable_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", False)


class TestAuthDisabled:
    def test_no_auth_required_by_default(self, client, disable_auth):
        response = client.get("/api/skills/")
        assert response.status_code == 200


class TestAuthEnabled:
    def test_missing_key_returns_401(self, client, enable_auth):
        response = client.get("/api/skills/")
        assert response.status_code == 401

    def test_invalid_key_returns_403(self, client, enable_auth):
        response = client.get("/api/skills/", headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 403

    def test_valid_header_key_returns_200(self, client, enable_auth):
        response = client.get("/api/skills/", headers={"X-API-Key": "test-secret-key"})
        assert response.status_code == 200

    def test_valid_bearer_token_returns_200(self, client, enable_auth):
        response = client.get(
            "/api/skills/",
            headers={"Authorization": "Bearer test-secret-key"},
        )
        assert response.status_code == 200

    def test_public_endpoints_remain_unauthenticated(self, client, enable_auth):
        # Root, health and metrics are defined directly on app, not under api_router.
        assert client.get("/").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/metrics").status_code in (200, 500)  # prometheus may or may not be installed
