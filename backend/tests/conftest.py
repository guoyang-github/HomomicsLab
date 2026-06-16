"""Global pytest configuration for the HomomicsLab backend."""

import os

import pytest

from homomics_lab.config import settings


# Run Hugging Face hubs in offline mode during tests. This prevents network
# timeouts when sentence-transformers tries to reach the remote model hub,
# while still allowing locally cached models to load.
os.environ.setdefault("HF_HUB_OFFLINE", "1")


@pytest.fixture(autouse=True)
def sandbox_backend_local(monkeypatch):
    """Force the skill sandbox backend to local for unit tests.

    The auto backend may select container/bubblewrap in CI or WSL environments
    where Docker is misconfigured, causing unrelated test failures.
    """
    monkeypatch.setattr(settings, "skill_sandbox_backend", "local")

