"""Tests for AgentSkillExecutor declarative skill execution."""

import json

import pytest

from homomics_lab.llm_client import FakeLLMClient
from homomics_lab.skills.agent_executor import AgentSkillExecutor
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema
from homomics_lab.tools.registry import ToolRegistry


@pytest.fixture
def tool_registry(tmp_path):
    registry = ToolRegistry()

    def file_write(path: str, content: str):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": str(target), "bytes_written": len(content)}

    registry.register_builtin(
        name="file_write",
        description="Write a file",
        handler=file_write,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    )

    def file_edit(path: str, old_string: str, new_string: str):
        target = tmp_path / path
        content = target.read_text(encoding="utf-8")
        content = content.replace(old_string, new_string, 1)
        target.write_text(content, encoding="utf-8")
        return {"path": str(target), "replaced": True}

    registry.register_builtin(
        name="file_edit",
        description="Edit a file",
        handler=file_edit,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
            },
            "required": ["path", "old_string", "new_string"],
        },
    )
    return registry


@pytest.mark.asyncio
async def test_agent_executor_knowledge_fallback_without_llm(tool_registry):
    executor = AgentSkillExecutor(tool_registry=tool_registry, llm_client=None)
    skill = SkillDefinition(
        id="nf_architect",
        name="Nextflow Architect",
        version="1.0",
        category="workflows",
        runtime={"type": "workflow"},
        metadata={
            "instructions": "Build a Nextflow pipeline.",
            "allowed_tools": ["file_write"],
        },
        input_schema=SkillInputSchema(),
    )

    result = await executor.execute(skill, {"task": "qc"})
    assert result["success"] is True
    assert result["mode"] == "knowledge"
    assert "instructions" in result


@pytest.mark.asyncio
async def test_agent_executor_runs_tool_and_returns_final(tool_registry):
    """Simulate an LLM that writes a file and then returns a final result."""
    responses = [
        json.dumps(
            {
                "thought": "write the file",
                "action": "tool",
                "tool": "file_write",
                "arguments": {"path": "main.nf", "content": "process QC {}"},
            }
        ),
        json.dumps(
            {
                "thought": "done",
                "action": "final",
                "final_output": {"nf_file": "main.nf"},
            }
        ),
    ]

    class SteppedFakeLLM(FakeLLMClient):
        def __init__(self, responses):
            super().__init__(response="")
            self._responses = responses
            self._idx = 0

        async def chat_completion(self, messages, **kwargs):
            resp = self._responses[self._idx]
            self._idx += 1
            return resp

    llm = SteppedFakeLLM(responses)
    executor = AgentSkillExecutor(tool_registry=tool_registry, llm_client=llm)
    skill = SkillDefinition(
        id="nf_architect",
        name="Nextflow Architect",
        version="1.0",
        category="workflows",
        runtime={"type": "workflow"},
        metadata={
            "instructions": "Build a Nextflow pipeline.",
            "allowed_tools": ["file_write"],
        },
        input_schema=SkillInputSchema(),
    )

    result = await executor.execute(skill, {"task": "qc"})
    assert result["success"] is True
    assert result["mode"] == "agent"
    assert result["final_output"]["nf_file"] == "main.nf"
    assert len(result["tool_outputs"]) == 1
    assert result["tool_outputs"][0]["success"] is True


@pytest.mark.asyncio
async def test_agent_executor_resolves_tool_aliases(tool_registry):
    """Community skills use names like write_file; our registry uses file_write."""
    responses = [
        json.dumps(
            {
                "thought": "use alias",
                "action": "tool",
                "tool": "write_file",
                "arguments": {"path": "alias.txt", "content": "hello"},
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

    class SteppedFakeLLM(FakeLLMClient):
        def __init__(self, responses):
            super().__init__(response="")
            self._responses = responses
            self._idx = 0

        async def chat_completion(self, messages, **kwargs):
            resp = self._responses[self._idx]
            self._idx += 1
            return resp

    skill = SkillDefinition(
        id="alias_skill",
        name="Alias Skill",
        version="1.0",
        category="test",
        runtime={"type": "cli"},
        metadata={
            "instructions": "Test aliases.",
            "allowed_tools": ["write_file"],
        },
        input_schema=SkillInputSchema(),
    )
    executor = AgentSkillExecutor(
        tool_registry=tool_registry,
        llm_client=SteppedFakeLLM(responses),
    )
    result = await executor.execute(skill, {})
    assert result["success"] is True
    assert result["tool_outputs"][0]["success"] is True
