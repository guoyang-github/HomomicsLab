"""Tests for the dual-layer prompt architecture."""

import pytest

from homomics_lab.context.prompter import Prompter
from homomics_lab.prompts import get_prompt_registry
from homomics_lab.prompts.layers import build_system_prompt, build_task_prompt


@pytest.fixture(autouse=True)
def fresh_registry():
    registry = get_prompt_registry()
    registry._templates.clear()
    registry.register("provider.base", "Provider identity.")
    registry.register("agent.qa", "Agent QA persona.")
    registry.register("agent.analysis", "Agent analysis persona.")
    registry.register("task.clustering", "Task clustering instructions.")
    yield
    registry._templates.clear()


def test_build_system_prompt_concatenates_layers():
    prompt = build_system_prompt(["provider.base", "agent.qa"], mode="qa")
    assert "Provider identity." in prompt
    assert "Agent QA persona." in prompt


def test_build_system_prompt_formats_mode_and_task():
    prompt = build_system_prompt(
        ["provider.base", "agent.{mode}", "task.{task}"],
        mode="analysis",
        task="clustering",
    )
    assert "Provider identity." in prompt
    assert "Agent analysis persona." in prompt
    assert "Task clustering instructions." in prompt


def test_build_system_prompt_ignores_missing_layers():
    prompt = build_system_prompt(["provider.base", "agent.missing"], mode="missing")
    assert "Provider identity." in prompt
    assert "missing" not in prompt.lower() or "Provider identity" in prompt


def test_build_task_prompt_includes_all_layers():
    prompt = build_task_prompt(mode="analysis", task="clustering")
    assert "Provider identity." in prompt
    assert "Agent analysis persona." in prompt
    assert "Task clustering instructions." in prompt


def test_prompter_system_prompt_backward_compatible():
    prompter = Prompter()
    prompt = prompter._system_prompt(mode="qa")
    assert "Provider identity." in prompt
    assert "Agent QA persona." in prompt


def test_prompter_build_task_prompt():
    prompter = Prompter()
    prompt = prompter.build_task_prompt(mode="analysis", task="clustering")
    assert "Provider identity." in prompt
    assert "Agent analysis persona." in prompt
    assert "Task clustering instructions." in prompt
