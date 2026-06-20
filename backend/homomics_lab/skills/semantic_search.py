"""Semantic search for skills using TF-IDF + cosine similarity.

Lightweight, no external vector DB required. Uses scikit-learn.
"""

from typing import Dict, List

from homomics_lab.skills.models import SkillDefinition


class SkillSemanticSearch:
    """Semantic search over skills using TF-IDF embeddings."""

    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}
        self._vectorizer = None
        self._vectors = None
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

    def search(self, query: str, top_k: int = 10) -> List[tuple[SkillDefinition, float]]:
        """Search skills by semantic similarity.

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

    def search_ids(self, query: str, top_k: int = 10) -> List[str]:
        """Search and return only skill IDs."""
        results = self.search(query, top_k)
        return [skill.id for skill, _ in results]
