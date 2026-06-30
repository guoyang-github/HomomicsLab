"""Abstract embedding provider interface."""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):
    """Pluggable dense embedding provider.

    All providers expose a synchronous ``encode`` method. Async callers should
    offload CPU-bound local models with ``asyncio.to_thread`` and use async
    HTTP clients for API-backed providers internally.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""

    @abstractmethod
    def encode(self, texts: List[str]) -> List[List[float]]:
        """Encode a list of texts into normalized dense embeddings."""

    def is_available(self) -> bool:
        """Return True when the provider can be used in the current environment."""
        return True
