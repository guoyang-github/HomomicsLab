"""Composite planner with cross-domain bridge skill insertion.

Builds on top of ``CrossDomainPlanner``: after a multi-domain plan is composed,
this planner looks for bridge skills that connect adjacent domain blocks and
inserts additional ``bridge`` phases between them.
"""

from typing import Dict, List, Optional, Set, Tuple

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.plan.cross_domain_planner import CrossDomainPlanner
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import Phase, PlanResult
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry, get_default_registry


class CompositePlanner:
    """Compose a cross-domain plan and enrich it with bridge skills."""

    BRIDGE_PHASE_TYPE = "bridge"
    BRIDGE_DERIVATION = "cross-domain-bridge"
    RISK_LEVEL = "medium"

    def __init__(
        self,
        plan_engine: PlanEngine,
        skill_registry: Optional[SkillRegistry] = None,
        cross_domain_planner: Optional[CrossDomainPlanner] = None,
    ):
        self.plan_engine = plan_engine
        self.skill_registry = skill_registry or get_default_registry()
        self.cross_domain_planner = cross_domain_planner or CrossDomainPlanner(
            plan_engine=plan_engine
        )

    async def plan(self, intent: UserIntent) -> Optional[PlanResult]:
        """Build an enriched cross-domain plan if the intent spans domains.

        Returns ``None`` when the request does not name multiple domains or when
        no cross-domain plan can be composed.
        """
        base_plan = await self.cross_domain_planner.plan(intent)
        if base_plan is None:
            return None

        domains = self._extract_domains(base_plan)
        if len(domains) < 2:
            return None

        enriched_phases = self._insert_bridge_phases(base_plan)
        if enriched_phases is base_plan.phases:
            return base_plan

        transitions = self._build_linear_transitions(enriched_phases)
        reproducibility_context = dict(base_plan.reproducibility_context)
        reproducibility_context["bridge_phases_inserted"] = len(
            [p for p in enriched_phases if p.derivation == self.BRIDGE_DERIVATION]
        )

        return PlanResult(
            phases=enriched_phases,
            strategy_name=base_plan.strategy_name,
            data_state=base_plan.data_state,
            gaps=list(base_plan.gaps),
            reproducibility_context=reproducibility_context,
            is_fallback=base_plan.is_fallback,
            is_information_request=base_plan.is_information_request,
            suggestion_text=base_plan.suggestion_text,
            phase_transitions=transitions,
            risks=list(base_plan.risks),
            strategy_trace=base_plan.strategy_trace,
            derivation=base_plan.derivation,
            risk_level=base_plan.risk_level,
            approval_required=base_plan.approval_required,
        )

    @staticmethod
    def _extract_domains(plan: PlanResult) -> List[str]:
        """Return the ordered list of distinct domains in the plan."""
        composed_from = plan.reproducibility_context.get("composed_from") or []
        if composed_from:
            seen: Set[str] = set()
            domains: List[str] = []
            for item in composed_from:
                domain = item.get("domain")
                if domain and domain not in seen:
                    seen.add(domain)
                    domains.append(domain)
            return domains

        # Fallback: infer from phase metadata.
        seen = set()
        domains = []
        for phase in plan.phases:
            for domain in phase.merged_from_domains:
                if domain not in seen:
                    seen.add(domain)
                    domains.append(domain)
        return domains

    def _insert_bridge_phases(self, plan: PlanResult) -> List[Phase]:
        """Insert bridge phases between adjacent domain blocks when possible."""
        if not plan.phases:
            return plan.phases

        groups = self._group_phases_by_domain(plan.phases)
        if len(groups) < 2:
            return plan.phases

        result: List[Phase] = []
        for i, (domain, phases) in enumerate(groups):
            result.extend(phases)
            if i >= len(groups) - 1:
                continue
            next_domain = groups[i + 1][0]
            bridge_skill = self._find_bridge_skill(domain, next_domain)
            if bridge_skill is not None:
                bridge_phase = self._build_bridge_phase(
                    bridge_skill, domain, next_domain
                )
                result.append(bridge_phase)

        return result

    @staticmethod
    def _group_phases_by_domain(
        phases: List[Phase],
    ) -> List[Tuple[str, List[Phase]]]:
        """Group consecutive phases that share the same primary domain."""
        groups: List[Tuple[str, List[Phase]]] = []
        for phase in phases:
            primary = phase.merged_from_domains[0] if phase.merged_from_domains else ""
            if groups and groups[-1][0] == primary:
                groups[-1][1].append(phase)
            else:
                groups.append((primary, [phase]))
        return groups

    def _find_bridge_skill(
        self,
        domain_a: str,
        domain_b: str,
    ) -> Optional[SkillDefinition]:
        """Find a skill that bridges ``domain_a`` and ``domain_b``.

        First prefer skills whose ``domains`` list contains both domains. If no
        such skill exists, fall back to skills tagged as ``bridge`` or
        ``cross-domain`` whose name/description matches both domains.
        """
        targets = {domain_a, domain_b}

        # Primary criterion: explicit dual-domain affiliation.
        for skill in self.skill_registry.list_all():
            domains = set(skill.domains or [])
            if targets <= domains:
                return skill

        # Fallback: bridge/cross-domain category with domain name matches.
        for skill in self.skill_registry.list_all():
            categories = {c.lower() for c in skill.categories or []}
            if "bridge" not in categories and "cross-domain" not in categories:
                continue
            if self._skill_matches_domains(skill, [domain_a, domain_b]):
                return skill

        return None

    @staticmethod
    def _skill_matches_domains(skill: SkillDefinition, domains: List[str]) -> bool:
        """Return True when the skill's text contains both domain names."""
        text = " ".join(
            [
                skill.name,
                skill.description,
                " ".join(skill.domains or []),
                " ".join(skill.categories or []),
            ]
        ).lower()
        return all((domain or "").lower() in text for domain in domains)

    def _build_bridge_phase(
        self,
        skill: SkillDefinition,
        from_domain: str,
        to_domain: str,
    ) -> Phase:
        """Build a bridge phase connecting two domains."""
        return Phase(
            phase_type=self.BRIDGE_PHASE_TYPE,
            description=(
                f"Bridge step from {from_domain} to {to_domain} "
                f"using {skill.name}"
            ),
            required=True,
            selected_skill=skill,
            derivation=self.BRIDGE_DERIVATION,
            risk_level=self.RISK_LEVEL,
            merged_from_domains=[from_domain, to_domain],
        )

    @staticmethod
    def _build_linear_transitions(phases: List[Phase]) -> List[Dict[str, str]]:
        """Build linear ``followed_by`` transitions across all phases."""
        transitions: List[Dict[str, str]] = []
        for i in range(1, len(phases)):
            transitions.append(
                {
                    "from": phases[i - 1].phase_type,
                    "to": phases[i].phase_type,
                    "type": "followed_by",
                }
            )
        return transitions
