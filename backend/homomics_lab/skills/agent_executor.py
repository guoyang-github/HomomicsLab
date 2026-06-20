"""Agent-based executor for declarative / CLI / workflow skills.

Skills that do not ship executable scripts but instead provide structured
instructions (e.g. ``utils-workflow-management-nextflow``) are executed by an
LLM agent that can call tools (file_read, file_write, shell_exec, etc.).

If no LLM is configured, the executor falls back to returning the skill
instructions as a knowledge resource so callers can still use them for
retrieval or manual execution.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.tools.approval import ToolApprovalRequired, get_default_approval_store
from homomics_lab.tools.models import ToolResult
from homomics_lab.tools.registry import ToolRegistry


# Common aliases used by community skills (e.g. utils-workflow-management-nextflow)
_TOOL_ALIASES = {
    "read_file": "file_read",
    "write_file": "file_write",
    "edit_file": "file_edit",
    "run_shell_command": "shell_exec",
    "execute_shell": "shell_exec",
}


class AgentSkillExecutor:
    """Execute declarative skills via an LLM tool loop.

    The skill's SKILL.md body is treated as the system prompt / specification.
    The LLM may call registered tools to produce files, run commands, or return
    a final result.
    """

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        llm_client: Optional[LLMClient] = None,
        max_iterations: int = 10,
        max_tool_retries: int = 2,
    ):
        self.tool_registry = tool_registry
        self.llm_client = llm_client
        self.max_iterations = max(max_iterations, 1)
        self.max_tool_retries = max(max_tool_retries, 0)

    async def execute(
        self,
        skill: SkillDefinition,
        inputs: Dict[str, Any],
        working_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Execute a declarative skill.

        Returns:
            On success: ``{"success": True, "mode": "agent|knowledge", ...}``
        """
        instructions = skill.metadata.get("instructions") or skill.description
        # No LLM configured → treat the skill as knowledge.
        if self.llm_client is None or not self.llm_client.is_configured():
            return {
                "success": True,
                "mode": "knowledge",
                "skill_id": skill.id,
                "skill_type": skill.runtime.type,
                "instructions": instructions,
                "inputs": inputs,
                "note": "No LLM configured; returning skill instructions as knowledge.",
            }

        if self.tool_registry is None:
            return {
                "success": False,
                "mode": "knowledge",
                "skill_id": skill.id,
                "error": "Agent skill requires a ToolRegistry but none was provided.",
                "instructions": instructions,
            }

        tools = self._available_tools(skill)
        if not tools:
            return {
                "success": False,
                "skill_id": skill.id,
                "error": (
                    "Skill requested tools that are not registered or all tools were disallowed."
                ),
            }

        system_prompt = self._build_system_prompt(skill, inputs, tools)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Execute skill '{skill.id}' with inputs: {json.dumps(inputs, ensure_ascii=False)}",
            },
        ]

        tool_outputs: List[Dict[str, Any]] = []
        consecutive_tool_errors = 0

        for iteration in range(self.max_iterations):
            try:
                response_text = await self.llm_client.chat_completion(
                    messages,
                    temperature=0.2,
                    max_tokens=4000,
                    response_format={"type": "json_object"},
                    intent_type="code_generation",
                )
            except Exception as exc:
                return {
                    "success": False,
                    "skill_id": skill.id,
                    "error": f"LLM call failed: {exc}",
                    "tool_outputs": tool_outputs,
                }

            action = self._parse_action(response_text)
            if action is None:
                return {
                    "success": False,
                    "skill_id": skill.id,
                    "error": f"LLM returned non-JSON response: {response_text[:500]}",
                    "tool_outputs": tool_outputs,
                }

            action_type = action.get("action")
            if action_type == "final":
                final_output = action.get("final_output", {})
                validation_errors = self._validate_output(skill, final_output)
                if validation_errors:
                    return {
                        "success": False,
                        "skill_id": skill.id,
                        "error": f"Output validation failed: {'; '.join(validation_errors)}",
                        "final_output": final_output,
                        "tool_outputs": tool_outputs,
                    }
                return {
                    "success": True,
                    "mode": "agent",
                    "skill_id": skill.id,
                    "final_output": final_output,
                    "thought": action.get("thought", ""),
                    "tool_outputs": tool_outputs,
                }

            if action_type != "tool":
                return {
                    "success": False,
                    "skill_id": skill.id,
                    "error": f"Unknown action type: {action_type}",
                    "raw_response": action,
                    "tool_outputs": tool_outputs,
                }

            tool_name = action.get("tool")
            arguments = action.get("arguments", {})
            if tool_name not in tools:
                return {
                    "success": False,
                    "skill_id": skill.id,
                    "error": f"Tool '{tool_name}' is not allowed or not registered.",
                    "tool_outputs": tool_outputs,
                }

            canonical_tool_name = _TOOL_ALIASES.get(tool_name, tool_name)
            tool_def = self.tool_registry.get(canonical_tool_name)

            # High-risk tool approval in interactive mode.
            if (
                tool_def is not None
                and tool_def.risk_level == "high"
                and settings.interactive_mode
            ):
                approval_store = get_default_approval_store()
                request = approval_store.create_request(
                    tool_name=tool_name,
                    arguments=arguments,
                    risk_level=tool_def.risk_level,
                )
                raise ToolApprovalRequired(
                    call_id=request.call_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    risk_level=tool_def.risk_level,
                )

            tool_output = await self._invoke_tool_with_logging(
                canonical_tool_name, tool_name, arguments
            )
            tool_outputs.append(tool_output)

            if tool_output.get("success") is False:
                consecutive_tool_errors += 1
                if consecutive_tool_errors > self.max_tool_retries:
                    return {
                        "success": False,
                        "skill_id": skill.id,
                        "error": (
                            f"Tool '{tool_name}' failed {consecutive_tool_errors} times in a row. "
                            "Stopping execution."
                        ),
                        "tool_outputs": tool_outputs,
                    }
            else:
                consecutive_tool_errors = 0

            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(action, ensure_ascii=False),
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": f"Tool result: {json.dumps(tool_output, ensure_ascii=False, default=str)}",
                }
            )

        return {
            "success": False,
            "skill_id": skill.id,
            "error": "Agent skill exceeded maximum iterations without producing a final result.",
            "tool_outputs": tool_outputs,
        }

    def _available_tools(self, skill: SkillDefinition) -> Dict[str, Any]:
        """Return the tool schemas available to this skill.

        Honors ``allowed-tools`` and ``disallowed-tools`` from the skill
        frontmatter. Tool specs may be space/comma-separated strings or YAML
        lists, and may include permission globs like ``Bash(git *)``.
        """
        if not self.tool_registry:
            return {}

        all_tools = {
            tool.name: tool
            for tool in self.tool_registry.list_all()
        }

        allowed = self._parse_tool_specs(skill.metadata.get("allowed_tools", []))
        disallowed = self._parse_tool_specs(skill.metadata.get("disallowed_tools", []))

        # Remove explicitly disallowed tools.
        for name in disallowed:
            canonical = _TOOL_ALIASES.get(name, name)
            all_tools.pop(canonical, None)

        if not allowed:
            return all_tools

        resolved = {}
        for name in allowed:
            canonical = _TOOL_ALIASES.get(name, name)
            if canonical in all_tools:
                resolved[name] = all_tools[canonical]
        return resolved

    @staticmethod
    def _parse_tool_specs(specs: Any) -> List[str]:
        """Normalize a tool-spec list into canonical tool names."""
        if not specs:
            return []
        if isinstance(specs, str):
            return [s.strip() for s in re.split(r"[,\s]+", specs) if s.strip()]
        if isinstance(specs, list):
            return [
                str(item).strip().split("(")[0].split()[0]
                for item in specs
                if str(item).strip()
            ]
        return []

    @staticmethod
    def _build_system_prompt(
        skill: SkillDefinition,
        inputs: Dict[str, Any],
        tools: Dict[str, Any],
    ) -> str:
        """Build the system prompt for the LLM agent."""
        instructions = skill.metadata.get("instructions") or skill.description

        tool_descriptions = []
        for name, tool in tools.items():
            schema = tool.input_schema if hasattr(tool, "input_schema") else {}
            desc = f"- {name}: {tool.description}\n    schema: {json.dumps(schema, ensure_ascii=False)}"
            tool_descriptions.append(desc)

        return f"""You are an autonomous agent executing the skill "{skill.id}".

## Skill instructions
{instructions}

## User inputs
{json.dumps(inputs, ensure_ascii=False, indent=2)}

## Available tools
{chr(10).join(tool_descriptions)}

## Output format
Respond ONLY with a JSON object containing one of the following:

1. To call a tool:
{{
  "thought": "brief reasoning",
  "action": "tool",
  "tool": "tool_name",
  "arguments": {{"arg1": "value1"}}
}}

2. To return the final result:
{{
  "thought": "brief summary",
  "action": "final",
  "final_output": {{"key": "value"}}
}}

Rules:
- Do not output markdown or explanatory text outside the JSON.
- Use relative paths when writing files when possible; the working directory is the project workspace.
- Exit with `action: "final"` as soon as the skill objective is complete.
"""

    @staticmethod
    def _parse_action(response_text: str) -> Optional[Dict[str, Any]]:
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
            return json.loads(text)
        except json.JSONDecodeError:
            return AgentSkillExecutor._extract_json(text)

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Try to extract the first JSON object from a string."""
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        return None
        return None

    async def _invoke_tool_with_logging(
        self,
        canonical_name: str,
        display_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Invoke a tool and return a structured output record."""
        import time

        start = time.time()
        try:
            result = await self.tool_registry.invoke_async(canonical_name, arguments)
            # If the tool itself returns a ToolResult (e.g. a nested handler), use it directly.
            if isinstance(result.output, ToolResult):
                inner = result.output
                output = {
                    "tool": display_name,
                    "arguments": arguments,
                    "success": inner.success,
                    "output": inner.output,
                    "error_message": inner.error_message,
                    "latency_ms": (time.time() - start) * 1000,
                }
            else:
                output = {
                    "tool": display_name,
                    "arguments": arguments,
                    "success": result.success,
                    "output": result.output,
                    "error_message": result.error_message,
                    "latency_ms": (time.time() - start) * 1000,
                }
        except Exception as exc:
            output = {
                "tool": display_name,
                "arguments": arguments,
                "success": False,
                "error_message": str(exc),
                "latency_ms": (time.time() - start) * 1000,
            }

        # Best-effort audit log
        try:
            from homomics_lab.tools.audit import log_tool_call

            log_tool_call(
                tool_name=display_name,
                arguments=arguments,
                success=output["success"],
                error_message=output.get("error_message"),
                latency_ms=output.get("latency_ms", 0.0),
            )
        except Exception:
            pass
        return output

    @staticmethod
    def _validate_output(skill: SkillDefinition, output: Dict[str, Any]) -> List[str]:
        """Validate agent final output against skill output_schema."""
        schema = skill.output_schema
        if not schema.properties and not schema.required:
            return []

        errors = []
        for field_name in schema.required:
            if field_name not in output:
                errors.append(f"Missing required output field: '{field_name}'")

        type_checks = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
        }

        for field_name, value in output.items():
            if field_name in schema.properties:
                prop = schema.properties[field_name]
                expected = prop.get("type")
                if expected and not type_checks.get(expected, lambda _: True)(value):
                    errors.append(
                        f"Type mismatch for field '{field_name}': expected {expected}, got {type(value).__name__}"
                    )
        return errors
