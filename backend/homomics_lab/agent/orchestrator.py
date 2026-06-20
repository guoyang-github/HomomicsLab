import asyncio
import dataclasses
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from homomics_lab.agent.agent_registry import AgentRegistry, get_default_registry
from homomics_lab.agent.intent_analyzer import UserIntent
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
from homomics_lab.tasks.models import TaskNode
from homomics_lab.tasks.state_machine import TaskStateMachine
from homomics_lab.tasks.task_tree import TaskTree
from homomics_lab.hitl.detector import HITLDetector
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.observability.trace_store import TraceStore


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
    ):
        self.registry = registry or get_default_registry()
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

    async def run_tree(self, tree: TaskTree, context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        self._ensure_workspace_manager(context)
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

            for task in ready_tasks:
                if task.status in (TaskStatus.COMPLETED, TaskStatus.ABORTED):
                    continue

                self._report_progress(
                    ExecutionState(
                        job_id="",
                        status="RUNNING",
                        current_phase=task.name,
                        progress_pct=self._compute_progress(tree),
                        scheduler_type="agent",
                    )
                )

                # Check HITL
                checkpoint = self.hitl_detector.check(task, context)
                if checkpoint:
                    self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
                    results[task.id] = {"hitl": checkpoint.model_dump()}
                    hitl_triggered = True
                    self._report_progress(
                        ExecutionState(
                            job_id="",
                            status="AWAITING_HUMAN",
                            current_phase=task.name,
                            progress_pct=self._compute_progress(tree),
                            scheduler_type="agent",
                        )
                    )
                    continue

                try:
                    result = await self._execute_task(task, context, results)
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

                # SWR: escalate worker failures that survived retries.
                if self.supervisor is not None:
                    worker_result = results.get(task.id, result)
                    if isinstance(worker_result, dict) and worker_result.get("status") == "failure":
                        failure_count = getattr(task, "attempt_count", 1)
                        decision = self.supervisor.handle_worker_failure(task, failure_count)
                        if decision["action"] == "replan" and task.replan_attempt_count < task.max_replan_attempts:
                            await self._replan_for_worker_failure(tree, task, worker_result, context)
                            self.state_machine.transition(task, TaskStatus.COMPLETED)
                            continue
                        # Escalate to HITL (or replan exhausted).
                        checkpoint = self._create_worker_failure_checkpoint(task, worker_result)
                        task.hitl_checkpoints.insert(0, checkpoint)
                        self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
                        results[task.id] = {"hitl": checkpoint.model_dump()}
                        hitl_triggered = True
                        self._report_progress(
                            ExecutionState(
                                job_id="",
                                status="AWAITING_HUMAN",
                                current_phase=task.name,
                                progress_pct=self._compute_progress(tree),
                                scheduler_type="agent",
                            )
                        )
                        continue

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
                        continue

                    # Escalate to HITL.
                    checkpoint = self._create_phase_gate_checkpoint(task, gate_result)
                    task.hitl_checkpoints.insert(0, checkpoint)
                    self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
                    results[task.id] = {"hitl": checkpoint.model_dump()}
                    hitl_triggered = True
                    self._report_progress(
                        ExecutionState(
                            job_id="",
                            status="AWAITING_HUMAN",
                            current_phase=task.name,
                            progress_pct=self._compute_progress(tree),
                            scheduler_type="agent",
                        )
                    )
                    continue

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
                            continue

                        checkpoint = self._create_reviewer_reject_checkpoint(
                            task, review_decision
                        )
                        task.hitl_checkpoints.insert(0, checkpoint)
                        self.state_machine.transition(task, TaskStatus.AWAITING_HUMAN)
                        results[task.id] = {"hitl": checkpoint.model_dump()}
                        hitl_triggered = True
                        self._report_progress(
                            ExecutionState(
                                job_id="",
                                status="AWAITING_HUMAN",
                                current_phase=task.name,
                                progress_pct=self._compute_progress(tree),
                                scheduler_type="agent",
                            )
                        )
                        continue

                # Gate passed — interpret the result and adaptively replan if
                # the interpretation recommends it (e.g. missing downstream step).
                await self._maybe_adaptive_replan(tree, task, result, context)

                # Gate passed.
                self.state_machine.transition(task, TaskStatus.COMPLETED)

        if hitl_triggered:
            self._report_progress(
                ExecutionState(
                    job_id="",
                    status="AWAITING_HUMAN",
                    current_phase="workflow",
                    progress_pct=self._compute_progress(tree),
                    scheduler_type="agent",
                )
            )
        else:
            self._report_progress(
                ExecutionState(
                    job_id="",
                    status="COMPLETED",
                    current_phase="workflow",
                    progress_pct=100.0,
                    scheduler_type="agent",
                )
            )

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
        """Update the trace node with the task outcome."""
        trace_id = context.get("trace_id") if context else None
        if not trace_id or not node_id:
            return
        try:
            store = TraceStore()
            result = results.get(task.id, {})
            success = isinstance(result, dict) and not result.get("error")
            await store.update_node(
                trace_id=trace_id,
                node_id=node_id,
                status="completed" if success else "failed",
                outputs=result if isinstance(result, dict) else {"output": result},
                error=result.get("error") if isinstance(result, dict) else None,
            )
        except Exception:
            pass

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
                self.state_machine.transition(task, TaskStatus.COMPLETED)

        # Continue with remaining tasks
        remaining_results = await self.run_tree(tree, context)
        results.update(remaining_results)

        return results

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

        if self.supervisor is not None:
            try:
                return await self._execute_task_with_supervisor(task, context, results)
            finally:
                await self._finish_trace_node(task, context, trace_node_id, results)

        max_attempts = task.retry_policy.max_attempts
        backoff = task.retry_policy.backoff_seconds

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
                    task.error_message = str(e)
                    task.attempt_count = attempt

                    if attempt < max_attempts:
                        # Transition to FAILED so we can retry
                        self.state_machine.transition(task, TaskStatus.FAILED)
                        # Retry with backoff
                        await asyncio.sleep(backoff * (2 ** (attempt - 1)))
                    else:
                        # Final attempt failed
                        self.state_machine.transition(task, TaskStatus.FAILED)
                        raise
        finally:
            await self._finish_trace_node(task, context, trace_node_id, results)

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
