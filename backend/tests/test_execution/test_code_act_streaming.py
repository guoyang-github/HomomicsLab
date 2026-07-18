"""Tests for the CodeAct output line callback (real-time phase markers).

``execute_code`` forwards an optional ``on_output_line`` callback to the
sandbox so consumers see output lines as they arrive; the exit-code marker
file (``__code_act_exit__``) and the returned output text are unchanged.
Sandbox backends that predate the callback degrade to batch collection.
"""

import pytest

from homomics_lab.execution.code_act import (
    _supports_output_line_callback,
    execute_code,
    run_code_act,
)
from homomics_lab.skills.sandbox import LocalSandbox


@pytest.mark.asyncio
async def test_execute_code_streams_lines_and_preserves_output(tmp_path):
    lines = []
    code = (
        "print('__homomics_phase__:qc:start')\n"
        "print('computing...')\n"
        "result = {'cells': 3}\n"
    )
    result = await execute_code(
        code,
        "python",
        working_dir=tmp_path,
        on_output_line=lambda line, stream: lines.append((line, stream)),
    )
    assert result["success"] is True
    assert result["exit_code"] == 0
    assert result["result"] == {"cells": 3}
    assert "__homomics_phase__:qc:start" in result["stdout"]
    assert ("__homomics_phase__:qc:start", "stdout") in lines
    assert ("computing...", "stdout") in lines


@pytest.mark.asyncio
async def test_execute_code_failure_keeps_exit_code_with_callback(tmp_path):
    lines = []
    code = "print('before-crash')\nraise ValueError('boom')\n"
    result = await execute_code(
        code,
        "python",
        working_dir=tmp_path,
        on_output_line=lambda line, stream: lines.append((line, stream)),
    )
    # The __code_act_exit__ marker mechanism still reports the real exit code.
    assert result["success"] is False
    assert result["exit_code"] == 1
    assert "before-crash" in result["stderr"]
    assert "ValueError" in result["stderr"]
    # Lines printed before the crash were still reported live.
    assert ("before-crash", "stdout") in lines


@pytest.mark.asyncio
async def test_execute_code_without_callback_unchanged(tmp_path):
    code = "print('plain')\nresult = {'ok': True}\n"
    result = await execute_code(code, "python", working_dir=tmp_path)
    assert result["success"] is True
    assert "plain" in result["stdout"]
    assert result["result"] == {"ok": True}


class _LegacySandbox:
    """A sandbox backend that predates the ``on_output_line`` parameter."""

    def __init__(self):
        self.commands = []

    async def run_command(self, command, cwd=None, env=None, timeout_seconds=30.0):
        self.commands.append(command)
        return "__legacy_output__"


def test_supports_output_line_callback_detection(tmp_path):
    assert _supports_output_line_callback(LocalSandbox(tmp_path)) is True
    assert _supports_output_line_callback(_LegacySandbox()) is False


@pytest.mark.asyncio
async def test_execute_code_degrades_for_legacy_sandbox(tmp_path, monkeypatch):
    legacy = _LegacySandbox()
    monkeypatch.setattr(
        "homomics_lab.skills.sandbox.Sandbox.create",
        staticmethod(lambda *args, **kwargs: legacy),
    )
    callback_lines = []
    result = await execute_code(
        "print('x')\n",
        "python",
        working_dir=tmp_path,
        on_output_line=lambda line, stream: callback_lines.append(line),
    )
    # Batch degradation: execution still succeeds with the collected output.
    assert result["success"] is True
    assert result["stdout"] == "__legacy_output__"
    assert legacy.commands, "run_command was invoked without the callback kwarg"
    assert callback_lines == []


@pytest.mark.asyncio
async def test_run_code_act_forwards_line_callback(tmp_path, monkeypatch):
    captured = {}

    async def fake_execute_code(code, language, working_dir, **kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "result": {},
        }

    monkeypatch.setattr(
        "homomics_lab.execution.code_act.execute_code", fake_execute_code
    )
    callback = lambda line, stream: None  # noqa: E731
    result = await run_code_act(
        "compute something",
        working_dir=tmp_path,
        llm_client=None,
        use_cache=False,
        on_output_line=callback,
    )
    assert result["success"] is True
    assert captured.get("on_output_line") is callback
