"""WorkerAgent — executes skills and returns structured WorkerResult."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from homomics_lab.agent.core.dynamic_agent import DynamicAgent
from homomics_lab.agent.core.role import RoleDefinition
from homomics_lab.models.common import AgentMessage, AgentType


@dataclass
class WorkerResult:
    """Structured result of a WorkerAgent task execution."""

    task_id: Optional[str]
    status: str  # "success" | "failure" | "skipped"
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "execution_time_seconds": self.execution_time_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerResult":
        return cls(
            task_id=data.get("task_id"),
            status=data.get("status", "success"),
            output=data.get("output", {}),
            error=data.get("error"),
            execution_time_seconds=data.get("execution_time_seconds", 0.0),
            metadata=data.get("metadata", {}),
        )


class WorkerAgent(DynamicAgent):
    """Agent responsible for executing skills and reporting structured outcomes."""

    agent_type = AgentType.WORKER

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

    async def run(self, task: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task, catch errors, and return a WorkerResult dict."""
        start = time.perf_counter()
        task_id = getattr(task, "id", None)
        task_name = getattr(task, "name", "unknown")

        if self.message_bus is not None:
            await self.message_bus.publish(
                "swr",
                AgentMessage(
                    from_agent=self.name,
                    to_agent="system",
                    content=f"worker_start:{task_id}:{task_name}",
                ),
            )

        try:
            output = await super().run(task, context)
            elapsed = time.perf_counter() - start
            error = output.get("error")
            status = "failure" if error else "success"
            result = WorkerResult(
                task_id=task_id,
                status=status,
                output=output,
                error=error,
                execution_time_seconds=elapsed,
                metadata={"agent_type": self.agent_type.value, "role_id": self.role.role_id},
            )
        except Exception as exc:  # pragma: no cover - safety net
            elapsed = time.perf_counter() - start
            result = WorkerResult(
                task_id=task_id,
                status="failure",
                output={},
                error=str(exc),
                execution_time_seconds=elapsed,
                metadata={"agent_type": self.agent_type.value, "role_id": self.role.role_id},
            )

        if self.message_bus is not None:
            await self.message_bus.publish(
                "swr",
                AgentMessage(
                    from_agent=self.name,
                    to_agent="system",
                    content=f"worker_complete:{task_id}:{result.status}",
                ),
            )

        return result.to_dict()
