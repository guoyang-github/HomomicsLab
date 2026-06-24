from pathlib import Path

import pytest

from homomics_lab.config import Settings


def test_default_port():
    settings = Settings()
    assert settings.port == 8080
    assert settings.host == "0.0.0.0"
    assert settings.debug is False
    assert isinstance(settings.data_dir, Path)


def test_env_override(monkeypatch):
    monkeypatch.setenv("HOMOMICS_PORT", "9000")
    settings = Settings()
    assert settings.port == 9000


def test_app_name_default():
    settings = Settings()
    assert settings.app_name == "HomomicsLab"


def test_session_memory_settings():
    settings = Settings()
    assert settings.session_store_url == "sqlite+aiosqlite:///./data/sessions.db"
    assert settings.session_ttl_days == 90
    assert settings.enable_semantic_memory is True
    assert settings.semantic_memory_backend == "sqlite"
    assert settings.semantic_memory_postgres_url is None


def test_semantic_memory_backend_default_is_sqlite():
    settings = Settings()
    assert settings.semantic_memory_backend == "sqlite"


def test_semantic_memory_backend_accepts_postgres():
    settings = Settings(semantic_memory_backend="postgres")
    assert settings.semantic_memory_backend == "postgres"


def test_semantic_memory_backend_rejects_unknown():
    with pytest.raises(ValueError):
        Settings(semantic_memory_backend="redis")


def test_database_url_validator_accepts_sqlite_async_driver():
    settings = Settings(database_url="sqlite+aiosqlite:///./test.db")
    assert settings.database_url == "sqlite+aiosqlite:///./test.db"


def test_database_url_validator_rejects_legacy_sqlite_driver():
    with pytest.raises(ValueError):
        Settings(database_url="sqlite:///./test.db")


def test_database_url_validator_normalizes_postgres_url():
    settings = Settings(database_url="postgresql://user:pass@localhost/db")
    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost/db"

    settings2 = Settings(database_url="postgres://user:pass@localhost/db")
    assert settings2.database_url == "postgresql+asyncpg://user:pass@localhost/db"


def test_database_url_validator_preserves_asyncpg_url():
    url = "postgresql+asyncpg://user:pass@localhost/db"
    settings = Settings(database_url=url)
    assert settings.database_url == url


def test_session_store_url_validator_rejects_legacy_sqlite_driver():
    with pytest.raises(ValueError):
        Settings(session_store_url="sqlite:///./test.db")


def test_session_store_url_validator_normalizes_postgres_url():
    settings = Settings(session_store_url="postgres://user:pass@localhost/db")
    assert settings.session_store_url == "postgresql+asyncpg://user:pass@localhost/db"


def test_storage_backend_validator_rejects_unknown_backend():
    with pytest.raises(ValueError):
        Settings(storage_backend="gcs")


def test_queue_backend_validator_rejects_unknown_backend():
    with pytest.raises(ValueError):
        Settings(queue_backend="rabbitmq")


def test_masked_dump_redacts_secrets():
    settings = Settings(
        api_key="super-secret-key",
        storage_s3_secret_key="s3-secret",
    )
    data = settings.masked_dump()
    assert "super-secret-key" not in data["api_key"]
    assert "s3-secret" not in data["storage_s3_secret_key"]
    assert len(data["api_key"]) > 0


def test_rate_limit_backend_defaults_to_memory():
    settings = Settings()
    assert settings.rate_limit_backend == "memory"


def test_rate_limit_backend_rejects_unknown():
    with pytest.raises(ValueError):
        Settings(rate_limit_backend="memcached")


def test_rate_limit_redis_url_defaults_to_redis_url():
    settings = Settings(redis_url="redis://custom:6379/0")
    assert settings.rate_limit_redis_url == "redis://custom:6379/0"


def test_cors_origins_parses_comma_separated_string():
    settings = Settings(cors_origins="https://app.homomics.lab,https://admin.homomics.lab")
    assert settings.cors_origins == ["https://app.homomics.lab", "https://admin.homomics.lab"]


def test_cors_origins_accepts_list():
    settings = Settings(cors_origins=["https://a.lab", "https://b.lab"])
    assert settings.cors_origins == ["https://a.lab", "https://b.lab"]


def test_cors_origins_empty_string_becomes_none():
    settings = Settings(cors_origins="")
    assert settings.cors_origins is None


def test_hitl_threshold_defaults():
    settings = Settings()
    assert settings.hitl_confidence_threshold == 0.7
    assert settings.hitl_risk_threshold == 0.6


def test_debate_judge_backend_defaults_to_rule():
    settings = Settings()
    assert settings.debate_judge_backend == "rule"


def test_debate_judge_backend_accepts_llm():
    settings = Settings(debate_judge_backend="llm")
    assert settings.debate_judge_backend == "llm"


def test_debate_judge_backend_rejects_unknown():
    with pytest.raises(ValueError):
        Settings(debate_judge_backend="human")


def test_literature_settings_defaults():
    settings = Settings()
    assert settings.literature_retrieval_enabled is False
    assert settings.ncbi_email is None
    assert settings.ncbi_api_key is None
    assert settings.literature_cache_ttl_seconds == 3600.0
    assert settings.literature_max_results == 10


def test_literature_settings_env_override(monkeypatch):
    monkeypatch.setenv("HOMOMICS_LITERATURE_RETRIEVAL_ENABLED", "true")
    monkeypatch.setenv("HOMOMICS_NCBI_EMAIL", "test@example.com")
    monkeypatch.setenv("HOMOMICS_NCBI_API_KEY", "secret-key")
    monkeypatch.setenv("HOMOMICS_LITERATURE_CACHE_TTL_SECONDS", "120.0")
    monkeypatch.setenv("HOMOMICS_LITERATURE_MAX_RESULTS", "25")
    settings = Settings()
    assert settings.literature_retrieval_enabled is True
    assert settings.ncbi_email == "test@example.com"
    assert settings.ncbi_api_key == "secret-key"
    assert settings.literature_cache_ttl_seconds == 120.0
    assert settings.literature_max_results == 25
