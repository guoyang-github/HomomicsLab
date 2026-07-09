"""Tool selection for the Open Agent Planner.

Constrains LLM tool choices to the registered ToolRegistry white list and
prepares OpenAI-compatible function schemas.
"""

from typing import Any, Dict, List, Optional

from homomics_lab.agent.open_agent.models import CapabilityCandidate, ToolCallIntent
from homomics_lab.skills.capability_index import CapabilityType
from homomics_lab.tools.models import ToolDefinition
from homomics_lab.tools.registry import ToolRegistry, get_default_tool_registry


class ToolSelector:
    """Select and validate tools from the registry for the open agent."""

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tool_registry = tool_registry or get_default_tool_registry()

    def select_from_capabilities(
        self,
        capabilities: List[CapabilityCandidate],
    ) -> List[ToolDefinition]:
        """Return registered tools referenced by ``capabilities``."""
        tools: List[ToolDefinition] = []
        seen: set = set()
        for c in capabilities:
            if c.type != CapabilityType.TOOL:
                continue
            tool = self.tool_registry.get(c.id)
            if tool is None:
                # Payload may contain the tool definition even if registry miss.
                tool = c.payload.get("tool")
            if tool is None or tool.name in seen:
                continue
            seen.add(tool.name)
            tools.append(tool)
        return tools

    def to_openai_tools(
        self,
        tools: List[ToolDefinition],
    ) -> List[Dict[str, Any]]:
        """Export tools as OpenAI function-calling schema."""
        result: List[Dict[str, Any]] = []
        for tool in tools:
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
            )
        return result

    def validate_intents(
        self,
        intents: List[ToolCallIntent],
    ) -> List[ToolCallIntent]:
        """Drop intents that reference unknown tools.

        Returns only intents whose tool is registered.
        """
        validated: List[ToolCallIntent] = []
        for intent in intents:
            if self.tool_registry.get(intent.tool_name) is not None:
                validated.append(intent)
        return validated
