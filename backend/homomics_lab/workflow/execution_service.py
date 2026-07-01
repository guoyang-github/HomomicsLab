"""Workflow execution service — materialize a Plan into a concrete execution backend."""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.plan.models import DataState, PlanResult
from homomics_lab.config import settings
from homomics_lab.hpc.router import select_execution_backend
from homomics_lab.hpc.scheduler import NextflowRunner
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.llm_client import LLMClient
from homomics_lab.plan.models import Plan
from homomics_lab.skills.registry import SkillRegistry, get_default_registry
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.tasks.task_tree import TaskTree
from homomics_lab.tools.registry import ToolRegistry, get_default_tool_registry
from homomics_lab.workspace.manager import WorkspaceManager

from .cache import WorkflowCache
from .models import WorkflowArtifact, WorkflowResult
from .nextflow_inputs import NextflowInputBuilder

logger = logging.getLogger(__name__)


class WorkflowExecutionService:
    """Execute an approved Plan through the best available backend.

    This is the bridge between the agent's plan and the actual compute:

        Plan (Agent)
            ↓
        WorkflowExecutionService
            ↓
        local / slurm / nextflow

    For multi-phase, data-heavy workflows, Nextflow is preferred because it
    provides cross-step caching, containerization, and resume. For single-step
    or lightweight tasks, the existing Orchestrator is used.
    """

    def __init__(
        self,
        skill_registry: Optional[SkillRegistry] = None,
        tool_registry: Optional[ToolRegistry] = None,
        llm_client: Optional[LLMClient] = None,
        orchestrator: Optional[Orchestrator] = None,
        progress_callback: Optional[Callable[[Any], None]] = None,
        cbkb: Optional[CBKB] = None,
        workflow_cache: Optional[WorkflowCache] = None,
    ):
        self.skill_registry = skill_registry or get_default_registry()
        self.tool_registry = tool_registry or get_default_tool_registry()
        self.llm_client = llm_client
        self.orchestrator = orchestrator
        self.progress_callback = progress_callback
        self.cbkb = cbkb
        self.workflow_cache: Optional[WorkflowCache]
        if workflow_cache is not None:
            self.workflow_cache = workflow_cache
        elif getattr(settings, "workflow_cache_enabled", True):
            cache_dir = getattr(settings, "workflow_cache_dir", None)
            self.workflow_cache = WorkflowCache(cache_dir=cache_dir)
        else:
            self.workflow_cache = None

    async def execute(
        self,
        plan: Plan,
        project_id: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> WorkflowResult:
        """Execute ``plan`` for ``project_id`` and return a unified result."""
        data_state = self._build_data_state(plan.plan_result, project_id)
        backend = select_execution_backend(plan.plan_result, data_state)

        result: Optional[WorkflowResult] = None
        try:
            if backend == "nextflow" and self._nextflow_enabled():
                if NextflowRunner.is_available():
                    try:
                        result = await self._execute_nextflow(
                            plan, project_id, timeout_seconds=timeout_seconds
                        )
                    except Exception as exc:
                        logger.warning(
                            "Nextflow execution failed for plan %s; falling back to local: %s",
                            plan.plan_id,
                            exc,
                            exc_info=True,
                        )
                        result = await self._execute_local(plan, project_id, context=context)
                else:
                    logger.info("Nextflow selected but not installed; falling back to local.")
                    result = await self._execute_local(plan, project_id, context=context)
            else:
                result = await self._execute_local(plan, project_id, context=context)
        finally:
            if result is not None:
                self._record_outcome(plan, result)

        return result

    @staticmethod
    def _nextflow_enabled() -> bool:
        return getattr(settings, "workflow_nextflow_enabled", True)

    def _build_data_state(self, plan_result: PlanResult, project_id: str) -> DataState:
        """Build a DataState for backend routing heuristics."""
        data_state = DataState()
        # Use phase count / sample hints embedded in parameters.
        for phase in plan_result.phases:
            for key in ("n_samples", "sample_count"):
                value = phase.parameters.get(key)
                if isinstance(value, int):
                    data_state.n_samples = value
            value = phase.parameters.get("n_cells")
            if isinstance(value, int):
                data_state.n_cells = value
        # Try to discover real file count from workspace data dir.
        try:
            ws = WorkspaceManager(settings.data_dir, project_id)
            data_dir = ws.get_path("data")
            if data_dir.exists():
                file_count = len(
                    [p for p in data_dir.iterdir() if p.is_file() and not p.name.startswith(".")]
                )
                if file_count:
                    data_state.set("n_samples", file_count)
        except Exception:
            pass
        return data_state

    async def _execute_local(
        self,
        plan: Plan,
        project_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        """Fallback local execution through the Orchestrator."""
        orchestrator = self.orchestrator or Orchestrator(
            registry=None,
            progress_callback=self.progress_callback,
            skill_registry=self.skill_registry,
            workflow_cache=self.workflow_cache,
        )
        run_context = dict(context or {})
        run_context.setdefault("project_id", project_id)
        run_context.setdefault("user_message", "workflow execution")

        results = await orchestrator.run_tree(plan.task_tree, context=run_context)

        # Map orchestrator results to a unified WorkflowResult.
        failed = any(
            getattr(task.status, "value", task.status) in ("failed",)
            for task in plan.task_tree.tasks
        )
        return WorkflowResult(
            success=not failed,
            backend="local",
            task_tree=plan.task_tree,
            metadata={"results": results},
        )

    async def _execute_nextflow(
        self,
        plan: Plan,
        project_id: str,
        timeout_seconds: Optional[float] = None,
    ) -> WorkflowResult:
        """Execute the plan as a Nextflow workflow."""
        timeout = timeout_seconds or settings.default_job_timeout_seconds
        working_dir = self._nextflow_working_dir(project_id, plan.plan_id)

        builder = NextflowInputBuilder(settings.data_dir, project_id)
        template_name = self._resolve_template_name(plan)
        inputs = builder.build(plan.plan_result, template_name=template_name)

        runtime = SkillRuntimeExecutor(
            registry=self.skill_registry,
            tool_registry=self.tool_registry,
            llm_client=self.llm_client,
            working_dir=working_dir,
            executor_type="nextflow",
            progress_callback=self.progress_callback,
        )

        try:
            result = await runtime.run_nextflow_plan(
                plan.plan_result,
                inputs,
                timeout_seconds=timeout,
                intent_analysis_type=plan.intent_analysis_type,
                resume=True,
            )
        except Exception as exc:
            logger.exception("Nextflow execution failed for plan %s", plan.plan_id)
            return WorkflowResult(
                success=False,
                backend="nextflow",
                task_tree=plan.task_tree,
                error_message=str(exc),
                logs=[str(exc)],
            )

        # Map overall success to the task tree.
        success = result.get("status") in ("completed", "COMPLETED")
        self._sync_tree_with_nextflow_result(plan.task_tree, result, success)

        artifacts = self._collect_artifacts(result, inputs)
        return WorkflowResult(
            success=success,
            backend="nextflow",
            task_tree=plan.task_tree,
            artifacts=artifacts,
            error_message=result.get("error") or result.get("error_message"),
            logs=result.get("stdout", []),
            metadata={
                "nf_file": result.get("nf_file"),
                "trace": result.get("trace"),
                "timeline_path": result.get("timeline_path"),
                "pipeline_dir": result.get("pipeline_dir"),
                "template": result.get("template"),
            },
        )

    @staticmethod
    def _nextflow_working_dir(project_id: str, plan_id: str) -> Path:
        """Create a dedicated working directory for this Nextflow run."""
        path = settings.data_dir / "workflows" / project_id / plan_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _resolve_template_name(plan: Plan) -> Optional[str]:
        """Determine which curated template (if any) matches the plan intent."""
        from homomics_lab.hpc.template_registry import get_template_registry

        registry = get_template_registry()
        intent = plan.intent_analysis_type
        for template_name in ("single_cell", "rnaseq"):
            path = registry.get_template(template_name)
            if path is None:
                continue
            # The registry maps these intents to template names.
            mapping = {
                "single_cell_analysis": "single_cell",
                "single_cell": "single_cell",
                "rnaseq_analysis": "rnaseq",
                "rnaseq": "rnaseq",
                "rna_seq": "rnaseq",
                "differential_expression": "rnaseq",
            }
            if mapping.get(intent) == template_name:
                return template_name
        return None

    @staticmethod
    def _sync_tree_with_nextflow_result(
        tree: TaskTree,
        result: Dict[str, Any],
        success: bool,
    ) -> None:
        """Update TaskTree statuses from a Nextflow execution result."""
        from homomics_lab.tasks.models import TaskStatus

        status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        for task in tree.tasks:
            task.status = status
            if not success:
                task.error_message = result.get("error") or result.get("error_message", "Nextflow failed")

    def _collect_artifacts(
        self,
        result: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> List[WorkflowArtifact]:
        """Collect artifacts produced by the Nextflow run."""
        artifacts: List[WorkflowArtifact] = []

        # Generated files that are paths.
        for key, artifact_type in (
            ("nf_file", "log"),
            ("timeline_path", "log"),
        ):
            value = result.get(key)
            if value:
                artifacts.append(WorkflowArtifact(path=str(value), artifact_type=artifact_type))

        # Ingested artifacts from nf-core / curated templates.
        ingested = result.get("ingested_artifacts") or []
        for item in ingested:
            if isinstance(item, dict):
                artifacts.append(
                    WorkflowArtifact(
                        path=item.get("relative_path", item.get("path", "")),
                        artifact_type=item.get("artifact_type", "output"),
                        task_id=item.get("task_id"),
                        metadata=item.get("metadata", {}),
                    )
                )

        # If an outdir is known, scan it for additional outputs.
        outdir = result.get("outdir") or inputs.get("outdir")
        if outdir:
            out_path = Path(outdir)
            if out_path.exists():
                for p in sorted(out_path.rglob("*")):
                    if p.is_file():
                        artifacts.append(
                            WorkflowArtifact(
                                path=str(p),
                                artifact_type="output",
                            )
                        )

        return artifacts


    def _record_outcome(self, plan: Plan, result: WorkflowResult) -> None:
        """Record the plan execution outcome in CBKB for feedback-loop tracking."""
        if self.cbkb is None or plan is None:
            return
        try:
            self.cbkb.record_plan_outcome(
                plan_id=plan.plan_id,
                strategy_name=plan.plan_result.strategy_name or "unknown",
                template_id=getattr(plan, "template_id", None),
                success=result.success,
                error_message=result.error_message,
                artifact_count=len(result.artifacts),
            )
        except Exception as exc:
            logger.warning("Failed to record plan outcome in CBKB: %s", exc, exc_info=True)
