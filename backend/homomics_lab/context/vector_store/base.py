"""Abstract vector store backend."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class VectorSearchResult:
    """Result from a vector store search."""

    id: str
    score: float
    text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class VectorStoreBackend(ABC):
    """Pluggable backend for dense/sparse vector storage and retrieval."""

    @abstractmethod
    async def create_collection(
        self,
        collection: str,
        dimension: int,
    ) -> None:
        """Create a collection/index if it does not exist."""

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Insert or update vectors."""

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Dense vector search with optional metadata filters."""

    @abstractmethod
    async def keyword_search(
        self,
        collection: str,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Sparse/keyword search with optional metadata filters."""

    @abstractmethod
    async def delete(
        self,
        collection: str,
        ids: List[str],
    ) -> None:
        """Delete vectors by id."""

    @abstractmethod
    async def close(self) -> None:
        """Release underlying connections."""
