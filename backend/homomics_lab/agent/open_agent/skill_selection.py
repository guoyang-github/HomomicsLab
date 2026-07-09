"""Skill selection for the Open Agent Planner.

Constrains LLM skill choices to the registered SkillRegistry white list.
"""

from typing import List, Optional

from homomics_lab.agent.open_agent.models import CapabilityCandidate, SkillCallIntent
from homomics_lab.skills.capability_index import CapabilityType
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry, get_default_registry


class SkillSelector:
    """Select and validate skills from the registry for the open agent."""

    def __init__(self, skill_registry: Optional[SkillRegistry] = None):
        self.skill_registry = skill_registry or get_default_registry()

    def select_from_capabilities(
        self,
        capabilities: List[CapabilityCandidate],
    ) -> List[SkillDefinition]:
        """Return registered skills referenced by ``capabilities``."""
        skills: List[SkillDefinition] = []
        seen: set = set()
        for c in capabilities:
            if c.type != CapabilityType.SKILL:
                continue
            skill = self.skill_registry.get(c.id)
            if skill is None:
                skill = c.payload.get("skill")
            if skill is None or skill.id in seen:
                continue
            seen.add(skill.id)
            skills.append(skill)
        return skills

    def validate_intents(
        self,
        intents: List[SkillCallIntent],
    ) -> List[SkillCallIntent]:
        """Drop intents that reference unknown skills.

        Returns only intents whose skill is registered.
        """
        validated: List[SkillCallIntent] = []
        for intent in intents:
            if self.skill_registry.get(intent.skill_id) is not None:
                validated.append(intent)
        return validated
