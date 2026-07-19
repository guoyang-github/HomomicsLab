"""Hybrid semantic search for skills — the single skill-search implementation.

Dense sentence embeddings (sentence-transformers) capture synonyms and
paraphrases (e.g. "QC" vs "quality control"); sparse TF-IDF provides exact
token matching and requires no model load. The two rankings are fused with
Reciprocal Rank Fusion (RRF) so each contributes without brittle score
normalization.

The engine degrades gracefully: when sentence-transformers is not installed
or the dense model cannot be loaded, search falls back to sparse TF-IDF only.

This module is the sole skill search implementation — it subsumes the former
TF-IDF-only and dense-only variants.
"""

import logging
from typing import Dict, List, Optional, Tuple

from homomics_lab.skills.models import SkillDefinition

logger = logging.getLogger(__name__)


class _SparseSkillSearch:
    """TF-IDF + cosine similarity over skill metadata. Zero external services."""

    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}
        self._vectorizer = None
        self._vectors = None
        self._skill_ids: List[str] = []
        self._dirty = True

    def _get_vectorizer(self):
        """Lazy-import scikit-learn to avoid hard import-time dependency."""
        if self._vectorizer is None:
            from sklearn.feature_extraction.text import TfidfVectorizer

            self._vectorizer = TfidfVectorizer(
                lowercase=True,
                stop_words="english",
                ngram_range=(1, 2),
                max_features=5000,
            )
        return self._vectorizer

    def add(self, skill: SkillDefinition) -> None:
        """Add a skill to the index."""
        self._skills[skill.id] = skill
        self._dirty = True

    def remove(self, skill_id: str) -> None:
        """Remove a skill from the index."""
        self._skills.pop(skill_id, None)
        self._dirty = True

    def _build_index(self) -> None:
        """Rebuild the TF-IDF index."""
        if not self._skills:
            self._vectors = None
            self._skill_ids = []
            self._dirty = False
            return

        from sklearn.metrics.pairwise import cosine_similarity

        texts = []
        self._skill_ids = []
        for skill_id, skill in self._skills.items():
            # Combine name, description, keywords, and category for embedding
            text_parts = [
                skill.name,
                skill.description,
                skill.category,
            ]
            text_parts.extend(skill.metadata.get("tags", []))
            text_parts.extend(skill.metadata.get("keywords", []))
            text_parts.extend(skill.metadata.get("supported_tools", []))
            text_parts.append(skill.metadata.get("primary_tool", ""))
            texts.append(" ".join(filter(None, text_parts)))
            self._skill_ids.append(skill_id)

        vectorizer = self._get_vectorizer()
        self._vectors = vectorizer.fit_transform(texts)
        self._dirty = False
        # Keep cosine_similarity bound for search() to avoid repeated import
        self._cosine_similarity = cosine_similarity

    def search(self, query: str, top_k: int = 10) -> List[Tuple[SkillDefinition, float]]:
        """Search skills by TF-IDF cosine similarity.

        Returns list of (skill, score) tuples sorted by relevance.
        """
        if self._dirty:
            self._build_index()

        if not self._skills or self._vectors is None:
            return []

        vectorizer = self._get_vectorizer()
        query_vec = vectorizer.transform([query])
        similarities = self._cosine_similarity(query_vec, self._vectors).flatten()

        # Get top-k results
        indexed_scores = list(enumerate(similarities))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed_scores[:top_k]:
            if score > 0:
                skill_id = self._skill_ids[idx]
                results.append((self._skills[skill_id], float(score)))

        return results


class _DenseSkillSearch:
    """Dense embeddings via sentence-transformers (lazy model load)."""

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: Optional[str] = None):
        self._skills: Dict[str, SkillDefinition] = {}
        self._model_name = model_name or self.DEFAULT_MODEL
        self._model = None
        self._embeddings: Optional[List] = None
        self._skill_ids: List[str] = []
        self._dirty = True

    def _load_model(self):
        """Lazy-load the sentence-transformers model.

        Prefer the local Hugging Face cache (``local_files_only=True``) so that
        startup never blocks on network HEAD/etag checks when the model is
        already cached. Only fall back to an online load on a genuine cache miss.
        """
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            try:
                self._model = SentenceTransformer(self._model_name, local_files_only=True)
                logger.info(
                    "Loaded sentence-transformers model from local cache: %s",
                    self._model_name,
                )
            except Exception:
                logger.info(
                    "Local cache miss for %s; falling back to online load",
                    self._model_name,
                    exc_info=True,
                )
                self._model = SentenceTransformer(self._model_name)

    def add(self, skill: SkillDefinition) -> None:
        """Add a skill to the index."""
        self._skills[skill.id] = skill
        self._dirty = True

    def remove(self, skill_id: str) -> None:
        """Remove a skill from the index."""
        self._skills.pop(skill_id, None)
        self._dirty = True

    def _skill_to_text(self, skill: SkillDefinition) -> str:
        """Convert skill to searchable text."""
        parts = [
            skill.name,
            skill.description,
            skill.category.replace("-", " ").replace("_", " "),
        ]
        parts.extend(skill.metadata.get("tags", []))
        parts.extend(skill.metadata.get("keywords", []))
        parts.extend(skill.metadata.get("supported_tools", []))
        parts.append(skill.metadata.get("primary_tool", ""))
        return " ".join(filter(None, parts))

    def _build_index(self) -> None:
        """Rebuild the embedding index."""
        if not self._skills:
            self._embeddings = None
            self._skill_ids = []
            self._dirty = False
            return

        self._load_model()
        self._skill_ids = []
        texts = []
        for skill_id, skill in self._skills.items():
            self._skill_ids.append(skill_id)
            texts.append(self._skill_to_text(skill))

        self._embeddings = self._model.encode(texts, convert_to_tensor=False)
        self._dirty = False

    def search(self, query: str, top_k: int = 10) -> List[Tuple[SkillDefinition, float]]:
        """Search skills by dense embedding cosine similarity.

        Returns list of (skill, score) tuples sorted by relevance.
        Score is cosine similarity in [0, 1].
        """
        if self._dirty:
            self._build_index()

        if not self._skills or self._embeddings is None:
            return []

        self._load_model()
        query_embedding = self._model.encode([query], convert_to_tensor=False)

        # Compute cosine similarities
        import numpy as np

        # Normalize embeddings
        query_norm = query_embedding / np.linalg.norm(query_embedding, axis=1, keepdims=True)
        skill_norms = self._embeddings / np.linalg.norm(self._embeddings, axis=1, keepdims=True)

        similarities = np.dot(skill_norms, query_norm.T).flatten()

        # Get top-k results
        indexed_scores = list(enumerate(similarities))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed_scores[:top_k]:
            if score > 0.15:  # Lower threshold for semantic search
                skill_id = self._skill_ids[idx]
                results.append((self._skills[skill_id], float(score)))

        return results


class HybridSkillSearch:
    """Combine dense sentence embeddings with sparse TF-IDF for skill retrieval.

    This is the only skill search engine used by ``SkillRegistry``.
    """

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: Optional[str] = None):
        self._skills: Dict[str, SkillDefinition] = {}
        self._model_name = model_name or self.DEFAULT_MODEL
        self._dense: Optional[_DenseSkillSearch] = None
        self._sparse = _SparseSkillSearch()
        self._dense_available: Optional[bool] = None

    @property
    def _dense_enabled(self) -> bool:
        if self._dense_available is None:
            try:
                self._dense = _DenseSkillSearch(model_name=self._model_name)
                self._dense_available = True
            except Exception as exc:
                # Model construction failure should not break skill search.
                logger.warning(
                    "Dense skill search unavailable (%s); falling back to sparse search",
                    exc,
                )
                self._dense_available = False
        return self._dense_available

    def _disable_dense(self, exc: Exception) -> None:
        """Permanently disable the dense index after a runtime failure."""
        logger.warning(
            "Dense skill search failed (%s); falling back to sparse search", exc
        )
        self._dense_available = False
        self._dense = None

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
        combined robustly without cross-index calibration. A dense failure
        (e.g. model not cached and no network) degrades to sparse-only results.
        """
        sparse_results = self._sparse.search(query, top_k=top_k * 2)
        dense_results: List[Tuple[SkillDefinition, float]] = []
        if self._dense_enabled and self._dense is not None:
            try:
                dense_results = self._dense.search(query, top_k=top_k * 2)
            except Exception as exc:
                self._disable_dense(exc)

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
