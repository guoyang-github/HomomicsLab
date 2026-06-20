"""Tests for AgentSkillExecutor robustness features."""


import pytest

from homomics_lab.llm_client import FakeLLMClient
from homomics_lab.skills.agent_executor import AgentSkillExecutor
from homomics_lab.skills.models import SkillDefinition, SkillOutputSchema
from homomics_lab.tools.models import ToolDefinition, ToolResult
from homomics_lab.tools.registry import ToolRegistry


def make_skill(output_schema=None):
    return SkillDefinition(
        id="test-skill",
        name="Test Skill",
        version="1.0.0",
        category="test",
        runtime={"type": "agent"},
        metadata={"instructions": "Do something useful"},
        output_schema=output_schema or SkillOutputSchema(),
    )


@pytest.mark.asyncio
async def test_parse_action_handles_markdown_fence():
    executor = AgentSkillExecutor(tool_registry=ToolRegistry())
    text = '```json\n{"action": "final", "final_output": {"x": 1}}\n```'
    action = executor._parse_action(text)
    assert action["action"] == "final"
    assert action["final_output"]["x"] == 1


@pytest.mark.asyncio
async def test_parse_action_extracts_json_from_text():
    executor = AgentSkillExecutor(tool_registry=ToolRegistry())
    text = 'Some extra text before {"action": "final", "final_output": {}} and after'
    action = executor._parse_action(text)
    assert action["action"] == "final"


@pytest.mark.asyncio
async def test_output_schema_validation_catches_missing_field():
    executor = AgentSkillExecutor(tool_registry=ToolRegistry())
    skill = make_skill(
        output_schema=SkillOutputSchema(
            properties={"result": {"type": "object"}},
            required=["result"],
        )
    )
    errors = executor._validate_output(skill, {"other": 1})
    assert any("Missing required output field: 'result'" in e for e in errors)


@pytest.mark.asyncio
async def test_output_schema_validation_catches_type_mismatch():
    executor = AgentSkillExecutor(tool_registry=ToolRegistry())
    skill = make_skill(
        output_schema=SkillOutputSchema(
            properties={"count": {"type": "integer"}},
        )
    )
    errors = executor._validate_output(skill, {"count": "many"})
    assert any("Type mismatch for field 'count'" in e for e in errors)


@pytest.mark.asyncio
async def test_tool_error_retry_limit():
    tool_registry = ToolRegistry()
    fake_tool = ToolDefinition(
        name="fail_tool",
        description="fails",
        input_schema={},
        risk_level="low",
        handler=lambda **kwargs: ToolResult(success=False, output=None, error_message="boom"),
    )
    tool_registry.register(fake_tool)

    executor = AgentSkillExecutor(
        tool_registry=tool_registry,
        llm_client=FakeLLMClient(
            response='{"action":"tool","tool":"fail_tool","arguments":{}}'
        ),
        max_iterations=5,
        max_tool_retries=2,
    )
    skill = make_skill()
    skill.metadata["allowed_tools"] = ["fail_tool"]
    result = await executor.execute(skill, {})
    assert result["success"] is False
    assert "failed 3 times" in result["error"]
