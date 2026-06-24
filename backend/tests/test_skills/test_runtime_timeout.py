from unittest.mock import AsyncMock

import pytest

from homomics_lab.config import settings
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.registry import SkillRegistry


@pytest.fixture
def executor(tmp_path):
    return SkillRuntimeExecutor(registry=SkillRegistry(), working_dir=tmp_path)


@pytest.fixture
def script_skill(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "run.py").write_text("result = {'ok': True}\n")
    return SkillDefinition(
        id="timeout_test",
        name="Timeout Test",
        version="1.0.0",
        category="test",
        runtime={
            "type": "python",
            "python_version": "3.10",
            "resources": {"time": "30m"},
        },
        metadata={
            "scripts_dir": str(scripts_dir),
            "source_dir": str(tmp_path),
            "entrypoint": "scripts/run.py",
            "disclosure_level": "activated",
        },
        input_schema=SkillInputSchema(),
    )


def test_parse_timeout_minutes(executor):
    assert executor._parse_timeout("30m") == 30 * 60


def test_parse_timeout_hours(executor):
    assert executor._parse_timeout("1h") == 3600


def test_parse_timeout_seconds(executor):
    assert executor._parse_timeout("100s") == 100


def test_parse_timeout_empty_returns_default(executor):
    assert executor._parse_timeout("") == settings.default_job_timeout_seconds
    assert executor._parse_timeout(None) == settings.default_job_timeout_seconds
    assert executor._parse_timeout("   ") == settings.default_job_timeout_seconds


def test_parse_timeout_clamped_to_max(executor):
    over_max = settings.max_skill_timeout_seconds + 1000
    assert executor._parse_timeout(f"{int(over_max)}s") == settings.max_skill_timeout_seconds
    assert executor._parse_timeout("25h") == settings.max_skill_timeout_seconds


def test_parse_timeout_minimum_one_second(executor):
    assert executor._parse_timeout("0") == 1.0
    assert executor._parse_timeout("0.5s") == 1.0
    assert executor._parse_timeout("-10s") == 1.0


@pytest.mark.asyncio
async def test_per_task_timeout_override(executor, script_skill, tmp_path):
    """A task-supplied timeout overrides the skill's default runtime time."""
    scheduler_mock = AsyncMock()
    scheduler_mock.execute = AsyncMock(return_value={"success": True})
    executor._scheduler = scheduler_mock

    await executor._execute_from_dir(
        script_skill,
        tmp_path / "scripts",
        "python",
        {"timeout_seconds": "15m"},
    )

    call_kwargs = scheduler_mock.execute.call_args.kwargs
    assert call_kwargs["timeout_seconds"] == 15 * 60


@pytest.mark.asyncio
async def test_per_task_timeout_override_clamped(executor, script_skill, tmp_path):
    """Per-task timeouts above the configured max are clamped."""
    scheduler_mock = AsyncMock()
    scheduler_mock.execute = AsyncMock(return_value={"success": True})
    executor._scheduler = scheduler_mock

    await executor._execute_from_dir(
        script_skill,
        tmp_path / "scripts",
        "python",
        {"_timeout_seconds": f"{int(settings.max_skill_timeout_seconds + 3600)}s"},
    )

    call_kwargs = scheduler_mock.execute.call_args.kwargs
    assert call_kwargs["timeout_seconds"] == settings.max_skill_timeout_seconds
