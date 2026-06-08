from homomics_lab.agent.agent_registry import get_default_registry
from homomics_lab.agent.bioinfo_agent import BioinfoAgent
from homomics_lab.agent.viz_agent import VizAgent
from homomics_lab.agent.experiment_agent import ExperimentAgent


def create_default_agents():
    """Register all default agents."""
    registry = get_default_registry()

    registry.register(BioinfoAgent())
    registry.register(VizAgent())
    registry.register(ExperimentAgent())
