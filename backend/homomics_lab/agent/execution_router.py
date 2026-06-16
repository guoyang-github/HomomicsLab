"""ExecutionRouter — route a plan phase to the best execution backend.

Foundation-first design: CodeAct / generated code is the default execution
substrate. Curated skills are treated as "pre-validated, version-locked
optimizations" that are preferred when they match well.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from homomics_lab.agent.plan.models import Phase
from homomics_lab.agent.retrieval import RetrievalContext, RetrievedSkill
from homomics_lab.skills.models import SkillDefinition


class ExecutionMode(str, Enum):
    """Supported execution modes for a plan phase."""

    CURATED_SKILL = "curated_skill"
    GENERATED_FROM_TEMPLATE = "generated_from_template"
    CODE_FROM_RETRIEVAL = "code_from_retrieval"
    CODE_FROM_SCRATCH = "code_from_scratch"
    TOOL_ONLY = "tool_only"


class ExecutionRoute:
    """A concrete execution decision for a phase."""

    def __init__(
        self,
        mode: ExecutionMode,
        skill: Optional[SkillDefinition] = None,
        task: str = "",
        language: str = "python",
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
        fallback_message: str = "",
    ):
        self.mode = mode
        self.skill = skill
        self.task = task
        self.language = language
        self.context = context or {}
        self.tools = tools or []
        self.fallback_message = fallback_message


class ExecutionRouter:
    """Select the best execution backend for a plan phase.

    The router is intentionally simple and rule-based today so that its
    decisions are auditable. The thresholds can be overridden via environment
    variables or per-project config.
    """

    def __init__(
        self,
        curated_skill_threshold: float = 0.8,
        schema_compatible_bonus: float = 0.1,
        code_first_domains: Optional[List[str]] = None,
        curated_only_domains: Optional[List[str]] = None,
    ):
        self.curated_skill_threshold = curated_skill_threshold
        self.schema_compatible_bonus = schema_compatible_bonus
        self.code_first_domains = set(code_first_domains or [])
        self.curated_only_domains = set(curated_only_domains or [])

    def route(
        self,
        phase: Phase,
        retrieval_context: Optional[RetrievalContext],
        data_state: Optional[Dict[str, Any]] = None,
        user_preference: str = "auto",
    ) -> ExecutionRoute:
        """Decide how to execute a plan phase.

        Args:
            phase: Plan phase (contains phase_type, description, selected_skill).
            retrieval_context: Combined RAP context (skills, tools, SOPs, ...).
            data_state: Current data state (file formats, QC status, ...).
            user_preference: "auto" | "curated_only" | "code_first".
        """
        data_state = data_state or {}

        # 1. User override
        if user_preference == "curated_only":
            return self._route_curated_only(phase, retrieval_context)
        if user_preference == "code_first":
            return self._route_code_first(phase, retrieval_context)

        # 2. Domain-level override
        intent_type = retrieval_context.intent_type if retrieval_context else ""
        if intent_type in self.curated_only_domains:
            return self._route_curated_only(phase, retrieval_context)
        if intent_type in self.code_first_domains:
            return self._route_code_first(phase, retrieval_context)

        # 3. Tool-only short-circuit for atomic retrieval tasks
        if self._is_tool_only_phase(phase, retrieval_context):
            return ExecutionRoute(
                mode=ExecutionMode.TOOL_ONLY,
                task=f"{phase.phase_type}: {phase.description}",
                tools=self._relevant_tool_names(phase, retrieval_context),
            )

        # 4. Evaluate curated skill fit
        skill, score = self._best_curated_skill(phase, retrieval_context)
        if skill is not None:
            effective_score = score + self.schema_compatible_bonus
            if effective_score >= self.curated_skill_threshold:
                return ExecutionRoute(
                    mode=ExecutionMode.CURATED_SKILL,
                    skill=skill,
                    task=phase.description,
                    context={"phase": phase.phase_type, "parameters": phase.parameters},
                )

        # 5. Generated from template if a lower-scoring skill exists
        if skill is not None:
            return ExecutionRoute(
                mode=ExecutionMode.GENERATED_FROM_TEMPLATE,
                skill=skill,
                task=phase.description,
                context={
                    "phase": phase.phase_type,
                    "parameters": phase.parameters,
                    "template_skill_id": skill.id,
                },
            )

        # 6. Code from retrieval context
        if retrieval_context is not None and (
            retrieval_context.tools or retrieval_context.data_sources or retrieval_context.sops
        ):
            return ExecutionRoute(
                mode=ExecutionMode.CODE_FROM_RETRIEVAL,
                task=phase.description,
                context={
                    "phase": phase.phase_type,
                    "parameters": phase.parameters,
                    "data_state": data_state,
                },
                tools=self._relevant_tool_names(phase, retrieval_context),
            )

        # 7. Fallback: generate from scratch
        return ExecutionRoute(
            mode=ExecutionMode.CODE_FROM_SCRATCH,
            task=phase.description,
            context={"phase": phase.phase_type, "parameters": phase.parameters, "data_state": data_state},
        )

    def _route_curated_only(
        self,
        phase: Phase,
        retrieval_context: Optional[RetrievalContext],
    ) -> ExecutionRoute:
        skill, _ = self._best_curated_skill(phase, retrieval_context)
        if skill is not None:
            return ExecutionRoute(
                mode=ExecutionMode.CURATED_SKILL,
                skill=skill,
                task=phase.description,
            )
        return ExecutionRoute(
            mode=ExecutionMode.CODE_FROM_SCRATCH,
            task=phase.description,
            fallback_message="No curated skill available in curated_only mode; falling back to generated code.",
        )

    def _route_code_first(
        self,
        phase: Phase,
        retrieval_context: Optional[RetrievalContext],
    ) -> ExecutionRoute:
        skill, _ = self._best_curated_skill(phase, retrieval_context)
        if skill is not None:
            return ExecutionRoute(
                mode=ExecutionMode.GENERATED_FROM_TEMPLATE,
                skill=skill,
                task=phase.description,
                context={"template_skill_id": skill.id},
            )
        return ExecutionRoute(
            mode=ExecutionMode.CODE_FROM_RETRIEVAL,
            task=phase.description,
            context={"phase": phase.phase_type, "parameters": phase.parameters},
            tools=self._relevant_tool_names(phase, retrieval_context),
        )

    def _best_curated_skill(
        self,
        phase: Phase,
        retrieval_context: Optional[RetrievalContext],
    ) -> tuple[Optional[SkillDefinition], float]:
        """Return the best matching curated skill and its score."""
        if phase.selected_skill is not None:
            return phase.selected_skill, 1.0

        if retrieval_context is None or not retrieval_context.skills:
            return None, 0.0

        best: Optional[RetrievedSkill] = None
        best_score = 0.0
        for rs in retrieval_context.skills:
            score = rs.semantic_score + rs.graph_boost
            if score > best_score:
                best = rs
                best_score = score
        if best is None:
            return None, 0.0
        return best.skill, best_score

    def _is_tool_only_phase(
        self,
        phase: Phase,
        retrieval_context: Optional[RetrievalContext],
    ) -> bool:
        """Heuristic: some phases are pure lookups and need no code/skill."""
        lookup_phase_types = {"literature_review", "pubmed_search", "database_query", "file_lookup"}
        if phase.phase_type in lookup_phase_types:
            return True
        if retrieval_context is None:
            return False
        query = f"{phase.phase_type} {phase.description}".lower()
        return "query" in query and ("pubmed" in query or "uniprot" in query or "search" in query)

    def _relevant_tool_names(
        self,
        phase: Phase,
        retrieval_context: Optional[RetrievalContext],
    ) -> List[str]:
        """Return names of tools that look relevant to this phase.

        Tools are already ranked by the SkillRetriever; here we just take the
        top candidates. In the future this can be refined with phase-specific
        reranking.
        """
        if retrieval_context is None:
            return []
        return [t.name for t in retrieval_context.tools[:5]]
