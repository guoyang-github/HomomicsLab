"""ReviewerAgent — independent validation of Worker results and Phase Gate outcomes."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from homomics_lab.agent.core.dynamic_agent import DynamicAgent
from homomics_lab.agent.core.role import RoleDefinition
from homomics_lab.models.common import AgentMessage, AgentType


@dataclass
class ReviewDecision:
    """Decision produced by a ReviewerAgent."""

    approved: bool
    action: str = "proceed"  # "proceed" | "replan" | "hitl"
    reason: Optional[str] = None
    risk_level: str = "low"  # "low" | "medium" | "high"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "action": self.action,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewDecision":
        return cls(
            approved=data.get("approved", True),
            action=data.get("action", "proceed"),
            reason=data.get("reason"),
            risk_level=data.get("risk_level", "low"),
            metadata=data.get("metadata", {}),
        )


class ReviewerAgent(DynamicAgent):
    """Agent that reviews task results and decides whether to proceed, replan, or escalate."""

    agent_type = AgentType.REVIEWER

    def __init__(
        self,
        role: RoleDefinition,
        name: Optional[str] = None,
        skill_executor=None,
        tool_registry=None,
        message_bus=None,
    ):
        super().__init__(
            role=role,
            name=name or role.name,
            skill_executor=skill_executor,
            tool_registry=tool_registry,
        )
        self.message_bus = message_bus

    async def review(
        self,
        task: Any,
        worker_result: Dict[str, Any],
        gate_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Review a completed task and return a ReviewDecision dict.

        Rules (deterministic for tests, extensible later):
        - Worker failure -> replan.
        - Phase gate failure -> replan.
        - Clustering phase with custom parameters -> HITL (user confirmation).
        - Otherwise -> proceed.
        """
        if not self.role.permissions.can_review:
            return ReviewDecision(
                approved=True,
                reason="review_not_enabled",
                metadata={"role_id": self.role.role_id},
            ).to_dict()

        task_id = getattr(task, "id", None)
        task_name = getattr(task, "name", "unknown")
        phase = getattr(task, "phase", "execution")
        parameters = getattr(task, "parameters", {}) or {}

        if self.message_bus is not None:
            await self.message_bus.publish(
                "swr",
                AgentMessage(
                    from_agent=self.name,
                    to_agent="system",
                    content=f"review_start:{task_id}:{task_name}",
                ),
            )

        status = worker_result.get("status", "success")
        error = worker_result.get("error")
        gate_passed = gate_result.get("passed", True) if gate_result else True

        if status == "failure" or error:
            decision = ReviewDecision(
                approved=False,
                action="replan",
                reason=f"worker reported failure: {error}",
                risk_level="high",
                metadata={"role_id": self.role.role_id},
            )
        elif not gate_passed:
            gate_message = (gate_result or {}).get("message", "phase gate failed")
            decision = ReviewDecision(
                approved=False,
                action="replan",
                reason=gate_message,
                risk_level="high",
                metadata={"role_id": self.role.role_id},
            )
        elif phase == "clustering" and bool(parameters):
            # User-customized clustering parameters require explicit confirmation.
            decision = ReviewDecision(
                approved=False,
                action="hitl",
                reason="clustering parameters were customized; please confirm",
                risk_level="medium",
                metadata={"role_id": self.role.role_id, "parameters": parameters},
            )
        else:
            decision = ReviewDecision(
                approved=True,
                action="proceed",
                reason="review passed",
                risk_level="low",
                metadata={"role_id": self.role.role_id},
            )

        if self.message_bus is not None:
            await self.message_bus.publish(
                "swr",
                AgentMessage(
                    from_agent=self.name,
                    to_agent="system",
                    content=f"review_complete:{task_id}:{decision.action}",
                ),
            )

        return decision.to_dict()
