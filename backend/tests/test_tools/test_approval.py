"""Tests for high-risk tool approval flow."""

import json

import pytest

from homomics_lab.llm_client import FakeLLMClient
from homomics_lab.skills.agent_executor import AgentSkillExecutor
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.tools.approval import ToolApprovalRequired
from homomics_lab.tools.builtin import register_all_builtin_tools
from homomics_lab.tools.registry import ToolRegistry


@pytest.fixture
def tool_registry(tmp_path):
    registry = ToolRegistry()
    register_all_builtin_tools(registry)
    return registry


@pytest.mark.asyncio
async def test_high_risk_tool_requires_approval_in_interactive_mode(tool_registry, monkeypatch, tmp_path):
    """When interactive_mode is enabled, shell_exec requires approval."""
    from homomics_lab import config

    monkeypatch.setattr(config.settings, "interactive_mode", True)
    monkeypatch.setattr(config.settings, "data_dir", tmp_path)
    monkeypatch.setattr(config.settings, "force_sandbox", False)
    monkeypatch.setattr(config.settings, "skill_sandbox_backend", "local")

    class SteppedFakeLLM(FakeLLMClient):
        def __init__(self):
            super().__init__(response="")

        async def chat_completion(self, messages, **kwargs):
            return json.dumps(
                {
                    "thought": "run command",
                    "action": "tool",
                    "tool": "shell_exec",
                    "arguments": {"command": "echo hello"},
                }
            )

    executor = AgentSkillExecutor(tool_registry=tool_registry, llm_client=SteppedFakeLLM())
    skill = SkillDefinition(
        id="test_skill",
        name="Test Skill",
        version="1.0",
        category="test",
        runtime={"type": "agent"},
        metadata={"instructions": "Run a shell command."},
        input_schema=SkillInputSchema(),
    )

    with pytest.raises(ToolApprovalRequired) as exc_info:
        await executor.execute(skill, {})

    assert exc_info.value.tool_name == "shell_exec"
    assert exc_info.value.risk_level == "high"
    assert exc_info.value.call_id is not None


@pytest.mark.asyncio
async def test_low_risk_tool_does_not_require_approval(tool_registry, monkeypatch, tmp_path):
    """Low-risk tools execute normally even in interactive mode."""
    from homomics_lab import config

    monkeypatch.setattr(config.settings, "interactive_mode", True)
    monkeypatch.setattr(config.settings, "data_dir", tmp_path)

    class SteppedFakeLLM(FakeLLMClient):
        def __init__(self):
            super().__init__(response="")

        async def chat_completion(self, messages, **kwargs):
            return json.dumps(
                {
                    "thought": "search",
                    "action": "tool",
                    "tool": "web_search",
                    "arguments": {"query": "hello"},
                }
            )

    executor = AgentSkillExecutor(tool_registry=tool_registry, llm_client=SteppedFakeLLM())
    skill = SkillDefinition(
        id="test_skill",
        name="Test Skill",
        version="1.0",
        category="test",
        runtime={"type": "agent"},
        metadata={"instructions": "Search the web."},
        input_schema=SkillInputSchema(),
    )

    result = await executor.execute(skill, {})
    assert result["success"] is False  # web_search may fail without DDGS
    assert result.get("mode") != "awaiting_tool_approval"


@pytest.mark.asyncio
async def test_non_interactive_mode_allows_high_risk_tools(tool_registry, monkeypatch, tmp_path):
    """When interactive_mode is disabled, high-risk tools execute without approval."""
    from homomics_lab import config

    monkeypatch.setattr(config.settings, "interactive_mode", False)
    monkeypatch.setattr(config.settings, "data_dir", tmp_path)
    monkeypatch.setattr(config.settings, "force_sandbox", False)
    monkeypatch.setattr(config.settings, "skill_sandbox_backend", "local")

    class SteppedFakeLLM(FakeLLMClient):
        def __init__(self):
            super().__init__(response="")
            # The agent loop enforces an inspection-first Phase 1, so the first
            # turn must be a non-writing tool call before file_write is allowed.
            self._responses = [
                json.dumps(
                    {
                        "thought": "inspect workspace",
                        "action": "tool",
                        "tool": "file_list",
                        "arguments": {"directory": str(tmp_path)},
                    }
                ),
                json.dumps(
                    {
                        "thought": "write file",
                        "action": "tool",
                        "tool": "file_write",
                        "arguments": {"path": str(tmp_path / "test.txt"), "content": "hello"},
                    }
                ),
                json.dumps(
                    {
                        "thought": "done",
                        "action": "final",
                        "final_output": {"ok": True},
                    }
                ),
            ]
            self._idx = 0

        async def chat_completion(self, messages, **kwargs):
            resp = self._responses[self._idx]
            self._idx += 1
            return resp

    executor = AgentSkillExecutor(tool_registry=tool_registry, llm_client=SteppedFakeLLM())
    skill = SkillDefinition(
        id="test_skill",
        name="Test Skill",
        version="1.0",
        category="test",
        runtime={"type": "agent"},
        metadata={"instructions": "Write a file."},
        input_schema=SkillInputSchema(),
    )

    result = await executor.execute(skill, {})
    assert result["success"] is True
    write_outputs = [
        o for o in result["tool_outputs"] if o.get("tool") == "file_write"
    ]
    assert write_outputs, "file_write should have executed without approval"
    assert write_outputs[0]["success"] is True
