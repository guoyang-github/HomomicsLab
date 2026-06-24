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

from typing import Any, Dict, List, Optional, Tuple

from homomics_lab.agent.information_gathering import InformationGatheringEngine
from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.literature_retriever import LiteratureRetriever
from homomics_lab.agent.plan.llm_fallback import LLMFallbackPlanner
from homomics_lab.agent.plan.models import DataState, Phase, PlannedGap, PlanResult
from homomics_lab.agent.plan.strategies import AnalysisStrategy, StrategyLibrary
from homomics_lab.agent.retrieval import SkillRetriever
from homomics_lab.agent.plan.validator import PlanValidator
from homomics_lab.config import settings
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.skill_dag import SkillDAG
from homomics_lab.tools.registry import ToolRegistry


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
        skill_retriever: Optional[SkillRetriever] = None,
        llm_fallback: Optional[LLMFallbackPlanner] = None,
        cbkb: Optional[CBKB] = None,
        tool_registry: Optional[ToolRegistry] = None,
        data_sources: Optional[List[Dict[str, Any]]] = None,
        literature_retriever: Optional[LiteratureRetriever] = None,
        enable_information_gathering: bool = False,
    ):
        self.skill_registry = skill_registry
        self.skill_dag = skill_dag
        self.enable_information_gathering = enable_information_gathering
        if literature_retriever is None and settings.literature_retrieval_enabled:
            literature_retriever = LiteratureRetriever()
        self.skill_retriever = skill_retriever or SkillRetriever(
            skill_registry=skill_registry,
            skill_dag=skill_dag,
            tool_registry=tool_registry,
            data_sources=data_sources,
            literature_retriever=literature_retriever,
        )
        self.plan_validator = PlanValidator(skill_registry=skill_registry)
        self.strategy_library = StrategyLibrary(skill_registry=skill_registry)
        self.information_gathering = InformationGatheringEngine(
            skill_registry=skill_registry,
            skill_dag=skill_dag,
        )
        self.llm_fallback = llm_fallback or LLMFallbackPlanner(skill_registry)
        self.cbkb = cbkb

    async def plan(
        self,
        intent: UserIntent,
        data_state: Optional[DataState] = None,
        top_k: int = 1,
    ) -> PlanResult:
        """Generate an analysis plan from user intent and data state.

        Args:
            intent: The user's analysis intent.
            data_state: Current known data state.
            top_k: Number of strategy candidates to consider.  When ``top_k > 1``
                a lightweight beam search ranks candidate plans by gaps and
                skill coverage.  Defaults to 1 for backward compatibility.

        Returns:
            PlanResult containing the phase sequence, selected skills, and gaps.
        """
        data_state = data_state or DataState()

        # 1. Active information gathering: if enabled and critical keys are
        # missing, return an information-request plan instead of a premature
        # analysis plan.  Disabled by default to preserve backward compatibility
        # with callers that supply an empty DataState.
        if self.enable_information_gathering:
            probes = self.information_gathering.decide_probes(intent, data_state)
        else:
            probes = []
        if probes and intent.analysis_type != "information_gathering":
            probe_list = "\n".join(
                f"- {p.skill_id}: {p.reason} (cost: {p.estimated_cost})"
                for p in probes
            )
            return PlanResult(
                phases=[],
                strategy_name="information_gathering",
                data_state=data_state,
                is_information_request=True,
                suggestion_text=(
                    "Missing critical metadata. Please run the following probe skills "
                    f"so I can build an accurate plan:\n{probe_list}"
                ),
                reproducibility_context={"probes": [self._probe_to_dict(p) for p in probes]},
            )

        # 2. Select strategy based on intent (probabilistic when top_k > 1).
        if top_k > 1:
            ranked = self.strategy_library.select_top_k(
                intent.analysis_type, data_state, top_k=top_k
            )
            candidates = [strategy for strategy, _score in ranked]
        else:
            strategy = self.strategy_library.select(intent.analysis_type)
            candidates = [strategy]

        # 3. Build candidate plans and pick the best one.
        candidate_plans: List[PlanResult] = []
        for strategy in candidates:
            plan_result = await self._build_plan_for_strategy(
                intent, data_state, strategy
            )
            candidate_plans.append(plan_result)

        plan_result = self._pick_best_plan(candidate_plans)

        # 4. Validate and enrich with SkillDAG risk exposure.
        validation_report = self.plan_validator.validate(plan_result)
        reproducibility_context = dict(plan_result.reproducibility_context)
        reproducibility_context["validation"] = {
            "valid": validation_report.valid,
            "errors": [
                {"severity": e.severity, "phase": e.phase, "skill_id": e.skill_id, "message": e.message}
                for e in validation_report.errors
            ],
            "warnings": [
                {"severity": w.severity, "phase": w.phase, "skill_id": w.skill_id, "message": w.message}
                for w in validation_report.warnings
            ],
        }
        plan_result.reproducibility_context = reproducibility_context

        if self.skill_dag is not None:
            plan_result.risks.extend(
                self._evaluate_skill_dag_risks(plan_result)
            )

        return plan_result

    async def _build_plan_for_strategy(
        self,
        intent: UserIntent,
        data_state: DataState,
        strategy: AnalysisStrategy,
    ) -> PlanResult:
        """Build a PlanResult for a single selected strategy."""
        if strategy.name == "generic":
            return await self.llm_fallback.generate_plan(intent, data_state)

        phases = strategy.generate_skeleton(data_state)

        retrieval_query = self._build_retrieval_query(intent, phases)
        retrieval_context = await self.skill_retriever.retrieve(
            query=retrieval_query,
            intent_type=intent.analysis_type,
            data_sources=strategy.data_sources,
            include_literature=self.skill_retriever.literature_retriever is not None,
        )

        learned_defaults: List[Dict[str, Any]] = []
        for phase in phases:
            phase.selected_skill = self._select_skill_for_phase(
                phase, data_state, retrieval_context
            )
            injected = self._apply_learned_defaults(phase)
            learned_defaults.extend(injected)

        gaps = self._detect_gaps(phases)

        reproducibility_context = {
            "plan_engine_version": "0.3.0",
            "strategy": strategy.name,
            "intent": intent.analysis_type,
            "data_state": data_state.to_context(),
            "retrieval_context": retrieval_context.to_prompt_context(),
            "learned_defaults": learned_defaults,
        }

        return PlanResult(
            phases=phases,
            strategy_name=strategy.name,
            data_state=data_state,
            gaps=gaps,
            reproducibility_context=reproducibility_context,
            phase_transitions=strategy.phase_transitions,
        )

    @staticmethod
    def _pick_best_plan(candidate_plans: List[PlanResult]) -> PlanResult:
        """Pick the candidate plan with the fewest gaps and highest skill coverage."""
        if len(candidate_plans) == 1:
            return candidate_plans[0]

        def _plan_score(plan: PlanResult) -> Tuple[int, int]:
            gap_count = len([g for g in plan.gaps if g.gap_type != "none"])
            skill_count = len(plan.skill_sequence)
            return (-skill_count, gap_count)

        candidate_plans.sort(key=_plan_score)
        return candidate_plans[0]

    @staticmethod
    def _probe_to_dict(probe: Any) -> Dict[str, Any]:
        return {
            "skill_id": probe.skill_id,
            "reason": probe.reason,
            "missing_key": probe.missing_key,
            "estimated_cost": probe.estimated_cost,
        }

    def _evaluate_skill_dag_risks(self, plan_result: PlanResult) -> List[Dict[str, Any]]:
        """Evaluate SkillDAG risks for a plan result."""
        risks: List[Dict[str, Any]] = []
        if self.skill_dag is None:
            return risks

        skill_sequence = plan_result.skill_sequence
        validation = self.skill_dag.validate_sequence(skill_sequence)

        for error in validation.errors:
            risk_type = "conflict"
            if "depends" in error.lower():
                risk_type = "dependency"
            risks.append({
                "type": risk_type,
                "severity": "error",
                "message": error,
                "skill_ids": skill_sequence,
            })

        for warning in validation.warnings:
            risks.append({
                "type": "dependency",
                "severity": "warning",
                "message": warning,
                "skill_ids": skill_sequence,
            })

        # Informational risks: high-confidence alternatives exist.
        for skill_id in skill_sequence:
            alternatives = self.skill_dag.get_alternatives(skill_id)
            for alt_id, confidence in alternatives:
                if confidence >= 0.7:
                    risks.append({
                        "type": "alternative",
                        "severity": "warning",
                        "message": (
                            f"High-confidence alternative to '{skill_id}' available: "
                            f"'{alt_id}' (confidence={confidence:.2f})"
                        ),
                        "skill_ids": [skill_id, alt_id],
                    })

        return risks

    @staticmethod
    def _build_retrieval_query(intent: UserIntent, phases: List[Phase]) -> str:
        """Build a rich query for skill retrieval from intent and skeleton."""
        parts = [intent.analysis_type]
        keywords = getattr(intent, "keywords", None) or []
        parts.extend(keywords)
        for phase in phases:
            parts.append(phase.phase_type)
            if phase.description:
                parts.append(phase.description)
        return " ".join(parts)

    def _select_skill_for_phase(
        self,
        phase: Phase,
        data_state: DataState,
        retrieval_context: Optional[Any] = None,
    ) -> Optional[Any]:
        """Select the best skill for a given phase.

        When a retrieval context is available we re-rank the retrieved skills
        by how well they match the phase type/description. Otherwise we fall
        back to direct registry semantic search.
        """
        query = f"{phase.phase_type} {phase.description}"

        if retrieval_context is not None and retrieval_context.skills:
            # Re-rank retrieved skills for this specific phase
            ranked = self._rank_skills_for_phase(query, retrieval_context.skills)
            if ranked:
                return ranked[0].skill

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

    def _apply_learned_defaults(
        self,
        phase: Phase,
    ) -> List[Dict[str, Any]]:
        """Inject historically successful parameter defaults from CBKB.

        Only fills parameters that are absent from the phase and present in the
        skill's input schema.  Requires at least 3 historical samples.
        """
        injected: List[Dict[str, Any]] = []
        if self.cbkb is None or phase.selected_skill is None:
            return injected

        schema_props = phase.selected_skill.input_schema.properties or {}
        if not schema_props:
            return injected

        suggestions = self.cbkb.suggest_parameters(phase.selected_skill.id)
        seen_params: set = set()
        for suggestion in suggestions:
            param_name = suggestion["param_name"]
            if param_name in seen_params:
                continue
            seen_params.add(param_name)
            if param_name not in schema_props:
                continue
            if param_name in phase.parameters:
                continue
            if suggestion.get("samples", 0) < 3:
                continue
            phase.parameters[param_name] = suggestion["param_value"]
            injected.append(
                {
                    "phase": phase.phase_type,
                    "skill_id": phase.selected_skill.id,
                    "param_name": param_name,
                    "param_value": suggestion["param_value"],
                    "mean_outcome": suggestion["mean_outcome"],
                    "samples": suggestion["samples"],
                }
            )
        return injected

    @staticmethod
    def _rank_skills_for_phase(
        query: str,
        retrieved_skills: List[Any],
    ) -> List[Any]:
        """Re-rank retrieved skills for a specific phase query.

        Simple keyword matching boost on top of the retrieval score.
        """
        query_lower = query.lower()
        scored = []
        for rs in retrieved_skills:
            text = " ".join([
                rs.skill.name,
                rs.skill.description,
                rs.skill.category,
                *rs.skill.metadata.get("keywords", []),
            ]).lower()
            keyword_hits = sum(1 for token in query_lower.split() if len(token) > 2 and token in text)
            score = rs.semantic_score + rs.graph_boost + keyword_hits * 0.05
            scored.append((score, rs))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [rs for _, rs in scored]

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
