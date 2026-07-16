"""Qdrant vector store backend.

Qdrant client imports are deferred until this backend is actually instantiated so
that the package can be imported even when ``qdrant-client`` is not installed.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from homomics_lab.context.vector_store.base import VectorSearchResult, VectorStoreBackend

logger = logging.getLogger(__name__)

# Namespace for deterministic UUID generation from string ids.
_ID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


class QdrantBackend(VectorStoreBackend):
    """Qdrant-backed vector store. Supports in-memory mode for tests."""

    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None) -> None:
        from qdrant_client import QdrantClient

        if url and url.lower() == ":memory:":
            self.client: QdrantClient = QdrantClient(":memory:")
        elif url:
            self.client = QdrantClient(url=url, api_key=api_key)
        else:
            self.client = QdrantClient(":memory:")

    async def create_collection(self, collection: str, dimension: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        try:
            self.client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                logger.warning("Failed to create Qdrant collection: %s", exc)

    async def upsert(
        self,
        collection: str,
        ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        from qdrant_client.models import PointStruct

        await self.create_collection(collection, len(embeddings[0]))
        points = []
        for i, doc_id in enumerate(ids):
            payload = {"text": texts[i], "_external_id": doc_id}
            if metadata and i < len(metadata):
                payload.update(metadata[i])
            points.append(
                PointStruct(
                    id=self._to_uuid(doc_id),
                    vector=embeddings[i],
                    payload=payload,
                )
            )
        self.client.upsert(collection_name=collection, points=points, wait=True)

    async def search(
        self,
        collection: str,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        qdrant_filter = self._build_filter(filters)
        response = self.client.query_points(
            collection_name=collection,
            query=query_embedding,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        return [self._to_result(r) for r in response.points]

    async def keyword_search(
        self,
        collection: str,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        # Qdrant does not have built-in BM25. Fall back to payload full-text search.
        qdrant_filter = self._build_filter(filters)
        results = self.client.scroll(
            collection_name=collection,
            scroll_filter=qdrant_filter,
            limit=top_k * 4,
            with_payload=True,
        )[0]
        query_lower = query.lower()
        scored = []
        for r in results:
            text = (r.payload or {}).get("text", "")
            if query_lower in text.lower():
                scored.append(self._to_result(r, score=1.0))
        return scored[:top_k]

    async def delete(self, collection: str, ids: List[str]) -> None:
        from qdrant_client.models import PointIdsList

        self.client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=[self._to_uuid(i) for i in ids]),
        )

    async def close(self) -> None:
        self.client.close()

    @staticmethod
    def _to_uuid(external_id: str) -> str:
        return str(uuid.uuid5(_ID_NAMESPACE, external_id))

    @classmethod
    def _to_result(cls, r, score: Optional[float] = None) -> VectorSearchResult:
        payload = r.payload or {}
        metadata = cls._clean_metadata(payload)
        return VectorSearchResult(
            id=payload.get("_external_id", str(r.id)),
            score=score if score is not None else r.score,
            text=payload.get("text"),
            metadata=metadata,
        )

    @staticmethod
    def _build_filter(filters: Optional[Dict[str, Any]]) -> Optional[Any]:
        if not filters:
            return None
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

        conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                conditions.append(FieldCondition(key=key, match=MatchAny(any=value)))
            else:
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
        return Filter(must=conditions) if conditions else None

    @staticmethod
    def _clean_metadata(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        metadata = dict(payload)
        metadata.pop("text", None)
        metadata.pop("_external_id", None)
        return metadata
