import asyncio
import dataclasses
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from homomics_lab.agent.agent_registry import AgentRegistry, get_default_registry
from homomics_lab.config import settings
from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.execution.code_act import run_code_act
from homomics_lab.llm_client import LLMClient
from homomics_lab.agent.interpretation import InterpretationEngine
from homomics_lab.agent.message_bus import AgentMessageBus
from homomics_lab.agent.phase_gate import GateResult, PhaseGateEvaluator
from homomics_lab.agent.plan.models import DataState, Phase, PlanResult, SuccessCriterion
from homomics_lab.agent.plan.replanning import DynamicReplanningEngine, ReplanningTrigger
from homomics_lab.agent.reviewer import ReviewerAgent
from homomics_lab.agent.supervisor import SupervisorAgent
from homomics_lab.agent.task_decomposer import TaskDecomposer
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.models.common import AgentType, HITLCheckpoint, HITLTrigger, Option, TaskStatus
from homomics_lab.skills.registry import SkillRegistry, get_default_registry as get_default_skill_registry
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.state_machine import TaskStateMachine
from homomics_lab.tasks.task_tree import TaskTree
from homomics_lab.hitl.detector import HITLDetector
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.observability.trace_store import TraceStore
from homomics_lab.workspace.context import workspace_context
from homomics_lab.workflow.cache import WorkflowCache

logger = logging.getLogger(__name__)

_UNSET = object()


class Orchestrator:
    """Central task scheduler and executor."""

    def __init__(
        self,
        registry: AgentRegistry = None,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        workspace_manager=None,
        phase_gate_evaluator: Optional[PhaseGateEvaluator] = None,
        replanning_engine: Optional[DynamicReplanningEngine] = None,
        supervisor: Optional[SupervisorAgent] = None,
        reviewer: Optional[ReviewerAgent] = None,
        message_bus: Optional[AgentMessageBus] = None,
        interpretation_engine: Optional[InterpretationEngine] = _UNSET,
        cbkb: Optional[CBKB] = None,
        skill_registry: Optional[SkillRegistry] = None,
        workflow_cache: Optional[WorkflowCache] = None,
        skill_executor: Optional[Any] = None,
        execution_router: Optional[Any] = None,
    ):
        self.registry = registry or get_default_registry()
        self.skill_registry = skill_registry or get_default_skill_registry()
        self.skill_executor = skill_executor
        self.execution_router = execution_router
        self.workflow_cache = workflow_cache
        self.state_machine = TaskStateMachine()
        self.hitl_detector = HITLDetector()
        self._progress_callback = progress_callback
        self.workspace_manager = workspace_manager
        self.phase_gate_evaluator = phase_gate_evaluator
        self.replanning_engine = replanning_engine
        self.supervisor = supervisor
        self.reviewer = reviewer
        self.message_bus = message_bus
        if interpretation_engine is _UNSET and self.replanning_engine is not None:
            skill_dag = getattr(self.replanning_engine, "skill_dag", None)
            self.interpretation_engine = InterpretationEngine(skill_dag=skill_dag)
        elif interpretation_engine is _UNSET:
            self.interpretation_engine = None
        else:
            self.interpretation_engine = interpretation_engine

        self.cbkb = cbkb
        self._ingestion_service = None
        if self.cbkb is not None:
            from homomics_lab.evolution.ingestion import CBKBIngestionService

            self._ingestion_service = CBKBIngestionService(self.cbkb)

    def _resolve_skill_definition(self, task: TaskNode) -> Optional[Any]:
        """Resolve the SkillDefinition a task will execute, if known."""
        skill_id = task.skills_required[0] if task.skills_required else None
        if not skill_id:
            return None
        skill = self.skill_registry.get(skill_id)
        if skill is not None:
            return skill
        if self.replanning_engine is not None and self.replanning_engine.skill_dag is not None:
            return self.replanning_engine.skill_dag.registry.get(skill_id)
        return None

    def _collect_workspace_inputs(self, task: TaskNode, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect file inputs that should participate in the cache key."""
        workspace_inputs: Dict[str, Any] = {}
        for key, value in task.parameters.items():
            if isinstance(value, (str, Path)):
                path = Path(value)
                if path.is_file():
                    workspace_inputs[key] = path
                else:
                    workspace_inputs[key] = str(value)
            elif isinstance(value, dict) and "path" in value:
                path = Path(value["path"])
                if path.is_file():
                    workspace_inputs[key] = path
                else:
                    workspace_inputs[key] = str(value["path"])
            else:
                workspace_inputs[key] = value

        ctx_inputs = context.get("workspace_inputs") if context else None
        if isinstance(ctx_inputs, dict):
            for key, value in ctx_inputs.items():
                if key not in workspace_inputs:
                    if isinstance(value, (str, Path)):
                        path = Path(value)
                        workspace_inputs[key] = path if path.is_file() else str(value)
                    else:
                        workspace_inputs[key] = value
        return workspace_inputs

    def _try_restore_from_cache(
        self,
        tree: TaskTree,
        task: TaskNode,
        results: Dict[str, Any],
        context: Dict[str, Any],
    ) -> bool:
        """Restore a task from the workflow cache if possible.

        Returns True when the task was completed from cache.
        """
        if self.workflow_cache is None or not getattr(settings, "workflow_cache_enabled", True):
            return False

        skill = self._resolve_skill_definition(task)
        upstream_results = {dep_id: results[dep_id] for dep_id in task.dependencies if dep_id in results}
        workspace_inputs = self._collect_workspace_inputs(task, context)
        key = self.workflow_cache.compute_task_key(
            task,
            skill=skill,
            upstream_results=upstream_results,
            workspace_inputs=workspace_inputs,
        )
        entry = self.workflow_cache.get(key)
        if entry is None or not entry.success:
            task.input_hash = key
            task.cache_key = key
            return False

        task.input_hash = key
        task.output_hash = self.workflow_cache.compute_hash(entry.result)
        task.cache_key = key
        task.cache_hit = True
        task.result = entry.result
        results[task.id] = entry.result
        self.state_machine.transition(task, TaskStatus.RUNNING)
        self.state_machine.transition(task, TaskStatus.COMPLETED)
        self._publish_task_update(tree, task, "COMPLETED")
        return True

    def _collect_artifacts_from_result(self, result: Dict[str, Any]) -> List[Path]:
        """Collect output file paths from a result dict for caching."""
        artifacts: List[Path] = []
        for key in ("output_files", "artifacts", "output_paths"):
            value = result.get(key)
            if not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, (str, Path)):
                    path = Path(item)
                    if path.exists():
                        artifacts.append(path)
                elif isinstance(item, dict):
                    path_str = item.get("path") or item.get("file")
                    if path_str:
                        path = Path(path_str)
                        if path.exists():
                            artifacts.append(path)
        for key, value in result.items():
            if isinstance(value, (str, Path)):
                path = Path(value)
                if path.exists() and path.is_file():
                    artifacts.append(path)
        return artifacts

    def _cache_task_result(
        self,
        task: TaskNode,
        results: Dict[str, Any],
        context: Dict[str, Any],
    ) -> None:
        """Store a successful task result in the workflow cache."""
        if self.workflow_cache is None or not getattr(settings, "workflow_cache_enabled", True):
            return
        if task.cache_hit:
            return
        result = results.get(task.id)
        if not isinstance(result, dict):
            return
        if result.get("status") == "error" or result.get("error"):
            return
        if result.get("status") == "awaiting_human":
            return

        skill = self._resolve_skill_definition(task)
        upstream_results = {dep_id: results[dep_id] for dep_id in task.dependencies if dep_id in results}
        workspace_inputs = self._collect_workspace_inputs(task, context)
        key = self.workflow_cache.compute_task_key(
            task,
            skill=skill,
            upstream_results=upstream_results,
            workspace_inputs=workspace_inputs,
        )
        task.input_hash = key
        task.output_hash = self.workflow_cache.compute_hash(result)
        task.cache_key = key
        task.cache_hit = False
        artifacts = self._collect_artifacts_from_result(result)
        self.workflow_cache.put(
            key,
            result,
            artifacts=artifacts,
            metadata={
                "task_name": task.name,
                "skill_id": skill.id if skill is not None else task.name,
                "skill_version": skill.version if skill is not None else "unknown",
            },
        )

    async def run_tree(self, tree: TaskTree, context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        self._ensure_workspace_manager(context)
        with workspace_context(self.workspace_manager):
            return await self._run_tree_inner(tree, context)

    async def _run_tree_inner(self, tree: TaskTree, context: Dict[str, Any]) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        hitl_triggered = False

        self._report_progress(
            ExecutionState(
                job_id="",
                status="PENDING",
                current_phase="workflow",
                progress_pct=0.0,
                scheduler_type="agent",
            )
        )

        while True:
            ready_tasks = tree.get_ready_tasks()
            if not ready_tasks:
                break

            # HITL checks are cheap and sequential; they may remove tasks from
            # the ready set before execution.
            executable_tasks: List[Any] = []
            for task in ready_tasks:
                if task.status in (TaskStatus.COMPLETED, TaskStatus.ABORTED):
                    continue

                if self._try_restore_from_cache(tree, task, results, context):
                    continue

                checkpoint = self.hitl_detector.check(task, context)
                if checkpoint:
                    self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
                    results[task.id] = {"hitl": checkpoint.model_dump()}
                    hitl_triggered = True
                    self._publish_task_update(tree, task, "AWAITING_HUMAN")
                    continue

                executable_tasks.append(task)
                self._publish_task_update(tree, task, "RUNNING")

            # Execute independent ready tasks in parallel.
            if executable_tasks:
                async def run_one(task):
                    try:
                        result = await self._execute_task(task, context, results)
                    except Exception as exc:
                        self._publish_task_update(tree, task, "FAILED", error_message=str(exc))
                        raise
                    await self._process_task_result(task, result, tree, context, results)
                    return task.id

                await asyncio.gather(*[run_one(t) for t in executable_tasks])

            # Check whether any task escalated to HITL during post-processing.
            if any(t.status == TaskStatus.AWAITING_HUMAN for t in executable_tasks):
                hitl_triggered = True

        has_failed = any(t.status == TaskStatus.FAILED for t in tree.tasks)
        if has_failed:
            self._publish_task_update(tree, status="FAILED")
        elif hitl_triggered:
            self._publish_task_update(tree, status="AWAITING_HUMAN")
        else:
            self._publish_task_update(tree, status="COMPLETED")

        if self._ingestion_service is not None:
            try:
                project_id = context.get("project_id", "unknown") if context else "unknown"
                duration_seconds = None
                if hasattr(self, "_tree_start_time"):
                    duration_seconds = (
                        datetime.now(timezone.utc) - self._tree_start_time
                    ).total_seconds()
                self._ingestion_service.ingest_workflow(
                    project_id=project_id,
                    task_tree=tree,
                    phase_results=results,
                    success=not hitl_triggered,
                    duration_seconds=duration_seconds,
                )
            except Exception:
                # Ingestion failures must not break execution.
                pass

        return results

    async def _add_trace_node(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        node_type: str,
    ) -> Optional[str]:
        """Add a trace node for the task if a trace_id is present in context."""
        trace_id = context.get("trace_id") if context else None
        if not trace_id:
            return None
        try:
            store = TraceStore()
            node = await store.add_node(
                trace_id=trace_id,
                node_type=node_type,
                name=task.name,
                parent_id="root",
                inputs={"skills": task.skills_required, "parameters": task.parameters},
                metadata={"phase": task.phase, "task_id": task.id},
            )
            return node.node_id if node else None
        except Exception:
            # Trace recording must not break execution.
            return None

    async def _finish_trace_node(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        node_id: Optional[str],
        results: Dict[str, Any],
    ) -> None:
        """Update the trace node with the task outcome and execution logs."""
        trace_id = context.get("trace_id") if context else None
        if not trace_id or not node_id:
            return
        try:
            store = TraceStore()
            result = results.get(task.id, {})
            success = isinstance(result, dict) and not result.get("error")
            logs: List[str] = []
            if isinstance(result, dict):
                stdout = result.get("stdout")
                stderr = result.get("stderr")
                if stdout:
                    logs.append("STDOUT:\n" + str(stdout))
                if stderr:
                    logs.append("STDERR:\n" + str(stderr))
            await store.update_node(
                trace_id=trace_id,
                node_id=node_id,
                status="completed" if success else "failed",
                outputs=result if isinstance(result, dict) else {"output": result},
                error=result.get("error") if isinstance(result, dict) else None,
                logs=logs or None,
            )
        except Exception:
            pass

    async def _process_task_result(
        self,
        task: Any,
        result: Any,
        tree: TaskTree,
        context: Dict[str, Any],
        results: Dict[str, Any],
    ) -> None:
        """Post-process a single task result: HITL, gates, review, replan."""
        # A skill may request HITL by returning a ``hitl`` payload.
        if isinstance(result, dict) and result.get("status") == "awaiting_human" and "hitl" in result:
            from homomics_lab.models.common import HITLCheckpoint

            checkpoint = HITLCheckpoint(**result["hitl"])
            task.hitl_checkpoints.insert(0, checkpoint)
            self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
            results[task.id] = {"hitl": checkpoint.model_dump()}
            self._publish_task_update(tree, task, "AWAITING_HUMAN")
            return

        # Respect explicit agent/skill failure before gates/reviewers.
        if isinstance(result, dict) and result.get("success") is False:
            error_message = result.get("error") or "Skill execution failed"
            fallback = await self._try_codeact_fallback(
                task, context, original_error=error_message
            )
            if fallback is not None:
                results[task.id] = fallback
                task.result = fallback
                # Replace the failed result with the fallback and continue normal
                # post-processing (gate, cache, completion).
                result = fallback
            else:
                task.error_message = error_message
                self.state_machine.transition(task, TaskStatus.FAILED)
                self._publish_task_update(
                    tree, task, "FAILED", error_message=error_message
                )
                return

        # SWR: escalate worker failures that survived retries.
        if self.supervisor is not None:
            worker_result = results.get(task.id, result)
            if isinstance(worker_result, dict) and worker_result.get("status") == "failure":
                failure_count = getattr(task, "attempt_count", 1)
                decision = self.supervisor.handle_worker_failure(task, failure_count)
                if decision["action"] == "replan" and task.replan_attempt_count < task.max_replan_attempts:
                    await self._replan_for_worker_failure(tree, task, worker_result, context)
                    self.state_machine.transition(task, TaskStatus.COMPLETED)
                    return
                # Replan exhausted — try CodeAct fallback before escalating to HITL.
                fallback = await self._try_codeact_fallback(
                    task, context, original_error=worker_result.get("error")
                )
                if fallback is not None:
                    results[task.id] = fallback
                    task.result = fallback
                    result = fallback
                else:
                    # Escalate to HITL.
                    checkpoint = self._create_worker_failure_checkpoint(task, worker_result)
                    task.hitl_checkpoints.insert(0, checkpoint)
                    self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
                    results[task.id] = {"hitl": checkpoint.model_dump()}
                    self._publish_task_update(tree, task, "AWAITING_HUMAN")
                    return

        # Snapshot before gate evaluation if needed.
        if self._should_snapshot(task):
            try:
                task.pre_snapshot_id = self.workspace_manager.snapshot(
                    f"pre_{task.id}"
                )
            except Exception:
                # Snapshots are best-effort; do not break execution.
                pass

        gate_result = await self._evaluate_gate(task, result)
        if not gate_result.passed:
            task.gate_result = self._gate_result_to_dict(gate_result)
            if self._should_auto_replan(task, gate_result):
                await self._replan_after_gate(tree, task, gate_result, context)
                # Mark the failed task as completed so that remediation
                # phases downstream can execute.
                self.state_machine.transition(task, TaskStatus.COMPLETED)
                return

            # Escalate to HITL.
            checkpoint = self._create_phase_gate_checkpoint(task, gate_result)
            task.hitl_checkpoints.insert(0, checkpoint)
            self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
            results[task.id] = {"hitl": checkpoint.model_dump()}
            self._publish_task_update(tree, task, "AWAITING_HUMAN")
            return

        # SWR: reviewer checks gate-passed results.
        if self.reviewer is not None:
            review_decision = await self.reviewer.review(
                task,
                results.get(task.id, result),
                self._gate_result_to_dict(gate_result),
            )
            if not review_decision.get("approved", True):
                action = review_decision.get("action", "hitl")
                if action == "replan" and task.replan_attempt_count < task.max_replan_attempts:
                    await self._replan_for_reviewer_rejection(
                        tree, task, review_decision, context
                    )
                    self.state_machine.transition(task, TaskStatus.COMPLETED)
                    return

                checkpoint = self._create_reviewer_reject_checkpoint(
                    task, review_decision
                )
                task.hitl_checkpoints.insert(0, checkpoint)
                self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
                results[task.id] = {"hitl": checkpoint.model_dump()}
                self._publish_task_update(tree, task, "AWAITING_HUMAN")
                return

        # Gate passed — interpret the result and adaptively replan if
        # the interpretation recommends it (e.g. missing downstream step).
        await self._maybe_adaptive_replan(tree, task, result, context)

        # Gate passed — cache the successful result for incremental replay.
        self._cache_task_result(task, results, context)

        self.state_machine.transition(task, TaskStatus.COMPLETED)
        self._publish_task_update(tree, task, "COMPLETED")

    async def resume_task(
        self,
        tree: TaskTree,
        task_id: str,
        human_response: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        context = context or {}
        self._ensure_workspace_manager(context)
        task = tree.get_task(task_id)
        if task.status != TaskStatus.AWAITING_HUMAN:
            raise ValueError(f"Task {task_id} is not awaiting human input")

        choice = human_response.get("choice", "retry")
        if "parameters" in human_response:
            task.parameters.update(human_response["parameters"])

        # If the task was paused by a skill that requested HITL, feed the human
        # response back into the skill as a ``resolution`` input so it can
        # finalize its output on retry.
        if self._is_skill_requested_hitl(task):
            task.parameters["resolution"] = {
                "choice": choice,
                "parameters": human_response.get("parameters", {}),
            }

        context = context or {}
        results: Dict[str, Any] = {}

        self._report_progress(
            ExecutionState(
                job_id="",
                status="RUNNING",
                current_phase=task.name,
                progress_pct=self._compute_progress(tree),
                scheduler_type="agent",
            )
        )

        if choice == "skip":
            task.status = TaskStatus.COMPLETED
            task.result = task.result or {"skipped": True}
            results[task.id] = task.result

        elif choice == "replan":
            gate_result = self._gate_result_from_dict(task.gate_result)
            if gate_result is not None:
                await self._replan_after_gate(tree, task, gate_result, context)
            # Mark the gated task as completed so remediation phases can run.
            self.state_machine.transition(task, TaskStatus.COMPLETED)

        else:
            # Default: retry from snapshot if available.
            if choice == "retry" and task.pre_snapshot_id and self.workspace_manager is not None:
                try:
                    self.workspace_manager.restore(task.pre_snapshot_id)
                except Exception:
                    # Best-effort restore.
                    pass

            try:
                await self._execute_task(task, context, results)
            except Exception as exc:
                self._report_progress(
                    ExecutionState(
                        job_id="",
                        status="FAILED",
                        current_phase=task.name,
                        progress_pct=self._compute_progress(tree),
                        scheduler_type="agent",
                        error_message=str(exc),
                    )
                )
                raise

            # Snapshot before gate if needed.
            if self._should_snapshot(task):
                try:
                    task.pre_snapshot_id = self.workspace_manager.snapshot(
                        f"pre_{task.id}"
                    )
                except Exception:
                    pass

            gate_result = await self._evaluate_gate(task, results[task.id])
            if not gate_result.passed:
                task.gate_result = self._gate_result_to_dict(gate_result)
                checkpoint = self._create_phase_gate_checkpoint(task, gate_result)
                task.hitl_checkpoints.insert(0, checkpoint)
                self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
                results[task.id] = {"hitl": checkpoint.model_dump()}
                self._report_progress(
                    ExecutionState(
                        job_id="",
                        status="AWAITING_HUMAN",
                        current_phase=task.name,
                        progress_pct=self._compute_progress(tree),
                        scheduler_type="agent",
                    )
                )
            else:
                self._cache_task_result(task, results, context)
                self.state_machine.transition(task, TaskStatus.COMPLETED)

        # Continue with remaining tasks
        remaining_results = await self.run_tree(tree, context)
        results.update(remaining_results)

        return results

    @staticmethod
    def _is_skill_requested_hitl(task: TaskNode) -> bool:
        """Return True when the task was paused by a skill's HITL payload."""
        result = task.result
        if not isinstance(result, dict):
            return False
        return result.get("status") == "awaiting_human" and "hitl" in result

    def _ensure_workspace_manager(self, context: Dict[str, Any]) -> None:
        if self.workspace_manager is not None:
            return
        project_id = context.get("project_id")
        if not project_id:
            return
        from homomics_lab.config import settings
        from homomics_lab.workspace.manager import WorkspaceManager

        self.workspace_manager = WorkspaceManager(
            base_dir=settings.data_dir,
            project_id=project_id,
        )

    def _should_snapshot(self, task: TaskNode) -> bool:
        if self.workspace_manager is None:
            return False
        # Snapshot policy is not yet stored per-task; default to "auto".
        if not task.success_criteria:
            return False
        return True

    async def _evaluate_gate(
        self,
        task: TaskNode,
        result: Dict[str, Any],
    ) -> GateResult:
        if self.phase_gate_evaluator is None or not task.success_criteria:
            return GateResult(passed=True)
        # Unwrap WorkerResult if present so existing gate metrics keep working.
        gate_input = result
        if isinstance(result, dict) and "output" in result and "status" in result:
            gate_input = result["output"]
        return await self.phase_gate_evaluator.evaluate(task, gate_input)

    def _should_auto_replan(
        self,
        task: TaskNode,
        gate_result: GateResult,
    ) -> bool:
        if self.replanning_engine is None or gate_result.criterion is None:
            return False
        if gate_result.criterion.on_failure != "replan":
            return False
        return task.replan_attempt_count < task.max_replan_attempts

    def _create_phase_gate_checkpoint(
        self,
        task: TaskNode,
        gate_result: GateResult,
    ) -> HITLCheckpoint:
        message = gate_result.message
        if gate_result.criterion and gate_result.criterion.message:
            try:
                message = gate_result.criterion.message.format(
                    actual=gate_result.actual_value,
                    expected=gate_result.expected,
                    metric=gate_result.criterion.metric,
                )
            except Exception:
                message = gate_result.criterion.message
        return HITLCheckpoint(
            id=f"hitl_gate_{task.id}",
            trigger_reason=HITLTrigger.PHASE_GATE_FAIL,
            context_summary=message,
            options=[
                Option(
                    id="retry",
                    label="Retry",
                    description="Restore snapshot and retry this step",
                ),
                Option(
                    id="replan",
                    label="Replan",
                    description="Insert a remediation step and continue",
                ),
                Option(
                    id="skip",
                    label="Skip",
                    description="Skip this step and continue",
                ),
            ],
            default_option=Option(
                id="replan",
                label="Replan",
                description="Recommended: insert a remediation step",
            ),
            metadata={
                "risk_level": "high",
                "recommended_action": "replan",
                "metric": gate_result.criterion.metric if gate_result.criterion else None,
                "actual_value": gate_result.actual_value,
                "expected": gate_result.expected,
                "task_name": task.name,
            },
        )

    def _create_worker_failure_checkpoint(
        self,
        task: TaskNode,
        worker_result: Dict[str, Any],
    ) -> HITLCheckpoint:
        error = worker_result.get("error") or "worker failed"
        return HITLCheckpoint(
            id=f"hitl_worker_failure_{task.id}",
            trigger_reason=HITLTrigger.WORKER_FAILURE,
            context_summary=f"Worker failed for {task.name}: {error}",
            options=[
                Option(id="retry", label="Retry", description="Retry the failed task"),
                Option(id="replan", label="Replan", description="Let the Supervisor replan"),
                Option(id="skip", label="Skip", description="Skip this step"),
            ],
            default_option=Option(
                id="replan", label="Replan", description="Let the Supervisor replan"
            ),
            metadata={
                "risk_level": "high",
                "recommended_action": "replan",
                "error": error,
                "task_name": task.name,
            },
        )

    def _create_reviewer_reject_checkpoint(
        self,
        task: TaskNode,
        review_decision: Dict[str, Any],
    ) -> HITLCheckpoint:
        reason = review_decision.get("reason") or "reviewer rejected this step"
        action = review_decision.get("action", "hitl")
        risk_level = review_decision.get("risk_level", "medium")
        default_action = "replan" if action == "replan" else "proceed"
        return HITLCheckpoint(
            id=f"hitl_reviewer_reject_{task.id}",
            trigger_reason=HITLTrigger.REVIEWER_REJECT,
            context_summary=f"Reviewer rejected {task.name}: {reason}",
            options=[
                Option(id="proceed", label="Proceed", description="Approve and continue"),
                Option(id="replan", label="Replan", description="Let the Supervisor replan"),
                Option(id="skip", label="Skip", description="Skip this step"),
            ],
            default_option=Option(
                id=default_action,
                label=default_action.capitalize(),
                description="Recommended by Reviewer",
            ),
            metadata={
                "risk_level": risk_level,
                "recommended_action": default_action,
                "reason": reason,
                "task_name": task.name,
            },
        )

    async def _replan_for_worker_failure(
        self,
        tree: TaskTree,
        task: TaskNode,
        worker_result: Dict[str, Any],
        context: Dict[str, Any],
    ) -> None:
        task.replan_attempt_count += 1
        skill_id = task.skills_required[0] if task.skills_required else ""
        trigger = ReplanningTrigger(
            trigger_type="skill_failure",
            context={
                "failed_skill_id": skill_id,
                "phase_type": task.name,
                "error": worker_result.get("error"),
            },
            severity="major",
        )
        await self._apply_replan(tree, task, trigger, context)

    async def _replan_for_reviewer_rejection(
        self,
        tree: TaskTree,
        task: TaskNode,
        review_decision: Dict[str, Any],
        context: Dict[str, Any],
    ) -> None:
        task.replan_attempt_count += 1
        trigger = ReplanningTrigger(
            trigger_type="user_intervention",
            context={
                "phase_type": task.name,
                "new_params": task.parameters,
                "reason": review_decision.get("reason"),
            },
            severity="minor",
        )
        await self._apply_replan(tree, task, trigger, context)

    async def _apply_replan(
        self,
        tree: TaskTree,
        task: TaskNode,
        trigger: ReplanningTrigger,
        context: Dict[str, Any],
    ) -> None:
        """Apply a replanning trigger to the current tree."""
        if self.replanning_engine is None:
            return

        current_plan = self._build_plan_result_from_tree(tree)
        data_state = (
            self.phase_gate_evaluator.data_state
            if self.phase_gate_evaluator
            else DataState()
        )
        new_plan = self.replanning_engine.replan(
            current_plan,
            triggers=[trigger],
            data_state=data_state,
        )
        self._merge_replan_into_tree(tree, new_plan, task)

        if self.workspace_manager is not None:
            try:
                self.workspace_manager.snapshot(
                    f"replan_{task.id}_attempt_{task.replan_attempt_count}"
                )
            except Exception:
                pass

    @staticmethod
    def _gate_result_to_dict(gate_result: GateResult) -> Dict[str, Any]:
        return {
            "passed": gate_result.passed,
            "criterion": (
                dataclasses.asdict(gate_result.criterion)
                if gate_result.criterion
                else None
            ),
            "actual_value": gate_result.actual_value,
            "expected": gate_result.expected,
            "operator": gate_result.operator,
            "message": gate_result.message,
        }

    @staticmethod
    def _gate_result_from_dict(
        data: Optional[Dict[str, Any]],
    ) -> Optional[GateResult]:
        if data is None:
            return None
        criterion = None
        criterion_data = data.get("criterion")
        if criterion_data is not None:
            criterion = SuccessCriterion(**criterion_data)
        return GateResult(
            passed=data.get("passed", False),
            criterion=criterion,
            actual_value=data.get("actual_value"),
            expected=data.get("expected"),
            operator=data.get("operator", ""),
            message=data.get("message", ""),
        )

    async def _replan_after_gate(
        self,
        tree: TaskTree,
        task: TaskNode,
        gate_result: GateResult,
        context: Dict[str, Any],
    ) -> None:
        task.replan_attempt_count += 1

        trigger = ReplanningTrigger(
            trigger_type="phase_gate_fail",
            context={
                "phase_type": task.name,
                "metric": (
                    gate_result.criterion.metric
                    if gate_result.criterion
                    else ""
                ),
                "actual_value": gate_result.actual_value,
                "threshold": gate_result.expected,
                **(
                    gate_result.criterion.replan_context
                    if gate_result.criterion
                    else {}
                ),
            },
            severity="major",
        )
        await self._apply_replan(tree, task, trigger, context)

    async def _maybe_adaptive_replan(
        self,
        tree: TaskTree,
        task: TaskNode,
        result: Dict[str, Any],
        context: Dict[str, Any],
    ) -> None:
        """Interpret a successful result and replan if recommendations warrant it."""
        if self.interpretation_engine is None or self.replanning_engine is None:
            return

        if task.adaptive_replan_count >= task.max_adaptive_replan_attempts:
            return

        interpretation = await self._interpret_task_result(task, result, context)
        if interpretation is None:
            return

        phase = Phase(
            phase_type=task.name,
            parameters=dict(task.parameters),
            selected_skill=self._resolve_skill_for_task(task),
        )
        triggers = self.interpretation_engine.to_triggers(interpretation, phase)
        if not triggers:
            return

        current_plan = self._build_plan_result_from_tree(tree)
        data_state = (
            self.phase_gate_evaluator.data_state
            if self.phase_gate_evaluator
            else DataState()
        )
        new_plan = self.replanning_engine.replan(
            current_plan, triggers, data_state
        )

        delta = new_plan.reproducibility_context.get("replanning_delta", {})
        total_changes = (
            delta.get("phases_inserted", 0)
            + delta.get("phases_removed", 0)
            + delta.get("phases_modified", 0)
        )
        if total_changes == 0:
            return

        task.adaptive_replan_count += 1
        self._merge_replan_into_tree(tree, new_plan, task)

        if self.workspace_manager is not None:
            try:
                self.workspace_manager.snapshot(
                    f"adaptive_replan_{task.id}_attempt_{task.adaptive_replan_count}"
                )
            except Exception:
                pass

    async def _interpret_task_result(
        self,
        task: TaskNode,
        result: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[Any]:
        """Build an Interpretation for a completed task."""

        output = result
        if isinstance(result, dict) and "output" in result and isinstance(result["output"], dict):
            output = result["output"]

        phase = Phase(
            phase_type=task.name,
            parameters=dict(task.parameters),
            selected_skill=self._resolve_skill_for_task(task),
        )
        data_state = (
            self.phase_gate_evaluator.data_state
            if self.phase_gate_evaluator
            else DataState()
        )
        try:
            return self.interpretation_engine.interpret_phase(
                phase, output, data_state
            )
        except Exception:
            return None

    def _resolve_skill_for_task(
        self,
        task: TaskNode,
    ) -> Optional[Any]:
        """Resolve the SkillDefinition for a task from skill_dag or skills_required."""
        skill_id = task.skills_required[0] if task.skills_required else None
        if not skill_id:
            return None
        if self.replanning_engine is not None and self.replanning_engine.skill_dag is not None:
            return self.replanning_engine.skill_dag.registry.get(skill_id)
        return None

    def _build_plan_result_from_tree(self, tree: TaskTree) -> PlanResult:
        decomposer = TaskDecomposer()
        return decomposer._task_tree_to_plan_result(
            tree,
            intent=UserIntent(analysis_type="replan", complexity="complex"),
        )

    def _merge_replan_into_tree(
        self,
        tree: TaskTree,
        new_plan: PlanResult,
        current_task: TaskNode,
    ) -> None:
        old_by_name = {t.name: t for t in tree.tasks}
        new_tasks: List[TaskNode] = []
        id_map: Dict[str, str] = {}

        for i, phase in enumerate(new_plan.phases):
            if phase.phase_type == current_task.name:
                # Keep the current task object so the caller can update its status.
                new_tasks.append(current_task)
                id_map[phase.phase_type] = current_task.id
                continue

            existing = old_by_name.get(phase.phase_type)
            if existing is not None and existing.status == TaskStatus.COMPLETED:
                new_tasks.append(existing)
                id_map[phase.phase_type] = existing.id
                continue

            task_id = existing.id if existing is not None else str(uuid.uuid4())[:8]
            id_map[phase.phase_type] = task_id

            dependencies: List[str] = []
            if i > 0:
                prev_phase = new_plan.phases[i - 1]
                prev_id = id_map.get(prev_phase.phase_type)
                if prev_id is not None:
                    dependencies.append(prev_id)

            skills: List[str] = []
            if existing is not None and existing.skills_required:
                skills = list(existing.skills_required)
            elif phase.selected_skill is not None:
                skills = [phase.selected_skill.id]

            success_criteria = [
                dataclasses.asdict(c) for c in phase.success_criteria
            ]

            new_task = TaskNode(
                id=task_id,
                name=phase.phase_type,
                description=phase.description,
                phase=phase.phase_type,
                skills_required=skills,
                dependencies=dependencies,
                parameters=dict(phase.parameters),
                success_criteria=success_criteria,
            )
            new_tasks.append(new_task)

        tree.tasks = new_tasks

    def _fallback_task_prompt(
        self,
        task: TaskNode,
        original_error: Optional[str] = None,
    ) -> str:
        """Build a concise CodeAct prompt from the failed task metadata."""
        parts = [
            f"Task: {task.name}",
            f"Description: {task.description or task.name}",
        ]
        if task.skills_required:
            parts.append(f"Skills that failed: {', '.join(task.skills_required)}")
        if task.parameters:
            # Keep the prompt focused; avoid dumping huge nested structures.
            params = {
                k: v for k, v in task.parameters.items()
                if isinstance(v, (str, int, float, bool)) or v is None
            }
            if params:
                parts.append(f"Parameters: {params}")
        if original_error:
            parts.append(f"Original error: {original_error}")
        return "\n".join(parts)

    def _fallback_working_dir(self, context: Dict[str, Any]) -> Optional[Path]:
        """Resolve a working directory for CodeAct fallback."""
        project_id = context.get("project_id") if context else None
        if project_id:
            return settings.data_dir / "workspaces" / project_id
        return None

    async def _try_codeact_fallback(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        original_error: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Try to recover a failed task by generating and executing code.

        Returns a skill-style result dict on success, or None when fallback
        is disabled, unavailable, or also fails.
        """
        # Fixed-pipeline mode means curated skills must succeed or fail cleanly;
        # do not silently generate code.
        if self._execution_mode(context) == "fixed_pipeline":
            return None

        codeact_result = await self._run_codeact_for_task(
            task, context, original_error=original_error
        )
        if not codeact_result.get("success"):
            return None
        return self._normalize_codeact_result(
            task, codeact_result, original_error=original_error, fallback=True
        )

    def _execution_mode(self, context: Dict[str, Any]) -> str:
        """Return the plan-level execution mode from context."""
        mode = context.get("execution_mode") if context else None
        if mode in ("fixed_pipeline", "codeact", "auto"):
            return mode
        return "auto"

    async def _execute_task_codeact(
        self,
        task: TaskNode,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a task directly with CodeAct (foundation-first path).

        This is the primary execution strategy when ``execution_mode`` is
        ``codeact``. Curated skills are treated as references, not as rigid
        entrypoints, so the agent can generate bridging code as needed.
        """
        self.state_machine.transition(task, TaskStatus.RUNNING)
        codeact_result = await self._run_codeact_for_task(task, context)
        return self._normalize_codeact_result(
            task, codeact_result, skill_name="codeact"
        )

    async def _run_codeact_for_task(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        original_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate and run CodeAct for a task."""
        if not getattr(settings, "codeact_fallback_enabled", True):
            return {"success": False, "error": "CodeAct execution disabled"}

        working_dir = self._fallback_working_dir(context)
        if working_dir is None:
            return {"success": False, "error": "No project working directory available"}

        outputs_dir = working_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        prompt = self._fallback_task_prompt(task, original_error)
        prompt += (
            "\n\nImportant: write all output files (CSV, TXT, JSON, PNG, PDF, etc.) "
            f"to the directory '{outputs_dir}'. Do not scatter outputs in the working directory."
        )
        code_context: Dict[str, Any] = {
            "task_name": task.name,
            "task_description": task.description or task.name,
            "project_id": context.get("project_id"),
            "output_dir": str(outputs_dir),
            "working_dir": str(working_dir),
        }
        for key, value in task.parameters.items():
            if isinstance(value, (str, Path)):
                path = Path(value)
                if path.is_file() or path.is_dir():
                    code_context[key] = str(value)
            elif isinstance(value, dict) and "path" in value:
                code_context[key] = value["path"]
            elif isinstance(value, (int, float, bool)) or value is None:
                code_context[key] = value

        llm_client: Optional[LLMClient] = None
        try:
            llm_client = LLMClient()
        except Exception:
            llm_client = None

        max_attempts = max(1, task.retry_policy.max_attempts)
        backoff = task.retry_policy.backoff_seconds
        last_error: Optional[str] = original_error
        for attempt in range(1, max_attempts + 1):
            attempt_prompt = self._fallback_task_prompt(task, last_error)
            attempt_prompt += (
                "\n\nImportant: write all output files (CSV, TXT, JSON, PNG, PDF, etc.) "
                f"to the directory '{outputs_dir}'. Do not scatter outputs in the working directory."
            )
            self._emit_progress(
                status="RUNNING",
                current_phase=f"正在生成分析脚本… (尝试 {attempt}/{max_attempts})",
                progress_pct=10.0 + (attempt - 1) * 20.0,
            )
            try:
                codeact_result = await run_code_act(
                    task=attempt_prompt,
                    language="python",
                    context=code_context,
                    working_dir=working_dir,
                    llm_client=llm_client,
                    skill_registry=self.skill_registry,
                    tool_registry=None,
                )
                if codeact_result.get("success"):
                    self._emit_progress(
                        status="RUNNING",
                        current_phase="脚本执行完成，正在整理结果…",
                        progress_pct=80.0,
                    )
                    return codeact_result
                last_error = codeact_result.get("stderr") or codeact_result.get("error") or "unknown error"
            except Exception as exc:
                last_error = str(exc)
                logger.warning("CodeAct execution failed for task %s (attempt %d): %s", task.name, attempt, exc)

            if attempt < max_attempts:
                self._emit_progress(
                    status="RETRYING",
                    current_phase=f"检测到错误，正在自动修复并重试… (attempt {attempt + 1}/{max_attempts})",
                    progress_pct=30.0 + attempt * 20.0,
                    error_message=last_error[:500],
                )
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))

        return {"success": False, "error": last_error or "CodeAct execution failed after retries"}

    @staticmethod
    def _normalize_codeact_result(
        task: TaskNode,
        codeact_result: Dict[str, Any],
        original_error: Optional[str] = None,
        fallback: bool = False,
        skill_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Normalize a CodeAct result into a skill-style result dict."""
        if skill_name is None:
            skill_name = task.skills_required[0] if task.skills_required else "codeact"
        normalized: Dict[str, Any] = {
            "status": "success" if codeact_result.get("success") else "error",
            "skill": skill_name,
            "fallback": fallback,
            "original_error": original_error,
            "result": codeact_result.get("result") or {},
            "stdout": codeact_result.get("stdout", ""),
            "stderr": codeact_result.get("stderr", ""),
            "code": codeact_result.get("code", ""),
        }
        result_data = normalized["result"]
        if isinstance(result_data, dict):
            for key in ("output_path", "output_file", "plot_path"):
                if key in result_data and "output_files" not in normalized:
                    normalized["output_files"] = [result_data[key]]
                    break
        return normalized

    async def _execute_task(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a task and return its result.

        The caller is responsible for phase-gate evaluation and marking the
        task as COMPLETED / AWAITING_HUMAN / FAILED.
        """
        trace_node_id = await self._add_trace_node(task, context, node_type="phase")

        mode = self._execution_mode(context)

        # Skill-as-reference mode: when the decomposer has selected a concrete
        # skill but the user really wants an end-to-end compact script, generate
        # code with the skill docs/scripts as reference instead of running the
        # skill's own entrypoint. This takes precedence over the curated skill
        # runtime and supervisor delegation.
        if (
            mode != "fixed_pipeline"
            and task.parameters.get("use_skill_reference")
            and task.skills_required
        ):
            try:
                result = await self._execute_task_with_skill_reference(task, context)
                results[task.id] = result
                task.result = result
                return result
            finally:
                await self._finish_trace_node(task, context, trace_node_id, results)

        if self.supervisor is not None:
            try:
                return await self._execute_task_with_supervisor(task, context, results)
            finally:
                await self._finish_trace_node(task, context, trace_node_id, results)

        # CodeAct-first mode: skip curated skill runtime entirely.
        if mode == "codeact":
            try:
                result = await self._execute_task_codeact(task, context)
                results[task.id] = result
                task.result = result
                return result
            finally:
                await self._finish_trace_node(task, context, trace_node_id, results)

        max_attempts = task.retry_policy.max_attempts
        backoff = task.retry_policy.backoff_seconds
        last_error: Optional[Exception] = None

        try:
            for attempt in range(1, max_attempts + 1):
                # Only transition if not already running (e.g., on retry)
                if task.status != TaskStatus.RUNNING:
                    self.state_machine.transition(task, TaskStatus.RUNNING)

                try:
                    agent = self._resolve_agent(task)
                    if agent is None:
                        raise RuntimeError(f"No agent found for task {task.name}")

                    result = await agent.run(task, context)
                    results[task.id] = result
                    task.result = result
                    return result

                except Exception as e:
                    last_error = e
                    task.error_message = str(e)
                    task.attempt_count = attempt

                    if attempt < max_attempts:
                        # Transition to FAILED so we can retry
                        self.state_machine.transition(task, TaskStatus.FAILED)
                        # Retry with backoff
                        await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                    else:
                        # Final attempt failed; try CodeAct fallback unless we
                        # are in fixed-pipeline mode (where curated skills must
                        # succeed or fail cleanly).
                        if mode != "fixed_pipeline":
                            fallback = await self._try_codeact_fallback(
                                task, context, original_error=str(e)
                            )
                            if fallback is not None:
                                results[task.id] = fallback
                                task.result = fallback
                                return fallback
                        # Fallback unavailable, disabled, or fixed-pipeline —
                        # raise the original error.
                        self.state_machine.transition(task, TaskStatus.FAILED)
                        raise last_error
        finally:
            await self._finish_trace_node(task, context, trace_node_id, results)

    def _load_skill_reference(self, skill: Any) -> str:
        """Load SKILL.md and reference scripts for use as prompt context.

        The text is aggressively size-capped so it can be fed into the LLM
        prompt without crowding out the user's specific request.  SKILL.md
        gets the largest budget; each reference script is limited to a small
        chunk so only the most relevant scripts are included.
        """
        parts: List[str] = []
        if skill.body_path and skill.body_path.is_file():
            try:
                text = skill.body_path.read_text(encoding="utf-8", errors="ignore")
                parts.append(f"=== SKILL DOCUMENTATION ({skill.id}) ===\n{text[:12000]}")
            except Exception as exc:
                logger.warning("Failed to read skill body for %s: %s", skill.id, exc)

        if skill.has_scripts and skill.source_dir:
            scripts_dir = skill.source_dir / "scripts"
            if scripts_dir.is_dir():
                parts.append(f"=== REFERENCE SCRIPTS ({skill.id}) ===")
                total_chars = 0
                max_total = 30000
                per_file_max = 5000
                for path in sorted(scripts_dir.rglob("*")):
                    if not path.is_file():
                        continue
                    suffix = path.suffix.lower()
                    if suffix in (".pyc", ".pyo", ".so", ".dll", ".exe", ".bin"):
                        continue
                    if "__pycache__" in path.parts:
                        continue
                    if path.stat().st_size > 200_000:
                        continue
                    try:
                        snippet = path.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    if not snippet.strip():
                        continue
                    header = f"--- {path.relative_to(scripts_dir)} ---"
                    chunk = f"{header}\n{snippet[:per_file_max]}"
                    if total_chars + len(chunk) > max_total:
                        break
                    parts.append(chunk)
                    total_chars += len(chunk)
        return "\n\n".join(parts)

    def _build_skill_reference_prompt(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        reference_text: str,
    ) -> str:
        """Build a CodeAct prompt that treats a skill as reference material."""
        user_request = (
            task.parameters.get("user_request")
            or task.description
            or task.name
        )
        preflight = task.parameters.get("preflight") or {}

        # Resolve input files from task parameters and context.
        input_files: List[str] = []
        for key, value in task.parameters.items():
            if isinstance(value, (str, Path)):
                path = Path(value)
                if path.is_file() and str(path) not in input_files:
                    input_files.append(str(path))
            elif isinstance(value, dict) and "path" in value:
                p = value["path"]
                if p not in input_files:
                    input_files.append(p)

        ctx_inputs = context.get("workspace_inputs") or {}
        for value in ctx_inputs.values():
            if isinstance(value, (str, Path)):
                path = Path(value)
                if path.is_file() and str(path) not in input_files:
                    input_files.append(str(path))

        working_dir = self._fallback_working_dir(context)
        outputs_dir = (working_dir / "outputs") if working_dir else Path(".")

        parts = [
            f"User request: {user_request}",
            f"Task: {task.name}",
            f"Skill reference: {task.skills_required[0] if task.skills_required else 'unknown'}",
        ]
        if input_files:
            parts.append(f"Input files: {', '.join(input_files)}")
        if preflight:
            parts.append(
                "Data preflight (use this to decide the minimal workflow): "
                f"{json.dumps(preflight, ensure_ascii=False, default=str)}"
            )
        if reference_text:
            parts.append(reference_text)
        parts.append(
            "\nGenerate a compact, self-contained Python script (ideally ≤60 lines) that fulfills "
            "the user request. Use the skill documentation and reference scripts above as "
            "implementation guidance, but adapt the code to the user's specific data and request. "
            f"Read data from the Input files listed above, and write all output files "
            f"(CSV, TXT, JSON, PNG, PDF, etc.) to '{outputs_dir}'. Do not scatter outputs. "
            "If the user asked to compare results with an existing label column (e.g. all_celltype), "
            "include the comparison and report agreement metrics (ARI, NMI, confusion matrix). "
            "Print a brief summary of results at the end and assign it to the `result` variable."
        )
        return "\n\n".join(parts)

    async def _run_codeact_with_prompt(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        prompt: str,
    ) -> Dict[str, Any]:
        """Run CodeAct with a fully custom prompt."""
        if not getattr(settings, "codeact_fallback_enabled", True):
            return {"success": False, "error": "CodeAct execution disabled"}

        working_dir = self._fallback_working_dir(context)
        if working_dir is None:
            return {"success": False, "error": "No project working directory available"}

        outputs_dir = working_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        code_context: Dict[str, Any] = {
            "task_name": task.name,
            "task_description": task.description or task.name,
            "project_id": context.get("project_id"),
            "output_dir": str(outputs_dir),
            "working_dir": str(working_dir),
            "skills_required": task.skills_required,
        }
        first_input_path: Optional[str] = None
        for key, value in task.parameters.items():
            if isinstance(value, (str, Path)):
                path = Path(value)
                if path.is_file() or path.is_dir():
                    code_context[key] = str(path)
                    if first_input_path is None and path.is_file():
                        first_input_path = str(path)
            elif isinstance(value, dict) and "path" in value:
                code_context[key] = value["path"]
                if first_input_path is None:
                    first_input_path = value["path"]
            elif isinstance(value, (int, float, bool)) or value is None:
                code_context[key] = value

        if first_input_path is not None:
            code_context["input_path"] = first_input_path
            code_context["adata_path"] = first_input_path

        llm_client: Optional[LLMClient] = None
        try:
            llm_client = LLMClient()
        except Exception:
            llm_client = None

        try:
            return await run_code_act(
                task=prompt,
                language="python",
                context=code_context,
                working_dir=working_dir,
                llm_client=llm_client,
                skill_registry=self.skill_registry,
                tool_registry=None,
                max_tokens=8000,
            )
        except Exception as exc:
            logger.warning("CodeAct execution failed for task %s: %s", task.name, exc)
            return {"success": False, "error": str(exc)}

    async def _execute_task_with_skill_reference(
        self,
        task: TaskNode,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a task by asking the LLM to write a compact script using a skill as reference.

        This is the default path for concrete skill requests: instead of invoking
        the skill's own entrypoint, the LLM reads the skill documentation and
        reference scripts and produces an end-to-end script tailored to the
        user's data and question.
        """
        skill = self._resolve_skill_definition(task)
        if skill is None:
            return {
                "success": False,
                "error": f"Skill not found: {task.skills_required}",
            }

        reference_text = self._load_skill_reference(skill)
        prompt = self._build_skill_reference_prompt(task, context, reference_text)

        self.state_machine.transition(task, TaskStatus.RUNNING)
        max_attempts = max(1, task.retry_policy.max_attempts)
        backoff = task.retry_policy.backoff_seconds
        last_error: Optional[str] = None
        for attempt in range(1, max_attempts + 1):
            self._emit_progress(
                status="RUNNING",
                current_phase=f"正在生成分析脚本… (尝试 {attempt}/{max_attempts})",
                progress_pct=10.0 + (attempt - 1) * 20.0,
            )
            codeact_result = await self._run_codeact_with_prompt(task, context, prompt)
            if codeact_result.get("success"):
                self._emit_progress(
                    status="RUNNING",
                    current_phase="脚本执行完成，正在整理结果…",
                    progress_pct=80.0,
                )
                return self._normalize_codeact_result(
                    task, codeact_result, skill_name=skill.id
                )
            last_error = codeact_result.get("stderr") or codeact_result.get("error") or "unknown error"
            if attempt < max_attempts:
                prompt = self._build_skill_reference_prompt(task, context, reference_text)
                prompt += (
                    f"\n\nThe previous attempt failed with the following error. "
                    f"Please fix the script and try again.\nError: {last_error[:2000]}"
                )
                self._emit_progress(
                    status="RETRYING",
                    current_phase=f"检测到错误，正在自动修复并重试… (attempt {attempt + 1}/{max_attempts})",
                    progress_pct=30.0 + attempt * 20.0,
                    error_message=last_error[:500],
                )
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
        return {
            "success": False,
            "error": last_error or "Skill-as-reference execution failed after retries",
            "skill": skill.id,
        }

    async def _execute_task_with_supervisor(
        self,
        task: TaskNode,
        context: Dict[str, Any],
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a task under Supervisor delegation.

        Returns a WorkerResult-style dict on failure instead of raising, so
        the Orchestrator can decide retry/replan/HITL.
        """
        max_attempts = task.retry_policy.max_attempts
        backoff = task.retry_policy.backoff_seconds

        for attempt in range(1, max_attempts + 1):
            if task.status != TaskStatus.RUNNING:
                self.state_machine.transition(task, TaskStatus.RUNNING)

            try:
                worker = await self.supervisor.delegate(task, context)
                if worker is None:
                    raise RuntimeError(f"Supervisor could not delegate task {task.name}")

                raw_result = await worker.run(task, context)
            except Exception as e:
                task.error_message = str(e)
                task.attempt_count = attempt
                if attempt < max_attempts:
                    self.state_machine.transition(task, TaskStatus.FAILED)
                    await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                    continue
                raw_result = {
                    "task_id": task.id,
                    "status": "failure",
                    "output": {},
                    "error": str(e),
                    "execution_time_seconds": 0.0,
                    "metadata": {},
                }

            task.attempt_count = attempt
            task.error_message = raw_result.get("error") if isinstance(raw_result, dict) else None

            # If the worker returned a structured failure, retry internally.
            if isinstance(raw_result, dict) and raw_result.get("status") == "failure":
                if attempt < max_attempts:
                    self.state_machine.transition(task, TaskStatus.FAILED)
                    await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                    continue

            results[task.id] = raw_result
            task.result = raw_result
            return raw_result

    def _resolve_agent(self, task: TaskNode):
        """Find the best agent for a task."""
        # First try by explicit assignment
        if task.agent_assignment:
            agent_type = task.agent_assignment
            if isinstance(agent_type, str):
                try:
                    agent_type = AgentType(agent_type)
                except ValueError:
                    agent_type = None
            if agent_type:
                agent = self.registry.get_agent(agent_type)
                if agent:
                    return agent

        # Then try by required skills
        for skill in task.skills_required:
            agent = self.registry.find_agent_for_task(skill)
            if agent:
                return agent

        return None

    def get_progress(self, tree: TaskTree) -> Dict[str, int]:
        total = len(tree.tasks)
        by_status = {
            "total": total,
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "awaiting_human": 0,
            "aborted": 0,
        }

        for task in tree.tasks:
            if task.status == TaskStatus.PENDING:
                by_status["pending"] += 1
            elif task.status == TaskStatus.RUNNING:
                by_status["running"] += 1
            elif task.status == TaskStatus.COMPLETED:
                by_status["completed"] += 1
            elif task.status == TaskStatus.FAILED:
                by_status["failed"] += 1
            elif task.status == TaskStatus.AWAITING_HUMAN:
                by_status["awaiting_human"] += 1
            elif task.status == TaskStatus.ABORTED:
                by_status["aborted"] += 1

        by_status["percent"] = int((by_status["completed"] / total) * 100) if total > 0 else 0
        return by_status

    def _compute_progress(self, tree: TaskTree) -> float:
        progress = self.get_progress(tree)
        return float(progress.get("percent", 0.0))

    def _report_progress(self, state: ExecutionState) -> None:
        if self._progress_callback is not None:
            try:
                self._progress_callback(state)
            except Exception:
                # Never break execution because of a monitoring callback.
                pass

    def _emit_progress(
        self,
        status: str,
        current_phase: str,
        progress_pct: float,
        error_message: Optional[str] = None,
    ) -> None:
        """Emit a fine-grained progress event for long-running sub-steps."""
        self._report_progress(
            ExecutionState(
                job_id="",
                status=status,
                current_phase=current_phase,
                progress_pct=progress_pct,
                scheduler_type="agent",
                error_message=error_message,
            )
        )

    @staticmethod
    def _build_task_snapshot(tree: TaskTree) -> List[Dict[str, Any]]:
        """Return a JSON-serializable snapshot of the task tree."""
        return [t.model_dump(mode="json") for t in tree.tasks]

    def _publish_task_update(
        self,
        tree: TaskTree,
        active_task: Optional[TaskNode] = None,
        status: str = "RUNNING",
        error_message: Optional[str] = None,
    ) -> None:
        """Publish a task-level update with the current tree snapshot."""
        if self._progress_callback is None:
            return
        state = ExecutionState(
            job_id="",
            status=status,
            current_phase=active_task.name if active_task else "workflow",
            progress_pct=self._compute_progress(tree),
            scheduler_type="agent",
            tasks=self._build_task_snapshot(tree),
            active_task_id=active_task.id if active_task else None,
            error_message=error_message,
        )
        self._report_progress(state)
