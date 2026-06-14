"""PlanEngine — state-driven analysis plan generation.

PlanEngine does NOT rely on SkillDAG traversal for skeleton generation.
Instead, it uses:
  1. Domain knowledge (strategy templates) for the plan skeleton
  2. DataState for dynamic adaptation (insert/skip/modify steps)
  3. SkillDAG ONLY for skill selection ("which QC tool to use?")

This separation ensures that:
  - Plan structure comes from biological domain knowledge, not graph edges
  - SkillDAG provides value at scale (skill discovery from large libraries)
  - The system remains interpretable and auditable
"""

from typing import Any, List, Optional

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.llm_fallback import LLMFallbackPlanner
from homomics_lab.agent.plan.models import DataState, Phase, PlannedGap, PlanResult
from homomics_lab.agent.plan.strategies import StrategyLibrary
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import SkillDAG


class PlanEngine:
    """Generates analysis plans based on domain knowledge and data state.

    Usage:
        plan_engine = PlanEngine(skill_registry, skill_dag)
        plan = await plan_engine.plan(
            intent=UserIntent(analysis_type="single_cell_analysis", ...),
            data_state=DataState(has_qc=False, n_cells=5000),
        )
        # plan.phases -> [QC, Normalization, PCA, Clustering, ...]
    """

    def __init__(
        self,
        skill_registry: SkillRegistry,
        skill_dag: Optional[SkillDAG] = None,
        llm_fallback: Optional[LLMFallbackPlanner] = None,
    ):
        self.skill_registry = skill_registry
        self.skill_dag = skill_dag
        self.strategy_library = StrategyLibrary()
        self.llm_fallback = llm_fallback or LLMFallbackPlanner(skill_registry)

    async def plan(
        self,
        intent: UserIntent,
        data_state: Optional[DataState] = None,
    ) -> PlanResult:
        """Generate an analysis plan from user intent and data state.

        Returns:
            PlanResult containing the phase sequence, selected skills, and gaps.
        """
        data_state = data_state or DataState()

        # 1. Select strategy based on intent
        strategy = self.strategy_library.select(intent.analysis_type)

        # 2. If no domain strategy matches, use LLM fallback to build an executable plan
        if strategy.name == "generic":
            return await self.llm_fallback.generate_plan(intent, data_state)

        # 3. Generate skeleton (domain knowledge + state adaptation)
        phases = strategy.generate_skeleton(data_state)

        # 4. Select skills for each phase (SkillDAG assists here)
        for phase in phases:
            if not phase.required:
                continue
            phase.selected_skill = self._select_skill_for_phase(phase, data_state)

        # 5. Detect gaps between phases
        gaps = self._detect_gaps(phases)

        # 6. Build reproducibility context
        reproducibility_context = {
            "plan_engine_version": "0.3.0",
            "strategy": strategy.name,
            "intent": intent.analysis_type,
            "data_state": data_state.to_context(),
        }

        return PlanResult(
            phases=phases,
            strategy_name=strategy.name,
            data_state=data_state,
            gaps=gaps,
            reproducibility_context=reproducibility_context,
        )

    def _select_skill_for_phase(
        self,
        phase: Phase,
        data_state: DataState,
    ) -> Optional[Any]:
        """Select the best skill for a given phase.

        SkillDAG is used here to discover relevant skills and filter conflicts.
        If SkillDAG is not available, falls back to semantic search.
        """
        query = f"{phase.phase_type} {phase.description}"

        if self.skill_dag is not None:
            # Use SkillDAG for structured search
            results = self.skill_dag.search(
                query=query,
                top_k=5,
                min_confidence=0.5,
            )
            if results:
                # Pick the highest-ranked skill
                return results[0].skill

        # Fallback: direct registry search
        skills = self.skill_registry.search(query)
        return skills[0] if skills else None

    def _detect_gaps(self, phases: List[Phase]) -> List[PlannedGap]:
        """Detect potential gaps between consecutive phases.

        A gap occurs when the output schema of one skill does not directly
        match the input schema of the next skill.
        """
        gaps = []
        for i in range(len(phases) - 1):
            current = phases[i]
            next_phase = phases[i + 1]

            if current.selected_skill is None or next_phase.selected_skill is None:
                continue

            # Simple schema compatibility check
            output_schema = current.selected_skill.output_schema
            input_schema = next_phase.selected_skill.input_schema

            gap = self._check_schema_gap(
                from_phase=current.phase_type,
                to_phase=next_phase.phase_type,
                from_skill=current.selected_skill.id,
                to_skill=next_phase.selected_skill.id,
                output_schema=output_schema,
                input_schema=input_schema,
            )
            if gap.gap_type != "none":
                gaps.append(gap)

        return gaps

    @staticmethod
    def _check_schema_gap(
        from_phase: str,
        to_phase: str,
        from_skill: str,
        to_skill: str,
        output_schema: Any,
        input_schema: Any,
    ) -> PlannedGap:
        """Check for schema incompatibilities between two skills."""
        # Empty schemas = no gap (pass-through)
        if not input_schema.properties and not input_schema.required:
            return PlannedGap(
                from_phase=from_phase,
                to_phase=to_phase,
                from_skill=from_skill,
                to_skill=to_skill,
                gap_type="none",
            )

        # Check for missing required fields in output
        missing = []
        for field_name in input_schema.required:
            if field_name not in output_schema.properties:
                missing.append(field_name)

        if missing:
            return PlannedGap(
                from_phase=from_phase,
                to_phase=to_phase,
                from_skill=from_skill,
                to_skill=to_skill,
                gap_type="field_missing",
                estimated_complexity="moderate" if len(missing) > 2 else "simple",
            )

        return PlannedGap(
            from_phase=from_phase,
            to_phase=to_phase,
            from_skill=from_skill,
            to_skill=to_skill,
            gap_type="none",
        )
