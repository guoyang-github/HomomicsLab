"""Rank and deduplicate context parts for the ContextEngine."""

import logging
import math
from typing import Any, Dict, List, Optional

from homomics_lab.context.context_engine.models import ContextPart, ContextSource
from homomics_lab.context.reranker import BiEncoderReranker

logger = logging.getLogger(__name__)


# Base priority by source. Higher is more important.
SOURCE_PRIORITY: Dict[ContextSource, int] = {
    ContextSource.SYSTEM: 10,
    ContextSource.PROJECT_STATE: 10,
    ContextSource.CBKB: 8,
    ContextSource.EPISODIC_SUMMARY: 7,
    ContextSource.SEMANTIC_MEMORY: 6,
    ContextSource.CHAT: 4,
}


class ContextRanker:
    """Score context parts by relevance and remove near-duplicates."""

    def __init__(
        self,
        embedding_model_name: Optional[str] = None,
        reranker: Optional[Any] = None,
    ):
        self.embedding_model_name = embedding_model_name
        self._embedding_model = None
        self._reranker = reranker or BiEncoderReranker(model_name=embedding_model_name)

    def _get_embedding_model(self):
        if self._embedding_model is None and self.embedding_model_name:
            try:
                from sentence_transformers import SentenceTransformer

                self._embedding_model = SentenceTransformer(self.embedding_model_name)
            except Exception as exc:
                logger.warning("Could not load ranker embedding model: %s", exc)
        return self._embedding_model

    def score(
        self,
        part: ContextPart,
        query: str,
    ) -> float:
        """Return a relevance score for a context part."""
        source_score = SOURCE_PRIORITY.get(part.source, 5) / 10.0

        # Temporal decay over 24 hours
        hours = part.hours_since_created or 0.0
        temporal_score = math.exp(-hours / 24.0)

        # Pin and critical boosts
        pin_score = 1.0 if part.is_pinned else 0.0
        critical_score = 1.0 if part.is_critical else 0.0

        # Lexical overlap with query
        semantic_score = self._lexical_similarity(part.content, query)

        # Optional dense similarity
        dense_score = 0.0
        model = self._get_embedding_model()
        if model is not None:
            try:
                import numpy as np

                embeddings = model.encode([part.content, query], convert_to_tensor=False)
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                norms[norms == 0] = 1
                embeddings = embeddings / norms
                dense_score = float(np.dot(embeddings[0], embeddings[1]))
            except Exception as exc:
                logger.debug("Dense scoring failed: %s", exc)

        # Combine. Weights tuned so source and criticality dominate.
        final = (
            source_score * 0.35
            + temporal_score * 0.10
            + pin_score * 0.15
            + critical_score * 0.15
            + max(semantic_score, dense_score) * 0.25
        )
        return final

    @staticmethod
    def _lexical_similarity(a: str, b: str) -> float:
        """Simple Jaccard similarity between two strings."""
        if not a or not b:
            return 0.0
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def rank(
        self,
        parts: List[ContextPart],
        query: str,
    ) -> List[ContextPart]:
        """Rank parts by score, preserving original order for ties."""
        scored = [(part, self.score(part, query)) for part in parts]
        scored.sort(key=lambda x: x[1], reverse=True)
        ranked = [part for part, _ in scored]
        return self.rerank(ranked, query)

    def rerank(
        self,
        parts: List[ContextPart],
        query: str,
        top_k: Optional[int] = None,
    ) -> List[ContextPart]:
        """Apply a cross-encoder or bi-encoder reranker to the ranked list.

        The first pass source/temporal score provides a stable ordering;
        the reranker refines relevance for the top candidates.
        """
        if not parts or not query.strip():
            return parts

        try:
            return self._reranker.rerank(
                query=query,
                candidates=parts,
                text_fn=lambda part: part.content,
                top_k=top_k,
            )
        except Exception as exc:
            logger.warning("ContextRanker reranking failed: %s", exc)
            return parts

    def deduplicate(
        self,
        parts: List[ContextPart],
        threshold: float = 0.85,
    ) -> List[ContextPart]:
        """Remove near-duplicate parts, keeping the higher-priority one."""
        if len(parts) <= 1:
            return parts

        model = self._get_embedding_model()
        if model is not None:
            try:
                import numpy as np

                texts = [p.content for p in parts]
                embeddings = model.encode(texts, convert_to_tensor=False)
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                norms[norms == 0] = 1
                embeddings = embeddings / norms

                result: List[ContextPart] = []
                kept_indices = set()
                for i, part in enumerate(parts):
                    if i in kept_indices:
                        continue
                    for j in range(i + 1, len(parts)):
                        if j in kept_indices:
                            continue
                        sim = float(np.dot(embeddings[i], embeddings[j]))
                        if sim > threshold:
                            # Keep the higher-priority / higher-source one
                            if self._prefer(part, parts[j]):
                                kept_indices.add(j)
                            else:
                                kept_indices.add(i)
                                break
                    if i not in kept_indices:
                        result.append(part)
                return result
            except Exception as exc:
                logger.warning("Embedding dedup failed: %s", exc)

        # Fallback to lexical Jaccard dedup
        result = []
        for part in parts:
            is_dup = False
            for existing in result:
                if self._lexical_similarity(part.content, existing.content) > threshold:
                    if not self._prefer(part, existing):
                        is_dup = True
                        break
            if not is_dup:
                result.append(part)
        return result

    @staticmethod
    def _prefer(a: ContextPart, b: ContextPart) -> bool:
        """Return True if a should be kept over b."""
        if a.is_pinned != b.is_pinned:
            return a.is_pinned
        if a.is_critical != b.is_critical:
            return a.is_critical
        if a.priority != b.priority:
            return a.priority > b.priority
        return (a.hours_since_created or 0) <= (b.hours_since_created or 0)
