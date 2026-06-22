import pytest

from homomics_lab.agent.orchestrator import Orchestrator
from homomics_lab.agent.agent_registry import AgentRegistry
from homomics_lab.agent.core import DynamicAgent, RoleDefinition
from homomics_lab.agent.task_decomposer import TaskTree
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.builtin import register_builtin_skills
from homomics_lab.tasks.models import TaskNode
from homomics_lab.models.common import TaskStatus


def _register_mock_qc_skill(executor: SkillRuntimeExecutor, tmp_path):
    """Register a tiny script-based QC skill for integration tests."""
    skill_dir = tmp_path / "mock_qc_skill"
    scripts = skill_dir / "scripts" / "python"
    scripts.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: mock_qc\nversion: \"1.0.0\"\n---\n\n# Mock QC\n", encoding="utf-8"
    )
    (scripts / "run.py").write_text("result = {'output_cells': 2531}\n")

    skill = SkillDefinition(
        id="mock_qc",
        name="Mock QC",
        version="1.0.0",
        category="test",
        runtime={"type": "python", "python_version": "3.10"},
        metadata={
            "source_dir": str(skill_dir),
            "scripts_dir": str(scripts),
            "entrypoint": "scripts/python/run.py",
            "trusted": True,
        },
        input_schema=SkillInputSchema(),
    )
    executor.registry.register(skill)


@pytest.fixture
async def skill_orchestrator(tmp_path):
    registry = AgentRegistry()

    skill_registry = SkillRegistry()
    executor = SkillRuntimeExecutor(registry=skill_registry, working_dir=tmp_path)
    register_builtin_skills(executor)
    _register_mock_qc_skill(executor, tmp_path)

    role = RoleDefinition(
        role_id="bioinfo",
        name="Bioinfo",
        agent_type="bioinfo",
        allowed_skills=["mock_qc"],
    )
    agent = DynamicAgent(role=role, skill_executor=executor)
    registry.register(agent)

    return Orchestrator(registry=registry)


@pytest.mark.asyncio
async def test_orchestrator_executes_skill(tmp_path):
    skill_registry = SkillRegistry()
    executor = SkillRuntimeExecutor(registry=skill_registry, working_dir=tmp_path)
    register_builtin_skills(executor)
    _register_mock_qc_skill(executor, tmp_path)

    registry = AgentRegistry()
    role = RoleDefinition(
        role_id="bioinfo",
        name="Bioinfo",
        agent_type="bioinfo",
        allowed_skills=["mock_qc"],
    )
    registry.register(DynamicAgent(role=role, skill_executor=executor))

    orchestrator = Orchestrator(registry=registry)
    tree = TaskTree([
        TaskNode(
            id="t1",
            name="quality_control",
            description="QC",
            skills_required=["mock_qc"],
            parameters={"adata_path": "/fake/data.h5ad"},
        ),
    ])

    results = await orchestrator.run_tree(tree)

    assert "t1" in results
    assert results["t1"]["result"]["output_cells"] == 2531
    assert tree.get_task("t1").status == TaskStatus.COMPLETED
