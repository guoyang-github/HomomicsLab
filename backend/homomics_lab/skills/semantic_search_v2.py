"""Semantic search for skills using sentence-transformers.

Higher quality embeddings than TF-IDF. Uses a lightweight model
(all-MiniLM-L6-v2) for good quality/speed tradeoff.
"""

from typing import Dict, List, Optional

from homomics_lab.skills.models import SkillDefinition


class SemanticSearchEngine:
    """Semantic search over skills using dense embeddings."""

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: Optional[str] = None):
        self._skills: Dict[str, SkillDefinition] = {}
        self._model_name = model_name or self.DEFAULT_MODEL
        self._model = None
        self._embeddings: Optional[List] = None
        self._skill_ids: List[str] = []
        self._dirty = True

    def _load_model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

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

    def search(self, query: str, top_k: int = 10) -> List[tuple[SkillDefinition, float]]:
        """Search skills by semantic similarity.

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

    def search_ids(self, query: str, top_k: int = 10) -> List[str]:
        """Search and return only skill IDs."""
        results = self.search(query, top_k)
        return [skill.id for skill, _ in results]
