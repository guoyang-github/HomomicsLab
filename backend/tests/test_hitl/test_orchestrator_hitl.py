import pytest
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.agent_registry import AgentRegistry
from homomics_lab.agent.base_agent import BaseAgent
from homomics_lab.tasks.task_tree import TaskTree
from homomics_lab.models.common import AgentType, TaskStatus, HITLTrigger
from homomics_lab.tasks.models import TaskNode


class FakeBioinfoAgent(BaseAgent):
    agent_type = AgentType.BIOINFO
    capabilities = ["scanpy_qc"]

    async def run(self, task, context):
        return {"done": True}


@pytest.mark.asyncio
async def test_orchestrator_pauses_for_hitl():
    registry = AgentRegistry()
    registry.register(FakeBioinfoAgent())
    orchestrator = Orchestrator(registry=registry)

    tree = TaskTree([
        TaskNode(
            id="t1",
            name="clustering",
            description="cluster",
            skills_required=["scanpy_qc"],
            hitl_checkpoints=[{
                "trigger_reason": HITLTrigger.POLICY,
                "context_summary": "Confirm",
                "options": [{"id": "ok", "label": "OK"}],
            }],
        ),
    ])

    result = await orchestrator.run_tree(tree)

    # With HITL, task should be awaiting human
    task = tree.get_task("t1")
    assert task.status == TaskStatus.AWAITING_HUMAN
    assert "hitl" in result["t1"]


@pytest.mark.asyncio
async def test_orchestrator_resumes_after_hitl():
    registry = AgentRegistry()
    registry.register(FakeBioinfoAgent())
    orchestrator = Orchestrator(registry=registry)

    tree = TaskTree([
        TaskNode(
            id="t1",
            name="clustering",
            description="cluster",
            skills_required=["scanpy_qc"],
            hitl_checkpoints=[{
                "trigger_reason": HITLTrigger.POLICY,
                "context_summary": "Confirm",
                "options": [{"id": "ok", "label": "OK"}],
            }],
        ),
    ])

    # First run pauses
    await orchestrator.run_tree(tree)
    assert tree.get_task("t1").status == TaskStatus.AWAITING_HUMAN

    # Resume
    await orchestrator.resume_task(tree, "t1", {"choice": "ok"})
    assert tree.get_task("t1").status == TaskStatus.COMPLETED
