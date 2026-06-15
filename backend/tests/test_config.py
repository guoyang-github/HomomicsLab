from pathlib import Path
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
