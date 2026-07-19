"""SelfCorrectionHandler — evaluates failed executions and decides replan/HITL/stop.

Extracted from ``turn_runner.TurnRunner`` as a pure code move (no logic
changes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.replanning import ReplanningTrigger
from homomics_lab.agent.plan.self_correction import SelfCorrectionAction
from homomics_lab.models.common import ChatMessage, MessageType

if TYPE_CHECKING:
    from homomics_lab.agent.turn_runner import TurnResult, TurnRunner
    from homomics_lab.context.working_memory import WorkingMemory
    from homomics_lab.tasks.task_tree import TaskTree


class SelfCorrectionHandler:
    """Apply self-correction to failed task trees via replanning or HITL."""

    def __init__(self, runner: "TurnRunner"):
        self._runner = runner

    async def apply(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
        project_id: str,
        error: Exception,
        intent: Optional["UserIntent"] = None,
        user_message: Optional[str] = None,
    ) -> Optional["TurnResult"]:
        """Try to self-correct a failed execution.

        Returns a TurnResult if a correction decision was made, or None if the
        engine decided to stop or no failed tasks were found.
        """
        from homomics_lab.agent.turn_runner import ExecutionMode, TurnResult

        failed_tasks = [
            t for t in tree.tasks if str(t.status.value) == "failed"
        ]
        if not failed_tasks:
            return None

        # Respect per-task replan limits to avoid infinite loops.
        for task in failed_tasks:
            if task.replan_attempt_count >= task.max_replan_attempts:
                return None
            task.replan_attempt_count += 1

        triggers: List[ReplanningTrigger] = []
        for task in failed_tasks:
            error_msg = task.error_message or str(error)
            severity = "major" if "validation" in error_msg.lower() else "minor"
            triggers.append(
                ReplanningTrigger(
                    trigger_type="skill_failure",
                    severity=severity,
                    context={
                        "phase_type": task.phase,
                        "task_id": task.id,
                        "skill_id": task.skills_required[0] if task.skills_required else None,
                        "error": error_msg,
                        "reason": f"Skill execution failed for {task.name}: {error_msg}",
                    },
                )
            )

        # Build a PlanResult from the current task tree so the replanning engine
        # has a plan to mutate.
        placeholder_intent = intent or UserIntent(
            intent_type="analysis",
            interaction_mode="execute",
            scope="single_step",
            target="runtime_replan",
        )
        current_plan = self._runner.task_decomposer._task_tree_to_plan_result(
            tree,
            placeholder_intent,
            strategy_name="runtime-replan",
        )

        decision = self._runner._get_self_correction_engine().evaluate(
            current_plan=current_plan,
            triggers=triggers,
        )

        if decision.action == SelfCorrectionAction.STOP:
            return None

        if decision.action == SelfCorrectionAction.HITL_REPLAN:
            response_text = (
                f"执行中遇到问题，我计划调整方案：{decision.delta_summary}"
                "请确认是否继续。"
            )
            agent_msg = ChatMessage(
                id=f"msg_{len(working_memory.messages)}",
                type=MessageType.EXECUTION_PLAN,
                content={
                    "response_text": response_text,
                    "tasks": [t.model_dump() for t in tree.tasks],
                    "delta_summary": decision.delta_summary,
                    "replanned": True,
                },
                sender="agent",
            )
            working_memory.add_message(agent_msg)
            return TurnResult(
                mode=ExecutionMode.AWAITING_PLAN_APPROVAL,
                response_text=response_text,
                task_tree=tree,
                agent_message=agent_msg,
            )

        # AUTO_REPLAN: rebuild the task tree from the new plan and re-execute.
        if decision.new_plan is not None:
            new_tree = self._runner.task_decomposer._plan_result_to_task_tree(decision.new_plan)
            if len(new_tree.tasks) == 1:
                return await self._runner._handle_single_step(
                    new_tree,
                    working_memory,
                    project_id,
                    intent=intent,
                    user_message=user_message,
                )
            return await self._runner._handle_workflow(
                new_tree,
                working_memory,
                project_id,
                intent=intent,
                user_message=user_message,
            )

        return None
