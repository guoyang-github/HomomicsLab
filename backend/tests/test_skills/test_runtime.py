import pytest
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.registry import SkillRegistry


@pytest.fixture
def executor(tmp_path):
    registry = SkillRegistry()
    return SkillRuntimeExecutor(registry=registry, working_dir=tmp_path)


@pytest.mark.asyncio
async def test_execute_builtin_skill(executor, tmp_path):
    """Test executing a skill from a scripts directory (unified path)."""
    scripts_dir = tmp_path / "scripts" / "python"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "core_analysis.py").write_text("""
result = {"sum": a + b}
""")

    skill = SkillDefinition(
        id="add_numbers",
        name="Add Numbers",
        version="1.0.0",
        category="math",
        runtime={"type": "python", "python_version": "3.10"},
        metadata={
            "scripts_dir": str(scripts_dir),
            "source_dir": str(tmp_path),
            "disclosure_level": "activated",
        },
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
    (scripts_dir / "core_analysis.py").write_text("""
result = {"product": x * y}
""")

    skill = SkillDefinition(
        id="multiply",
        name="Multiply",
        version="1.0.0",
        category="math",
        runtime={"type": "python", "python_version": "3.10"},
        metadata={
            "scripts_dir": str(scripts_dir),
            "source_dir": str(tmp_path),
            "disclosure_level": "activated",
        },
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

    result = await executor.execute("multiply", {"x": 3, "y": 4})
    assert result["product"] == 12


@pytest.mark.asyncio
async def test_execute_file_based_r_skill(executor, tmp_path):
    """Test executing a file-based R skill."""
    scripts_dir = tmp_path / "scripts" / "r"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "core_analysis.R").write_text("""
result <- list(sum = a + b)
""")

    skill = SkillDefinition(
        id="add_r",
        name="Add R",
        version="1.0.0",
        category="math",
        runtime={"type": "r"},
        metadata={
            "scripts_dir": str(scripts_dir),
            "source_dir": str(tmp_path),
            "disclosure_level": "activated",
        },
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

    result = await executor.execute("add_r", {"a": 5, "b": 7})
    assert result["sum"] == 12


@pytest.mark.asyncio
async def test_execute_mixed_skill_chooses_python(executor, tmp_path):
    """Test that mixed skill with Python primary_tool uses Python."""
    scripts_dir = tmp_path / "scripts" / "python"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "core_analysis.py").write_text("""
result = {"lang": "python"}
""")

    skill = SkillDefinition(
        id="mixed_python",
        name="Mixed Python",
        version="1.0.0",
        category="test",
        runtime={"type": "mixed"},
        metadata={
            "primary_tool": "scanpy",
            "scripts_dir": str(scripts_dir),
            "source_dir": str(tmp_path),
            "disclosure_level": "activated",
        },
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
    (scripts_dir / "core_analysis.R").write_text("""
result <- list(lang = "r")
""")

    skill = SkillDefinition(
        id="mixed_r",
        name="Mixed R",
        version="1.0.0",
        category="test",
        runtime={"type": "mixed"},
        metadata={
            "primary_tool": "Seurat",
            "scripts_dir": str(scripts_dir),
            "source_dir": str(tmp_path),
            "disclosure_level": "activated",
        },
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
    (scripts_dir / "core_analysis.py").write_text("""
result = {"greeting": "hello"}
""")

    skill = SkillDefinition(
        id="hello",
        name="Hello",
        version="1.0.0",
        category="test",
        runtime={"type": "python"},
        metadata={
            "scripts_dir": str(scripts_dir),
            "source_dir": str(tmp_path),
            "disclosure_level": "activated",
        },
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


@pytest.mark.asyncio
async def test_execute_declarative_workflow_skill_returns_knowledge(executor):
    """A workflow skill without scripts should not fail; it returns instructions."""
    skill = SkillDefinition(
        id="utils-workflow-management-nextflow",
        name="Nextflow Workflow Architect",
        version="1.0",
        category="workflows",
        runtime={"type": "workflow"},
        metadata={
            "instructions": "Generate a production-grade Nextflow DSL2 pipeline.",
            "allowed_tools": ["file_read", "file_write", "shell_exec"],
        },
        input_schema=SkillInputSchema(),
    )
    executor.registry.register(skill)

    result = await executor.execute("utils-workflow-management-nextflow", {"task": "build QC pipeline"})
    assert result["success"] is True
    assert result["mode"] == "knowledge"
    assert "instructions" in result


@pytest.mark.asyncio
async def test_execute_python_skill_without_scripts_returns_knowledge(executor):
    """A python skill missing scripts_dir is treated as knowledge/agentic instead of crashing."""
    skill = SkillDefinition(
        id="declarative_python",
        name="Declarative Python",
        version="1.0",
        category="test",
        runtime={"type": "python"},
        metadata={},
        input_schema=SkillInputSchema(),
    )
    executor.registry.register(skill)

    result = await executor.execute("declarative_python", {})
    assert result["success"] is True
    assert result["mode"] == "knowledge"


@pytest.mark.asyncio
async def test_script_skill_concatenates_all_scripts(tmp_path):
    """All .py files in the scripts directory are concatenated and executed."""
    skill_dir = tmp_path / "concat-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        """\
---
name: concat-skill
description: Concatenate all scripts.
tool_type: python
---

# Instructions
Run the concatenated scripts.
""",
        encoding="utf-8",
    )
    scripts = skill_dir / "scripts" / "python"
    scripts.mkdir(parents=True)
    (scripts / "core_analysis.py").write_text("result = {'source': 'core_analysis.py'}\n")
    (scripts / "helper.py").write_text("result = {'source': 'helper.py'}\n")

    registry = SkillRegistry()
    loader = SkillLoader(registry=registry)
    skill = loader.load_discovery(skill_dir)
    skill.metadata["trusted"] = True
    registry.register(skill)

    executor = SkillRuntimeExecutor(registry=registry, working_dir=tmp_path)
    result = await executor.execute("concat-skill", {})
    # helper.py runs after core_analysis.py alphabetically, so its assignment wins.
    assert result["source"] == "helper.py"
