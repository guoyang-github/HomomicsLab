from typing import Any, Dict
from homomics_lab.agent.base_agent import BaseAgent
from homomics_lab.models.common import AgentType


class VizAgent(BaseAgent):
    agent_type = AgentType.VIZ
    capabilities = ["plot_umap", "plot_heatmap", "plot_violin"]

    async def run(self, task: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "task": task.name,
            "plot_type": task.skills_required[0] if task.skills_required else "unknown",
            "message": f"VizAgent generated visualization for {task.name}",
        }
