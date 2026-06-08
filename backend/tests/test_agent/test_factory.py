from homics_lab.agent.factory import create_default_agents
from homics_lab.agent.agent_registry import get_default_registry
from homics_lab.models.common import AgentType


def test_create_default_agents():
    create_default_agents()
    registry = get_default_registry()

    assert registry.get_agent(AgentType.BIOINFO) is not None
    assert registry.get_agent(AgentType.VIZ) is not None
    assert registry.get_agent(AgentType.EXPERIMENT) is not None

    # Reset for isolation
    registry.reset()
