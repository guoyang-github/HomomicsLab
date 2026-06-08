from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from homics_lab.models.common import AgentMessage, AgentType


class BaseAgent(ABC):
    agent_type: AgentType = None
    capabilities: List[str] = []

    def __init__(self, name: Optional[str] = None):
        self.name = name or self.agent_type

    def can_handle(self, task_type: str) -> bool:
        return task_type in self.capabilities or task_type == self.agent_type

    @abstractmethod
    async def run(self, task: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's core logic for a given task."""
        pass

    async def review(self, task: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        """Optional review step. Override for QA agents."""
        return {"approved": True, "feedback": None}

    def send_message(self, to_agent: str, content: str) -> AgentMessage:
        return AgentMessage(
            from_agent=self.name,
            to_agent=to_agent,
            content=content,
        )
