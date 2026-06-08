from typing import Dict, List, Optional
from homics_lab.skills.models import SkillDefinition


class SkillRegistry:
    """Registry for skill definitions."""

    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.id] = skill

    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._skills.get(skill_id)

    def list_all(self) -> List[SkillDefinition]:
        return list(self._skills.values())

    def list_by_category(self, category: str) -> List[SkillDefinition]:
        return [s for s in self._skills.values() if s.category == category]

    def search(self, query: str) -> List[SkillDefinition]:
        """Simple keyword search."""
        query = query.lower()
        results = []
        for skill in self._skills.values():
            if (query in skill.name.lower() or
                query in skill.description.lower() or
                query in skill.category.lower() or
                any(query in tag.lower() for tag in skill.metadata.get("tags", []))):
                results.append(skill)
        return results

    def reset(self) -> None:
        self._skills.clear()


_default_registry = SkillRegistry()


def get_default_registry() -> SkillRegistry:
    return _default_registry
