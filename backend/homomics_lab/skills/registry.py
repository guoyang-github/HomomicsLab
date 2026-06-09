from typing import Dict, List, Optional

from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.semantic_search import SkillSemanticSearch


class SkillRegistry:
    """Registry for skill definitions with keyword and semantic search."""

    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}
        self._semantic = SkillSemanticSearch()

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.id] = skill
        self._semantic.add(skill)

    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._skills.get(skill_id)

    def list_all(self) -> List[SkillDefinition]:
        return list(self._skills.values())

    def list_by_category(self, category: str) -> List[SkillDefinition]:
        return [s for s in self._skills.values() if s.category == category]

    def search(self, query: str) -> List[SkillDefinition]:
        """Search skills by keyword (legacy) or semantic similarity.

        Falls back to keyword search if semantic search returns no results.
        """
        # Try semantic search first
        semantic_results = self._semantic.search(query, top_k=10)
        if semantic_results:
            return [skill for skill, _ in semantic_results]

        # Fall back to keyword search
        query = query.lower()
        results = []
        for skill in self._skills.values():
            if (query in skill.name.lower() or
                query in skill.description.lower() or
                query in skill.category.lower() or
                any(query in tag.lower() for tag in skill.metadata.get("tags", []))):
                results.append(skill)
        return results

    def semantic_search(self, query: str, top_k: int = 10) -> List[tuple[SkillDefinition, float]]:
        """Search skills by semantic similarity with scores."""
        return self._semantic.search(query, top_k)

    def reset(self) -> None:
        self._skills.clear()
        self._semantic = SkillSemanticSearch()


_default_registry = SkillRegistry()


def get_default_registry() -> SkillRegistry:
    return _default_registry
