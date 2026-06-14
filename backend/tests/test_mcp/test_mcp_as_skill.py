"""Tests for MCP tools wrapped as skills."""

import pytest

from homomics_lab.mcp.integration import register_mcp_skills
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema, SkillRuntime
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills.tracker import SkillPerformanceTracker
from homomics_lab.tools.models import ToolDefinition
from homomics_lab.tools.registry import ToolRegistry


@pytest.fixture
def mcp_skill_registry():
    """A tool registry with one MCP tool and a matching skill executor."""
    tool_registry = ToolRegistry()
    tool_registry.register(
        ToolDefinition(
            name="uniprot_search",
            description="Search UniProt",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
            source="mcp",
            handler=lambda **inputs: {"count": 1, "results": [{"entry": inputs["query"]}]},
        )
    )

    skill_registry = SkillRegistry()
    tracker = SkillPerformanceTracker()
    executor = SkillRuntimeExecutor(
        registry=skill_registry,
        tracker=tracker,
        tool_registry=tool_registry,
    )
    return executor


@pytest.mark.asyncio
async def test_mcp_skill_registration(mcp_skill_registry):
    executor = mcp_skill_registry
    register_mcp_skills(executor, executor.tool_registry)

    skill = executor.registry.get("mcp_uniprot_search")
    assert skill is not None
    assert skill.runtime.type == "mcp"
    assert skill.metadata["tool_name"] == "uniprot_search"


@pytest.mark.asyncio
async def test_mcp_skill_execution(mcp_skill_registry):
    executor = mcp_skill_registry
    register_mcp_skills(executor, executor.tool_registry)

    result = await executor.execute(
        "mcp_uniprot_search",
        {"query": "p53", "limit": 3},
    )
    assert result["success"] is True
    assert result["output"]["count"] == 1


@pytest.mark.asyncio
async def test_mcp_skill_missing_tool_name():
    skill_registry = SkillRegistry()
    tool_registry = ToolRegistry()
    executor = SkillRuntimeExecutor(
        registry=skill_registry,
        tool_registry=tool_registry,
    )

    bad_skill = SkillDefinition(
        id="mcp_bad",
        name="bad",
        version="1.0",
        category="mcp",
        runtime=SkillRuntime(type="mcp"),
        input_schema=SkillInputSchema(),
        metadata={},
    )
    skill_registry.register(bad_skill)

    with pytest.raises(RuntimeError, match="missing metadata.tool_name"):
        await executor.execute("mcp_bad", {})
