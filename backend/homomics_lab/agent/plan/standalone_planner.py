"""Standalone skill planner for capability-first routing.

When the user request does not carry a strong domain signal, the standalone
planner tries to match the request against skills that are not tied to a
specific domain and assembles a small linear execution plan. This keeps
generic, reusable capabilities available without forcing every skill into a
domain strategy.
"""

from typing import List, Optional

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.intent.models import intent_strategy_key
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry, get_default_registry


class StandaloneSkillPlanner:
    """Plan a linear workflow from standalone / domain-agnostic skills.

    The planner is intentionally simple: it performs a semantic search over the
    skill registry, keeps the top-k standalone matches, and returns a linear
    plan. If no standalone skill matches, it returns ``None`` so the caller can
    fall back to domain planning or LLM fallback.
    """

    DEFAULT_TOP_K = 3
    DERIVATION = "standalone-skill"
    RISK_LEVEL = "low"

    def __init__(self, skill_registry: Optional[SkillRegistry] = None, top_k: int = DEFAULT_TOP_K):
        self.skill_registry = skill_registry or get_default_registry()
        self.top_k = top_k

    def plan(self, intent: UserIntent) -> Optional[PlanResult]:
        """Build a standalone plan for ``intent`` if matching skills exist.

        Args:
            intent: The analyzed user intent.

        Returns:
            A linear ``PlanResult`` built from standalone skills, or ``None`` if
            no standalone skill is a good match.
        """
        query = self._build_query(intent)
        if not query:
            return None

        matches = self.skill_registry.semantic_search(query, top_k=self.top_k)
        if not matches:
            # Fall back to keyword search; it is cheaper and catches exact names.
            keyword_matches = self.skill_registry.search(query)
            matches = [(skill, 0.0) for skill in keyword_matches]

        selected: List[SkillDefinition] = []
        seen: set = set()
        for skill, _score in matches:
            if skill.id in seen:
                continue
            # Only use skills that are explicitly standalone / domain-agnostic.
            if not skill.is_standalone:
                continue
            selected.append(skill)
            seen.add(skill.id)
            if len(selected) >= self.top_k:
                break

        if not selected:
            return None

        phases: List[Phase] = []
        for skill in selected:
            phases.append(
                Phase(
                    phase_type=skill.id,
                    description=skill.description or f"Execute skill {skill.name}",
                    required=True,
                    selected_skill=skill,
                    derivation=self.DERIVATION,
                    risk_level=self.RISK_LEVEL,
                )
            )

        return PlanResult(
            phases=phases,
            strategy_name="standalone-skill-planner",
            data_state=DataState(),
            derivation=self.DERIVATION,
            risk_level=self.RISK_LEVEL,
            approval_required=False,
        )

    def _build_query(self, intent: UserIntent) -> str:
        """Build a search query from the intent."""
        # Prefer the original user message because it carries the richest
        # semantic signal. Fall back to structured fields for robustness.
        if intent.original_message:
            return intent.original_message
        parts = [intent_strategy_key(intent)]
        if intent.target:
            parts.append(intent.target)
        if intent.domain:
            parts.append(intent.domain)
        return " ".join(parts)
