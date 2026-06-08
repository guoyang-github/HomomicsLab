from typing import Any, Dict
from homomics_lab.agent.base_agent import BaseAgent
from homomics_lab.models.common import AgentType


class ExperimentAgent(BaseAgent):
    agent_type = AgentType.EXPERIMENT
    capabilities = ["protocol_design", "primer_design"]

    async def run(self, task: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "task": task.name,
            "message": f"ExperimentAgent designed experiment for {task.name}",
        }
