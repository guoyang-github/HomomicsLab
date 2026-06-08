from typing import Any, Dict
from homomics_lab.agent.base_agent import BaseAgent
from homomics_lab.models.common import AgentType


class BioinfoAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = [
        "scanpy_qc",
        "scanpy_pca",
        "scanpy_cluster",
        "scanpy_annotation",
        "scanpy_de",
        "data_loader",
    ]

    async def run(self, task: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        if task.skills_required and self.skill_executor:
            skill_id = task.skills_required[0]
            result = await self.skill_executor.execute(skill_id, task.parameters)
            return {
                "agent_type": self.agent_type,
                "task": task.name,
                "skill": skill_id,
                "result": result,
            }

        return {
            "agent_type": self.agent_type,
            "task": task.name,
            "message": f"BioinfoAgent executed {task.name}",
        }
