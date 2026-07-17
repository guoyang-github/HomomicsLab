"""Script-first fast path for :class:`AgentSkillExecutor`.

Extracted from ``skills/agent_executor.py`` as a pure code move (no logic
changes). The runner holds a back-reference to the executor for the shared
services that remain on ``AgentSkillExecutor`` (``_call_llm``,
``_publish_progress``, ``_invoke_tool_with_logging``,
``_extract_script_from_markdown``) — same pattern as
``agent/orchestrator_executors.py``.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from homomics_lab.artifacts import build_artifact
from homomics_lab.skills.agent_executor_prompts import (
    _compact_skill_doc,
    _extract_script_reference,
)

if TYPE_CHECKING:
    from homomics_lab.skills.agent_executor import AgentSkillExecutor
    from homomics_lab.skills.models import SkillDefinition


def _is_valid_python(code: str) -> bool:
    """Return True if ``code`` parses as Python without syntax errors."""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


class ScriptFirstRunner:
    """Single-shot driver-script generation + execution (fast path)."""

    def __init__(self, executor: "AgentSkillExecutor"):
        self._executor = executor

    async def execute(
        self,
        skill: "SkillDefinition",
        inputs: Dict[str, Any],
        working_dir: Optional[Path],
        tools: Dict[str, Any],
        preexisting_files: Optional[set] = None,
    ) -> Optional[Dict[str, Any]]:
        """Try to complete the skill in one shot: ask LLM for a driver script and run it.

        This is the fast path for skills that ship helper scripts. It avoids the
        slow multi-turn exploration loop that often times out on slow providers.
        If the generated script fails, the caller falls back to the normal agent
        loop with the error context.
        """
        # Imported here (not at module top) to avoid a circular import with
        # skills/agent_executor.py; resolving at call time also keeps
        # monkeypatching of the agent_executor module effective.
        from homomics_lab.skills.agent_executor import (
            _compact_tool_output,
            _truncate_text,
            harvest_agent_artifacts,
        )

        executor = self._executor
        source_dir = skill.source_dir
        scripts_python = Path(source_dir) / "scripts" / "python" if source_dir else None
        if scripts_python is None or not scripts_python.is_dir():
            return None

        runner = "python"
        import_path = str(scripts_python)
        script_reference = _extract_script_reference(source_dir, max_chars=800)

        objective = str(inputs.get("user_request", "")) if isinstance(inputs, dict) else ""
        input_file = ""
        if isinstance(inputs, dict):
            input_file = str(inputs.get("input_file", ""))
            if not input_file and isinstance(inputs.get("uploaded_files"), list) and inputs["uploaded_files"]:
                input_file = str(inputs["uploaded_files"][0].get("path", ""))

        skill_doc = ""
        raw_instructions = str(skill.metadata.get("instructions") or "")
        if raw_instructions:
            skill_doc = (
                "## Skill documentation (contractual — follow its defaults, "
                "output filenames, and report sections)\n"
                + _compact_skill_doc(raw_instructions, max_chars=4000)
                + "\n\n"
            )

        prompt = (
            f"Write a compact, complete Python driver script for skill '{skill.id}'.\n\n"
            f"## Helpers\n"
            f"```python\nimport sys, os\nsys.path.insert(0, '{import_path}')\n"
            f"from core_analysis import *\nfrom utils import *\n```\n\n"
            f"{skill_doc}"
            f"{script_reference}\n\n"
            f"## Objective\n"
            f"{objective}\n\n"
            f"## Input file\n"
            f"{input_file}\n\n"
            f"## Requirements\n"
            f"- Follow the skill documentation above exactly: default parameters, output "
            f"filenames, and report sections are contractual (downstream summaries parse them).\n"
            f"- Save outputs under {working_dir}/outputs/ with clear filenames.\n"
            f"- Keep under 70 lines, no plots.\n"
            f"- After writing all outputs, also write a JSON manifest at {working_dir}/__skill_outputs__.json "
            f"listing every output file path relative to {working_dir}.\n"
            f"Return only a ```python code block."
        )

        executor._publish_progress(
            status="RUNNING",
            phase="正在生成一次性驱动脚本",
            progress_pct=10.0,
            active_task_id=skill.id,
        )
        response_text, llm_error = await executor._call_llm(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate the driver script."},
            ],
            max_tokens=8000,
            json_mode=False,
        )
        if llm_error is not None:
            return None

        script_code = executor._extract_script_from_markdown(response_text)
        expected_outputs: List[str] = []
        if not script_code:
            return None

        # If the extracted script is not valid Python (e.g. truncated), ask the
        # LLM once more to complete/fix it before falling back to the slow loop.
        if not _is_valid_python(script_code):
            fix_prompt = (
                "The previous driver script was cut off or has a syntax error. "
                "Return the COMPLETE, fixed Python script in a single markdown code block.\n\n"
                "Continue/fix from here:\n"
                f"```python\n{script_code}\n```"
            )
            response_text, llm_error = await executor._call_llm(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": fix_prompt},
                ],
                max_tokens=3000,
                json_mode=False,
            )
            if llm_error is None:
                script_code = executor._extract_script_from_markdown(response_text)
            if not script_code or not _is_valid_python(script_code):
                return None

        if not working_dir:
            working_dir = Path.cwd()
        else:
            working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
        script_path = working_dir / f"__skill_driver_{skill.id}.py"
        script_path.write_text(script_code, encoding="utf-8")

        executor._publish_progress(
            status="RUNNING",
            phase=f"正在运行驱动脚本：{script_path.name}",
            progress_pct=50.0,
            active_task_id=skill.id,
        )
        output = await executor._invoke_tool_with_logging(
            "shell_exec",
            "shell_exec",
            {"command": f"{runner} {script_path}", "timeout": 600},
        )
        # Compact before the record is persisted in the result or handed to the
        # fallback loop (which extends its tool_outputs from this result).
        # Structured fields (returncode, paths) survive truncation.
        output = _compact_tool_output(output)

        # shell_exec reports tool-level success even when the inner command exits
        # non-zero. Treat a non-zero returncode as a script failure so we fall
        # back or retry instead of claiming success.
        tool_output = output.get("output", {}) if isinstance(output.get("output"), dict) else {}
        command_returncode = tool_output.get("returncode", 0)
        if output.get("success") and command_returncode == 0:
            # Verify expected outputs exist; harvest artifacts.
            artifacts, output_files = harvest_agent_artifacts(
                working_dir, [output], ignore_preexisting=preexisting_files
            )

            # If the driver script wrote a manifest of its outputs, honor it.
            # This avoids losing files when the workspace scan hits its limit or
            # when outputs were overwritten and look stale against preexisting files.
            manifest_path = working_dir / "__skill_outputs__.json"
            if manifest_path.is_file():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest_paths = manifest.get("output_files", []) if isinstance(manifest, dict) else manifest
                    for rel in manifest_paths:
                        if not isinstance(rel, str):
                            continue
                        p = working_dir / rel
                        # The manifest itself is an internal bookkeeping file, not a user-facing output.
                        if p == manifest_path:
                            continue
                        if p.is_file() and str(p) not in output_files:
                            output_files.append(str(p))
                            env = build_artifact(p)
                            if env is not None:
                                artifacts.append(env)
                except Exception:
                    pass

            # Also check expected_outputs explicitly.
            for rel in expected_outputs:
                p = working_dir / rel
                if p.is_file() and str(p) not in output_files:
                    output_files.append(str(p))
                    env = build_artifact(p)
                    if env is not None:
                        artifacts.append(env)
            return {
                "success": True,
                "mode": "agent",
                "skill_id": skill.id,
                "final_output": {
                    "note": "Driver script executed successfully.",
                    "expected_outputs": expected_outputs,
                    "output_files": output_files,
                },
                "artifacts": artifacts,
                "output_files": output_files,
                "tool_outputs": [output],
            }

        # Script failed: return a partial result so the caller can fall back.
        # ``output`` was already compacted above; bound the error string itself
        # too, since it propagates into the job result and the parent agent's
        # context — a raw multi-KB log must not leak through it (tail-priority:
        # the actionable traceback lines sit at the end).
        raw_error = output.get("error_message") or "unknown error"
        if not isinstance(raw_error, str):
            raw_error = str(raw_error)
        return {
            "success": False,
            "partial": False,
            "skill_id": skill.id,
            "error": f"Generated driver script failed: {_truncate_text(raw_error, 2000, is_error=True)}",
            "tool_outputs": [output],
        }
