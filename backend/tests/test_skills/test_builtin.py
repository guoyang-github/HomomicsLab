import pytest
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.builtin import register_builtin_skills


@pytest.fixture
def executor(tmp_path):
    registry = SkillRegistry()
    exec = SkillRuntimeExecutor(registry=registry, working_dir=tmp_path)
    register_builtin_skills(exec)
    return exec


@pytest.mark.asyncio
async def test_data_loader_skill(executor):
    result = await executor.execute("data_loader", {"format": "10x", "path": "/fake/path"})
    assert result["format"] == "10x"
    assert "loaded" in result["status"]


@pytest.mark.asyncio
async def test_scanpy_qc_defaults(executor):
    result = await executor.execute("scanpy_qc", {"adata_path": "/fake/data.h5ad"})
    assert result["min_genes"] == 200
    assert result["min_cells"] == 3


@pytest.mark.asyncio
async def test_general_code_assistant_registered(executor):
    skill = executor.registry.get("general_code_assistant")
    assert skill is not None
    assert skill.category == "general"
    assert "data processing" in skill.description.lower()


@pytest.mark.asyncio
async def test_general_code_assistant_execution(executor):
    result = await executor.execute(
        "general_code_assistant",
        {
            "request": "filter CSV rows",
            "generated_code": "import pandas as pd\ndf = pd.read_csv('data.csv')",
        },
    )
    assert "code" in result
    assert "explanation" in result
    assert "warnings" in result
