import dataclasses
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from homomics_lab.agent.intent.alias_registry import AliasRegistry
from homomics_lab.agent.intent.routing_decision import Route, RoutingDecision
from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.display_plan import DisplayStep
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

logger = logging.getLogger(__name__)


# Non-phase semantic sub-intents used only for display/TODO purposes.
# Phase-level aliases are now centralised in ``AliasRegistry``.
_LABEL_COMPARISON_KEYWORDS: List[Tuple[str, str]] = [
    ("label_comparison", "比较"),
    ("label_comparison", "对比"),
    ("label_comparison", "一致性"),
    ("label_comparison", "all_celltype"),
    ("label_comparison", "compare"),
    ("label_comparison", "agreement"),
    ("label_comparison", "consistency"),
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
        alias_registry: Optional[AliasRegistry] = None,
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
        self._alias_registry = alias_registry

    def _get_capability_assembler(self) -> CapabilityAssembler:
        """Lazy initialize the capability-first routing assembler."""
        if self._capability_assembler is None:
            self._capability_assembler = CapabilityAssembler(
                capability_index=self._capability_index,
                template_store=self._analysis_template_store,
                skill_registry=self._skill_registry,
                alias_registry=self._ensure_alias_registry(),
            )
        return self._capability_assembler

    def _ensure_alias_registry(self) -> AliasRegistry:
        """Lazy initialize the alias registry from current domains and skills."""
        if self._alias_registry is None:
            from homomics_lab.domain.registry import get_domain_registry

            self._alias_registry = AliasRegistry.build(
                domains=get_domain_registry().list_all(),
                skills=self._skill_registry.list_all(),
            )
        return self._alias_registry

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

    def _derive_sub_intents_from_message(self, message: str) -> List[UserIntent]:
        """Infer sub-intents from explicit phase keywords in the user message.

        This is a lightweight fallback when the intent classifier returns a
        broad domain intent (e.g. ``single_cell_analysis``) without narrowing
        it down to the specific phases the user actually asked for.

        Phase-level aliases are resolved through ``AliasRegistry``; only the
        non-phase ``label_comparison`` intent is still keyword-derived here
        because it is a display-level semantic sub-goal, not an executable
        phase.
        """
        if not message:
            return []
        lowered = message.lower()
        matched: set[str] = set()

        # Phase-level aliases from the canonical registry.
        for phase_id in self._ensure_alias_registry().match_phases(message).keys():
            matched.add(phase_id)

        # Display-level semantic sub-intents.
        for analysis_type, keyword in _LABEL_COMPARISON_KEYWORDS:
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

    @staticmethod
    def _build_display_subtasks(
        intent: UserIntent,
        skills: List[SkillDefinition],
    ) -> List[Dict[str, Any]]:
        """Build user-facing milestone steps from the user's actual request.

        Instead of mirroring the internal domain phases, the TODO checklist
        shows the few logical goals the user asked for: load/check data,
        run the requested method, compare results, and summarize. Broad
        domain containers and implicit upstream phases (qc, normalization,
        clustering) are intentionally hidden unless the user asked for them.
        """
        user_msg = (intent.original_message or "").lower()
        skill_name = skills[0].name if skills else ""
        skill_id = skills[0].id if skills else ""

        # Extract the primary file name the user referenced.
        import re
        file_candidates = re.findall(r"[\w\-]+\.\w{2,8}", user_msg)
        primary_file = file_candidates[0] if file_candidates else "input data"

        # Detect Chinese to produce Chinese-facing milestones.
        has_chinese = bool(re.search(r"[\u4e00-\u9fff]", user_msg))

        # Build milestones from explicit user goals, not from sub_intents.
        milestones: List[Dict[str, Any]] = []

        # 1. Data inspection (always useful, lightweight).
        milestones.append({
            "id": f"{skill_id or 'step'}_inspect",
            "description": (
                f"读取并检查 {primary_file} 的数据结构"
                if has_chinese
                else f"Inspect {primary_file} and verify required columns/fields"
            ),
            "analysis_type": "data_inspection",
        })

        # 2. Core analysis requested by the user.
        method_name = skill_name or "selected method"
        # Try to extract a friendly method name from the skill id tail.
        if "-" in (skill_id or ""):
            method_name = skill_id.split("-")[-1].replace("_", " ").title()
        if "celltypist" in user_msg:
            method_name = "CellTypist"
        elif "singler" in user_msg:
            method_name = "SingleR"

        if "annotate" in user_msg or "annotation" in user_msg or "注释" in user_msg:
            desc = f"使用 {method_name} 进行细胞类型注释" if has_chinese else f"Run cell type annotation with {method_name}"
        elif "describe" in user_msg or "描述性统计" in user_msg or "统计" in user_msg:
            desc = f"计算 {primary_file} 的描述性统计" if has_chinese else f"Compute descriptive statistics for {primary_file}"
        elif "cluster" in user_msg or "聚类" in user_msg or "louvain" in user_msg or "leiden" in user_msg:
            desc = f"使用 {method_name} 对细胞进行聚类" if has_chinese else f"Cluster cells with {method_name}"
        elif "normalize" in user_msg or "归一化" in user_msg or "标准化" in user_msg:
            desc = f"对 {primary_file} 进行归一化" if has_chinese else f"Normalize {primary_file}"
        elif "qc" in user_msg or "质控" in user_msg:
            desc = f"对 {primary_file} 进行质控" if has_chinese else f"Quality control on {primary_file}"
        else:
            desc = f"使用 {method_name} 分析 {primary_file}" if has_chinese else f"Run {method_name} analysis on {primary_file}"
        milestones.append({
            "id": f"{skill_id or 'step'}_core",
            "description": desc,
            "analysis_type": "core_analysis",
        })

        # 3. Comparison / downstream goal if explicitly requested.
        has_comparison = any(kw in user_msg for kw in ("比较", "对比", "一致性", "compare", "agreement", "consistency"))
        if has_comparison:
            if has_chinese:
                compare_target = "现有注释标签"
                if "all_celltype" in user_msg:
                    compare_target = "all_celltype 标签"
                desc = f"与 {compare_target} 比较一致性"
            else:
                compare_target = "existing annotations"
                if "all_celltype" in user_msg:
                    compare_target = "existing all_celltype labels"
                desc = f"Compare results with {compare_target}"
            milestones.append({
                "id": f"{skill_id or 'step'}_compare",
                "description": desc,
                "analysis_type": "label_comparison",
            })

        # 4. Summary.
        milestones.append({
            "id": f"{skill_id or 'step'}_summarize",
            "description": "总结结果并给出下一步建议" if has_chinese else "Summarize results and suggest next steps",
            "analysis_type": "summarize",
        })

        return milestones

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

    async def _make_routing_decision(
        self,
        intent: UserIntent,
        context: Dict[str, Any],
    ) -> RoutingDecision:
        """Return the canonical routing decision for ``intent``.

        This is the single place where all routing signals are evaluated.  The
        decision object captures the chosen route, the reason, confidence, and
        any pre-resolved skills/template, forming an auditable record that
        downstream code can execute without re-interpreting the intent.
        """
        if intent.analysis_type == "clarification":
            return RoutingDecision.direct(
                Route.CLARIFICATION, "Intent classified as clarification"
            )
        if intent.analysis_type == "file_conversion":
            return RoutingDecision.direct(
                Route.FILE_CONVERSION, "Intent classified as file conversion"
            )
        if intent.analysis_type == "qa":
            return RoutingDecision.direct(Route.QA, "Intent classified as QA")

        # Data exploration / descriptive statistics should not be forced into a
        # domain template; generate targeted summary code via CodeAct with the
        # general coding skill as reference (fast, single-shot path).
        if intent.analysis_type == "descriptive_statistics":
            return RoutingDecision.direct(
                Route.DESCRIPTIVE_STATISTICS,
                "Descriptive statistics: fast CodeAct summary",
            )

        data_state = context.get("data_state") or DataState()
        assembly = await self._get_capability_assembler().assemble(
            intent, data_state=data_state
        )

        # DataPreflight may indicate that the user's request can be fulfilled in a
        # single shot (e.g. "run CellTypist and compare labels" needs no qc,
        # normalization, or clustering). In that case, prefer an explicit skill
        # target over a full domain phase pipeline, even when the classifier
        # mapped the request to a phase-level analysis_type.
        preflight = context.get("preflight") or {}
        preflight_required = preflight.get("required_steps") or []
        is_single_shot = (
            len(preflight_required) <= 4
            and not preflight.get("needs_qc", False)
            and not preflight.get("needs_normalization", False)
            and not preflight.get("needs_clustering", False)
        )
        if is_single_shot:
            explicit_skill = self._get_capability_assembler()._resolve_explicit_target_skill(
                intent
            )
            if explicit_skill is not None:
                return RoutingDecision(
                    route=Route.STANDALONE_SKILL,
                    reason=(
                        f"Preflight indicates single-shot task; explicit skill target "
                        f"'{explicit_skill.id}'"
                    ),
                    confidence=1.0,
                    skills=[explicit_skill],
                    trace=[
                        {
                            "route": Route.STANDALONE_SKILL.value,
                            "reason": assembly.reason,
                            "score": max(assembly.score, assembly.coverage),
                        },
                        {
                            "route": Route.STANDALONE_SKILL.value,
                            "reason": "Preflight single-shot override",
                            "score": 1.0,
                        },
                    ],
                )

        # Domain/phase-level intents declared in a domain.yaml should be planned
        # by the domain strategy, not delegated to the open agent.
        if (
            assembly.route == "open_agent"
            and self._has_domain_strategy(intent.analysis_type)
        ):
            domains = [intent.domain] if intent.domain else []
            if not domains:
                for sub in intent.sub_intents:
                    if sub.domain:
                        domains.append(sub.domain)
                        break
            reason = (
                f"Phase-level intent '{intent.analysis_type}' mapped to domain strategy"
                if self._ensure_alias_registry().is_phase_level(intent.analysis_type)
                else f"Domain-level intent '{intent.analysis_type}' mapped to domain strategy"
            )
            return RoutingDecision(
                route=Route.DOMAIN_TEMPLATE,
                reason=reason,
                domains=domains,
                trace=[
                    {
                        "route": Route.OPEN_AGENT.value,
                        "reason": assembly.reason,
                        "score": 0.0,
                    },
                    {
                        "route": Route.DOMAIN_TEMPLATE.value,
                        "reason": "Redirected to domain strategy",
                        "score": 0.0,
                    },
                ],
            )

        route_map = {
            "cross_domain": Route.CROSS_DOMAIN,
            "domain_template": Route.DOMAIN_TEMPLATE,
            "standalone_skill": Route.STANDALONE_SKILL,
            "open_agent": Route.OPEN_AGENT,
        }
        route = route_map.get(assembly.route, Route.OPEN_AGENT)
        return RoutingDecision(
            route=route,
            reason=assembly.reason,
            confidence=max(assembly.score, assembly.coverage),
            domains=assembly.domains,
            template=assembly.template,
            skills=assembly.prebuilt_skills,
            trace=[
                {
                    "route": route.value,
                    "reason": assembly.reason,
                    "score": max(assembly.score, assembly.coverage),
                }
            ],
        )

    async def _execute_routing_decision(
        self,
        decision: RoutingDecision,
        intent: UserIntent,
        context: Dict[str, Any],
    ) -> Tuple[PlanResult, TaskTree]:
        """Execute a previously-made routing decision into a plan and task tree."""
        route = decision.route

        if route == Route.CLARIFICATION:
            tree = self._build_clarification_task(intent)
            return self._task_tree_to_plan_result(
                tree, intent, strategy_name="clarification"
            ), tree

        if route == Route.FILE_CONVERSION:
            tree = self._build_single_step(
                "convert_file", "Convert file format", ["core_code_act"]
            )
            return self._task_tree_to_plan_result(
                tree, intent, strategy_name="file_conversion"
            ), tree

        if route == Route.QA:
            tree = self._build_single_step(
                "answer_question", "Answer user question", []
            )
            return self._task_tree_to_plan_result(tree, intent, strategy_name="qa"), tree

        if route == Route.DESCRIPTIVE_STATISTICS:
            has_chinese = any(
                ord(c) > 127 for c in (intent.original_message or "")
            )
            tree = self._build_single_step(
                "descriptive_statistics",
                "生成描述性统计摘要" if has_chinese else "Generate descriptive statistics summary",
                ["core_code_act"],
                parameters={
                    "use_skill_reference": True,
                    "user_request": intent.original_message,
                },
            )
            return (
                self._task_tree_to_plan_result(
                    tree, intent, strategy_name="descriptive_statistics"
                ),
                tree,
            )

        if route == Route.CROSS_DOMAIN:
            composite_plan = await self._get_composite_planner().plan(intent)
            if composite_plan is not None:
                return composite_plan, self._plan_result_to_task_tree(composite_plan)
            # Degrade to open agent if composition is unavailable.
            open_plan = await self._get_open_agent_planner().plan(intent)
            if open_plan is not None:
                return open_plan, self._plan_result_to_task_tree(open_plan)

        if route == Route.STANDALONE_SKILL:
            effective_intent = self._merge_derived_sub_intents(intent)
            if decision.skills:
                standalone_plan = self._plan_from_prebuilt_skills(
                    decision.skills, effective_intent, context=context
                )
            else:
                standalone_plan = self._get_standalone_planner().plan(effective_intent)
            if standalone_plan is not None:
                tree = self._plan_result_to_task_tree(standalone_plan)
                tree.display_steps = standalone_plan.display_steps
                return standalone_plan, tree
            # Degrade to open agent if standalone planning is unavailable.
            open_plan = await self._get_open_agent_planner().plan(intent)
            if open_plan is not None:
                return open_plan, self._plan_result_to_task_tree(open_plan)

        if route == Route.OPEN_AGENT:
            open_plan = await self._get_open_agent_planner().plan(intent)
            if open_plan is not None:
                return open_plan, self._plan_result_to_task_tree(open_plan)

        # DOMAIN_TEMPLATE or any route that declined: use PlanEngine.
        return await self._plan_via_domain_engine(intent, context, decision.template)

    async def _plan_via_domain_engine(
        self,
        intent: UserIntent,
        context: Dict[str, Any],
        template: Optional[AnalysisTemplate] = None,
    ) -> Tuple[PlanResult, TaskTree]:
        """Plan through the domain engine and apply sub-intent narrowing."""
        project_id = context.get("project_id")
        if template is None:
            template = self._load_project_template(project_id)
        plan = await self._get_plan_engine().plan(
            intent,
            data_state=context.get("data_state") or DataState(),
            project_id=project_id,
            template=template,
        )

        effective_intent = self._merge_derived_sub_intents(intent)
        if plan.is_fallback and effective_intent.sub_intents:
            effective_intent, plan = await self._try_promote_domain_intent(
                effective_intent, plan, project_id, template
            )

        # DataPreflight may tell us to skip phases that are not needed for the
        # user's actual request (e.g. skip qc/clustering for CellTypist-only
        # annotation).
        skip_phases = set((context.get("preflight") or {}).get("skip_phases", []))
        if skip_phases and plan.phases:
            plan.phases = [
                p for p in plan.phases if p.phase_type not in skip_phases
            ]
            if plan.phase_transitions:
                plan.phase_transitions = [
                    t
                    for t in plan.phase_transitions
                    if t.get("from") not in skip_phases
                    and t.get("to") not in skip_phases
                ]

        if effective_intent.sub_intents and not plan.is_fallback:
            plan, tree = self._filter_plan_by_sub_intents(plan, effective_intent)
            plan.display_steps = self._build_display_steps_from_plan(plan)
            self._stamp_domain_pipeline(plan, tree, effective_intent.domain or intent.domain)
            return plan, tree

        if plan.is_fallback and not plan.phases:
            tree = self._build_suggestion_task(plan)
            plan.display_steps = self._build_display_steps_from_plan(plan)
            return plan, tree

        plan.display_steps = self._build_display_steps_from_plan(plan)
        tree = self._plan_result_to_task_tree(plan)
        self._stamp_domain_pipeline(plan, tree, effective_intent.domain or intent.domain)
        return plan, tree

    @staticmethod
    def _stamp_domain_pipeline(
        plan: PlanResult,
        tree: TaskTree,
        domain: Optional[str],
    ) -> None:
        """Stamp domain ownership and the (preflight-trimmed) pipeline phases
        onto each task's parameters.

        CodeAct executions read this back (see ``agent/workflow_markers.py``)
        to inject the phase-marker convention into generated scripts and to
        emit the ``workflow_skeleton`` / ``phase`` progress events.  Generic
        or domain-less intents stamp nothing, which downstream treats as
        "no workflow DAG".
        """
        if not domain:
            return
        phases = [
            {"phase_type": p.phase_type, "name": p.description or p.phase_type}
            for p in plan.phases
            if p.required
        ]
        for task in tree.tasks:
            task.parameters.setdefault("domain", domain)
            if phases:
                task.parameters.setdefault("domain_phases", phases)

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
        decision = await self._make_routing_decision(intent, context)
        logger.info(
            "TaskDecomposer routing decision route=%s reason=%s analysis_type=%s confidence=%.2f",
            decision.route.value,
            decision.reason,
            intent.analysis_type,
            decision.confidence,
        )
        if decision.trace:
            logger.debug("Routing trace for %s: %s", intent.analysis_type, decision.trace)
        plan, tree = await self._execute_routing_decision(decision, intent, context)
        if plan.routing_trace is None or not plan.routing_trace:
            plan.routing_trace = list(decision.trace)
        return plan, tree

    def _build_single_step(
        self,
        name: str,
        description: str,
        skills: List[str],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> TaskTree:
        """Build a single-step task tree."""
        task = TaskNode(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            phase="execution",
            skills_required=skills,
            parameters=parameters or {},
        )
        return TaskTree([task])

    def _plan_from_prebuilt_skills(
        self,
        skills: List[SkillDefinition],
        intent: UserIntent,
        context: Optional[Dict[str, Any]] = None,
    ) -> PlanResult:
        """Build a linear plan directly from explicitly selected skills.

        This avoids re-running semantic search when the assembler has already
        resolved the request to one or more concrete skills. When the user
        message implies multiple semantic sub-steps (e.g. annotate + compare
        consistency), they are stored as ``display_subtasks`` on the phase so
        the TODO list can surface them without forcing a single skill to be
        executed more than once.
        """
        from homomics_lab.agent.plan.display_plan import DisplayStep
        from homomics_lab.agent.plan.standalone_planner import (
            StandaloneSkillPlanner,
        )

        context = context or {}
        preflight = context.get("preflight") or {}
        display_subtasks = self._build_display_subtasks(intent, skills)

        phases: List[Phase] = []
        for skill in skills:
            parameters: Dict[str, Any] = {
                "use_skill_reference": True,
                "preflight": preflight,
                "user_request": intent.original_message,
            }
            if intent.domain:
                # Domain ownership without a domain pipeline: the workflow
                # skeleton degrades to display_subtasks / the task's phase.
                parameters["domain"] = intent.domain
            if display_subtasks:
                parameters["display_subtasks"] = display_subtasks
            phases.append(
                Phase(
                    phase_type=skill.id,
                    description=skill.description or f"Execute skill {skill.name}",
                    required=True,
                    selected_skill=skill,
                    parameters=parameters,
                    derivation=StandaloneSkillPlanner.DERIVATION,
                    risk_level=StandaloneSkillPlanner.RISK_LEVEL,
                )
            )

        display_steps = [
            DisplayStep(
                id=sub["id"],
                description=sub["description"],
                analysis_type=sub.get("analysis_type"),
                phase_type=skills[0].id if skills else None,
                source=skills[0].id if skills else None,
            )
            for sub in display_subtasks
        ]

        return PlanResult(
            phases=phases,
            strategy_name="standalone-skill-planner",
            data_state=DataState(),
            derivation=StandaloneSkillPlanner.DERIVATION,
            risk_level=StandaloneSkillPlanner.RISK_LEVEL,
            approval_required=False,
            display_steps=display_steps,
        )

    @staticmethod
    def _build_display_steps_from_plan(plan: PlanResult) -> List["DisplayStep"]:
        """Build a user-facing display plan from an execution plan.

        The display steps mirror the executable phases by default.  When the
        plan already carries finer-grained display steps (e.g. from a standalone
        skill with semantic sub-intents), those are preserved.
        """
        if plan.display_steps:
            return plan.display_steps

        return [
            DisplayStep(
                id=f"display_{phase.phase_type}",
                description=phase.description or f"{phase.phase_type} analysis step",
                phase_type=phase.phase_type,
                source=phase.selected_skill.id if phase.selected_skill else None,
            )
            for phase in plan.phases
            if phase.required
        ]

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

        return TaskTree(
            tasks=tasks,
            display_steps=plan.display_steps,
            execution_mode=plan.execution_mode,
        )

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
        alias_registry = self._ensure_alias_registry()
        for sub in intent.sub_intents:
            phase_id = alias_registry.resolve_phase(sub.analysis_type)
            if phase_id is not None:
                target_phase_ids.add(phase_id)

        # Avoid redundant data-loading tasks: if a self-contained analysis phase
        # (e.g. descriptive_statistics) is explicitly requested, do not also keep
        # a generic data_io target that merely loads the same input file.
        if "descriptive_statistics" in target_phase_ids and "data_io" in target_phase_ids:
            target_phase_ids.discard("data_io")

        if not target_phase_ids:
            return plan, self._plan_result_to_task_tree(plan)

        # Build prerequisite map from execution-oriented transitions and a
        # map of whether each phase is required in the full domain strategy.
        prereqs: Dict[str, set] = {
            phase.phase_type: set() for phase in plan.phases
        }
        required_map: Dict[str, bool] = {
            phase.phase_type: phase.required for phase in plan.phases
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
        # Optional phases are only kept when explicitly requested as a target;
        # they are never pulled in automatically as prerequisites of another
        # step.  This prevents a request like "descriptive_statistics" from
        # dragging in the optional "fastq_processing" phase just because the
        # domain declares a natural ordering edge from fastq_processing to data_io.
        # However, an optional phase is still traversed so that required phases
        # upstream of it (e.g. data_io -> qc -> optional doublet_removal ->
        # normalization) are included when the user asks for clustering.
        kept_phase_ids: set = set()
        visited: set = set()
        for target in target_phase_ids:
            if target not in prereqs:
                continue
            stack = [target]
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                if current in target_phase_ids or required_map.get(current, False):
                    kept_phase_ids.add(current)
                for prerequisite in prereqs.get(current, set()):
                    if prerequisite in visited:
                        continue
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
