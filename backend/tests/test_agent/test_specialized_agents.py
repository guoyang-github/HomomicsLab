import pytest

from homomics_lab.agent.core import DynamicAgent, RoleDefinition, RolePermissions
from homomics_lab.models.common import AgentType


@pytest.mark.asyncio
async def test_bioinfo_agent():
    role = RoleDefinition(
        role_id="bioinfo",
        name="Bioinfo",
        agent_type="bioinfo",
        allowed_skills=["scanpy_qc"],
    )
    agent = DynamicAgent(role=role)
    task = type("Task", (), {"name": "qc", "skills_required": ["scanpy_qc"], "parameters": {}})()
    result = await agent.run(task, {})
    assert result["agent_type"] == AgentType.BIOINFO


@pytest.mark.asyncio
async def test_viz_agent():
    role = RoleDefinition(
        role_id="viz",
        name="Viz",
        agent_type="viz",
        allowed_skills=["plot_umap"],
    )
    agent = DynamicAgent(role=role)
    task = type("Task", (), {"name": "umap", "skills_required": ["plot_umap"], "parameters": {}})()
    result = await agent.run(task, {})
    assert result["agent_type"] == AgentType.VIZ


@pytest.mark.asyncio
async def test_experiment_agent():
    role = RoleDefinition(
        role_id="experiment",
        name="Experiment",
        agent_type="experiment",
        allowed_skills=["protocol_design"],
    )
    agent = DynamicAgent(role=role)
    task = type("Task", (), {"name": "protocol", "skills_required": ["protocol_design"], "parameters": {}})()
    result = await agent.run(task, {})
    assert result["agent_type"] == AgentType.EXPERIMENT
