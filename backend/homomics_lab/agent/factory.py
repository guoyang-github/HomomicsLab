"""Agent factory — creates default agents using dynamic role injection.

Replaces hardcoded BioinfoAgent/VizAgent/ExperimentAgent with AgentCore.
"""

from pathlib import Path

from homomics_lab.agent.agent_registry import get_default_registry
from homomics_lab.agent.core import AgentCore, RoleRegistry


def create_default_agents(skill_executor=None, tool_registry=None):
    """Register all default agents using AgentCore dynamic roles.

    Creates:
      - 1 permanent Analyst agent
      - Pre-spawned specialist agents for common roles
    """
    registry = get_default_registry()
    if registry.list_agents():
        # Already initialized
        return

    core = AgentCore(
        role_registry=RoleRegistry(),
        agent_registry=registry,
        skill_executor=skill_executor,
        tool_registry=tool_registry,
    )

    # Load built-in role definitions
    roles_dir = Path(__file__).parent / "core" / "roles"
    core.role_registry.load_all(roles_dir)

    # Initialize permanent analyst
    analyst = core.init_analyst()

    # Pre-spawn common specialists for backward compatibility
    for role_id in ("visualization",):
        if core.role_registry.get(role_id):
            core.spawn_specialist(role_id)

    return core
