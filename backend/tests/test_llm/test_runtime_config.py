"""Tests for LLM runtime configuration loading and persistence."""

import pytest

from homomics_lab.config import settings
from homomics_lab.llm.runtime_config import (
    LLMRuntimeConfig,
    load_llm_runtime_config,
    save_llm_runtime_config,
)
from homomics_lab.secrets import get_secrets_manager, reset_secrets_manager


@pytest.fixture(autouse=True)
def reset_singleton(tmp_path, monkeypatch):
    reset_secrets_manager()
    # SecretsManager uses settings.data_dir as the default DB parent.
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "secrets_master_key", "runtime-test-key")
    yield
    reset_secrets_manager()


class TestRuntimeConfig:
    def test_load_defaults_when_empty(self, monkeypatch):
        monkeypatch.setattr(settings, "llm_provider", "deepseek")
        monkeypatch.setattr(settings, "llm_model", "deepseek-chat")

        config = load_llm_runtime_config()
        assert config.provider == "deepseek"
        assert config.model == "deepseek-chat"
        assert config.api_key is None

    def test_save_and_load_roundtrip(self):
        save_llm_runtime_config(
            LLMRuntimeConfig(
                provider="qwen",
                model="qwen-turbo",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key="sk-qwen-test",
                temperature=0.7,
                max_tokens=1024,
            )
        )

        config = load_llm_runtime_config()
        assert config.provider == "qwen"
        assert config.model == "qwen-turbo"
        assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert config.api_key == "sk-qwen-test"
        assert config.temperature == 0.7
        assert config.max_tokens == 1024

    def test_api_key_is_encrypted_at_rest(self, tmp_path):
        save_llm_runtime_config(
            LLMRuntimeConfig(provider="openai", model="gpt-4o", api_key="sk-secret")
        )
        # Read raw SQLite value and ensure it is not plaintext.
        import sqlite3

        db_path = tmp_path / "secrets.db"
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT value FROM secrets WHERE namespace = 'llm' AND key = 'api_key'"
            ).fetchone()
        assert row is not None
        assert "sk-secret" not in row[0]

    def test_frontend_dict_masks_key(self):
        config = LLMRuntimeConfig(provider="openai", model="gpt-4o", api_key="sk-abcdef123456")
        frontend = config.to_frontend_dict()
        assert frontend["provider"] == "openai"
        assert "..." in (frontend["api_key"] or "")
        assert "abcdef" not in (frontend["api_key"] or "")

    def test_local_provider_defaults_fallback_to_primary_model(self, monkeypatch):
        monkeypatch.setattr(settings, "llm_provider", "ollama")
        monkeypatch.setattr(settings, "llm_model", "qwen2.5:1.5b")

        config = load_llm_runtime_config()
        assert config.provider == "ollama"
        assert config.model == "qwen2.5:1.5b"
        # Must not contain cloud-only fallback models such as gpt-4o-mini.
        assert config.fallback_models == ["qwen2.5:1.5b"]
        assert "gpt-4o-mini" not in config.fallback_models
