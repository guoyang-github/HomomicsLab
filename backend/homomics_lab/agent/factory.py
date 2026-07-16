"""Agent factory — creates default agents using dynamic role injection.

Replaces hardcoded BioinfoAgent/VizAgent/ExperimentAgent with AgentCore.
"""

from pathlib import Path

from homomics_lab.agent.agent_registry import get_default_registry
from homomics_lab.agent.core import AgentCore, RoleRegistry
from homomics_lab.models.common import AgentType
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

    # Capture the existing analyst's wiring before init_analyst() potentially
    # overwrites it with a None-wired instance (scheduler calls without args).
    existing_analyst = registry.get_agent(AgentType.BIOINFO)
    existing_skill_executor = getattr(existing_analyst, "skill_executor", None)
    existing_tool_registry = getattr(existing_analyst, "tool_registry", None)

    # Always ensure the permanent analyst is present. It handles all
    # bioinformatics tasks and is required for single-cell workflows.
    core.init_analyst()

    # If a later caller (e.g. scheduler) invokes create_default_agents() without
    # a skill_executor after bootstrap already wired one, init_analyst() above
    # would have replaced the wired analyst with an unwired one. Restore the
    # previous wiring so agents can still invoke skills at runtime.
    analyst_agent = registry.get_agent(AgentType.BIOINFO)
    if analyst_agent is not None:
        if skill_executor is None and existing_skill_executor is not None:
            analyst_agent.skill_executor = existing_skill_executor
        if tool_registry is None and existing_tool_registry is not None:
            analyst_agent.tool_registry = existing_tool_registry

    # Pre-spawn common specialists for backward compatibility
    for role_id in ("visualization",):
        if core.role_registry.get(role_id):
            # Idempotent: only spawn if no agent of this type is registered yet
            if registry.get_agent(core.role_registry.get(role_id).agent_type) is None:
                core.spawn_specialist(role_id)

    # Register SWR system agents. When a real skill_executor / tool_registry is
    # provided we replace any stale agents created by early callers (e.g. the
    # scheduler) so the agents can actually invoke skills at runtime.
    force_replace = skill_executor is not None or tool_registry is not None

    worker_role = core.role_registry.get("worker")
    if worker_role and (force_replace or registry.get_agent(worker_role.agent_type) is None):
        registry.register(
            WorkerAgent(
                role=worker_role,
                skill_executor=skill_executor,
                tool_registry=tool_registry,
            )
        )

    reviewer_role = core.role_registry.get("reviewer")
    if reviewer_role and (force_replace or registry.get_agent(reviewer_role.agent_type) is None):
        registry.register(
            ReviewerAgent(
                role=reviewer_role,
                skill_executor=skill_executor,
                tool_registry=tool_registry,
            )
        )

    supervisor_role = core.role_registry.get("supervisor")
    if supervisor_role and (force_replace or registry.get_agent(supervisor_role.agent_type) is None):
        registry.register(
            SupervisorAgent(
                role=supervisor_role,
                agent_core=core,
                skill_executor=skill_executor,
                tool_registry=tool_registry,
            )
        )

    # Also ensure the permanent analyst is wired up, because it is the agent
    # that actually executes bioinformatics skills in the orchestrator.
    analyst_agent = registry.get_agent(AgentType.BIOINFO)
    if analyst_agent is not None and force_replace:
        analyst_agent.skill_executor = skill_executor
        analyst_agent.tool_registry = tool_registry

    return core
