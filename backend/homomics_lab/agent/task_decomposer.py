import dataclasses
import uuid
from typing import Any, Dict, List, Optional, Tuple

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.engine import PlanEngine
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult, SuccessCriterion
from homomics_lab.models.common import AgentType, HITLCheckpoint, Option
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry, get_default_registry
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.task_tree import TaskTree


# Map sub-intent types to concrete pipeline steps for single-cell workflows.
SUB_INTENT_STEP_MAP = {
    "qc": {
        "name": "quality_control",
        "description": "Filter low-quality cells and genes",
        "phase": "preprocessing",
        "agent": AgentType.BIOINFO,
        "skills": ["scanpy_qc"],
    },
    "quality_control": {
        "name": "quality_control",
        "description": "Filter low-quality cells and genes",
        "phase": "preprocessing",
        "agent": AgentType.BIOINFO,
        "skills": ["scanpy_qc"],
    },
    "normalization": {
        "name": "normalization",
        "description": "Normalize gene expression counts",
        "phase": "preprocessing",
        "agent": AgentType.BIOINFO,
        "skills": ["scanpy_normalize"],
    },
    "dim_reduction": {
        "name": "dimensionality_reduction",
        "description": "Compute PCA on normalized data",
        "phase": "analysis",
        "agent": AgentType.BIOINFO,
        "skills": ["scanpy_pca"],
    },
    "pca": {
        "name": "dimensionality_reduction",
        "description": "Compute PCA on normalized data",
        "phase": "analysis",
        "agent": AgentType.BIOINFO,
        "skills": ["scanpy_pca"],
    },
    "clustering": {
        "name": "clustering",
        "description": "Compute neighbors and UMAP embedding",
        "phase": "analysis",
        "agent": AgentType.BIOINFO,
        "skills": ["scanpy_cluster"],
        "hitl": ["n_neighbors", "resolution"],
    },
    "annotation": {
        "name": "cell_annotation",
        "description": "Annotate cell clusters with marker genes",
        "phase": "analysis",
        "agent": AgentType.BIOINFO,
        "skills": ["scanpy_annotation"],
    },
    "cell_annotation": {
        "name": "cell_annotation",
        "description": "Annotate cell clusters with marker genes",
        "phase": "analysis",
        "agent": AgentType.BIOINFO,
        "skills": ["scanpy_annotation"],
    },
    "differential_expression": {
        "name": "differential_expression",
        "description": "Find marker genes for each cluster",
        "phase": "analysis",
        "agent": AgentType.BIOINFO,
        "skills": ["scanpy_de"],
    },
    "de": {
        "name": "differential_expression",
        "description": "Find marker genes for each cluster",
        "phase": "analysis",
        "agent": AgentType.BIOINFO,
        "skills": ["scanpy_de"],
    },
    "visualization": {
        "name": "visualization",
        "description": "Generate UMAP plots and heatmaps",
        "phase": "reporting",
        "agent": AgentType.VIZ,
        "skills": ["plot_umap", "plot_heatmap"],
    },
    "umap": {
        "name": "visualization",
        "description": "Generate UMAP plots and heatmaps",
        "phase": "reporting",
        "agent": AgentType.VIZ,
        "skills": ["plot_umap", "plot_heatmap"],
    },
}


class TaskDecomposer:
    """Decomposes user intent into executable task trees.

    For well-known intents (single-cell, file conversion, QA) the decomposer
    uses fast, hard-coded templates. For everything else it delegates to
    ``PlanEngine``, which can either use a registered domain strategy or the
    LLM fallback planner for unknown domains.
    """

    SINGLE_CELL_PIPELINE = [
        {
            "name": "quality_control",
            "description": "Filter low-quality cells and genes",
            "phase": "preprocessing",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_qc"],
            "success_criteria": [
                {
                    "metric": "result.qc.pass_rate",
                    "operator": ">=",
                    "threshold": 0.4,
                    "on_failure": "hitl",
                    "message": "QC 过滤率异常（{actual}），请确认是否继续。",
                }
            ],
        },
        {
            "name": "dimensionality_reduction",
            "description": "Compute PCA on normalized data",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_pca"],
            "dependencies": ["quality_control"],
        },
        {
            "name": "clustering",
            "description": "Compute neighbors and UMAP embedding",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_cluster"],
            "dependencies": ["dimensionality_reduction"],
            "hitl": ["n_neighbors", "resolution"],
        },
        {
            "name": "cell_annotation",
            "description": "Annotate cell clusters with marker genes",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_annotation"],
            "dependencies": ["clustering"],
        },
        {
            "name": "differential_expression",
            "description": "Find marker genes for each cluster",
            "phase": "analysis",
            "agent": AgentType.BIOINFO,
            "skills": ["scanpy_de"],
            "dependencies": ["cell_annotation"],
        },
        {
            "name": "visualization",
            "description": "Generate UMAP plots and heatmaps",
            "phase": "reporting",
            "agent": AgentType.VIZ,
            "skills": ["plot_umap", "plot_heatmap"],
            "dependencies": ["clustering", "cell_annotation"],
        },
    ]

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

        # Fast path: hard-coded templates for the most common known intents.
        # Any concrete single-cell request (even a short one) maps to the standard
        # pipeline so that agent assignments and required skills are explicit.
        if intent.analysis_type == "single_cell_analysis":
            tree = self._build_single_cell_pipeline(context)
            return self._task_tree_to_plan_result(
                tree, intent, strategy_name="single_cell_standard"
            ), tree

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

        # If sub-intents are present, build a tailored pipeline.
        if intent.sub_intents and intent.analysis_type in ("single_cell_analysis",):
            tree = self._build_sub_intent_pipeline(intent, context)
            return self._task_tree_to_plan_result(
                tree, intent, strategy_name="single_cell_standard"
            ), tree

        # General path: use PlanEngine (domain strategy or LLM fallback).
        plan_engine = self._get_plan_engine()
        plan = await plan_engine.plan(intent)

        if plan.is_fallback and not plan.phases:
            # LLM fallback produced only a suggestion with no executable skills.
            tree = self._build_suggestion_task(plan)
            return plan, tree

        return plan, self._plan_result_to_task_tree(plan)

    def _build_single_cell_pipeline(self, context: Dict[str, Any]) -> TaskTree:
        """Build the hard-coded single-cell analysis pipeline."""
        tasks = []
        id_map = {}

        for step in self.SINGLE_CELL_PIPELINE:
            task_id = str(uuid.uuid4())[:8]
            id_map[step["name"]] = task_id

            dependencies = [
                id_map[dep] for dep in step.get("dependencies", [])
                if dep in id_map
            ]

            hitl_checkpoints = []
            if "hitl" in step:
                hitl_checkpoints.append(HITLCheckpoint(
                    id=f"hitl_{task_id}",
                    trigger_reason="policy",
                    context_summary=f"Please confirm parameters for {step['name']}: {', '.join(step['hitl'])}",
                    options=[
                        Option(id="default", label="Use defaults", description="Use recommended parameter values"),
                        Option(id="custom", label="Customize", description="Set custom parameter values"),
                    ],
                ))

            task = TaskNode(
                id=task_id,
                name=step["name"],
                description=step["description"],
                phase=step["phase"],
                agent_assignment=step["agent"],
                skills_required=step["skills"],
                dependencies=dependencies,
                hitl_checkpoints=hitl_checkpoints,
                success_criteria=step.get("success_criteria", []),
            )
            tasks.append(task)

        return TaskTree(tasks)

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
        """Convert a PlanResult into an executable TaskTree."""
        tasks: List[TaskNode] = []
        task_ids: List[str] = []

        for phase in plan.phases:
            if not phase.required:
                continue

            task_id = str(uuid.uuid4())[:8]
            task_ids.append(task_id)

            # Linear dependency on the previous required phase.
            dependencies = [task_ids[-2]] if len(task_ids) > 1 else []

            skill_id = phase.selected_skill.id if phase.selected_skill else None
            skills_required = [skill_id] if skill_id else []

            hitl_checkpoints: List[HITLCheckpoint] = []
            if plan.is_fallback:
                # Add a confirmation checkpoint for LLM-generated plans.
                hitl_checkpoints.append(
                    HITLCheckpoint(
                        id=f"hitl_{task_id}",
                        trigger_reason="policy",
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
                dependencies=dependencies,
                parameters=phase.parameters,
                hitl_checkpoints=hitl_checkpoints,
                success_criteria=success_criteria,
            )
            tasks.append(task)

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

    def _build_sub_intent_pipeline(
        self,
        intent: UserIntent,
        context: Dict[str, Any],
    ) -> TaskTree:
        """Build a pipeline from explicit sub-intents (e.g., QC then cluster)."""
        steps = []
        seen_names = set()

        # Primary intent itself may imply a starting step.
        if intent.analysis_type == "single_cell_analysis":
            steps.append(SUB_INTENT_STEP_MAP.get("qc", SUB_INTENT_STEP_MAP["quality_control"]))

        for sub in intent.sub_intents:
            step = SUB_INTENT_STEP_MAP.get(sub.analysis_type)
            if step is None:
                continue
            if step["name"] in seen_names:
                continue
            steps.append(step)
            seen_names.add(step["name"])

        if not steps:
            # Fall back to full pipeline if no recognized sub-intents.
            return self._build_single_cell_pipeline(context)

        tasks = []
        id_map = {}

        for step in steps:
            task_id = str(uuid.uuid4())[:8]
            id_map[step["name"]] = task_id

            dependencies = [
                id_map[dep] for dep in step.get("dependencies", [])
                if dep in id_map
            ]

            hitl_checkpoints = []
            if "hitl" in step:
                hitl_checkpoints.append(HITLCheckpoint(
                    id=f"hitl_{task_id}",
                    trigger_reason="policy",
                    context_summary=f"Please confirm parameters for {step['name']}: {', '.join(step['hitl'])}",
                    options=[
                        Option(id="default", label="Use defaults", description="Use recommended parameter values"),
                        Option(id="custom", label="Customize", description="Set custom parameter values"),
                    ],
                ))

            task = TaskNode(
                id=task_id,
                name=step["name"],
                description=step["description"],
                phase=step["phase"],
                agent_assignment=step["agent"],
                skills_required=step["skills"],
                dependencies=dependencies,
                hitl_checkpoints=hitl_checkpoints,
                success_criteria=step.get("success_criteria", []),
            )
            tasks.append(task)

        return TaskTree(tasks)
