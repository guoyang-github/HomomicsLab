"""SupervisorAgent — plans, delegates, reviews, and replans."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from homomics_lab.agent.core.dynamic_agent import DynamicAgent
from homomics_lab.agent.core.role import RoleDefinition
from homomics_lab.agent.plan.models import PlanResult
from homomics_lab.agent.plan.replanning import DynamicReplanningEngine, ReplanningTrigger
from homomics_lab.agent.task_decomposer import TaskDecomposer
from homomics_lab.models.common import AgentMessage, AgentType


@dataclass
class SupervisorDecision:
    """Decision returned by SupervisorAgent.handle_worker_failure."""

    action: str  # "retry" | "replan" | "hitl"
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class SupervisorAgent(DynamicAgent):
    """Top-level agent that supervises workers, reviewers, and replanning."""

    agent_type = AgentType.SUPERVISOR

    def __init__(
        self,
        role: RoleDefinition,
        agent_core: Optional[Any] = None,
        name: Optional[str] = None,
        skill_executor=None,
        tool_registry=None,
        replanning_engine: Optional[DynamicReplanningEngine] = None,
        message_bus=None,
    ):
        super().__init__(
            role=role,
            name=name or role.name,
            skill_executor=skill_executor,
            tool_registry=tool_registry,
        )
        self.agent_core = agent_core
        self.replanning_engine = replanning_engine
        self.message_bus = message_bus

    async def delegate(self, task: Any, context: Dict[str, Any]) -> Any:
        """Pick the best agent to execute a task.

        Falls back to the Supervisor itself if no other agent is available.
        """
        task_id = getattr(task, "id", None)
        task_name = getattr(task, "name", "unknown")

        if self.message_bus is not None:
            await self.message_bus.publish(
                "swr",
                AgentMessage(
                    from_agent=self.name,
                    to_agent="system",
                    content=f"delegate_start:{task_id}:{task_name}",
                ),
            )

        agent = None

        # 1. Explicit assignment by agent type
        assignment = getattr(task, "agent_assignment", None)
        if assignment and self.agent_core is not None:
            from homomics_lab.models.common import AgentType

            if isinstance(assignment, AgentType):
                agent = self.agent_core.agent_registry.get_agent(assignment)
            elif isinstance(assignment, str):
                try:
                    agent_type = AgentType(assignment)
                    agent = self.agent_core.agent_registry.get_agent(agent_type)
                except ValueError:
                    agent = None

        # 2. Route via AgentCore (skips system roles internally)
        if agent is None and self.agent_core is not None:
            agent = self.agent_core.resolve_agent_for_task(task)

        # 3. Fallback to self
        if agent is None:
            agent = self

        if self.message_bus is not None:
            await self.message_bus.publish(
                "swr",
                AgentMessage(
                    from_agent=self.name,
                    to_agent=getattr(agent, "name", "unknown"),
                    content=f"delegate_complete:{task_id}:{getattr(agent, 'agent_type', 'unknown')}",
                ),
            )

        return agent

    async def review_result(
        self,
        task: Any,
        worker_result: Dict[str, Any],
        gate_result: Optional[Dict[str, Any]] = None,
        reviewer: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Review a completed task.

        If a dedicated Reviewer agent is provided, delegate to it. Otherwise
        the Supervisor makes a minimal deterministic decision.
        """
        if reviewer is not None:
            return await reviewer.review(task, worker_result, gate_result)

        # Minimal fallback decision logic
        status = worker_result.get("status", "success")
        gate_passed = gate_result.get("passed", True) if gate_result else True

        if status == "failure" or not gate_passed:
            return {
                "approved": False,
                "action": "replan",
                "reason": "worker failure or gate fail (supervisor fallback)",
                "risk_level": "high",
                "metadata": {"role_id": self.role.role_id},
            }

        return {
            "approved": True,
            "action": "proceed",
            "reason": "supervisor fallback approval",
            "risk_level": "low",
            "metadata": {"role_id": self.role.role_id},
        }

    def handle_worker_failure(
        self,
        task: Any,
        failure_count: int,
    ) -> Dict[str, Any]:
        """Decide what to do after a Worker failure.

        - failure_count < max_attempts  -> retry
        - failure_count == max_attempts -> replan
        - replan exhausted              -> hitl
        """
        max_attempts = getattr(task, "retry_policy", None)
        max_attempts = max_attempts.max_attempts if max_attempts else 3
        max_replan = getattr(task, "max_replan_attempts", 2)
        replan_count = getattr(task, "replan_attempt_count", 0)

        if failure_count < max_attempts:
            decision = SupervisorDecision(
                action="retry",
                reason=f"failure_count {failure_count} < max_attempts {max_attempts}",
            )
        elif replan_count < max_replan:
            decision = SupervisorDecision(
                action="replan",
                reason=f"max attempts reached; replan {replan_count + 1}/{max_replan}",
            )
        else:
            decision = SupervisorDecision(
                action="hitl",
                reason="worker failures and replan attempts exhausted",
            )

        return decision.to_dict()

    async def replan(
        self,
        tree: Any,
        trigger: ReplanningTrigger,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[PlanResult]:
        """Replan the remaining task tree after a failure or review rejection."""
        if self.replanning_engine is None:
            return None

        context = context or {}
        intent = context.get("intent")
        if intent is None:
            # Build a minimal intent from the tree if available
            intent = getattr(tree, "intent", None)

        decomposer = TaskDecomposer()
        current_plan = decomposer._task_tree_to_plan_result(
            tree,
            intent=intent,
            is_fallback=False,
            strategy_name="swr_replan",
        )
        data_state = current_plan.data_state

        new_plan = self.replanning_engine.replan(
            current_plan,
            triggers=[trigger],
            data_state=data_state,
        )

        if self.message_bus is not None:
            await self.message_bus.publish(
                "swr",
                AgentMessage(
                    from_agent=self.name,
                    to_agent="system",
                    content=f"replan_complete:{trigger.trigger_type}",
                ),
            )

        return new_plan
