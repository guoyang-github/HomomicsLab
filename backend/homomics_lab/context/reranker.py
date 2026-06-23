"""Cross-encoder reranker for context retrieval.

Provides a lightweight wrapper around sentence-transformers CrossEncoder models
for final-stage relevance reranking. Falls back to a lexical overlap baseline
when no model is available.
"""

import logging
from typing import Any, List, Optional, Protocol, TypeVar

from homomics_lab.context.embedding_cache import get_shared_embedding_model

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Reranker(Protocol):
    """Protocol for reranking candidates against a query."""

    def rerank(
        self,
        query: str,
        candidates: List[T],
        text_fn,
        top_k: Optional[int] = None,
    ) -> List[T]:
        """Return candidates ordered by relevance to the query."""
        ...


class CrossEncoderReranker:
    """Cross-encoder reranker for context parts or CBKB items.

    Args:
        model_name: CrossEncoder model name. Defaults to a lightweight
            MS MARCO model that is reasonably small and permissively licensed.
        device: Device override ("cpu", "cuda", etc.).
    """

    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
    ) -> None:
        self.model_name = model_name or self.DEFAULT_MODEL
        self.device = device
        self._model: Optional[Any] = None

    def _get_model(self) -> Optional[Any]:
        """Lazy-load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(
                    self.model_name,
                    device=self.device,
                    max_length=512,
                )
            except Exception as exc:
                logger.warning(
                    "Could not load cross-encoder model %s: %s", self.model_name, exc
                )
        return self._model

    def _fallback_order(
        self,
        query: str,
        candidates: List[T],
        text_fn,
    ) -> List[T]:
        """Lexical Jaccard fallback when no model is available."""
        query_tokens = set(query.lower().split())
        if not query_tokens:
            return candidates

        def score(candidate: T) -> float:
            text = text_fn(candidate).lower()
            text_tokens = set(text.split())
            union = query_tokens | text_tokens
            if not union:
                return 0.0
            return len(query_tokens & text_tokens) / len(union)

        return sorted(candidates, key=score, reverse=True)

    def rerank(
        self,
        query: str,
        candidates: List[T],
        text_fn,
        top_k: Optional[int] = None,
    ) -> List[T]:
        """Rerank candidates by cross-encoder relevance.

        Args:
            query: The user query.
            candidates: Items to rerank.
            text_fn: Callable that extracts text from a candidate.
            top_k: If provided, return only the top-k items.

        Returns:
            Candidates ordered by descending relevance.
        """
        if not candidates:
            return []

        model = self._get_model()
        if model is None:
            ordered = self._fallback_order(query, candidates, text_fn)
            return ordered[:top_k] if top_k else ordered

        try:
            pairs = [(query, text_fn(c)) for c in candidates]
            scores = model.predict(pairs, show_progress_bar=False)
            scored = list(zip(candidates, scores))
            scored.sort(key=lambda x: x[1], reverse=True)
            ordered = [c for c, _ in scored]
            return ordered[:top_k] if top_k else ordered
        except Exception as exc:
            logger.warning("Cross-encoder reranking failed: %s", exc)
            ordered = self._fallback_order(query, candidates, text_fn)
            return ordered[:top_k] if top_k else ordered


class BiEncoderReranker:
    """Bi-encoder fallback reranker using the shared embedding cache.

    This is useful when a cross-encoder is too heavy or unavailable, but
    a shared bi-encoder model is already loaded.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name
        self._model: Optional[Any] = None

    def _get_model(self) -> Optional[Any]:
        if self._model is None and self.model_name:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
            except Exception as exc:
                logger.warning("Could not load bi-encoder reranker: %s", exc)
        return self._model

    def rerank(
        self,
        query: str,
        candidates: List[T],
        text_fn,
        top_k: Optional[int] = None,
    ) -> List[T]:
        if not candidates:
            return []

        model = self._model
        if model is None and self.model_name:
            model = get_shared_embedding_model(self.model_name)
        if model is not None:
            try:
                import numpy as np

                texts = [text_fn(c) for c in candidates]
                embeddings = model.encode(texts, convert_to_tensor=False)
                query_embedding = model.encode([query], convert_to_tensor=False)
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                norms[norms == 0] = 1
                embeddings = embeddings / norms
                query_norm = np.linalg.norm(query_embedding, axis=1, keepdims=True)
                query_norm[query_norm == 0] = 1
                query_embedding = query_embedding / query_norm
                scores = np.dot(embeddings, query_embedding[0])
                scored = list(zip(candidates, scores))
                scored.sort(key=lambda x: x[1], reverse=True)
                ordered = [c for c, _ in scored]
                return ordered[:top_k] if top_k else ordered
            except Exception as exc:
                logger.warning("Bi-encoder reranking failed: %s", exc)
        ordered = sorted(
            candidates,
            key=lambda c: len(set(query.lower().split()) & set(text_fn(c).lower().split())),
            reverse=True,
        )
        return ordered[:top_k] if top_k else ordered
