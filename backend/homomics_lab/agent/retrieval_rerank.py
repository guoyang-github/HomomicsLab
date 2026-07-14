"""Lightweight BM25-style reranker for retrieved skill candidates.

The retriever's upstream signals are heterogeneous and uncalibrated:
``registry.search`` historically returned skills without any score (callers
hard-coded ``semantic_score=1.0``), and the hybrid index fuses dense/sparse
rankings with reciprocal rank fusion, whose scores carry no relevance
magnitude.  As a result, any query — including meaningless tokens like
``"x_alpha"`` — used to be force-matched to some skill.

This module reranks candidates with a transparent composite score in [0, 1]:

    composite = w_semantic * clamp(semantic_score)
              + w_bm25     * normalized_bm25(query, skill)
              + w_graph    * clamp(graph_boost)

The BM25 component is computed in pure Python over the skill's
name / description / category / keywords (name counted twice).  Candidates
below ``min_score`` are dropped, so unrelated queries retrieve nothing
instead of an arbitrary best-effort match.

``RetrievedSkill.semantic_score`` is overwritten with the composite score so
downstream consumers keep working unchanged; the original upstream score is
preserved on ``RetrievedSkill.raw_semantic_score`` for auditing.
"""

import math
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

if TYPE_CHECKING:  # Avoid a circular import with agent.retrieval at runtime.
    from homomics_lab.agent.retrieval import RetrievedSkill

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# BM25 saturation constant for normalizing raw BM25 into [0, 1):
#   bm25_norm = bm25 / (bm25 + BM25_NORM_K)
BM25_NORM_K = 1.5


def _tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric tokenizer; splits snake_case and kebab-case."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1]


def _skill_tokens(skill: Any) -> List[str]:
    """Build the token document for a skill (name weighted twice)."""
    metadata = getattr(skill, "metadata", None) or {}
    parts = [
        skill.name,
        skill.name,
        skill.description or "",
        (skill.category or "").replace("_", " ").replace("-", " "),
    ]
    for key in ("tags", "keywords", "supported_tools"):
        values = metadata.get(key) or []
        parts.extend(str(v) for v in values)
    primary_tool = metadata.get("primary_tool")
    if primary_tool:
        parts.append(str(primary_tool))
    return _tokenize(" ".join(p for p in parts if p))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class SkillReranker:
    """Rerank retrieved skill candidates with semantic + BM25 + graph signals.

    Args:
        semantic_weight: Weight of the upstream semantic score.
        bm25_weight: Weight of the normalized BM25 lexical overlap.
        graph_weight: Weight of the SkillDAG graph boost.
        min_score: Composite score floor; candidates below it are dropped.
        k1: BM25 term-frequency saturation parameter.
        b: BM25 document-length normalization parameter.
    """

    def __init__(
        self,
        semantic_weight: float = 0.4,
        bm25_weight: float = 0.5,
        graph_weight: float = 0.1,
        min_score: float = 0.1,
        k1: float = 1.2,
        b: float = 0.75,
    ):
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight
        self.graph_weight = graph_weight
        self.min_score = min_score
        self.k1 = k1
        self.b = b

    def rerank(
        self,
        query: str,
        candidates: Sequence["RetrievedSkill"],
        top_k: Optional[int] = None,
        corpus: Optional[Sequence[Any]] = None,
    ) -> List["RetrievedSkill"]:
        """Rerank candidates, drop those below ``min_score``, then truncate.

        The composite score is written back to ``semantic_score``; the
        previous value is kept on ``raw_semantic_score``.

        Args:
            query: The retrieval query.
            candidates: Retrieved skills to rerank.
            top_k: Optional truncation applied AFTER threshold filtering.
            corpus: Optional background skill collection used for BM25
                document-frequency / average-length statistics.  Without it
                the candidate set itself is the corpus, which makes idf
                vanish when only one candidate survives upstream filtering.
        """
        if not candidates:
            return []

        query_terms = _tokenize(query)
        corpus_tokens = [_skill_tokens(skill) for skill in corpus] if corpus else None
        bm25_scores = self._bm25(query_terms, candidates, corpus_tokens)

        scored: List["RetrievedSkill"] = []
        for idx, candidate in enumerate(candidates):
            bm25_norm = 0.0
            if bm25_scores[idx] > 0.0:
                bm25_norm = bm25_scores[idx] / (bm25_scores[idx] + BM25_NORM_K)
            composite = (
                self.semantic_weight * _clamp01(candidate.semantic_score)
                + self.bm25_weight * bm25_norm
                + self.graph_weight * _clamp01(candidate.graph_boost)
            )
            if composite < self.min_score:
                continue
            candidate.raw_semantic_score = candidate.semantic_score
            candidate.semantic_score = composite
            scored.append(candidate)

        # Stable sort: ties keep the upstream (semantic rank) order.
        scored.sort(key=lambda rs: rs.semantic_score, reverse=True)
        if top_k is not None:
            scored = scored[:top_k]
        return scored

    def _bm25(
        self,
        query_terms: Sequence[str],
        candidates: Sequence["RetrievedSkill"],
        corpus_tokens: Optional[List[List[str]]] = None,
    ) -> List[float]:
        """Compute BM25 scores of the query against the candidate corpus.

        Document-frequency and average-length statistics come from
        ``corpus_tokens`` when provided, otherwise from the candidates.
        """
        docs = [_skill_tokens(rs.skill) for rs in candidates]
        stats_docs = corpus_tokens if corpus_tokens else docs
        n_docs = len(stats_docs)
        avg_dl = sum(len(d) for d in stats_docs) / n_docs if n_docs else 0.0

        doc_freq: Dict[str, int] = {}
        for doc in stats_docs:
            for term in set(doc):
                doc_freq[term] = doc_freq.get(term, 0) + 1

        scores: List[float] = []
        for doc in docs:
            tf: Dict[str, int] = {}
            for term in doc:
                tf[term] = tf.get(term, 0) + 1
            dl = len(doc)
            score = 0.0
            for term in set(query_terms):
                freq = tf.get(term, 0)
                if freq == 0:
                    continue
                df = doc_freq.get(term, 0)
                idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
                denom = freq + self.k1 * (1.0 - self.b + self.b * dl / avg_dl) if avg_dl else freq + self.k1
                score += idf * (freq * (self.k1 + 1.0)) / denom
            scores.append(score)
        return scores
