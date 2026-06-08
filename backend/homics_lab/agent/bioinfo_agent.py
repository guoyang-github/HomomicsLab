from typing import Any, Dict
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.models.common import AgentType


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
        return {
            "agent_type": self.agent_type,
            "task": task.name,
            "skills": task.skills_required,
            "message": f"BioinfoAgent executed {task.name}",
            "output": context.get("input_data"),
        }
