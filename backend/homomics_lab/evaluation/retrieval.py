"""Retrieval evaluation utilities for memory and capability indexes.

Provides standard IR metrics to measure the quality of semantic / hybrid search:

- ``precision_at_k``
- ``recall_at_k``
- ``mean_reciprocal_rank`` (MRR)
- ``ndcg_at_k`` (Normalized Discounted Cumulative Gain)
- ``hit_rate_at_k``

These metrics let us regression-test the memory and capability backends as the
embedding model, ranking function, or feedback signals change.
"""

import math
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set


@dataclass
class RetrievalExample:
    """A single evaluation example."""

    query: str
    relevant_ids: Set[str]
    filters: Optional[Dict[str, Any]] = None


class RetrievalEvaluator:
    """Evaluate an async retrieval function against a labeled dataset."""

    def __init__(
        self,
        retrieve: Callable[..., Coroutine[Any, Any, List[Any]]],
        id_fn: Callable[[Any], str],
    ) -> None:
        """
        Args:
            retrieve: Async function that accepts ``query`` and ``top_k`` and returns ranked results.
            id_fn: Function to extract an id string from a result item.
        """
        self.retrieve = retrieve
        self.id_fn = id_fn

    async def evaluate(
        self,
        examples: List[RetrievalExample],
        ks: Optional[List[int]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Evaluate all examples and return per-metric scores at each k.

        Returns a dict mapping metric name to ``{k: score}``.
        """
        ks = ks or [1, 3, 5, 10]
        metrics = {
            "precision": {str(k): [] for k in ks},
            "recall": {str(k): [] for k in ks},
            "mrr": {str(k): [] for k in ks},
            "hit_rate": {str(k): [] for k in ks},
            "ndcg": {str(k): [] for k in ks},
        }

        for example in examples:
            max_k = max(ks)
            kwargs = {"query": example.query, "top_k": max_k}
            if example.filters:
                kwargs.update(example.filters)
            results = await self.retrieve(**kwargs)
            result_ids = [self.id_fn(r) for r in results]

            for k in ks:
                top_ids = result_ids[:k]
                relevant = example.relevant_ids

                # Precision / recall / hit rate
                retrieved_relevant = [rid for rid in top_ids if rid in relevant]
                precision = len(retrieved_relevant) / len(top_ids) if top_ids else 0.0
                recall = len(retrieved_relevant) / len(relevant) if relevant else 0.0
                hit_rate = 1.0 if any(rid in relevant for rid in top_ids) else 0.0

                # MRR
                mrr = 0.0
                for idx, rid in enumerate(top_ids, start=1):
                    if rid in relevant:
                        mrr = 1.0 / idx
                        break

                # NDCG (binary relevance)
                dcg = sum(
                    1.0 / math.log2(idx + 1)
                    for idx, rid in enumerate(top_ids, start=1)
                    if rid in relevant
                )
                ideal_hits = min(len(relevant), k)
                idcg = sum(1.0 / math.log2(idx + 1) for idx in range(1, ideal_hits + 1))
                ndcg = dcg / idcg if idcg > 0 else 0.0

                metrics["precision"][str(k)].append(precision)
                metrics["recall"][str(k)].append(recall)
                metrics["mrr"][str(k)].append(mrr)
                metrics["hit_rate"][str(k)].append(hit_rate)
                metrics["ndcg"][str(k)].append(ndcg)

        # Average across examples.
        return {
            metric: {k: sum(scores) / len(scores) if scores else 0.0 for k, scores in per_k.items()}
            for metric, per_k in metrics.items()
        }
