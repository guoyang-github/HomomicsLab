from pathlib import Path

import pytest

from homomics_lab.config import Settings


def test_default_port():
    settings = Settings()
    assert settings.port == 8080
    assert settings.debug is False
    assert isinstance(settings.data_dir, Path)


def test_env_override(monkeypatch):
    monkeypatch.setenv("HOMOMICS_PORT", "9000")
    settings = Settings()
    assert settings.port == 9000


def test_session_store_url_anchored_to_backend():
    # Pass the default value explicitly so the assertion does not depend on
    # process env (other tests may override HOMOMICS_SESSION_STORE_URL).
    settings = Settings(session_store_url="sqlite+aiosqlite:///./data/sessions.db")
    # Relative SQLite URLs are anchored to the backend directory at load time
    # (see _abs_sqlite_url), so the resolved value is an absolute path.
    assert settings.session_store_url.startswith("sqlite+aiosqlite:///")
    assert settings.session_store_url.endswith("/data/sessions.db")


def test_database_url_validator_accepts_sqlite_async_driver():
    settings = Settings(database_url="sqlite+aiosqlite:///./test.db")
    # Relative SQLite URLs are resolved to absolute paths anchored at the
    # backend directory (see _abs_sqlite_url).
    assert settings.database_url.startswith("sqlite+aiosqlite:///")
    assert settings.database_url.endswith("/test.db")


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


def test_cors_origins_parses_comma_separated_string():
    settings = Settings(cors_origins="https://app.homomics.lab,https://admin.homomics.lab")
    assert settings.cors_origins == ["https://app.homomics.lab", "https://admin.homomics.lab"]


def test_cors_origins_accepts_list():
    settings = Settings(cors_origins=["https://a.lab", "https://b.lab"])
    assert settings.cors_origins == ["https://a.lab", "https://b.lab"]


def test_cors_origins_empty_string_becomes_none():
    settings = Settings(cors_origins="")
    assert settings.cors_origins is None


# ---------------------------------------------------------------------------
# Former settings fields are now module-level constants at their call sites
# (docs/improvement-plan-v2.0.md, section 2). These tests pin the effective
# values so an accidental constant change is caught here.
# ---------------------------------------------------------------------------


def test_hitl_and_debate_constants():
    from homomics_lab.agent.turn_runner import DEBATE_JUDGE_BACKEND, HITL_RISK_THRESHOLD

    assert HITL_RISK_THRESHOLD == 0.6
    assert DEBATE_JUDGE_BACKEND == "rule"


def test_timeout_constants():
    from homomics_lab.skills.runtime import (
        DEFAULT_JOB_TIMEOUT_SECONDS,
        MAX_SKILL_TIMEOUT_SECONDS,
    )

    assert DEFAULT_JOB_TIMEOUT_SECONDS == 3600.0
    assert MAX_SKILL_TIMEOUT_SECONDS == 86400.0


def test_literature_constants():
    from homomics_lab.agent.literature_retriever import (
        LITERATURE_CACHE_TTL_SECONDS,
        LITERATURE_MAX_RESULTS,
        NCBI_API_KEY,
        NCBI_EMAIL,
    )

    assert NCBI_EMAIL is None
    assert NCBI_API_KEY is None
    assert LITERATURE_CACHE_TTL_SECONDS == 3600.0
    assert LITERATURE_MAX_RESULTS == 10


def test_semantic_memory_constant():
    from homomics_lab.context.memory_backend import ENABLE_SEMANTIC_MEMORY

    assert ENABLE_SEMANTIC_MEMORY is True


def test_container_sandbox_constants():
    from homomics_lab.skills.sandbox import (
        R_CONTAINER_IMAGE,
        SKILL_CONTAINER_CPUS,
        SKILL_CONTAINER_IMAGE,
        SKILL_CONTAINER_MEMORY_MB,
        SKILL_CONTAINER_PIDS_LIMIT,
        SKILL_CONTAINER_READONLY_ROOT,
    )

    assert SKILL_CONTAINER_IMAGE == "python:3.10-slim"
    assert R_CONTAINER_IMAGE == "r-base:4.3.0"
    assert SKILL_CONTAINER_MEMORY_MB == 1024
    assert SKILL_CONTAINER_CPUS == 1.0
    assert SKILL_CONTAINER_PIDS_LIMIT == 64
    assert SKILL_CONTAINER_READONLY_ROOT is True
