from typing import Dict, List, Optional, Type
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.models.common import AgentType


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[AgentType, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if agent.agent_type is None:
            raise ValueError("Agent must have an agent_type")
        self._agents[agent.agent_type] = agent

    def get_agent(self, agent_type: AgentType) -> Optional[BaseAgent]:
        return self._agents.get(agent_type)

    def list_agents(self) -> List[BaseAgent]:
        return list(self._agents.values())

    def find_agent_for_task(self, task_type: str) -> Optional[BaseAgent]:
        for agent in self._agents.values():
            if agent.can_handle(task_type):
                return agent
        return None

    def reset(self) -> None:
        self._agents.clear()


_registry = AgentRegistry()

def get_default_registry() -> AgentRegistry:
    return _registry
