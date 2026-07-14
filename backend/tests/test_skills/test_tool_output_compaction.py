"""Tests for agent tool-output compaction (_compact_tool_output).

Guards the invariant that multi-megabyte tool outputs (compile logs, long
stdout) never enter the LLM context or the persisted tool_outputs list
untruncated, and that error output keeps the tail (stack trace) where the
actionable debugging signal lives.
"""

from typing import Any, Dict, List

import pytest

from homomics_lab.llm_client import FakeLLMClient
from homomics_lab.skills import agent_executor
from homomics_lab.skills.agent_executor import AgentSkillExecutor, _compact_tool_output
from homomics_lab.skills.models import SkillDefinition, SkillOutputSchema
from homomics_lab.tools.models import ToolDefinition
from homomics_lab.tools.registry import ToolRegistry


def _make_skill() -> SkillDefinition:
    return SkillDefinition(
        id="test-skill",
        name="Test Skill",
        version="1.0.0",
        category="test",
        runtime={"type": "agent"},
        metadata={"instructions": "Do something useful"},
        output_schema=SkillOutputSchema(),
    )


class _ScriptedLLM(FakeLLMClient):
    """Fake LLM that replays canned responses and records every prompt."""

    def __init__(self, responses: List[str]) -> None:
        super().__init__(response="")
        self._responses = list(responses)
        self.calls: List[List[Dict[str, str]]] = []

    async def chat_completion(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        self.calls.append(messages)
        return self._responses.pop(0)


def test_success_output_truncated_head_and_tail() -> None:
    original = "A" * 25000 + "B" * 25000  # 50k chars
    compact = _compact_tool_output({"tool": "shell_exec", "success": True, "output": original})

    out = compact["output"]
    assert len(out) <= 4000
    assert "[truncated" in out
    # head+tail strategy: both ends survive, the middle is cut
    assert out.startswith("A" * 1000)
    assert out.endswith("B" * 1000)
    assert "A" * 3000 not in out
    assert "B" * 3000 not in out


def test_error_output_preserves_tail_stack() -> None:
    stack = 'Traceback (most recent call last):\n  File "pipeline.py", line 42, in <module>\nValueError: boom'
    original = "W" * 48000 + stack  # ~50k chars, stack trace at the very end
    compact = _compact_tool_output(
        {
            "tool": "shell_exec",
            "success": False,
            "output": None,
            "error_message": original,
        }
    )

    err = compact["error_message"]
    error_budget = int(4000 * 1.5)  # error output gets the wider budget
    assert len(err) <= error_budget
    assert "[truncated" in err
    # tail-priority: the stack trace at the end is preserved verbatim
    assert err.endswith(stack)
    # the head is compressed to a small context window (budget // 4 = 1500)
    assert not err.startswith("W" * 2000)
    assert err.startswith("W" * 500)


def test_error_detection_from_nested_stderr_and_returncode() -> None:
    original = "E" * 49000 + "ValueError: boom"
    # Tool-level success stays True for shell_exec; a non-zero returncode and
    # non-empty stderr must still trigger the tail-priority error path.
    compact = _compact_tool_output(
        {
            "tool": "shell_exec",
            "success": True,
            "output": {"returncode": 1, "stdout": "", "stderr": original},
        }
    )

    stderr = compact["output"]["stderr"]
    assert len(stderr) <= int(4000 * 1.5)
    assert stderr.endswith("ValueError: boom")
    assert not stderr.startswith("E" * 2000)


def test_structured_fields_preserved() -> None:
    record = {
        "tool": "shell_exec",
        "success": True,
        "arguments": {"command": "python pipeline.py", "timeout": 600},
        "output": {
            "returncode": 0,
            "stdout": "s" * 50000,
            "stderr": "",
            "path": "/tmp/results/out.txt",
            "elapsed": 12.5,
        },
        "latency_ms": 12500.0,
    }
    compact = _compact_tool_output(record)

    out = compact["output"]
    # structured / short fields pass through untouched
    assert out["returncode"] == 0
    assert out["path"] == "/tmp/results/out.txt"
    assert out["elapsed"] == 12.5
    assert compact["arguments"] == record["arguments"]
    assert compact["latency_ms"] == 12500.0
    # only the long text field is truncated
    assert len(out["stdout"]) <= 4000
    assert "[truncated" in out["stdout"]


def test_budget_configurable_via_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_executor.settings, "agent_tool_output_max_chars", 1000)

    original = "x" * 10000
    compact = _compact_tool_output({"tool": "t", "success": True, "output": original})
    assert len(compact["output"]) <= 1000

    # error output keeps the 1.5x wider budget
    failed = _compact_tool_output({"tool": "t", "success": False, "error_message": original})
    assert len(failed["error_message"]) <= 1500
    assert len(failed["error_message"]) > 1000


@pytest.mark.asyncio
async def test_agent_loop_stores_and_prompts_compacted_output(tmp_path) -> None:
    """A tool returning a 50k output: both the persisted tool_outputs list and
    the message replayed to the LLM must hold the compacted record."""
    huge = "A" * 25000 + "B" * 25000

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="big_tool",
            description="returns a huge output",
            input_schema={},
            risk_level="low",
            handler=lambda **kwargs: huge,
        )
    )
    llm = _ScriptedLLM(
        [
            '{"action":"tool","tool":"big_tool","arguments":{}}',
            '{"action":"final","final_output":{"summary":"done"}}',
        ]
    )
    executor = AgentSkillExecutor(tool_registry=registry, llm_client=llm, max_iterations=5)
    skill = _make_skill()
    skill.metadata["allowed_tools"] = ["big_tool"]

    result = await executor.execute(skill, {}, working_dir=tmp_path)

    assert result["success"] is True
    # persisted tool_outputs are compact (the :863 append site compacts first)
    stored = result["tool_outputs"][0]["output"]
    assert len(stored) <= 4000
    assert "[truncated" in stored
    assert stored.endswith("B" * 1000)

    # the tool result message replayed to the LLM is compact too
    tool_msgs = [
        m for call in llm.calls for m in call if m["role"] == "user" and m["content"].startswith("Tool result:")
    ]
    assert tool_msgs, "expected a tool result message in the LLM prompt"
    for msg in tool_msgs:
        assert huge not in msg["content"]
        assert "[truncated" in msg["content"]
        assert len(msg["content"]) < 10000
