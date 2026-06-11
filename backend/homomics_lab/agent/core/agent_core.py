"""AgentCore — central coordinator with dynamic role injection.

  1 permanent AnalystAgent + on-demand SpecialistAgent spawning.
  Replaces the old hardcoded agent factory.
"""

from typing import Any, Dict, List, Optional

from homomics_lab.agent.agent_registry import AgentRegistry

from .dynamic_agent import DynamicAgent
from .registry import RoleRegistry
from .role import RoleDefinition


class AgentCore:
    """Core agent coordinator with dynamic role injection."""

    ANALYST_ROLE_ID = "analyst"

    def __init__(
        self,
        role_registry: Optional[RoleRegistry] = None,
        agent_registry: Optional[AgentRegistry] = None,
        skill_executor=None,
        tool_registry=None,
        skill_dag=None,
    ):
        self.role_registry = role_registry or RoleRegistry()
        self.agent_registry = agent_registry or AgentRegistry()
        self.skill_executor = skill_executor
        self.tool_registry = tool_registry
        self.skill_dag = skill_dag

        self._analyst: Optional[DynamicAgent] = None
        self._specialists: Dict[str, DynamicAgent] = {}

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------
    def init_analyst(self) -> DynamicAgent:
        """Initialize or return the permanent AnalystAgent."""
        if self._analyst is not None:
            return self._analyst

        role = self.role_registry.get(self.ANALYST_ROLE_ID)
        if role is None:
            # Fallback default analyst role
            role = RoleDefinition(
                role_id=self.ANALYST_ROLE_ID,
                name="Analyst",
                description="Permanent coordinator agent",
                agent_type="bioinfo",
                system_prompt="You are the Analyst, a permanent coordinator for bioinformatics workflows.",
                permissions={"can_execute": True, "can_review": True, "can_spawn_specialist": True},
            )
            self.role_registry.register(role)

        self._analyst = DynamicAgent(
            role=role,
            name="Analyst",
            skill_executor=self.skill_executor,
            tool_registry=self.tool_registry,
        )
        self.agent_registry.register(self._analyst)
        return self._analyst

    def spawn_specialist(
        self,
        role_id: str,
        name: Optional[str] = None,
    ) -> DynamicAgent:
        """Spawn a temporary specialist agent for a specific role."""
        role = self.role_registry.get(role_id)
        if role is None:
            raise ValueError(f"Role '{role_id}' not found in registry")

        agent = DynamicAgent(
            role=role,
            name=name or f"{role.name}-{len(self._specialists)}",
            skill_executor=self.skill_executor,
            tool_registry=self.tool_registry,
        )
        self._specialists[agent.name] = agent
        self.agent_registry.register(agent)
        return agent

    def dismiss_specialist(self, name: str) -> bool:
        """Remove a specialist agent."""
        if name in self._specialists:
            del self._specialists[name]
            return True
        return False

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    def resolve_agent_for_task(self, task: Any, executed_skills: Optional[List[str]] = None) -> Optional[DynamicAgent]:
        """Find the best agent for a task.

        Priority:
          1. Explicit agent_assignment on task
          2. Analyst if it can handle the skill
          3. Best matching specialist (spawn if needed)
          4. Spawn new specialist from role_registry match

        If skill_dag is available, validates against executed sequence.
        """
        # 1. Explicit assignment
        if getattr(task, "agent_assignment", None):
            agent = self.agent_registry.get_agent(task.agent_assignment)
            if agent:
                return agent

        skill_id = None
        skill_category = None
        if getattr(task, "skills_required", None):
            skill_id = task.skills_required[0]

        # DAG conflict check (before agent resolution)
        if self.skill_dag and skill_id and executed_skills:
            seq = executed_skills + [skill_id]
            validation = self.skill_dag.validate_sequence(seq)
            if validation.errors:
                raise ValueError(f"Skill sequence invalid: {'; '.join(validation.errors)}")

        # 2. Check analyst
        analyst = self.init_analyst()
        if skill_id and analyst.can_handle(skill_id):
            return analyst

        # 3. Check existing specialists
        for agent in self._specialists.values():
            if skill_id and agent.can_handle(skill_id):
                return agent

        # 4. Find best role and spawn
        if skill_id:
            roles = self.role_registry.find_for_skill(skill_id, skill_category)
            if roles:
                # Skip analyst if it was the only match
                for role in roles:
                    if role.role_id != self.ANALYST_ROLE_ID:
                        return self.spawn_specialist(role.role_id)

        return None

    def recommend_next_skills(self, last_skill_id: str, min_confidence: float = 0.6) -> List[tuple]:
        """Recommend next skills based on SkillDAG followed_by edges."""
        if self.skill_dag is None:
            return []
        return self.skill_dag.get_followed_by(last_skill_id, min_confidence=min_confidence)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def get_analyst(self) -> Optional[DynamicAgent]:
        return self._analyst

    def list_specialists(self) -> List[DynamicAgent]:
        return list(self._specialists.values())

    def reset(self) -> None:
        """Clear all agents and re-init analyst."""
        self._specialists.clear()
        self._analyst = None
        self.agent_registry.reset()
        self.init_analyst()
