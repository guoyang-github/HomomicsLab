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
async def test_core_hitl_skill_requests_human_input(executor):
    """core_hitl returns an awaiting_human payload when no resolution is given."""
    result = await executor.execute("core_hitl", {
        "checkpoint_type": "approval",
        "message": "Approve before continuing",
        "options": [{"id": "yes", "label": "Yes"}, {"id": "no", "label": "No"}],
    })
    assert result["status"] == "awaiting_human"
    assert "hitl" in result
    assert result["hitl"]["context_summary"] == "Approve before continuing"
    option_ids = {o["id"] for o in result["hitl"]["options"]}
    assert option_ids == {"yes", "no"}


@pytest.mark.asyncio
async def test_core_hitl_skill_finalizes_on_resolution(executor):
    """core_hitl returns the resolved payload when a resolution is provided."""
    result = await executor.execute("core_hitl", {
        "checkpoint_type": "approval",
        "message": "Approve before continuing",
        "resolution": {"choice": "yes", "parameters": {"threshold": 0.5}},
    })
    assert result["status"] == "completed"
    assert result["resolution"]["choice"] == "yes"
    assert result["resolution"]["parameters"]["threshold"] == 0.5


@pytest.mark.asyncio
async def test_legacy_business_skills_removed(executor):
    """Legacy business skills have been removed from the builtin registry."""
    assert executor.registry.get("data_loader") is None
    assert executor.registry.get("scanpy_qc") is None
    assert executor.registry.get("scanpy_cluster") is None
