import shutil
from pathlib import Path

import pytest

from homomics_lab.config import settings
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.skill_store import SkillStore

SKILL_ID = "bio-statistics-visualization"
SKILL_DIR = Path(__file__).parents[2] / "data" / "skill_store" / "imported" / "local" / "bio-statistics-visualization"
SKILL_DIR = SKILL_DIR.resolve()


@pytest.fixture
def executor(tmp_path):
    """Provide a SkillRuntimeExecutor with the viz skill installed and trusted."""
    settings.data_dir = tmp_path
    settings.auto_install_dependencies = True
    settings.skill_sandbox_backend = "local"

    env_dir = tmp_path / "environments" / "python" / SKILL_ID
    if env_dir.exists():
        shutil.rmtree(env_dir)

    registry = SkillRegistry()
    executor = SkillRuntimeExecutor(registry=registry, working_dir=tmp_path)
    skill_store = SkillStore(registry=registry, store_dir=tmp_path / "skill_store")

    source = str(SKILL_DIR.resolve())
    skill = skill_store.import_skill(source=source, namespace="local", enable=True)
    skill_store.trust_skill(skill.id, namespace="local", trusted=True)
    executor.register_skill(skill)

    return executor


@pytest.fixture
def sample_workspace(executor, tmp_path):
    """Create a sample CSV in the workspace data directory."""
    project_id = "test_project"
    data_dir = tmp_path / "workspaces" / project_id / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "data.csv").write_text(
        "Control,Drug_A,Drug_B\n"
        "10.2,13.5,11.8\n"
        "11.5,14.2,12.3\n"
        "9.8,12.8,11.1\n"
        "10.5,13.9,12.0\n"
        "11.0,14.5,11.5\n"
    )
    return project_id


@pytest.mark.asyncio
async def test_skill_import_data(executor, sample_workspace):
    result = await executor.execute(
        SKILL_ID,
        {
            "action": "import_data",
            "project_id": sample_workspace,
            "session_id": "session_1",
            "params": {"source": "data.csv", "table_type": "column"},
            "source_dir": str(SKILL_DIR.resolve()),
            "workspace_base": str(settings.data_dir),
        },
    )
    assert result["success"] is True
    assert result["outputs"]["table_type"] == "column"
    assert len(result["outputs"]["group_columns"]) == 3


@pytest.mark.asyncio
async def test_skill_stat_test(executor, sample_workspace):
    import_result = await executor.execute(
        SKILL_ID,
        {
            "action": "import_data",
            "project_id": sample_workspace,
            "session_id": "session_1",
            "params": {"source": "data.csv", "table_type": "column"},
            "source_dir": str(SKILL_DIR.resolve()),
            "workspace_base": str(settings.data_dir),
        },
    )
    data_id = import_result["outputs"]["data_id"]

    result = await executor.execute(
        SKILL_ID,
        {
            "action": "stat_test",
            "project_id": sample_workspace,
            "session_id": "session_1",
            "params": {"data_id": data_id, "test_name": "one_way_anova"},
            "source_dir": str(SKILL_DIR.resolve()),
            "workspace_base": str(settings.data_dir),
        },
    )
    assert result["success"] is True
    assert "result_id" in result["outputs"]
    assert result["outputs"]["test_name"] == "One-way ANOVA"


@pytest.mark.asyncio
async def test_skill_render(executor, sample_workspace):
    import_result = await executor.execute(
        SKILL_ID,
        {
            "action": "import_data",
            "project_id": sample_workspace,
            "session_id": "session_1",
            "params": {"source": "data.csv", "table_type": "column"},
            "source_dir": str(SKILL_DIR.resolve()),
            "workspace_base": str(settings.data_dir),
        },
    )
    data_id = import_result["outputs"]["data_id"]

    stat_result = await executor.execute(
        SKILL_ID,
        {
            "action": "stat_test",
            "project_id": sample_workspace,
            "session_id": "session_1",
            "params": {"data_id": data_id, "test_name": "one_way_anova"},
            "source_dir": str(SKILL_DIR.resolve()),
            "workspace_base": str(settings.data_dir),
        },
    )
    result_id = stat_result["outputs"]["result_id"]

    render_result = await executor.execute(
        SKILL_ID,
        {
            "action": "render",
            "project_id": sample_workspace,
            "session_id": "session_1",
            "params": {
                "data_id": data_id,
                "result_id": result_id,
                "plot_type": "box",
                "theme": "nature",
                "formats": ["png", "svg"],
                "source_filename": "data.csv",
            },
            "source_dir": str(SKILL_DIR.resolve()),
            "workspace_base": str(settings.data_dir),
        },
    )
    assert render_result["success"] is True
    assert "figure_id" in render_result["outputs"]
    assert "png" in render_result["outputs"]["formats"]
    assert "svg" in render_result["outputs"]["formats"]


@pytest.mark.asyncio
async def test_skill_full_pipeline(executor, sample_workspace):
    result = await executor.execute(
        SKILL_ID,
        {
            "action": "full_pipeline",
            "project_id": sample_workspace,
            "session_id": "session_1",
            "params": {
                "source": "data.csv",
                "table_type": "column",
                "plot_type": "bar",
                "theme": "science",
                "formats": ["png"],
            },
            "source_dir": str(SKILL_DIR.resolve()),
            "workspace_base": str(settings.data_dir),
        },
    )
    assert result["success"] is True
    assert "figure_id" in result["outputs"]
    assert "data_id" in result["outputs"]
    assert "result_id" in result["outputs"]
