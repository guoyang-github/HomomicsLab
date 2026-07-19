"""Tests for the runtime LLM settings API."""

import pytest

from homomics_lab.config import settings
from homomics_lab.llm.providers import reset_provider_registry
from homomics_lab.secrets import reset_secrets_manager


@pytest.fixture(autouse=True)
def reset_singletons():
    reset_secrets_manager()
    reset_provider_registry()
    yield
    reset_secrets_manager()
    reset_provider_registry()


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch, tmp_path):
    # SecretsManager and the runtime settings store both use settings.data_dir at
    # call time. Point each test at its own temp directory so writes from one
    # test do not leak to another when sharing the module-scoped TestClient.
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "secrets_master_key", "settings-test-master-key")
    # Make sure env-level defaults do not leak into these tests.
    monkeypatch.setattr(settings, "llm_provider", None)
    monkeypatch.setattr(settings, "llm_model", None)


class TestLlmSettingsApi:
    def test_get_llm_config_fallback(self, client, monkeypatch):
        monkeypatch.setattr(settings, "llm_provider", "openai")
        monkeypatch.setattr(settings, "llm_model", "gpt-4o")

        response = client.get("/api/settings/llm", headers={"X-API-Key": "test-api-key"})
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-4o"
        assert data.get("api_key") is None

    def test_update_llm_config_persists_and_reloads(self, client):
        response = client.put(
            "/api/settings/llm",
            json={
                "provider": "moonshot",
                "model": "moonshot-v1-8k",
                "base_url": "https://api.moonshot.cn/v1",
                "api_key": "sk-ms-test",
                "temperature": 0.5,
                "max_tokens": 2048,
            },
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["provider"] == "moonshot"
        assert data["model"] == "moonshot-v1-8k"
        assert data["api_key"] is None or "..." in (data["api_key"] or "")

        response = client.get("/api/settings/llm", headers={"X-API-Key": "test-api-key"})
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "moonshot"
        assert data["model"] == "moonshot-v1-8k"
        assert data["base_url"] == "https://api.moonshot.cn/v1"

    def test_update_custom_provider_requires_url_and_key(self, client):
        response = client.put(
            "/api/settings/llm",
            json={
                "provider": "custom",
                "model": "my-model",
                "api_key": "secret",
            },
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 422

        response = client.put(
            "/api/settings/llm",
            json={
                "provider": "custom",
                "model": "my-model",
                "base_url": "http://localhost:9999/v1",
            },
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 422

    def test_update_custom_provider_succeeds(self, client):
        response = client.put(
            "/api/settings/llm",
            json={
                "provider": "custom",
                "model": "my-model",
                "base_url": "http://localhost:9999/v1",
                "api_key": "secret",
            },
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["provider"] == "custom"
        assert data["model"] == "my-model"

    def test_test_connection_reports_failure_for_bad_key(self, client, monkeypatch):
        from unittest.mock import AsyncMock

        client.put(
            "/api/settings/llm",
            json={
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": "sk-invalid",
            },
            headers={"X-API-Key": "test-api-key"},
        )
        # Avoid real network calls and the retry/fallback chain in this unit test.
        llm_client = client.app.state.llm_client
        monkeypatch.setattr(
            llm_client, "chat_completion", AsyncMock(side_effect=Exception("bad key"))
        )
        response = client.post(
            "/api/settings/llm/test",
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-4o-mini"
        assert "error" in data


class TestSystemSettingsApi:
    def test_get_system_settings_fallback(self, client):
        response = client.get("/api/settings/system", headers={"X-API-Key": "test-api-key"})
        assert response.status_code == 200
        data = response.json()
        assert "skill_sandbox_backend" in data

    def test_update_system_settings_persists(self, client, tmp_path):
        response = client.put(
            "/api/settings/system",
            json={"skill_sandbox_backend": "container"},
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["skill_sandbox_backend"] == "container"

        # Verify persistence by reading back
        response = client.get("/api/settings/system", headers={"X-API-Key": "test-api-key"})
        assert response.status_code == 200
        data = response.json()
        assert data["skill_sandbox_backend"] == "container"

    def test_update_system_settings_rejects_invalid_backend(self, client):
        response = client.put(
            "/api/settings/system",
            json={"skill_sandbox_backend": "invalid"},
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 422

    def test_update_system_settings_applies_in_memory(self, client, monkeypatch):
        from homomics_lab.config import settings as cfg

        monkeypatch.setattr(cfg, "skill_sandbox_backend", "local")
        response = client.put(
            "/api/settings/system",
            json={"skill_sandbox_backend": "bubblewrap"},
            headers={"X-API-Key": "test-api-key"},
        )
        assert response.status_code == 200
        assert cfg.skill_sandbox_backend == "bubblewrap"
