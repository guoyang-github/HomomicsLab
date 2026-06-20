"""Semantic memory consolidation: cluster and summarize old conversations.

This module provides higher-level memory maintenance than the simple
adjacent-chunk merging in `SemanticMemory.consolidate_conversation_chunks`:

- Semantic clustering of old conversation memories using embeddings.
- LLM-based (or fallback) summarization of each cluster into a ``concept``
  memory.
- Cleanup of the original low-level conversation rows after successful
  summarization.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import numpy as np

from homomics_lab.context.embedding_cache import get_shared_embedding_model
from homomics_lab.context.semantic_memory import SemanticMemory

logger = logging.getLogger(__name__)


class MemoryConsolidator:
    """Cluster and summarize old conversation memories into concept nodes."""

    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(
        self,
        semantic_memory: SemanticMemory,
        model_name: Optional[str] = None,
        llm_client: Optional[Any] = None,
    ) -> None:
        self.semantic_memory = semantic_memory
        self.model_name = model_name or self.DEFAULT_MODEL
        self.llm_client = llm_client

    def _embed(self, texts: List[str]) -> np.ndarray:
        """Encode texts into normalized embeddings."""
        if not texts:
            return np.array([])
        model = get_shared_embedding_model(self.model_name)
        embeddings = np.asarray(model.encode(texts), dtype=float)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return embeddings / norms

    def _cluster_embeddings(
        self,
        embeddings: np.ndarray,
        distance_threshold: float = 0.35,
    ) -> np.ndarray:
        """Return cluster labels for the given embeddings.

        Uses agglomerative clustering with cosine distance.  Memories that are
        too dissimilar from everything else receive label ``-1``.
        """
        if len(embeddings) < 2:
            return np.array([-1] * len(embeddings))

        try:
            from sklearn.cluster import AgglomerativeClustering
        except ImportError as exc:
            logger.warning("sklearn not available for memory clustering: %s", exc)
            return np.array([-1] * len(embeddings))

        # Clamp threshold to a sane range.
        distance_threshold = max(0.05, min(0.95, distance_threshold))
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            metric="cosine",
            linkage="average",
        )
        return clustering.fit_predict(embeddings)

    async def _summarize_cluster(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        """Generate a concise summary of a memory cluster.

        If an LLM client is configured, it is asked to extract the key
        concept/episode.  Otherwise a deterministic concatenated summary is
        returned.
        """
        texts = [r["text"] for r in rows]
        if not texts:
            return ""

        if self.llm_client is not None:
            try:
                prompt = (
                    "You are summarizing a cluster of related conversation "
                    "memories from a bioinformatics research assistant. "
                    "Extract the key concept, decision, or episode in 1-2 "
                    "concise sentences. Do not include timestamps or IDs.\n\n"
                    "Memories:\n"
                    + "\n---\n".join(texts)
                )
                summary = await self.llm_client.chat_completion(
                    messages=[
                        {"role": "system", "content": "Summarize conversation memories."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=400,
                    prefer_cheap=True,
                )
                summary = summary.strip()
                if summary:
                    return summary
            except Exception as exc:
                logger.warning("LLM memory summarization failed: %s", exc)

        # Fallback: deterministic concatenated summary.
        return "Summary of {} conversation memories:\n{}".format(
            len(texts), "\n---\n".join(texts)
        )

    async def consolidate(
        self,
        retention_days: int = 30,
        min_cluster_size: int = 2,
        distance_threshold: float = 0.35,
        memory_type: str = "conversation",
    ) -> int:
        """Cluster old memories and summarize them into concept nodes.

        Args:
            retention_days: Only consider memories older than this many days.
                Use ``0`` to consider all memories.
            min_cluster_size: Minimum cluster size to create a concept memory.
            distance_threshold: Cosine distance threshold for clustering;
                smaller values yield tighter clusters.
            memory_type: Type of memories to consolidate.

        Returns:
            Number of concept memories created.
        """
        conn = self.semantic_memory._get_conn()
        if retention_days > 0:
            rows = conn.execute(
                """
                SELECT id, text, metadata, importance, ttl_days, created_at,
                       project_id, session_id
                FROM memories
                WHERE memory_type = ? AND date(created_at) <= date('now', '-' || ? || ' days')
                ORDER BY created_at ASC
                """,
                (memory_type, retention_days),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, text, metadata, importance, ttl_days, created_at,
                       project_id, session_id
                FROM memories
                WHERE memory_type = ?
                ORDER BY created_at ASC
                """,
                (memory_type,),
            ).fetchall()

        if len(rows) < min_cluster_size:
            return 0

        texts = [r[1] for r in rows]
        embeddings = self._embed(texts)
        labels = self._cluster_embeddings(embeddings, distance_threshold=distance_threshold)

        clusters: Dict[int, List[tuple]] = {}
        for row, label in zip(rows, labels):
            if label < 0:
                continue
            clusters.setdefault(label, []).append(row)

        created = 0
        for cluster_rows in clusters.values():
            if len(cluster_rows) < min_cluster_size:
                continue

            summary_text = await self._summarize_cluster(
                [
                    {
                        "text": r[1],
                        "metadata": json.loads(r[2]),
                        "created_at": r[5],
                    }
                    for r in cluster_rows
                ]
            )
            if not summary_text:
                continue

            first = cluster_rows[0]
            source_ids = [r[0] for r in cluster_rows]
            importances = [r[3] for r in cluster_rows if r[3] is not None]
            merged_importance = sum(importances) / len(importances) if importances else 0.5
            ttl_days = first[4]
            project_id = first[6]
            session_id = first[7]
            meta = json.loads(first[2])
            meta.update(
                {
                    "consolidated": True,
                    "source_ids": source_ids,
                    "original_count": len(cluster_rows),
                    "source_memory_type": memory_type,
                }
            )

            try:
                await self.semantic_memory.add(
                    text=summary_text,
                    memory_type="concept",
                    metadata=meta,
                    importance=merged_importance,
                    ttl_days=ttl_days,
                    project_id=project_id,
                    session_id=session_id,
                )
                for memory_id in source_ids:
                    await self.semantic_memory.delete(memory_id)
                created += 1
            except Exception as exc:
                logger.warning("Failed to consolidate memory cluster: %s", exc)

        return created
