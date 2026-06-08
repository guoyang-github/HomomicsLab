import pytest
from homics_lab.agent.bioinfo_agent import BioinfoAgent
from homics_lab.agent.viz_agent import VizAgent
from homics_lab.agent.experiment_agent import ExperimentAgent
from homics_lab.models.common import AgentType


@pytest.mark.asyncio
async def test_bioinfo_agent():
    agent = BioinfoAgent()
    task = type("Task", (), {"name": "qc", "skills_required": ["scanpy_qc"], "parameters": {}})()
    result = await agent.run(task, {})
    assert result["agent_type"] == AgentType.BIOINFO
    assert "executed" in result["message"]


@pytest.mark.asyncio
async def test_viz_agent():
    agent = VizAgent()
    task = type("Task", (), {"name": "umap", "skills_required": ["plot_umap"], "parameters": {}})()
    result = await agent.run(task, {})
    assert result["agent_type"] == AgentType.VIZ


@pytest.mark.asyncio
async def test_experiment_agent():
    agent = ExperimentAgent()
    task = type("Task", (), {"name": "protocol", "skills_required": ["protocol_design"], "parameters": {}})()
    result = await agent.run(task, {})
    assert result["agent_type"] == AgentType.EXPERIMENT
