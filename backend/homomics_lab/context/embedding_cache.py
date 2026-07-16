"""Shared embedding model with LRU cache.

Prevents multiple components from loading separate sentence-transformers
instances and caches frequently used embeddings.
"""

import logging
from functools import lru_cache
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class SharedEmbeddingModel:
    """Singleton sentence-transformers wrapper with an LRU cache."""

    _instance: Optional["SharedEmbeddingModel"] = None

    def __new__(cls, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model_name = model_name
            cls._instance._model = None
        elif not cls._instance._model_name and model_name:
            cls._instance._model_name = model_name
        return cls._instance

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                try:
                    self._model = SentenceTransformer(
                        self._model_name, local_files_only=True
                    )
                    logger.info(
                        "Loaded embedding model from local cache: %s",
                        self._model_name,
                    )
                except Exception:
                    logger.info(
                        "Local cache miss for %s; falling back to online load",
                        self._model_name,
                        exc_info=True,
                    )
                    self._model = SentenceTransformer(self._model_name)
            except Exception as exc:
                logger.warning("Could not load embedding model %s: %s", self._model_name, exc)
                raise
        return self._model

    @lru_cache(maxsize=1024)
    def _cached_encode_tuple(self, texts: tuple) -> List[List[float]]:
        """Encode a tuple of strings; lru_cache requires hashable args."""
        model = self._load()
        import numpy as np

        embeddings = model.encode(list(texts), convert_to_tensor=False)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normalized = embeddings / norms
        return normalized.tolist()

    def encode(
        self,
        texts: List[str],
        convert_to_tensor: bool = False,
        **kwargs: Any,
    ) -> List[List[float]]:
        """Return normalized embeddings for a list of texts.

        Accepts ``convert_to_tensor`` for compatibility with the
        sentence-transformers API, but always returns plain normalized vectors.
        """
        if not texts:
            return []
        return self._cached_encode_tuple(tuple(texts))

    def reset(self):
        """Clear the cached model and embedding cache (useful in tests)."""
        self._model = None
        self._cached_encode_tuple.cache_clear()
        SharedEmbeddingModel._instance = None


def get_shared_embedding_model(model_name: Optional[str] = None) -> SharedEmbeddingModel:
    """Return the shared embedding model instance."""
    model_name = model_name or "sentence-transformers/all-MiniLM-L6-v2"
    return SharedEmbeddingModel(model_name)
