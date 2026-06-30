"""Factory for creating graph backends from settings."""

import logging
from typing import Optional

from homomics_lab.config import Settings, settings as default_settings
from homomics_lab.context.graph.base import GraphBackend
from homomics_lab.context.graph.networkx import NetworkXBackend

logger = logging.getLogger(__name__)


_graph_instance: Optional[GraphBackend] = None


def get_graph_backend(settings: Optional[Settings] = None) -> GraphBackend:
    """Return the configured graph backend singleton."""
    global _graph_instance
    if _graph_instance is not None:
        return _graph_instance

    settings = settings or default_settings
    backend = settings.graph_backend.lower()

    if backend == "networkx":
        storage_path = settings.data_dir / "memory_graph.json"
        _graph_instance = NetworkXBackend(storage_path=storage_path)
    elif backend == "neo4j":
        raise NotImplementedError(
            "neo4j backend is planned but not yet implemented. Use networkx."
        )
    else:
        raise ValueError(f"Unsupported graph_backend: {backend}")

    logger.info("Initialized graph backend: %s", backend)
    return _graph_instance


def reset_graph_backend() -> None:
    """Reset the singleton, primarily for tests."""
    global _graph_instance
    _graph_instance = None
