import dataclasses
import uuid
from typing import Any, Dict, List, Optional, Tuple

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult, SuccessCriterion
from homomics_lab.models.common import HITLCheckpoint, HITLTrigger, Option
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry, get_default_registry
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


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
        cbkb=None,
    ):
        self._plan_engine = plan_engine
        self._skill_registry = skill_registry or get_default_registry()
        self._cbkb = cbkb

    def _get_plan_engine(self) -> PlanEngine:
        """Lazy initialize PlanEngine with the skill registry."""
        if self._plan_engine is None:
            self._plan_engine = PlanEngine(
                skill_registry=self._skill_registry,
                cbkb=self._cbkb,
            )
        return self._plan_engine

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
                "convert_file", "Convert file format", ["data_loader"]
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

        # General path: use PlanEngine (domain strategy or LLM fallback).
        plan_engine = self._get_plan_engine()
        plan = await plan_engine.plan(intent)

        # If sub-intents are present, filter the generated plan to the requested
        # phases (keeping prerequisites) instead of running the full domain DAG.
        if intent.sub_intents and not plan.is_fallback:
            plan, tree = self._filter_plan_by_sub_intents(plan, intent)
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
            )
            tasks.append(task)

        # Build dependencies from phase transitions.
        task_ids_in_order = [t.id for t in tasks]
        if plan.phase_transitions:
            incoming: Dict[str, List[str]] = {t.id: [] for t in tasks}
            for transition in plan.phase_transitions:
                edge_type = transition.get("type", "followed_by")
                if edge_type in ("alternative_to", "parallel_to"):
                    continue
                from_id = phase_to_task_id.get(transition.get("from", ""))
                to_id = phase_to_task_id.get(transition.get("to", ""))
                if from_id and to_id and from_id != to_id:
                    incoming[to_id].append(from_id)
            for task in tasks:
                task.dependencies = list(dict.fromkeys(incoming.get(task.id, [])))
        else:
            # No transitions declared: fall back to a linear chain.
            for i, task in enumerate(tasks):
                if i > 0:
                    task.dependencies = [task_ids_in_order[i - 1]]

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
