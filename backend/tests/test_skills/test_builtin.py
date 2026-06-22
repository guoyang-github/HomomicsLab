import pytest

from homomics_lab.skills.builtin import register_builtin_skills
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.runtime import SkillRuntimeExecutor


@pytest.fixture
def executor(tmp_path):
    registry = SkillRegistry()
    exec = SkillRuntimeExecutor(registry=registry, working_dir=tmp_path)
    register_builtin_skills(exec)
    return exec


@pytest.mark.asyncio
async def test_core_planning_skill_registered(executor):
    skill = executor.registry.get("core_planning")
    assert skill is not None
    assert skill.category == "agent_core"


@pytest.mark.asyncio
async def test_core_code_act_skill_registered(executor):
    skill = executor.registry.get("core_code_act")
    assert skill is not None
    assert skill.category == "agent_core"


@pytest.mark.asyncio
async def test_core_skill_router_registered(executor):
    skill = executor.registry.get("core_skill_router")
    assert skill is not None
    assert skill.category == "agent_core"


@pytest.mark.asyncio
async def test_core_interpretation_registered(executor):
    skill = executor.registry.get("core_interpretation")
    assert skill is not None
    assert skill.category == "agent_core"


@pytest.mark.asyncio
async def test_core_reproducibility_registered(executor):
    skill = executor.registry.get("core_reproducibility")
    assert skill is not None
    assert skill.category == "agent_core"


@pytest.mark.asyncio
async def test_core_hitl_registered(executor):
    skill = executor.registry.get("core_hitl")
    assert skill is not None
    assert skill.category == "agent_core"


@pytest.mark.asyncio
async def test_legacy_business_skills_removed(executor):
    """Legacy business skills have been removed from the builtin registry."""
    assert executor.registry.get("data_loader") is None
    assert executor.registry.get("scanpy_qc") is None
    assert executor.registry.get("scanpy_cluster") is None
