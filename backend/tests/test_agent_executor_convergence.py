"""Convergence guardrails for the agentic skill executor.

These tests drive the LLM tool loop with fakes to prove that:

* a slow/flaky provider fails fast with a clear message instead of burning the
  whole iteration budget;
* a single non-JSON response is retried rather than fatal;
* a written-but-unrun script is executed deterministically at the end of the
  loop and its outputs are harvested;
* granular progress events are emitted so the UI is never silently stuck.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from homomics_lab.skills import agent_executor as ae
from homomics_lab.skills.agent_executor import AgentSkillExecutor


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeLLM:
    def __init__(self, responses: List[str], hang: float = 0.0) -> None:
        self._responses = list(responses)
        self._hang = hang
        self.calls = 0

    def is_configured(self) -> bool:
        return True

    async def chat_completion(self, messages, **kwargs) -> str:
        self.calls += 1
        if self._hang:
            await asyncio.sleep(self._hang)
        if self._responses:
            return self._responses.pop(0)
        # Default no-op tool to consume iterations without converging.
        return '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}'


def _tool_def(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description=f"fake {name}",
        input_schema={},
        risk_level="low",
    )


class _Result:
    def __init__(self, success=True, output=None, error_message=None) -> None:
        self.success = success
        self.output = output if output is not None else {}
        self.error_message = error_message


class _FakeToolRegistry:
    def __init__(self, working_dir: Path) -> None:
        self.working_dir = working_dir
        self.shell_commands: List[str] = []

    def list_all(self) -> List[SimpleNamespace]:
        return [_tool_def("file_write"), _tool_def("shell_exec"), _tool_def("file_list")]

    def get(self, name: str) -> Optional[SimpleNamespace]:
        return _tool_def(name) if name in {"file_write", "shell_exec", "file_list"} else None

    async def invoke_async(self, name: str, arguments: Dict[str, Any]) -> _Result:
        if name == "file_write":
            path = Path(str(arguments.get("path", "")))
            if not path.is_absolute():
                path = self.working_dir / path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(arguments.get("content", "")), encoding="utf-8")
            return _Result(output={"path": str(path)})
        if name == "shell_exec":
            cmd = str(arguments.get("command", ""))
            self.shell_commands.append(cmd)
            # Simulate the script producing its declared output file.
            out = self.working_dir / "labels.csv"
            out.write_text("cell,label\n1,T\n", encoding="utf-8")
            return _Result(output={"stdout": "ok", "path": str(out)})
        if name == "file_list":
            return _Result(output={"files": []})
        return _Result(success=False, error_message=f"unknown tool {name}")


def _skill() -> SimpleNamespace:
    return SimpleNamespace(
        id="test-skill",
        description="test",
        metadata={
            "instructions": "produce outputs",
            "allowed_tools": ["file_write", "shell_exec", "file_list"],
        },
        runtime=SimpleNamespace(type="agent"),
        output_schema=None,
        source_dir=None,
        has_scripts=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fail_fast_on_consecutive_llm_timeouts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ae, "_llm_call_timeout", lambda: 0.2)
    monkeypatch.setattr(ae, "_max_llm_failures", lambda: 2)

    llm = _FakeLLM(responses=[], hang=1.0)  # every call hangs past the 0.2s cap
    reg = _FakeToolRegistry(tmp_path)
    ex = AgentSkillExecutor(tool_registry=reg, llm_client=llm, max_iterations=10)

    result = asyncio.run(ex.execute(_skill(), inputs={}, working_dir=tmp_path))

    assert result["success"] is False
    assert "LLM 提供方连续不可用" in result["error"]
    # Stopped after the threshold (2), not after max_iterations (10).
    assert llm.calls == 2


def test_non_json_response_is_retried_then_recovers(tmp_path: Path) -> None:
    llm = _FakeLLM(
        responses=[
            "this is not json at all",
            '{"action":"final","final_output":{"ok":true}}',
        ]
    )
    reg = _FakeToolRegistry(tmp_path)
    ex = AgentSkillExecutor(tool_registry=reg, llm_client=llm, max_iterations=6)

    result = asyncio.run(ex.execute(_skill(), inputs={}, working_dir=tmp_path))

    assert result["success"] is True
    assert result["final_output"] == {"ok": True}


def test_auto_run_unrun_script_produces_partial_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ae, "_auto_run_enabled", lambda: True)
    monkeypatch.setattr(ae, "_max_llm_failures", lambda: 5)

    llm = _FakeLLM(
        responses=[
            # Write a script …
            '{"action":"tool","tool":"file_write","arguments":{"path":"run.py","content":"print(1)"}}',
            # … then never run it; burn the remaining iterations with a no-op.
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
        ]
    )
    reg = _FakeToolRegistry(tmp_path)
    ex = AgentSkillExecutor(tool_registry=reg, llm_client=llm, max_iterations=4)

    result = asyncio.run(ex.execute(_skill(), inputs={}, working_dir=tmp_path))

    assert result["success"] is True
    assert result.get("partial") is True
    assert result["artifacts"], "auto-run output should be harvested as an artifact"
    assert any("run.py" in cmd for cmd in reg.shell_commands)


def test_find_unrun_script_helper() -> None:
    outs = [
        {"tool": "file_write", "arguments": {"path": "pipeline.py"}},
        {"tool": "shell_exec", "arguments": {"command": "python pipeline.py"}},
    ]
    assert AgentSkillExecutor._find_unrun_script(outs) is None

    outs2 = [{"tool": "file_write", "arguments": {"path": "pipeline.py"}}]
    found = AgentSkillExecutor._find_unrun_script(outs2)
    assert found is not None
    assert found[0] == "pipeline.py" and found[1] == "python"


def test_progress_events_are_granular(tmp_path: Path) -> None:
    llm = _FakeLLM(
        responses=[
            '{"action":"tool","tool":"file_list","arguments":{"directory":"."}}',
            '{"action":"final","final_output":{"ok":true}}',
        ]
    )
    reg = _FakeToolRegistry(tmp_path)
    phases: List[str] = []
    ex = AgentSkillExecutor(
        tool_registry=reg,
        llm_client=llm,
        max_iterations=5,
        progress_callback=lambda state: phases.append(state.current_phase or ""),
    )

    asyncio.run(ex.execute(_skill(), inputs={}, working_dir=tmp_path))

    joined = "\n".join(phases)
    assert "正在调用模型规划下一步" in joined
    assert "调用工具" in joined
    assert "返回" in joined
