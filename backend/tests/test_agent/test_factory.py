from homomics_lab.agent.factory import create_default_agents
from homomics_lab.agent.agent_registry import get_default_registry
from homomics_lab.models.common import AgentType


def test_create_default_agents():
    create_default_agents()
    registry = get_default_registry()

    # Analyst is registered as bioinfo type
    assert registry.get_agent(AgentType.BIOINFO) is not None

    # Reset for isolation
    registry.reset()
