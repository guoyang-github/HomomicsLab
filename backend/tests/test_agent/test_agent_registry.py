import pytest
from homomics_lab.agent.agent_registry import AgentRegistry
from homomics_lab.agent.base_agent import BaseAgent
from homomics_lab.models.common import AgentType


class FakeBioinfoAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["qc", "clustering"]

    async def run(self, task, context):
        return {"result": "bioinfo"}


class FakeVizAgent(BaseAgent):
    agent_type = AgentType.VIZ
    capabilities = ["plot"]

    async def run(self, task, context):
        return {"result": "viz"}


@pytest.fixture
def registry():
    reg = AgentRegistry()
    reg.register(FakeBioinfoAgent())
    reg.register(FakeVizAgent())
    return reg


def test_register_agent(registry):
    assert len(registry.list_agents()) == 2

def test_get_agent_by_type(registry):
    agent = registry.get_agent(AgentType.BIOINFO)
    assert agent.agent_type == AgentType.BIOINFO

def test_find_agent_for_task(registry):
    agent = registry.find_agent_for_task("qc")
    assert agent.agent_type == AgentType.BIOINFO

    agent = registry.find_agent_for_task("plot")
    assert agent.agent_type == AgentType.VIZ

    agent = registry.find_agent_for_task("unknown")
    assert agent is None
