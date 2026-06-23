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
