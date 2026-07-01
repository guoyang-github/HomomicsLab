"""Hybrid semantic search for skills: dense embeddings + sparse TF-IDF.

When sentence-transformers is available, dense embeddings capture synonyms and
paraphrases (e.g. "QC" vs "quality control"). TF-IDF provides exact token
matching and requires no model load. The two are fused with reciprocal rank
fusion so each contributes without brittle score normalization.
"""

from typing import Any, Dict, List, Optional, Tuple

from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.semantic_search import SkillSemanticSearch


class HybridSkillSearch:
    """Combine dense sentence embeddings with sparse TF-IDF for skill retrieval."""

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: Optional[str] = None):
        self._skills: Dict[str, SkillDefinition] = {}
        self._model_name = model_name or self.DEFAULT_MODEL
        self._dense: Optional[Any] = None
        self._sparse = SkillSemanticSearch()
        self._dense_available: Optional[bool] = None

    @property
    def _dense_enabled(self) -> bool:
        if self._dense_available is None:
            try:
                from homomics_lab.skills.semantic_search_v2 import SemanticSearchEngine

                self._dense = SemanticSearchEngine(model_name=self._model_name)
                self._dense_available = True
            except Exception as exc:
                # Model download/import failure should not break skill search.
                import logging

                logging.getLogger(__name__).warning(
                    "Dense skill search unavailable (%s); falling back to sparse search", exc
                )
                self._dense_available = False
        return self._dense_available

    def add(self, skill: SkillDefinition) -> None:
        """Add a skill to both indexes."""
        self._skills[skill.id] = skill
        self._sparse.add(skill)
        if self._dense_enabled and self._dense is not None:
            self._dense.add(skill)

    def remove(self, skill_id: str) -> None:
        """Remove a skill from both indexes."""
        self._skills.pop(skill_id, None)
        self._sparse.remove(skill_id)
        if self._dense_enabled and self._dense is not None:
            self._dense.remove(skill_id)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[SkillDefinition, float]]:
        """Search skills using hybrid dense + sparse retrieval.

        Uses Reciprocal Rank Fusion (RRF) so scores from the two indexes can be
        combined robustly without cross-index calibration.
        """
        sparse_results = self._sparse.search(query, top_k=top_k * 2)
        dense_results: List[Tuple[SkillDefinition, float]] = []
        if self._dense_enabled and self._dense is not None:
            dense_results = self._dense.search(query, top_k=top_k * 2)

        return self._fuse_results(sparse_results, dense_results, top_k=top_k)

    def search_ids(self, query: str, top_k: int = 10) -> List[str]:
        """Search and return only skill IDs."""
        results = self.search(query, top_k)
        return [skill.id for skill, _ in results]

    def _fuse_results(
        self,
        sparse: List[Tuple[SkillDefinition, float]],
        dense: List[Tuple[SkillDefinition, float]],
        top_k: int,
        k: int = 60,
    ) -> List[Tuple[SkillDefinition, float]]:
        """Fuse sparse and dense rankings with Reciprocal Rank Fusion."""
        scores: Dict[str, float] = {}
        rank_lists: Dict[str, List[int]] = {}

        for rank, (skill, _) in enumerate(sparse, start=1):
            rank_lists.setdefault(skill.id, []).append(rank)
        for rank, (skill, _) in enumerate(dense, start=1):
            rank_lists.setdefault(skill.id, []).append(rank)

        for skill_id, ranks in rank_lists.items():
            scores[skill_id] = sum(1.0 / (k + r) for r in ranks)

        sorted_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]
        return [(self._skills[id_], scores[id_]) for id_ in sorted_ids if id_ in self._skills]
