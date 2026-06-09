import pytest
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


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


@pytest.mark.asyncio
async def test_execute_file_based_python_skill(executor, tmp_path):
    """Test executing a file-based Python skill."""
    scripts_dir = tmp_path / "scripts" / "python"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "math.py").write_text("""
result = {"product": x * y}
""")

    skill = SkillDefinition(
        id="multiply",
        name="Multiply",
        version="1.0.0",
        category="math",
        runtime={"type": "python", "python_version": "3.10"},
        input_schema=SkillInputSchema(
            type="object",
            properties={
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            required=["x", "y"],
        ),
    )
    executor.registry.register(skill)
    executor.register_file_skill(skill, scripts_dir)

    result = await executor.execute("multiply", {"x": 3, "y": 4})
    assert result["product"] == 12


@pytest.mark.asyncio
async def test_execute_file_based_r_skill(executor, tmp_path):
    """Test executing a file-based R skill."""
    scripts_dir = tmp_path / "scripts" / "r"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "math.R").write_text("""
result <- list(sum = a + b)
""")

    skill = SkillDefinition(
        id="add_r",
        name="Add R",
        version="1.0.0",
        category="math",
        runtime={"type": "r"},
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
    executor.register_file_skill(skill, scripts_dir)

    result = await executor.execute("add_r", {"a": 5, "b": 7})
    assert result["sum"] == 12


@pytest.mark.asyncio
async def test_execute_mixed_skill_chooses_python(executor, tmp_path):
    """Test that mixed skill with Python primary_tool uses Python."""
    scripts_dir = tmp_path / "scripts" / "python"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "calc.py").write_text("""
result = {"lang": "python"}
""")

    skill = SkillDefinition(
        id="mixed_python",
        name="Mixed Python",
        version="1.0.0",
        category="test",
        runtime={"type": "mixed"},
        metadata={"primary_tool": "scanpy", "scripts_dir": str(scripts_dir)},
        input_schema=SkillInputSchema(),
    )
    executor.registry.register(skill)

    result = await executor.execute("mixed_python", {})
    assert result["lang"] == "python"


@pytest.mark.asyncio
async def test_execute_mixed_skill_chooses_r(executor, tmp_path):
    """Test that mixed skill with R primary_tool uses R."""
    scripts_dir = tmp_path / "scripts" / "r"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "calc.R").write_text("""
result <- list(lang = "r")
""")

    skill = SkillDefinition(
        id="mixed_r",
        name="Mixed R",
        version="1.0.0",
        category="test",
        runtime={"type": "mixed"},
        metadata={"primary_tool": "Seurat", "scripts_dir": str(scripts_dir)},
        input_schema=SkillInputSchema(),
    )
    executor.registry.register(skill)

    result = await executor.execute("mixed_r", {})
    assert result["lang"] == "r"


@pytest.mark.asyncio
async def test_execute_file_skill_from_metadata(executor, tmp_path):
    """Test executing a skill that has scripts_dir in metadata."""
    scripts_dir = tmp_path / "scripts" / "python"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "hello.py").write_text("""
result = {"greeting": "hello"}
""")

    skill = SkillDefinition(
        id="hello",
        name="Hello",
        version="1.0.0",
        category="test",
        runtime={"type": "python"},
        metadata={"scripts_dir": str(scripts_dir)},
        input_schema=SkillInputSchema(),
    )
    executor.registry.register(skill)

    result = await executor.execute("hello", {})
    assert result["greeting"] == "hello"


def test_resolve_execution_type(executor):
    """Test execution type resolution."""
    python_skill = SkillDefinition(
        id="py", name="Py", version="1.0", category="test",
        runtime={"type": "python"},
    )
    assert executor._resolve_execution_type(python_skill) == "python"

    r_skill = SkillDefinition(
        id="r", name="R", version="1.0", category="test",
        runtime={"type": "r"},
    )
    assert executor._resolve_execution_type(r_skill) == "r"

    mixed_r = SkillDefinition(
        id="mr", name="MR", version="1.0", category="test",
        runtime={"type": "mixed"},
        metadata={"primary_tool": "Seurat"},
    )
    assert executor._resolve_execution_type(mixed_r) == "r"

    mixed_py = SkillDefinition(
        id="mp", name="MP", version="1.0", category="test",
        runtime={"type": "mixed"},
        metadata={"primary_tool": "scanpy"},
    )
    assert executor._resolve_execution_type(mixed_py) == "python"
