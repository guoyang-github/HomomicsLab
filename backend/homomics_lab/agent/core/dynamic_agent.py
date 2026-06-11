"""DynamicAgent — runtime agent driven by RoleDefinition.

Replaces hardcoded BioinfoAgent, VizAgent, ExperimentAgent, etc.
Each instance is configured by a RoleDefinition loaded at runtime.
"""

from typing import Any, Dict, List, Optional

from homomics_lab.agent.base_agent import BaseAgent
from homomics_lab.models.common import AgentType

from .role import RoleDefinition


class DynamicAgent(BaseAgent):
    """An agent whose capabilities are determined by a RoleDefinition."""

    def __init__(
        self,
        role: RoleDefinition,
        name: Optional[str] = None,
        skill_executor=None,
        tool_registry=None,
    ):
        self.role = role
        self.agent_type = AgentType(role.agent_type) if role.agent_type in {t.value for t in AgentType} else AgentType.BIOINFO
        self.capabilities = list(role.allowed_skills)
        self.tool_registry = tool_registry

        super().__init__(name=name or role.name, skill_executor=skill_executor)

    def can_handle(self, task_type: str) -> bool:
        return self.role.can_handle_skill(task_type)

    async def run(self, task: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task using role configuration."""
        skill_id = None
        if getattr(task, "skills_required", None):
            skill_id = task.skills_required[0]
            if not self.role.can_handle_skill(skill_id):
                return {
                    "agent_type": self.agent_type,
                    "task": task.name,
                    "error": f"Role {self.role.role_id} cannot handle skill {skill_id}",
                }

        result = None
        if skill_id and self.skill_executor:
            result = await self.skill_executor.execute(skill_id, getattr(task, "parameters", {}))
        else:
            result = {"message": f"Agent {self.name} executed {task.name}"}

        return {
            "agent_type": self.agent_type,
            "task": task.name,
            "role_id": self.role.role_id,
            "skill": skill_id,
            "result": result,
        }

    async def review(self, task: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        """Review if role has review permission."""
        if not self.role.permissions.can_review:
            return {"approved": True, "feedback": None, "reason": "review_not_enabled"}

        # Placeholder for actual review logic
        return {
            "approved": True,
            "feedback": f"Reviewed by {self.role.role_id}",
            "role_id": self.role.role_id,
        }

    def get_system_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Render system prompt with optional context substitution."""
        prompt = self.role.system_prompt
        if context:
            try:
                prompt = prompt.format(**context)
            except (KeyError, ValueError):
                pass
        return prompt

    def get_available_tools(self) -> List[str]:
        """Return list of tools this agent can use."""
        if self.tool_registry is None:
            return []
        all_tools = [t.name for t in self.tool_registry.list()]
        if not self.role.allowed_tools:
            return all_tools
        return [t for t in all_tools if t in self.role.allowed_tools]

    def get_skill_recommendations(self, skill_dag, min_confidence: float = 0.6) -> List[dict]:
        """Get followed_by recommendations from SkillDAG for this role's skills."""
        if skill_dag is None:
            return []

        recommendations = []
        for skill_id in self.role.allowed_skills:
            if skill_id == "*":
                continue
            for next_skill, confidence in skill_dag.get_followed_by(skill_id, min_confidence):
                if self.role.can_handle_skill(next_skill):
                    recommendations.append({
                        "from_skill": skill_id,
                        "to_skill": next_skill,
                        "confidence": confidence,
                    })
        # Deduplicate and sort by confidence desc
        seen = set()
        unique = []
        for rec in sorted(recommendations, key=lambda x: x["confidence"], reverse=True):
            key = rec["to_skill"]
            if key not in seen:
                seen.add(key)
                unique.append(rec)
        return unique
