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
settings.mcp_enabled = False
settings.auto_load_domain_strategies = False
settings.skill_sibling_discovery_enabled = False
settings.external_skills_dirs = []

# Use the locally cached sentence-transformers model to avoid network fallback
# attempts for other default models.
settings.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"


class _FakeEmbeddingProvider:
    """Deterministic, zero-cost embedding provider for test bootstrapping."""

    def __init__(self, dimension: int = 8):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def encode(self, texts):
        return [[0.0] * self._dimension for _ in texts]

    def is_available(self) -> bool:
        return True


# Seed the embedding-provider singleton before bootstrap so heavy models are not
# loaded during short-lived API/integration tests.  Tests that need real
# embeddings reset the singleton and configure the provider themselves.
from homomics_lab.embeddings import factory as _embedding_factory  # noqa: E402

_embedding_factory._provider_instance = _FakeEmbeddingProvider()


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
