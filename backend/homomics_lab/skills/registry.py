from typing import Any, Dict, List, Optional

from homomics_lab.skills.models import SkillDefinition
from homomics_lab.config import settings


class SkillRegistry:
    """Registry for skill definitions with keyword and semantic search."""

    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}
        self._semantic = self._create_search_engine()

    def _create_search_engine(self):
        """Create the semantic search engine based on config."""
        if settings.semantic_search_model:
            from homomics_lab.skills.semantic_search_v2 import SemanticSearchEngine

            return SemanticSearchEngine(model_name=settings.semantic_search_model)

        # Default: hybrid dense + sparse retrieval.
        from homomics_lab.skills.semantic_search_hybrid import HybridSkillSearch

        return HybridSkillSearch()

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.id] = skill
        self._semantic.add(skill)

    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._skills.get(skill_id)

    def activate(
        self,
        skill_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[SkillDefinition]:
        """Activate (load full body) a discovery-level skill.

        Progressive disclosure: the runtime registry may only hold
        name/description for a skill until it is actually used. Calling
        ``activate`` loads the full SKILL.md body, scripts, requirements, etc.
        into the existing SkillDefinition object.

        Args:
            skill_id: Skill to activate.
            context: Optional execution context for rendering dynamic content
                (``arguments``, ``inputs``, etc.).
        """
        skill = self._skills.get(skill_id)
        if skill is None:
            return None
        if skill.metadata.get("disclosure_level") == "activated":
            return skill

        from homomics_lab.skills.loader import SkillLoader

        SkillLoader().activate(skill, context=context)
        # Re-add to the semantic index so it picks up the full metadata.
        self._semantic.add(skill)
        return skill

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
        self._semantic = self._create_search_engine()


_default_registry = SkillRegistry()


def get_default_registry() -> SkillRegistry:
    return _default_registry
