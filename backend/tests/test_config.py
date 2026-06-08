import os
from homics_lab.config import Settings


def test_default_port():
    settings = Settings()
    assert settings.port == 8080


def test_env_override():
    os.environ["HOMICS_PORT"] = "9000"
    settings = Settings()
    assert settings.port == 9000
    del os.environ["HOMICS_PORT"]
