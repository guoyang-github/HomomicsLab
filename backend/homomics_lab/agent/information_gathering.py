"""Active information gathering — propose probe skills when data state is incomplete."""

from dataclasses import dataclass
from typing import List, Optional, Set

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.plan.models import DataState
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import SkillDAG


@dataclass
class ProbeSkill:
    """A probe skill proposed to gather missing information."""

    skill_id: str
    reason: str
    missing_key: str
    estimated_cost: str = "low"  # "low" | "medium" | "high"


class InformationGatheringEngine:
    """Decide when to run lightweight probe skills before planning.

    The engine inspects the data state for universal planning keys
    (organism, data_type, n_samples, batch_info).  When a required key is
    missing it proposes a cheap metadata inspection, QC, or summary skill
    from the registry.
    """

    REQUIRED_KEYS: tuple[str, ...] = ("organism", "data_type", "n_samples", "batch_info")

    def __init__(
        self,
        skill_registry: SkillRegistry,
        skill_dag: Optional[SkillDAG] = None,
    ):
        self.skill_registry = skill_registry
        self.skill_dag = skill_dag

    def decide_probes(
        self,
        intent: UserIntent,
        data_state: DataState,
    ) -> List[ProbeSkill]:
        """Return probe skills for any missing required data-state keys."""
        probes: List[ProbeSkill] = []
        for key in self.REQUIRED_KEYS:
            if not data_state.has_field(key):
                probe = self._find_probe_for_key(key, intent)
                if probe is not None:
                    probes.append(probe)
        return probes

    def _find_probe_for_key(
        self,
        missing_key: str,
        intent: UserIntent,
    ) -> Optional[ProbeSkill]:
        """Find the best probe skill for a missing key."""
        candidates = self._candidate_probe_skills()

        # Prefer skills whose names/descriptions mention the missing key.
        for skill in candidates:
            text = f"{skill.name} {skill.description} {skill.category}".lower()
            if missing_key in text or missing_key.replace("_", " ") in text:
                return self._make_probe(skill, missing_key)

        # Fall back to a metadata / qc / summary probe if one exists.
        for skill in candidates:
            text = f"{skill.name} {skill.description} {skill.category}".lower()
            if any(term in text for term in ("metadata", "summary", "inspect", "qc", "quality")):
                return self._make_probe(skill, missing_key)

        if candidates:
            return self._make_probe(candidates[0], missing_key)

        return None

    def _candidate_probe_skills(self) -> List[SkillDefinition]:
        """Return lightweight skills suitable for information gathering."""
        candidates: List[SkillDefinition] = []
        seen: Set[str] = set()
        for term in ("metadata", "qc", "summary", "inspect"):
            for skill in self.skill_registry.search(term):
                if not hasattr(skill, "id") or skill.id in seen:
                    continue
                seen.add(skill.id)
                candidates.append(skill)

        # If no specific probe skill is registered, fall back to all skills
        # and pick the ones with the fewest declared runtime dependencies.
        if not candidates:
            candidates = sorted(
                self.skill_registry.list_all(),
                key=lambda s: len(s.runtime.dependencies),
            )

        return candidates

    @staticmethod
    def _make_probe(skill: SkillDefinition, missing_key: str) -> ProbeSkill:
        """Build a ProbeSkill from a skill definition."""
        cost = "low"
        deps = len(skill.runtime.dependencies)
        if deps > 5:
            cost = "high"
        elif deps > 2:
            cost = "medium"

        return ProbeSkill(
            skill_id=skill.id,
            reason=f"Gather missing '{missing_key}' before analysis planning",
            missing_key=missing_key,
            estimated_cost=cost,
        )
