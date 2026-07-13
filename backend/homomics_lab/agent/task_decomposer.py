import dataclasses
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.capability_assembler import CapabilityAssembler
from homomics_lab.agent.plan.composite_planner import CompositePlanner
from homomics_lab.agent.plan.cross_domain_planner import CrossDomainPlanner
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult, SuccessCriterion
from homomics_lab.agent.open_agent.planner import OpenAgentPlanner
from homomics_lab.agent.plan.standalone_planner import StandaloneSkillPlanner
from homomics_lab.agent.plan.template import AnalysisTemplate
from homomics_lab.agent.plan.template_store import AnalysisTemplateStore
from homomics_lab.config import settings
from homomics_lab.models.common import HITLCheckpoint, HITLTrigger, Option
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry, get_default_registry
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import (
    TaskTree,
    build_dependencies_from_phase_transitions,
)


# Map common sub-intent analysis types to the phase IDs declared in domain
# templates. The decomposer uses the domain strategy skeleton and keeps the
# prefix up to and including the requested phases (so prerequisites are run).
SUB_INTENT_PHASE_MAP = {
    "qc": "qc",
    "quality_control": "qc",
    "normalization": "normalization",
    "dim_reduction": "dim_reduction",
    "dimensionality_reduction": "dim_reduction",
    "pca": "dim_reduction",
    "clustering": "clustering",
    "annotation": "annotation",
    "cell_annotation": "annotation",
    "differential_expression": "differential_expression",
    "de": "differential_expression",
    "visualization": "visualization",
    "umap": "visualization",
}

# Keywords (Chinese + English) used to infer sub-intents when the classifier
# did not explicitly provide them. Order matters: longer/more specific terms
# are checked first.
_SUB_INTENT_KEYWORDS: List[Tuple[str, str]] = [
    ("differential_expression", "差异表达"),
    ("differential_expression", "差异分析"),
    ("differential_expression", "differential expression"),
    ("differential_expression", "differential"),
    ("differential_expression", "deg"),
    ("annotation", "细胞类型注释"),
    ("annotation", "细胞注释"),
    ("annotation", "cell type annotation"),
    ("annotation", "cell annotation"),
    ("annotation", "annotate"),
    ("annotation", "注释"),
    ("visualization", "可视化"),
    ("visualization", "visualization"),
    ("visualization", "plot"),
    ("visualization", "umap"),
    ("dim_reduction", "降维"),
    ("dim_reduction", "dimensionality reduction"),
    ("dim_reduction", "pca"),
    ("clustering", "louvain"),
    ("clustering", "leiden"),
    ("clustering", "聚类"),
    ("clustering", "clustering"),
    ("clustering", "cluster"),
    ("normalization", "归一化"),
    ("normalization", "标准化"),
    ("normalization", "normalization"),
    ("normalization", "normalize"),
    ("qc", "质控"),
    ("qc", "quality control"),
    ("qc", "qc"),
]


class TaskDecomposer:
    """Decomposes user intent into executable task trees.

    Well-known single-step intents (file conversion, QA) use tiny hard-coded
    tasks. All other intents are routed through ``PlanEngine``, which picks a
    registered domain strategy (loaded from ``domains/<domain>/domain.yaml``)
    or falls back to the LLM planner for unknown domains.
    """

    def __init__(
        self,
        plan_engine: Optional[PlanEngine] = None,
        skill_registry: Optional[SkillRegistry] = None,
        standalone_planner: Optional[StandaloneSkillPlanner] = None,
        cross_domain_planner: Optional[CrossDomainPlanner] = None,
        open_agent_planner: Optional[OpenAgentPlanner] = None,
        cbkb=None,
        capability_index=None,
        analysis_template_store: Optional[AnalysisTemplateStore] = None,
        capability_assembler: Optional[CapabilityAssembler] = None,
        composite_planner: Optional[CompositePlanner] = None,
    ):
        self._plan_engine = plan_engine
        self._skill_registry = skill_registry or get_default_registry()
        self._standalone_planner = standalone_planner
        self._cross_domain_planner = cross_domain_planner
        self._open_agent_planner = open_agent_planner
        self._composite_planner = composite_planner
        self._cbkb = cbkb
        self._capability_index = capability_index
        self._analysis_template_store = analysis_template_store
        self._capability_assembler = capability_assembler

    def _get_capability_assembler(self) -> CapabilityAssembler:
        """Lazy initialize the capability-first routing assembler."""
        if self._capability_assembler is None:
            self._capability_assembler = CapabilityAssembler(
                capability_index=self._capability_index,
                template_store=self._analysis_template_store,
                skill_registry=self._skill_registry,
            )
        return self._capability_assembler

    def _get_plan_engine(self) -> PlanEngine:
        """Lazy initialize PlanEngine with the skill registry."""
        if self._plan_engine is None:
            self._plan_engine = PlanEngine(
                skill_registry=self._skill_registry,
                cbkb=self._cbkb,
                capability_index=self._capability_index,
            )
        return self._plan_engine

    def _load_project_template(self, project_id: Optional[str]) -> Optional[AnalysisTemplate]:
        """Load the AnalysisTemplate associated with a project, if any."""
        if not project_id:
            return None
        config_path = (
            settings.data_dir / "workspaces" / project_id / ".metadata" / "project_config.json"
        )
        if not config_path.exists():
            return None
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        template_id = config.get("template_id")
        if not template_id:
            return None
        store = self._analysis_template_store or AnalysisTemplateStore()
        return store.get_template(template_id)

    def _get_standalone_planner(self) -> StandaloneSkillPlanner:
        """Lazy initialize the standalone skill planner."""
        if self._standalone_planner is None:
            self._standalone_planner = StandaloneSkillPlanner(
                skill_registry=self._skill_registry
            )
        return self._standalone_planner

    def _get_open_agent_planner(self) -> OpenAgentPlanner:
        """Lazy initialize the open agent planner."""
        if self._open_agent_planner is None:
            self._open_agent_planner = OpenAgentPlanner(
                skill_registry=self._skill_registry,
                capability_index=self._capability_index,
            )
        return self._open_agent_planner

    def _should_use_open_agent_planner(self, intent: UserIntent) -> bool:
        """Return True when the request is open-ended, exploratory, or cross-domain.

        Open agent handles requests that do not fit cleanly into a domain
        template or standalone skill, such as literature exploration,
        method comparisons, diagnostic reasoning, and open-ended analysis.
        """
        if intent.interaction_mode == "explore":
            return True

        open_types = {
            "explore",
            "diagnose",
            "compare",
            "open_ended",
            "cross_domain_analysis",
            "general_scientific",
        }
        if intent.analysis_type in open_types:
            return True

        message = (intent.original_message or "").lower()
        diagnostic_keywords = [
            "为什么",
            "怎么回事",
            "诊断",
            "比较",
            "compare",
            "difference between",
            "why is",
            "diagnose",
        ]
        if any(kw in message for kw in diagnostic_keywords):
            return True

        # No domain signal and broad analysis type: let open agent try before fallback.
        if intent.domain is None and intent.analysis_type in {"general", "analysis", "unknown"}:
            return True

        return False

    def _get_cross_domain_planner(self) -> CrossDomainPlanner:
        """Lazy initialize the cross-domain planner."""
        if self._cross_domain_planner is None:
            self._cross_domain_planner = CrossDomainPlanner(
                plan_engine=self._get_plan_engine()
            )
        return self._cross_domain_planner

    def _get_composite_planner(self) -> CompositePlanner:
        """Lazy initialize the composite planner with bridge skill support."""
        if self._composite_planner is None:
            self._composite_planner = CompositePlanner(
                plan_engine=self._get_plan_engine(),
                skill_registry=self._skill_registry,
                cross_domain_planner=self._get_cross_domain_planner(),
            )
        return self._composite_planner

    @staticmethod
    def _should_use_cross_domain_planner(intent: UserIntent) -> bool:
        """Return True when the intent references multiple domains."""
        if intent.domain is None:
            return False
        domains = {intent.domain}
        for sub in intent.sub_intents:
            if sub.domain:
                domains.add(sub.domain)
        structured = getattr(intent, "structured_intent", None)
        if structured is not None:
            if getattr(structured, "domain", None):
                domains.add(structured.domain)
            for sub in getattr(structured, "sub_intents", []) or []:
                if getattr(sub, "domain", None):
                    domains.add(sub.domain)
        return len(domains) >= 2

    @staticmethod
    def _should_use_standalone_planner(intent: UserIntent) -> bool:
        """Return True when the intent is a generic, domain-agnostic request.

        Standalone skills are used only for the broad catch-all intent types
        produced by the classifier when it cannot map the request to a specific
        domain. Requests that already name a domain or a concrete analysis type
        are routed through the domain planner or LLM fallback so that domain
        knowledge and safety checkpoints (e.g., HITL for fallback plans) are
        preserved.
        """
        if intent.analysis_type in ("clarification", "file_conversion", "qa"):
            return False
        if intent.domain is not None:
            return False
        # Broad / unknown analysis types are good candidates for standalone routing.
        broad_types = {"general", "builtin_analysis", "analysis", "unknown"}
        if intent.analysis_type in broad_types:
            return True
        return False

    @staticmethod
    def _derive_sub_intents_from_message(message: str) -> List[UserIntent]:
        """Infer sub-intents from explicit phase keywords in the user message.

        This is a lightweight fallback when the intent classifier returns a
        broad domain intent (e.g. ``single_cell_analysis``) without narrowing
        it down to the specific phases the user actually asked for.
        """
        if not message:
            return []
        lowered = message.lower()
        matched: set[str] = set()
        for analysis_type, keyword in _SUB_INTENT_KEYWORDS:
            if keyword in lowered:
                matched.add(analysis_type)
        return [UserIntent(analysis_type=t, complexity="single_step") for t in sorted(matched)]

    def _merge_derived_sub_intents(self, intent: UserIntent) -> UserIntent:
        """Merge message-derived phase sub-intents with the classifier's sub-intents.

        Domain-level sub-intents (e.g. ``single_cell_analysis``) and
        phase-level sub-intents (e.g. ``clustering``) are kept together so the
        decomposer can both select the right domain strategy and filter to the
        requested phases.
        """
        derived = self._derive_sub_intents_from_message(intent.original_message)
        if not derived:
            return intent
        existing = {s.analysis_type for s in intent.sub_intents}
        combined = list(intent.sub_intents) + [
            s for s in derived if s.analysis_type not in existing
        ]
        if combined == intent.sub_intents:
            return intent
        return dataclasses.replace(intent, sub_intents=combined)

    def _has_domain_strategy(self, analysis_type: str) -> bool:
        """Return True if a non-generic strategy explicitly claims this intent."""
        plan_engine = self._get_plan_engine()
        for strategy in plan_engine.strategy_library.list_all():
            if strategy.name == "generic":
                continue
            if analysis_type in strategy.applicable_intents:
                return True
        return False

    async def _try_promote_domain_intent(
        self,
        intent: UserIntent,
        plan: PlanResult,
        project_id: Optional[str],
        template: Optional[AnalysisTemplate],
    ) -> Tuple[UserIntent, PlanResult]:
        """Promote a domain sub-intent to primary when the current plan is fallback."""
        if not plan.is_fallback or not intent.sub_intents:
            return intent, plan
        plan_engine = self._get_plan_engine()
        seen: set[str] = {intent.analysis_type}
        for sub in intent.sub_intents:
            if sub.analysis_type in seen:
                continue
            seen.add(sub.analysis_type)
            if not self._has_domain_strategy(sub.analysis_type):
                continue
            promoted = dataclasses.replace(
                intent,
                analysis_type=sub.analysis_type,
                complexity=sub.complexity or intent.complexity,
            )
            new_plan = await plan_engine.plan(
                promoted,
                project_id=project_id,
                template=template,
            )
            if not new_plan.is_fallback:
                return promoted, new_plan
        return intent, plan

    async def _route_via_capability_assembler(
        self,
        intent: UserIntent,
        context: Dict[str, Any],
    ) -> Optional[Tuple[PlanResult, TaskTree]]:
        """Dispatch ``intent`` using the unified CapabilityAssembler.

        Returns a plan/task-tree pair when a route produces an executable plan,
        or ``None`` to fall through to the general PlanEngine path.
        """
        data_state = context.get("data_state") or DataState()
        assembly = await self._get_capability_assembler().assemble(
            intent, data_state=data_state
        )

        if assembly.route == "cross_domain":
            composite_plan = await self._get_composite_planner().plan(intent)
            if composite_plan is not None:
                return composite_plan, self._plan_result_to_task_tree(composite_plan)
            return None

        if assembly.route == "domain_template":
            project_id = context.get("project_id")
            template = assembly.template or self._load_project_template(project_id)
            plan = await self._get_plan_engine().plan(
                intent,
                data_state=data_state,
                project_id=project_id,
                template=template,
            )
            # Apply the same sub-intent narrowing/post-processing used by the
            # general domain-strategy path.
            effective_intent = self._merge_derived_sub_intents(intent)
            if plan.is_fallback and effective_intent.sub_intents:
                effective_intent, plan = await self._try_promote_domain_intent(
                    effective_intent, plan, project_id, template
                )
            if effective_intent.sub_intents and not plan.is_fallback:
                plan, tree = self._filter_plan_by_sub_intents(plan, effective_intent)
                return plan, tree
            if plan.is_fallback and not plan.phases:
                return plan, self._build_suggestion_task(plan)
            return plan, self._plan_result_to_task_tree(plan)

        if assembly.route == "standalone_skill":
            if assembly.prebuilt_skills:
                standalone_plan = self._plan_from_prebuilt_skills(
                    assembly.prebuilt_skills, intent
                )
            else:
                standalone_plan = self._get_standalone_planner().plan(intent)
            if standalone_plan is not None:
                return standalone_plan, self._plan_result_to_task_tree(standalone_plan)
            return None

        if assembly.route == "open_agent":
            open_plan = await self._get_open_agent_planner().plan(intent)
            if open_plan is not None:
                return open_plan, self._plan_result_to_task_tree(open_plan)
            return None

        return None

    async def decompose(self, intent: UserIntent, context: Dict[str, Any]) -> TaskTree:
        """Decompose intent into a TaskTree.

        Backward-compatible wrapper around :meth:`decompose_with_plan`.
        """
        _, tree = await self.decompose_with_plan(intent, context)
        return tree

    async def decompose_with_plan(
        self,
        intent: UserIntent,
        context: Dict[str, Any],
    ) -> Tuple[PlanResult, TaskTree]:
        """Decompose intent into a canonical PlanResult and executable TaskTree."""
        # Clarification intent: non-executable, ask the user.
        if intent.analysis_type == "clarification":
            tree = self._build_clarification_task(intent)
            return self._task_tree_to_plan_result(
                tree, intent, strategy_name="clarification"
            ), tree

        # Fast path: hard-coded templates for the most common known single-step
        # intents. These are too trivial to warrant a dedicated domain strategy.
        if intent.analysis_type == "file_conversion":
            tree = self._build_single_step(
                "convert_file", "Convert file format", ["core_code_act"]
            )
            return self._task_tree_to_plan_result(
                tree, intent, strategy_name="file_conversion"
            ), tree

        if intent.analysis_type == "qa":
            tree = self._build_single_step(
                "answer_question", "Answer user question", []
            )
            return self._task_tree_to_plan_result(
                tree, intent, strategy_name="qa"
            ), tree

        # Capability-first routing (P3): unified decision via CapabilityAssembler.
        # When disabled, fall back to the legacy _should_use_* rule set below.
        if settings.capability_first_routing_enabled:
            routed = await self._route_via_capability_assembler(intent, context)
            if routed is not None:
                return routed
        else:
            # Legacy routing rules (kept for backward compatibility).
            # Cross-domain path: compose a plan when the intent spans multiple domains.
            if self._should_use_cross_domain_planner(intent):
                composite_plan = await self._get_composite_planner().plan(intent)
                if composite_plan is not None:
                    return composite_plan, self._plan_result_to_task_tree(composite_plan)

            # Standalone skill path: try standalone skills when no strong domain signal.
            if self._should_use_standalone_planner(intent):
                standalone_plan = self._get_standalone_planner().plan(intent)
                if standalone_plan is not None:
                    return standalone_plan, self._plan_result_to_task_tree(standalone_plan)

            # Open agent path: exploratory, cross-domain, diagnostic, or open-ended.
            if self._should_use_open_agent_planner(intent):
                open_plan = await self._get_open_agent_planner().plan(intent)
                if open_plan is not None:
                    return open_plan, self._plan_result_to_task_tree(open_plan)

        # General path: use PlanEngine (domain strategy or LLM fallback).
        plan_engine = self._get_plan_engine()
        project_id = context.get("project_id")
        template = self._load_project_template(project_id)
        plan = await plan_engine.plan(
            intent,
            project_id=project_id,
            template=template,
        )

        # Derive explicit phase sub-intents from the user message regardless of
        # whether the first plan was a domain strategy or a fallback. This lets
        # messages like "Louvain clustering" narrow the workflow even when the
        # classifier only returned a broad domain signal.
        effective_intent = self._merge_derived_sub_intents(intent)

        # If the primary intent is too broad/unknown and sub-intents name a domain
        # (e.g. primary="builtin_analysis", sub_intent="single_cell_analysis"),
        # promote that domain sub-intent to primary and replan so the domain
        # strategy is selected.
        if plan.is_fallback and effective_intent.sub_intents:
            effective_intent, plan = await self._try_promote_domain_intent(
                effective_intent, plan, project_id, template
            )

        if effective_intent.sub_intents and not plan.is_fallback:
            plan, tree = self._filter_plan_by_sub_intents(plan, effective_intent)
            return plan, tree

        if plan.is_fallback and not plan.phases:
            # LLM fallback produced only a suggestion with no executable skills.
            tree = self._build_suggestion_task(plan)
            return plan, tree

        return plan, self._plan_result_to_task_tree(plan)

    def _build_single_step(
        self,
        name: str,
        description: str,
        skills: List[str],
    ) -> TaskTree:
        """Build a single-step task tree."""
        task = TaskNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            phase="execution",
            skills_required=skills,
        )
        return TaskTree([task])

    def _plan_from_prebuilt_skills(
        self,
        skills: List[SkillDefinition],
        intent: UserIntent,
    ) -> PlanResult:
        """Build a linear plan directly from explicitly selected skills.

        This avoids re-running semantic search when the assembler has already
        resolved the user's request to one or more concrete skills.
        """
        from homomics_lab.agent.plan.standalone_planner import (
            StandaloneSkillPlanner,
        )

        phases: List[Phase] = []
        for skill in skills:
            phases.append(
                Phase(
                    phase_type=skill.id,
                    description=skill.description or f"Execute skill {skill.name}",
                    required=True,
                    selected_skill=skill,
                    derivation=StandaloneSkillPlanner.DERIVATION,
                    risk_level=StandaloneSkillPlanner.RISK_LEVEL,
                )
            )

        return PlanResult(
            phases=phases,
            strategy_name="standalone-skill-planner",
            data_state=DataState(),
            derivation=StandaloneSkillPlanner.DERIVATION,
            risk_level=StandaloneSkillPlanner.RISK_LEVEL,
            approval_required=False,
        )

    def _plan_result_to_task_tree(self, plan: PlanResult) -> TaskTree:
        """Convert a PlanResult into an executable TaskTree.

        Task dependencies are derived from ``plan.phase_transitions`` when they
        are available. Only ``followed_by`` and ``depends_on`` edges become
        execution dependencies; ``alternative_to`` and ``parallel_to`` edges are
        ignored. If no transitions are declared, the tasks fall back to a linear
        chain.
        """
        tasks: List[TaskNode] = []
        phase_to_task_id: Dict[str, str] = {}

        for phase in plan.phases:
            if not phase.required:
                continue

            task_id = str(uuid.uuid4())[:8]
            phase_to_task_id[phase.phase_type] = task_id

            skill_id = phase.selected_skill.id if phase.selected_skill else None
            skills_required = [skill_id] if skill_id else []

            hitl_checkpoints: List[HITLCheckpoint] = []
            if plan.is_fallback:
                # Add a confirmation checkpoint for LLM-generated plans.
                hitl_checkpoints.append(
                    HITLCheckpoint(
                        id=f"hitl_{task_id}",
                        trigger_reason=HITLTrigger.POLICY,
                        context_summary=(
                            f"This step was suggested by the LLM fallback planner: {phase.description}. "
                            "Please confirm before execution."
                        ),
                        options=[
                            Option(id="confirm", label="Confirm", description="Execute this step"),
                            Option(id="skip", label="Skip", description="Skip this step"),
                        ],
                    )
                )

            success_criteria = [
                dataclasses.asdict(c) for c in phase.success_criteria
            ]
            task = TaskNode(
                id=task_id,
                name=phase.phase_type,
                description=phase.description,
                phase=phase.phase_type,
                skills_required=skills_required,
                dependencies=[],
                parameters=phase.parameters,
                hitl_checkpoints=hitl_checkpoints,
                success_criteria=success_criteria,
                estimated_duration_minutes=int((phase.estimated_duration_seconds or 600) / 60.0),
                estimated_cost_usd=phase.estimated_cost_usd,
                estimated_input_tokens=phase.estimated_input_tokens,
                estimated_output_tokens=phase.estimated_output_tokens,
                derivation=phase.derivation or plan.derivation,
                risk_level=phase.risk_level or plan.risk_level,
            )
            tasks.append(task)

        # Build dependencies from phase transitions.
        task_ids_in_order = [t.id for t in tasks]
        incoming = build_dependencies_from_phase_transitions(
            task_ids_in_order,
            plan.phase_transitions,
        )
        for task in tasks:
            task.dependencies = list(dict.fromkeys(incoming.get(task.id, [])))

        return TaskTree(tasks)

    def _build_suggestion_task(self, plan: PlanResult) -> TaskTree:
        """Build a non-executable task tree that carries a suggestion message."""
        task = TaskNode(
            id=str(uuid.uuid4())[:8],
            name="fallback_suggestion",
            description=plan.suggestion_text or "No executable workflow could be planned.",
            phase="suggestion",
            skills_required=[],
        )
        return TaskTree([task])

    def _task_tree_to_plan_result(
        self,
        tree: TaskTree,
        intent: UserIntent,
        is_fallback: bool = False,
        strategy_name: str = "hardcoded",
    ) -> PlanResult:
        """Synthesize a PlanResult from a hard-coded TaskTree."""
        phases: List[Phase] = []
        for task in tree.tasks:
            success_criteria = [
                SuccessCriterion(**c) for c in (task.success_criteria or [])
            ]
            selected_skill = None
            if task.skills_required:
                skill_id = task.skills_required[0]
                selected_skill = SkillDefinition(
                    id=skill_id,
                    name=skill_id,
                    version="builtin",
                    category=task.phase or "analysis",
                )
            phases.append(
                Phase(
                    phase_type=task.name,
                    description=task.description,
                    required=True,
                    selected_skill=selected_skill,
                    parameters=task.parameters,
                    success_criteria=success_criteria,
                )
            )

        return PlanResult(
            phases=phases,
            strategy_name=strategy_name,
            data_state=DataState(),
            gaps=[],
            reproducibility_context={
                "plan_engine_version": "0.5.0",
                "strategy": strategy_name,
                "intent": intent.analysis_type,
            },
            is_fallback=is_fallback,
            derivation="hardcoded",
            risk_level="low",
            approval_required=False,
        )

    def _build_clarification_task(self, intent: UserIntent) -> TaskTree:
        """Build a non-executable task tree that asks the user for clarification."""
        question = (
            intent.metadata.get("clarification_question")
            or "我不太确定您的需求，请再具体描述一下。"
        )
        task = TaskNode(
            id=str(uuid.uuid4())[:8],
            name="clarification",
            description=question,
            phase="clarification",
            skills_required=[],
        )
        return TaskTree([task])

    def _filter_plan_by_sub_intents(
        self,
        plan: PlanResult,
        intent: UserIntent,
    ) -> Tuple[PlanResult, TaskTree]:
        """Filter a generated plan to only the phases requested by sub-intents.

        For each recognized sub-intent we map it to a phase ID, then collect that
        phase plus all of its required prerequisites using the domain's
        ``phase_transitions`` DAG. Requested phases are forced to ``required=True``
        so they appear in the resulting task tree even if they are optional in
        the full domain strategy.
        """
        if not plan.phases:
            return plan, self._plan_result_to_task_tree(plan)

        target_phase_ids = set()
        for sub in intent.sub_intents:
            phase_id = SUB_INTENT_PHASE_MAP.get(sub.analysis_type)
            if phase_id is not None:
                target_phase_ids.add(phase_id)

        if not target_phase_ids:
            return plan, self._plan_result_to_task_tree(plan)

        # Build prerequisite map from execution-oriented transitions.
        prereqs: Dict[str, set] = {
            phase.phase_type: set() for phase in plan.phases
        }
        for transition in plan.phase_transitions:
            edge_type = transition.get("type", "followed_by")
            if edge_type in ("alternative_to", "parallel_to"):
                continue
            to_phase = transition.get("to")
            from_phase = transition.get("from")
            if to_phase and from_phase:
                prereqs.setdefault(to_phase, set()).add(from_phase)

        # Determine which phases to keep: targets + required prerequisites.
        kept_phase_ids: set = set()
        for target in target_phase_ids:
            if target not in prereqs:
                continue
            stack = [target]
            while stack:
                current = stack.pop()
                if current in kept_phase_ids:
                    continue
                kept_phase_ids.add(current)
                for prerequisite in prereqs.get(current, set()):
                    if prerequisite not in kept_phase_ids:
                        stack.append(prerequisite)

        if not kept_phase_ids:
            return plan, self._plan_result_to_task_tree(plan)

        # Preserve topological order from the original plan.
        filtered_phases: List[Phase] = []
        for phase in plan.phases:
            if phase.phase_type not in kept_phase_ids:
                continue
            # Force requested phases (which may be optional in the domain) to run.
            if phase.phase_type in target_phase_ids and not phase.required:
                phase = dataclasses.replace(phase, required=True)
            filtered_phases.append(phase)

        filtered_transitions = [
            t
            for t in plan.phase_transitions
            if t.get("from") in kept_phase_ids and t.get("to") in kept_phase_ids
        ]

        filtered_plan = PlanResult(
            phases=filtered_phases,
            strategy_name=plan.strategy_name,
            data_state=plan.data_state,
            gaps=[
                g
                for g in plan.gaps
                if g.from_phase in kept_phase_ids and g.to_phase in kept_phase_ids
            ],
            reproducibility_context={
                **plan.reproducibility_context,
                "sub_intents": [sub.analysis_type for sub in intent.sub_intents],
            },
            is_fallback=plan.is_fallback,
            suggestion_text=plan.suggestion_text,
            phase_transitions=filtered_transitions,
        )
        return filtered_plan, self._plan_result_to_task_tree(filtered_plan)
