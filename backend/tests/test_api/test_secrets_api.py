"""Tests for secrets API endpoints."""

import pytest
from fastapi.testclient import TestClient

from homomics_lab.config import settings
from homomics_lab.main import app
from homomics_lab.secrets import reset_secrets_manager


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_secrets_manager()
    yield
    reset_secrets_manager()


@pytest.fixture
def client(tmp_path, monkeypatch):
    # The secrets DB lives at <data_dir>/secrets.db.
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "secrets_master_key", "api-test-master-key")
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_key", "test-api-key")
    with TestClient(app) as c:
        yield c


class TestSecretsApi:
    def test_create_and_list_secret(self, client):
        response = client.post(
            "/api/secrets/",
            json={
                "key": "OPENAI_API_KEY",
                "value": "sk-api-test",
                "namespace": "llm",
                "description": "test",
            },
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "OPENAI_API_KEY"
        assert data["namespace"] == "llm"

        response = client.get("/api/secrets/llm", headers={"X-API-Key": "test-api-key"})
        assert response.status_code == 200
        secrets = response.json()
        assert len(secrets) == 1
        assert secrets[0]["key"] == "OPENAI_API_KEY"

    def test_get_secret_value(self, client):
        client.post(
            "/api/secrets/",
            json={"key": "token", "value": "abc", "namespace": "default"},
            headers={"X-API-Key": "test-api-key"},
        )
        response = client.get(
            "/api/secrets/default/token",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        assert response.json()["value"] == "abc"

    def test_update_secret(self, client):
        client.post(
            "/api/secrets",
            json={"key": "token", "value": "v1", "namespace": "default"},
            headers={"X-API-Key": "test-api-key"},
        )
        response = client.put(
            "/api/secrets/default/token",
            json={"value": "v2", "description": "updated"},
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200

        response = client.get(
            "/api/secrets/default/token",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.json()["value"] == "v2"

    def test_delete_secret(self, client):
        client.post(
            "/api/secrets/",
            json={"key": "token", "value": "abc", "namespace": "default"},
            headers={"X-API-Key": "test-api-key"},
        )
        response = client.delete(
            "/api/secrets/default/token",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        assert response.json()["deleted"] is True

        response = client.get(
            "/api/secrets/default/token",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 404

    def test_auth_required(self, client):
        response = client.get("/api/secrets/default")
        assert response.status_code == 401
