"""Global pytest configuration for the HomomicsLab backend."""

import os

import pytest

from homomics_lab.config import settings


# Run Hugging Face hubs in offline mode during tests. This prevents network
# timeouts when sentence-transformers tries to reach the remote model hub,
# while still allowing locally cached models to load.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

# Disable external skill repository discovery and MCP client in tests. Both can
# trigger network or subprocess calls during bootstrap, causing unrelated test
# timeouts.
settings.external_skills_dirs = []
settings.mcp_enabled = False
settings.auto_load_domain_strategies = False

# Force app bootstrap to disable hot-reload watchers in tests; they can block
# TestClient lifespan shutdown and are not needed for unit tests.
import homomics_lab.bootstrap  # noqa: E402
import homomics_lab.main  # noqa: E402

_orig_bootstrap = homomics_lab.bootstrap.bootstrap_worker_context


async def _bootstrap_without_hot_reload(enable_hot_reload: bool = False, **kwargs):
    return await _orig_bootstrap(enable_hot_reload=False, **kwargs)


homomics_lab.bootstrap.bootstrap_worker_context = _bootstrap_without_hot_reload
homomics_lab.main.bootstrap_worker_context = _bootstrap_without_hot_reload


@pytest.fixture(autouse=True)
def sandbox_backend_local(monkeypatch):
    """Force the skill sandbox backend to local for unit tests.

    The auto backend may select container/bubblewrap in CI or WSL environments
    where Docker is misconfigured, causing unrelated test failures.
    """
    monkeypatch.setattr(settings, "skill_sandbox_backend", "local")

