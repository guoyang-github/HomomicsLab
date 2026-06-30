"""Factory for creating vector store backends from settings."""

import logging
from typing import Optional

from homomics_lab.config import Settings, settings as default_settings
from homomics_lab.context.vector_store.base import VectorStoreBackend
from homomics_lab.context.vector_store.qdrant import QdrantBackend
from homomics_lab.context.vector_store.sqlite_vec import SQLiteVecBackend

logger = logging.getLogger(__name__)


_vector_store_instance: Optional[VectorStoreBackend] = None


def get_vector_store(settings: Optional[Settings] = None) -> VectorStoreBackend:
    """Return the configured vector store backend singleton."""
    global _vector_store_instance
    if _vector_store_instance is not None:
        return _vector_store_instance

    settings = settings or default_settings
    backend = settings.vector_store_backend.lower()

    if backend == "qdrant":
        url = settings.vector_store_url or ":memory:"
        _vector_store_instance = QdrantBackend(url=url)
    elif backend == "sqlite-vec":
        db_path = settings.data_dir / "vector_store.db"
        _vector_store_instance = SQLiteVecBackend(db_path=db_path)
    elif backend == "pgvector":
        raise NotImplementedError(
            "pgvector backend is planned but not yet implemented. Use qdrant or sqlite-vec."
        )
    else:
        raise ValueError(f"Unsupported vector_store_backend: {backend}")

    logger.info("Initialized vector store backend: %s", backend)
    return _vector_store_instance


def reset_vector_store() -> None:
    """Reset the singleton, primarily for tests."""
    global _vector_store_instance
    _vector_store_instance = None
