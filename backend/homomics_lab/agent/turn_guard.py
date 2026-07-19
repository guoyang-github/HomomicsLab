"""TurnGuard — risk/correction collaborator for the turn pipeline.

Merges the former ``turn_risk_assessor`` and ``turn_self_correction``
collaborators into one cognitively cohesive module:

- ``RiskAssessor`` — prompt building and score parsing for turn risk
  evaluation (pure functions).
- ``SelfCorrectionHandler`` — evaluates failed executions and decides
  replan/HITL/stop.

No runner back-reference: services that are never reassigned after
``TurnRunner`` construction are constructor-injected, the lazily-built
self-correction engine is injected as a provider callable, and the re-entry
points for auto-replan (single-step / workflow handlers) are injected as
callables.
"""

from __future__ import annotations

import json
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    List,
    Optional,
)

from homomics_lab.agent.intent_analyzer import UserIntent
from homomics_lab.agent.plan.replanning import ReplanningTrigger
from homomics_lab.agent.plan.self_correction import (
    SelfCorrectionAction,
    SelfCorrectionEngine,
)
from homomics_lab.models.common import ChatMessage, MessageType

if TYPE_CHECKING:
    from homomics_lab.agent.task_decomposer import TaskDecomposer
    from homomics_lab.agent.turn_runner import TurnResult
    from homomics_lab.context.working_memory import WorkingMemory
    from homomics_lab.tasks.task_tree import TaskTree


class RiskAssessor:
    """Build risk-evaluation prompts and parse/heuristically derive risk scores."""

    @staticmethod
    def build_risk_prompt(
        intent: "UserIntent",
        user_message: str,
        working_memory: "WorkingMemory",
        project_id: Optional[str] = None,
    ) -> str:
        return (
            "Evaluate the risk that executing this user request will lead to "
            "data loss, destruction, or unintended modification of project state.\n\n"
            f"User message: {user_message}\n"
            f"Intent: {intent.intent_type} (mode={intent.interaction_mode}, scope={intent.scope})\n"
            f"Intent confidence: {intent.confidence:.2f}\n"
            f"Project ID: {project_id or 'unknown'}\n\n"
            'Respond with a JSON object: {"risk_score": 0.0} where the score is '
            "a float between 0.0 (no risk) and 1.0 (very high risk)."
        )

    @staticmethod
    def parse_risk_score(response: Any) -> float:
        """Parse a risk score from an LLM response."""
        text = ""
        if isinstance(response, str):
            text = response
        elif isinstance(response, dict):
            if "risk_score" in response:
                return float(response["risk_score"])
            text = str(response.get("content", response))
        else:
            text = str(response)

        # Try to extract JSON from the text.
        try:
            match = re.search(r"\{[^}]*\"risk_score\"[^}]*\}", text)
            if match:
                data = json.loads(match.group(0))
                return float(data["risk_score"])
        except Exception:
            pass

        # Fall back to a plain float in the response.
        try:
            return float(text.strip())
        except Exception:
            pass

        return 0.0

    @staticmethod
    def heuristic_risk_score(
        user_message: str,
        intent: "UserIntent",
        low_risk_keywords: set,
        high_risk_keywords: set,
    ) -> float:
        message_lower = user_message.lower()
        score = 0.0
        if any(kw in message_lower for kw in high_risk_keywords):
            score += 0.7
        if any(kw in message_lower for kw in low_risk_keywords):
            score -= 0.3
        if intent.interaction_mode == "answer" or intent.target == "convert_file":
            score -= 0.2
        return max(0.0, min(1.0, score))


class SelfCorrectionHandler:
    """Apply self-correction to failed task trees via replanning or HITL."""

    def __init__(
        self,
        *,
        task_decomposer: "TaskDecomposer",
        self_correction_engine_provider: Callable[[], SelfCorrectionEngine],
        single_step_handler: Callable[..., Awaitable["TurnResult"]],
        workflow_handler: Callable[..., Awaitable["TurnResult"]],
    ):
        self._task_decomposer = task_decomposer
        self._self_correction_engine_provider = self_correction_engine_provider
        self._single_step_handler = single_step_handler
        self._workflow_handler = workflow_handler

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
        current_plan = self._task_decomposer._task_tree_to_plan_result(
            tree,
            placeholder_intent,
            strategy_name="runtime-replan",
        )

        decision = self._self_correction_engine_provider().evaluate(
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
            new_tree = self._task_decomposer._plan_result_to_task_tree(decision.new_plan)
            if len(new_tree.tasks) == 1:
                return await self._single_step_handler(
                    new_tree,
                    working_memory,
                    project_id,
                    intent=intent,
                    user_message=user_message,
                )
            return await self._workflow_handler(
                new_tree,
                working_memory,
                project_id,
                intent=intent,
                user_message=user_message,
            )

        return None


class TurnGuard:
    """Facade over the risk/correction collaborators of the turn pipeline.

    Groups :class:`RiskAssessor` and :class:`SelfCorrectionHandler` behind a
    single entry point so ``TurnRunner`` holds one guard collaborator instead
    of two.
    """

    def __init__(
        self,
        *,
        task_decomposer: "TaskDecomposer",
        self_correction_engine_provider: Callable[[], SelfCorrectionEngine],
        single_step_handler: Callable[..., Awaitable["TurnResult"]],
        workflow_handler: Callable[..., Awaitable["TurnResult"]],
    ):
        self._self_correction_handler = SelfCorrectionHandler(
            task_decomposer=task_decomposer,
            self_correction_engine_provider=self_correction_engine_provider,
            single_step_handler=single_step_handler,
            workflow_handler=workflow_handler,
        )

    # --- RiskAssessor (pure functions) -------------------------------------

    @staticmethod
    def build_risk_prompt(
        intent: "UserIntent",
        user_message: str,
        working_memory: "WorkingMemory",
        project_id: Optional[str] = None,
    ) -> str:
        return RiskAssessor.build_risk_prompt(
            intent, user_message, working_memory, project_id
        )

    @staticmethod
    def parse_risk_score(response: Any) -> float:
        return RiskAssessor.parse_risk_score(response)

    @staticmethod
    def heuristic_risk_score(
        user_message: str,
        intent: "UserIntent",
        low_risk_keywords: set,
        high_risk_keywords: set,
    ) -> float:
        return RiskAssessor.heuristic_risk_score(
            user_message, intent, low_risk_keywords, high_risk_keywords
        )

    # --- SelfCorrectionHandler ----------------------------------------------

    async def apply_self_correction(
        self,
        tree: "TaskTree",
        working_memory: "WorkingMemory",
        project_id: str,
        error: Exception,
        intent: Optional["UserIntent"] = None,
        user_message: Optional[str] = None,
    ) -> Optional["TurnResult"]:
        return await self._self_correction_handler.apply(
            tree=tree,
            working_memory=working_memory,
            project_id=project_id,
            error=error,
            intent=intent,
            user_message=user_message,
        )
