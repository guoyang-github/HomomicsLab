import pytest
from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.agent_registry import AgentRegistry
from homomics_lab.agent.bioinfo_agent import BioinfoAgent
from homomics_lab.agent.task_decomposer import TaskTree
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.builtin import register_builtin_skills
from homomics_lab.tasks.models import TaskNode
from homomics_lab.models.common import TaskStatus


@pytest.fixture
async def skill_orchestrator(tmp_path):
    registry = AgentRegistry()

    skill_registry = SkillRegistry()
    executor = SkillRuntimeExecutor(registry=skill_registry, working_dir=tmp_path)
    register_builtin_skills(executor)

    agent = BioinfoAgent(skill_executor=executor)
    registry.register(agent)

    return Orchestrator(registry=registry)


@pytest.mark.asyncio
async def test_orchestrator_executes_skill(tmp_path):
    skill_registry = SkillRegistry()
    executor = SkillRuntimeExecutor(registry=skill_registry, working_dir=tmp_path)
    register_builtin_skills(executor)

    registry = AgentRegistry()
    registry.register(BioinfoAgent(skill_executor=executor))

    orchestrator = Orchestrator(registry=registry)
    tree = TaskTree([
        TaskNode(
            id="t1",
            name="quality_control",
            description="QC",
            skills_required=["scanpy_qc"],
            parameters={"adata_path": "/fake/data.h5ad"},
        ),
    ])

    results = await orchestrator.run_tree(tree)

    assert "t1" in results
    assert results["t1"]["result"]["output_cells"] == 2531
    assert tree.get_task("t1").status == TaskStatus.COMPLETED
