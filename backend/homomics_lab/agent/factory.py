"""Agent factory — creates default agents using dynamic role injection.

Replaces hardcoded BioinfoAgent/VizAgent/ExperimentAgent with AgentCore.
"""

from pathlib import Path

from homomics_lab.agent.agent_registry import get_default_registry
from homomics_lab.agent.core import AgentCore, RoleRegistry
from homomics_lab.agent.reviewer import ReviewerAgent
from homomics_lab.agent.supervisor import SupervisorAgent
from homomics_lab.agent.worker import WorkerAgent


def create_default_agents(skill_executor=None, tool_registry=None):
    """Register all default agents using AgentCore dynamic roles.

    Creates (idempotently):
      - 1 permanent Analyst agent (handles bioinformatics tasks)
      - Pre-spawned specialist agents for common roles
      - Supervisor / Worker / Reviewer for SWR collaboration
    """
    registry = get_default_registry()

    core = AgentCore(
        role_registry=RoleRegistry(),
        agent_registry=registry,
        skill_executor=skill_executor,
        tool_registry=tool_registry,
    )

    # Load built-in role definitions
    roles_dir = Path(__file__).parent / "core" / "roles"
    core.role_registry.load_all(roles_dir)

    # Always ensure the permanent analyst is present. It handles all
    # bioinformatics tasks and is required for single-cell workflows.
    core.init_analyst()

    # Pre-spawn common specialists for backward compatibility
    for role_id in ("visualization",):
        if core.role_registry.get(role_id):
            # Idempotent: only spawn if no agent of this type is registered yet
            if registry.get_agent(core.role_registry.get(role_id).agent_type) is None:
                core.spawn_specialist(role_id)

    # Register SWR system agents (idempotent by agent_type)
    worker_role = core.role_registry.get("worker")
    if worker_role and registry.get_agent(worker_role.agent_type) is None:
        registry.register(
            WorkerAgent(
                role=worker_role,
                skill_executor=skill_executor,
                tool_registry=tool_registry,
            )
        )

    reviewer_role = core.role_registry.get("reviewer")
    if reviewer_role and registry.get_agent(reviewer_role.agent_type) is None:
        registry.register(
            ReviewerAgent(
                role=reviewer_role,
                skill_executor=skill_executor,
                tool_registry=tool_registry,
            )
        )

    supervisor_role = core.role_registry.get("supervisor")
    if supervisor_role and registry.get_agent(supervisor_role.agent_type) is None:
        registry.register(
            SupervisorAgent(
                role=supervisor_role,
                agent_core=core,
                skill_executor=skill_executor,
                tool_registry=tool_registry,
            )
        )

    return core
