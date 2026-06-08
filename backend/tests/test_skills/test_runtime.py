import pytest
from homics_lab.skills.runtime import SkillRuntimeExecutor
from homics_lab.skills.models import SkillDefinition, SkillInputSchema
from homics_lab.skills.registry import SkillRegistry


@pytest.fixture
def executor(tmp_path):
    registry = SkillRegistry()
    return SkillRuntimeExecutor(registry=registry, working_dir=tmp_path)


@pytest.mark.asyncio
async def test_execute_builtin_skill(executor, tmp_path):
    skill = SkillDefinition(
        id="add_numbers",
        name="Add Numbers",
        version="1.0.0",
        category="math",
        runtime={"type": "python", "python_version": "3.10"},
        input_schema=SkillInputSchema(
            type="object",
            properties={
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            required=["a", "b"],
        ),
    )
    executor.registry.register(skill)

    # Register the skill code
    code = """
result = {"sum": a + b}
"""
    executor._register_builtin_code("add_numbers", code)

    result = await executor.execute("add_numbers", {"a": 2, "b": 3})
    assert result["sum"] == 5


@pytest.mark.asyncio
async def test_execute_unknown_skill(executor):
    with pytest.raises(ValueError) as exc_info:
        await executor.execute("unknown", {})
    assert "not found" in str(exc_info.value)
