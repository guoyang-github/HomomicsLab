import pytest
from homics_lab.agent.orchestrator import Orchestrator
from homics_lab.agent.agent_registry import AgentRegistry
from homics_lab.agent.base_agent import BaseAgent
from homics_lab.tasks.task_tree import TaskTree
from homics_lab.models.common import AgentType, TaskStatus
from homics_lab.tasks.models import TaskNode


class FakeBioinfoAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["scanpy_qc"]

    async def run(self, task, context):
        return {"output_file": "qc_result.h5ad"}


@pytest.fixture
def orchestrator():
    registry = AgentRegistry()
    registry.register(FakeBioinfoAgent())
    return Orchestrator(registry=registry)


@pytest.mark.asyncio
async def test_orchestrator_can_run_task(orchestrator):
    tree = TaskTree([
        TaskNode(id="t1", name="quality_control", description="QC", skills_required=["scanpy_qc"]),
    ])

    result = await orchestrator.run_tree(tree)

    assert result["t1"]["output_file"] == "qc_result.h5ad"
    task = tree.get_task("t1")
    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_orchestrator_respects_dependencies(orchestrator):
    tree = TaskTree([
        TaskNode(id="t1", name="step1", description="step 1", skills_required=["scanpy_qc"]),
        TaskNode(id="t2", name="step2", description="step 2", skills_required=["scanpy_qc"], dependencies=["t1"]),
    ])

    result = await orchestrator.run_tree(tree)

    assert "t1" in result
    assert "t2" in result
    assert tree.get_task("t1").status == TaskStatus.COMPLETED
    assert tree.get_task("t2").status == TaskStatus.COMPLETED


def test_orchestrator_progress(orchestrator):
    tree = TaskTree([
        TaskNode(id="t1", name="step1", description="step 1"),
        TaskNode(id="t2", name="step2", description="step 2", dependencies=["t1"]),
    ])

    progress = orchestrator.get_progress(tree)
    assert progress["total"] == 2
    assert progress["pending"] == 2
    assert progress["completed"] == 0
