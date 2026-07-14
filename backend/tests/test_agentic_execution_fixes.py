"""Tests for the agentic-skill execution fixes:

* artifact harvesting after an LLM tool loop (files must come back, not vanish);
* input binding from the workspace so the agent is not handed empty inputs;
* sandbox factory falling back when bubblewrap is present but non-functional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from homomics_lab.skills.agent_executor import (
    AgentSkillExecutor,
    _compact_tool_output,
    harvest_agent_artifacts,
)
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.skills import sandbox as sandbox_mod


# ---------------------------------------------------------------------------
# Artifact harvesting
# ---------------------------------------------------------------------------


def test_harvest_uses_paths_from_tool_outputs(tmp_path: Path) -> None:
    produced = tmp_path / "outputs" / "labels.csv"
    produced.parent.mkdir(parents=True)
    produced.write_text("cell,label\n1,T\n", encoding="utf-8")

    tool_outputs: List[Dict[str, Any]] = [
        {"tool": "file_write", "arguments": {"path": str(produced)}, "success": True}
    ]
    envelopes, output_files = harvest_agent_artifacts(tmp_path, tool_outputs)

    assert str(produced) in output_files
    assert any(e["name"] == "labels.csv" and e["kind"] == "table" for e in envelopes)


def test_harvest_fallback_scan_skips_input_dirs(tmp_path: Path) -> None:
    # inputs that must NOT be reported as produced artifacts
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "uploaded.h5ad").write_bytes(b"hd5")
    (tmp_path / ".metadata").mkdir()
    (tmp_path / ".metadata" / "registry.json").write_text("{}", encoding="utf-8")
    # real outputs
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs" / "result.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "summary.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    envelopes, output_files = harvest_agent_artifacts(tmp_path, [])

    names = {e["name"] for e in envelopes}
    assert "result.csv" in names
    assert "summary.png" in names
    assert "uploaded.h5ad" not in names
    assert "registry.json" not in names
    assert len(output_files) == 2


def test_harvest_ignores_paths_from_read_tools(tmp_path: Path) -> None:
    # The agent only READ these (inputs) — they must not become output artifacts.
    inp = tmp_path / "data" / "PA12_sc.h5ad"
    inp.parent.mkdir(parents=True)
    inp.write_bytes(b"hd5")
    tool_outputs = [
        {"tool": "file_read", "arguments": {"path": str(inp)}, "success": True},
    ]
    envelopes, output_files = harvest_agent_artifacts(tmp_path, tool_outputs)
    assert str(inp) not in output_files
    assert all(e["name"] != "PA12_sc.h5ad" for e in envelopes)


def test_harvest_excludes_shell_stdout_paths_under_input_dirs(tmp_path: Path) -> None:
    # A shell command that merely PRINTS input paths (e.g. `find`) must not
    # promote those input files into output artifacts.
    inp = tmp_path / "data" / "PA12_sc.h5ad"
    inp.parent.mkdir(parents=True)
    inp.write_bytes(b"hd5")
    tool_outputs = [
        {
            "tool": "shell_exec",
            "arguments": {"command": "find . -name '*.h5ad'"},
            "output": str(inp),
            "success": True,
        }
    ]
    envelopes, output_files = harvest_agent_artifacts(tmp_path, tool_outputs)
    assert str(inp) not in output_files
    assert all(e["name"] != "PA12_sc.h5ad" for e in envelopes)


def test_harvest_returns_empty_when_nothing_produced(tmp_path: Path) -> None:
    envelopes, output_files = harvest_agent_artifacts(tmp_path, [])
    assert envelopes == [] and output_files == []


def test_parse_action_extracts_first_decodable_json_object() -> None:
    payload = '{"action":"final","final_output":{"ok":true}}'
    wrapped = f'reasoning trace\n{payload}\n{{"action":"tool","tool":"shell_exec"}}'
    assert AgentSkillExecutor._parse_action(wrapped) == {
        "action": "final",
        "final_output": {"ok": True},
    }


def test_parse_action_normalizes_shell_command_shorthand() -> None:
    action = AgentSkillExecutor._parse_action('{"command":"pwd","timeout":30}')
    assert action == {
        "command": "pwd",
        "timeout": 30,
        "action": "tool",
        "tool": "shell_exec",
        "arguments": {"command": "pwd", "timeout": 30},
    }


def test_parse_action_infers_tool_when_tool_field_is_null() -> None:
    action = AgentSkillExecutor._parse_action(
        '{"action":"tool","tool":null,"arguments":{"command":"pwd"}}'
    )
    assert action == {
        "action": "tool",
        "tool": "shell_exec",
        "arguments": {"command": "pwd"},
    }


def test_parse_action_tolerates_raw_control_chars_in_json_strings() -> None:
    action = AgentSkillExecutor._parse_action(
        '{"action":"tool","tool":"shell_exec","arguments":{"command":"echo a\nb"}}'
    )
    assert action == {
        "action": "tool",
        "tool": "shell_exec",
        "arguments": {"command": "echo a\nb"},
    }


def test_compact_tool_output_bounds_prompt_size() -> None:
    compact = _compact_tool_output({"tool": "shell_exec", "output": "x" * 9000})
    assert compact["tool"] == "shell_exec"
    assert len(compact["output"]) < 9000
    assert "truncated" in compact["output"]


# ---------------------------------------------------------------------------
# Input binding for declarative skills
# ---------------------------------------------------------------------------


class _FakeWorkspace:
    def __init__(self, root: Path) -> None:
        self.workspace_dir = root


def test_augment_agent_inputs_surfaces_workspace_files(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "PA12_small.h5ad").write_bytes(b"hd5")
    (data / ".hidden").write_text("x", encoding="utf-8")

    validated: Dict[str, Any] = {}
    SkillRuntimeExecutor._augment_agent_inputs(
        validated, _FakeWorkspace(tmp_path), raw_inputs={}
    )

    assert validated["workspace_dir"] == str(tmp_path)
    assert validated["data_dir"] == str(data)
    assert any(f.endswith("PA12_small.h5ad") for f in validated["input_files"])
    assert all(".hidden" not in f for f in validated["input_files"])


def test_augment_agent_inputs_promotes_path_in_raw_inputs(tmp_path: Path) -> None:
    f = tmp_path / "explicit.h5ad"
    f.write_bytes(b"hd5")
    validated: Dict[str, Any] = {}
    SkillRuntimeExecutor._augment_agent_inputs(
        validated, _FakeWorkspace(tmp_path), raw_inputs={"some_arg": str(f)}
    )
    assert str(f) in validated.get("input_files", [])


def test_augment_agent_inputs_does_not_override(tmp_path: Path) -> None:
    validated: Dict[str, Any] = {"input_files": ["/keep/me.h5ad"]}
    SkillRuntimeExecutor._augment_agent_inputs(
        validated, _FakeWorkspace(tmp_path), raw_inputs={}
    )
    assert validated["input_files"] == ["/keep/me.h5ad"]


# ---------------------------------------------------------------------------
# Sandbox factory fallback
# ---------------------------------------------------------------------------


def _disable_venv_preference(monkeypatch: pytest.MonkeyPatch) -> None:
    # Tests run under `uv run`, i.e. inside a venv, where Sandbox.create("auto")
    # deliberately prefers LocalSandbox. Pin the selection to the
    # container → bubblewrap → local ordering these tests exercise.
    monkeypatch.setattr(
        sandbox_mod.Sandbox, "_running_in_venv", staticmethod(lambda: False)
    )


def test_auto_sandbox_falls_back_when_bubblewrap_unhealthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _disable_venv_preference(monkeypatch)
    monkeypatch.setattr(
        sandbox_mod.ContainerSandbox, "is_available", classmethod(lambda c: False)
    )
    monkeypatch.setattr(
        sandbox_mod.BubblewrapSandbox, "is_available", classmethod(lambda c: True)
    )
    monkeypatch.setattr(
        sandbox_mod.BubblewrapSandbox, "probe", lambda self: False
    )

    sb = sandbox_mod.Sandbox.create("auto", tmp_path)
    assert isinstance(sb, sandbox_mod.LocalSandbox)


def test_auto_sandbox_keeps_healthy_bubblewrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _disable_venv_preference(monkeypatch)
    monkeypatch.setattr(
        sandbox_mod.ContainerSandbox, "is_available", classmethod(lambda c: False)
    )
    monkeypatch.setattr(
        sandbox_mod.BubblewrapSandbox, "is_available", classmethod(lambda c: True)
    )
    monkeypatch.setattr(sandbox_mod.BubblewrapSandbox, "probe", lambda self: True)

    sb = sandbox_mod.Sandbox.create("auto", tmp_path)
    assert isinstance(sb, sandbox_mod.BubblewrapSandbox)
