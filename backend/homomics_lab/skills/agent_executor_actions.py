"""Action parsing for :class:`AgentSkillExecutor`.

Extracted from ``skills/agent_executor.py`` as a pure code move (no logic
changes): tolerant parsing/normalization of the LLM's JSON actions. Pure
functions — no executor state required.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


def parse_action(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse an agent action from LLM output, tolerating markdown fences.

    Tries a direct JSON parse first, then strips markdown fences, then
    extracts the first JSON object.
    """
    text = response_text.strip()
    # Strip markdown code fences if present.
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text, strict=False)
    except json.JSONDecodeError:
        parsed = extract_json(text)
    return normalize_action(parsed)


def normalize_action(parsed: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Accept common LLM shorthand shapes and coerce them to actions."""
    if not isinstance(parsed, dict):
        return None

    def inferred_tool(arguments: Dict[str, Any]) -> Optional[str]:
        if "command" in parsed or (
            isinstance(arguments, dict) and "command" in arguments
        ):
            return "shell_exec"
        if isinstance(arguments, dict):
            if "content" in arguments and "path" in arguments:
                return "file_write"
            if "old_string" in arguments and "new_string" in arguments:
                return "file_edit"
            if "directory" in arguments:
                return "file_list"
            if "path" in arguments:
                return "file_read"
        return None

    if parsed.get("action") == "final":
        return parsed
    if parsed.get("action") == "tool":
        normalized = dict(parsed)
        normalized.setdefault("arguments", {})
        if not normalized.get("tool"):
            tool = inferred_tool(normalized.get("arguments") or {})
            if tool is None:
                return normalized
            normalized["tool"] = tool
            if tool == "shell_exec" and "command" in normalized:
                normalized["arguments"] = {
                    "command": normalized["command"],
                    **({"timeout": normalized["timeout"]} if "timeout" in normalized else {}),
                }
        return normalized
    if "command" in parsed and "tool" not in parsed:
        normalized = dict(parsed)
        normalized["action"] = "tool"
        normalized["tool"] = "shell_exec"
        normalized.setdefault(
            "arguments",
            {
                "command": parsed["command"],
                **({"timeout": parsed["timeout"]} if "timeout" in parsed else {}),
            },
        )
        return normalized
    if "tool" in parsed:
        normalized = dict(parsed)
        normalized["action"] = "tool"
        normalized.setdefault("arguments", {})
        return normalized
    if "final_output" in parsed:
        normalized = dict(parsed)
        normalized["action"] = "final"
        return normalized
    # Accept bare file-write/file-edit shapes that some models emit.
    if "path" in parsed and "content" in parsed and "tool" not in parsed:
        return {
            "action": "tool",
            "tool": "file_write",
            "arguments": {
                "path": parsed["path"],
                "content": parsed["content"],
            },
        }
    if "path" in parsed and "old_string" in parsed and "new_string" in parsed and "tool" not in parsed:
        return {
            "action": "tool",
            "tool": "file_edit",
            "arguments": {
                "path": parsed["path"],
                "old_string": parsed["old_string"],
                "new_string": parsed["new_string"],
            },
        }
    return None


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Try to extract the first decodable JSON object from a string."""
    decoder = json.JSONDecoder(strict=False)
    start = text.find("{")
    while start != -1:
        try:
            obj, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(obj, dict):
            return obj
        start = text.find("{", start + 1)
    return None
