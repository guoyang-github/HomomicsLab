"""Cross-domain plan composition.

When a user request spans multiple analysis domains (e.g. "先做单细胞聚类，
再用空间转录组做反卷积"), this planner composes a single coherent plan from
multiple domain strategies. Overlapping phases such as QC or normalization are
deduplicated, and the final plan is marked as cross-domain so the execution
layer can require approval before running it.
"""

import dataclasses
from typing import Dict, List, Optional, Set, Tuple

from homomics_lab.agent.intent import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult


class CrossDomainPlanner:
    """Compose a unified plan from multiple domain strategies.

    The planner is intentionally conservative: it only activates when the intent
    carries explicit multi-domain signals (sub_intents with different domains,
    or structured intent decomposition naming multiple domains). For everything
    else it returns ``None`` so the caller can fall back to single-domain or
    standalone planning.
    """

    DERIVATION = "cross-domain-composition"
    RISK_LEVEL = "medium"

    # Partial order for well-known cross-domain pipelines. Domains earlier in
    # the list are expected to run before domains later in the list when both
    # are present. Unknown domains are appended in discovery order.
    _DOMAIN_ORDER = [
        "single-cell-transcriptomics",
        "spatial-transcriptomics",
        "metagenomics",
        "genomics",
        "transcriptomics",
        "proteomics",
        "epigenomics",
    ]

    # Phases that commonly appear in multiple omics domains and should only be
    # executed once in a cross-domain workflow.
    _OVERLAPPING_PHASES: Set[str] = {
        "data_io",
        "data_loading",
        "qc",
        "quality_control",
        "normalization",
        "normalize",
        "batch_integration",
        "dim_reduction",
        "dimensionality_reduction",
        "pca",
    }

    def __init__(self, plan_engine: PlanEngine):
        self.plan_engine = plan_engine

    async def plan(self, intent: UserIntent) -> Optional[PlanResult]:
        """Build a cross-domain plan if the intent names multiple domains.

        Args:
            intent: The analyzed user intent.

        Returns:
            A merged ``PlanResult`` covering all detected domains, or ``None``
            if the intent only names one or zero domains.
        """
        domains = self._detect_domains(intent)
        if len(domains) < 2:
            return None

        # Generate a sub-plan for each domain.
        sub_plans: List[Tuple[str, PlanResult]] = []
        for domain in domains:
            sub_intent = self._build_domain_sub_intent(intent, domain)
            sub_plan = await self.plan_engine.plan(
                sub_intent,
                data_state=DataState(),
            )
            if not sub_plan.phases:
                continue
            sub_plans.append((domain, sub_plan))

        if len(sub_plans) < 2:
            return None

        merged_phases, merged_transitions = self._merge_sub_plans(sub_plans)
        if not merged_phases:
            return None

        composed_from = [
            {
                "domain": domain,
                "strategy_name": sub_plan.strategy_name,
                "phase_count": len(sub_plan.phases),
            }
            for domain, sub_plan in sub_plans
        ]

        return PlanResult(
            phases=merged_phases,
            strategy_name="cross-domain-composition",
            data_state=DataState(),
            gaps=[],
            reproducibility_context={
                "plan_engine_version": "0.5.0",
                "strategy": "cross-domain-composition",
                "intent": intent.analysis_type,
                "composed_from": composed_from,
            },
            phase_transitions=merged_transitions,
            derivation=self.DERIVATION,
            risk_level=self.RISK_LEVEL,
            approval_required=True,
        )

    @classmethod
    def _detect_domains(cls, intent: UserIntent) -> List[str]:
        """Extract the ordered list of distinct domains referenced by intent."""
        domains: List[str] = []
        seen: Set[str] = set()

        def add(domain: Optional[str]) -> None:
            if not domain:
                return
            if domain not in seen:
                seen.add(domain)
                domains.append(domain)

        add(intent.domain)

        # Sub-intents may name different domains.
        for sub in intent.sub_intents:
            add(sub.domain)

        # Structured decomposition may also carry domain tags.
        structured = getattr(intent, "structured_intent", None)
        if structured is not None:
            add(getattr(structured, "domain", None))
            for sub in getattr(structured, "sub_intents", []) or []:
                add(getattr(sub, "domain", None))

        # Sort according to the known partial order.
        order_index = {d: i for i, d in enumerate(cls._DOMAIN_ORDER)}

        def sort_key(domain: str) -> int:
            return order_index.get(domain, len(cls._DOMAIN_ORDER))

        return sorted(domains, key=sort_key)

    def _build_domain_sub_intent(self, intent: UserIntent, domain: str) -> UserIntent:
        """Create a sub-intent scoped to a single domain.

        The analysis type is chosen to match the domain strategy's
        ``applicable_intents`` so the PlanEngine selects the real domain
        skeleton instead of falling back to the generic/LLM planner.
        """
        strategy = self.plan_engine.strategy_library.get(domain)
        if strategy is not None:
            analysis_type = next(
                (i for i in strategy.applicable_intents if i.endswith("_analysis")),
                f"{domain}_analysis",
            )
        else:
            analysis_type = f"{domain}_analysis"

        return dataclasses.replace(
            intent,
            analysis_type=analysis_type,
            domain=domain,
            sub_intents=[
                sub for sub in intent.sub_intents if sub.domain == domain
            ],
        )

    def _merge_sub_plans(
        self,
        sub_plans: List[Tuple[str, PlanResult]],
    ) -> Tuple[List[Phase], List[Dict[str, str]]]:
        """Merge domain sub-plans, deduplicating overlapping phases."""
        merged_phases: List[Phase] = []
        seen_overlapping: Set[str] = set()
        phase_id_map: Dict[str, str] = {}

        for domain, sub_plan in sub_plans:
            for phase in sub_plan.phases:
                if not phase.required:
                    continue

                is_overlap = phase.phase_type in self._OVERLAPPING_PHASES
                if is_overlap:
                    if phase.phase_type in seen_overlapping:
                        # Skip duplicate overlapping phase, but remember the
                        # domain that contributed it for provenance.
                        for existing in merged_phases:
                            if existing.phase_type == phase.phase_type:
                                if domain not in existing.merged_from_domains:
                                    existing.merged_from_domains.append(domain)
                                break
                        continue
                    seen_overlapping.add(phase.phase_type)

                copied = self._copy_phase(phase)
                if copied.derivation is None:
                    copied.derivation = "domain-strategy"
                if domain not in copied.merged_from_domains:
                    copied.merged_from_domains.append(domain)
                phase_id_map[phase.phase_type] = copied.phase_type
                merged_phases.append(copied)

        # Build linear transitions across the merged phases.
        transitions: List[Dict[str, str]] = []
        for i in range(1, len(merged_phases)):
            transitions.append(
                {
                    "from": merged_phases[i - 1].phase_type,
                    "to": merged_phases[i].phase_type,
                    "type": "followed_by",
                }
            )

        return merged_phases, transitions

    @staticmethod
    def _copy_phase(phase: Phase) -> Phase:
        """Create a deep-ish copy of a phase for cross-domain composition."""
        return dataclasses.replace(
            phase,
            candidate_skills=list(phase.candidate_skills),
            parameters=dict(phase.parameters),
            parameter_recommendations=dict(phase.parameter_recommendations),
            parameter_sources=dict(phase.parameter_sources),
            success_criteria=list(phase.success_criteria),
            merged_from_domains=list(phase.merged_from_domains),
        )
