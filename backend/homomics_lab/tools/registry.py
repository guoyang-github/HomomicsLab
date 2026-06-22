"""ToolRegistry — registry for atomic tool capabilities.

Tools are distinct from skills:
  - Tool: atomic, single-call, stateless (file_read, pubmed_search, shell_exec)
  - Skill: multi-step workflow with scripts (bio-single-cell-preprocessing, spatial_decon)

Tools can come from multiple sources:
  - builtin: shipped with HomomicsLab (file I/O, shell, web search)
  - mcp: dynamically registered from MCP servers
  - plugin: added by third-party plugins
"""

from typing import Any, Callable, Dict, List, Optional

from homomics_lab.models.common import AgentType
from homomics_lab.tools.models import ToolDefinition, ToolResult


class ToolRegistry:
    """Registry for tool definitions with role-based filtering."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    # ─────────────────────────────────────────
    # Registration
    # ─────────────────────────────────────────

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool. Overwrites if name already exists."""
        self._tools[tool.name] = tool

    def register_builtin(
        self,
        name: str,
        description: str,
        handler: Callable,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        risk_level: str = "low",
    ) -> ToolDefinition:
        """Convenience method to register a builtin tool."""
        tool = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema or {"type": "object"},
            output_schema=output_schema or {},
            handler=handler,
            source="builtin",
            risk_level=risk_level,
            metadata=metadata or {},
        )
        self.register(tool)
        return tool

    def register_from_mcp(self, mcp_tools: List[Dict[str, Any]]) -> None:
        """Register tools from an MCP server listing.

        Args:
            mcp_tools: List of tool dicts from MCP list_tools call.
                       Each dict should have: name, description, inputSchema
        """
        for mt in mcp_tools:
            tool = ToolDefinition(
                name=mt["name"],
                description=mt.get("description", ""),
                input_schema=mt.get("inputSchema", {"type": "object"}),
                source="mcp",
                metadata={"mcp_server": mt.get("server_name", "unknown")},
            )
            self.register(tool)

    # ─────────────────────────────────────────
    # Retrieval
    # ─────────────────────────────────────────

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_all(self) -> List[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_by_source(self, source: str) -> List[ToolDefinition]:
        """List tools from a specific source."""
        return [t for t in self._tools.values() if t.source == source]

    def get_for_role(self, role: AgentType) -> List[ToolDefinition]:
        """Get tools available to a specific agent role.

        Role-based filtering allows different agent personas to have
        access to different tool sets.
        """
        role_tools = {
            AgentType.PLANNER: ["file_read", "web_search", "memory_search"],
            AgentType.BIOINFO: [
                "file_read",
                "file_write",
                "shell_exec",
                "web_search",
                "memory_search",
            ],
            AgentType.VIZ: ["file_read", "plotly_render", "matplotlib_render"],
            AgentType.EXPERIMENT: ["file_read", "file_write", "web_search"],
            AgentType.QA: ["web_search", "memory_search", "pubmed_search"],
            AgentType.REPORT: ["file_read", "file_write", "web_search"],
        }
        tool_names = role_tools.get(role, ["file_read"])
        return [self._tools[name] for name in tool_names if name in self._tools]

    # ─────────────────────────────────────────
    # Execution
    # ─────────────────────────────────────────

    def invoke(self, name: str, inputs: Dict[str, Any]) -> ToolResult:
        """Invoke a tool by name with given inputs (synchronous).

        For async handlers, use invoke_async.

        Raises:
            ValueError: If tool not found.
            RuntimeError: If tool has no handler (e.g., MCP tool not bound).
        """
        tool = self.get(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' not found in registry")

        if tool.handler is None:
            raise RuntimeError(
                f"Tool '{name}' has no handler registered. "
                "This may be an MCP tool that needs a client binding."
            )

        try:
            # Validate inputs against schema (basic check)
            self._validate_inputs(tool, inputs)
            result = tool.handler(**inputs)
            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(success=False, output=None, error_message=str(e))

    async def invoke_async(self, name: str, inputs: Dict[str, Any]) -> ToolResult:
        """Invoke a tool by name with given inputs (asynchronous).

        Supports both sync and async handlers.
        """
        tool = self.get(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' not found in registry")

        if tool.handler is None:
            raise RuntimeError(
                f"Tool '{name}' has no handler registered. "
                "This may be an MCP tool that needs a client binding."
            )

        try:
            self._validate_inputs(tool, inputs)
            if self._is_async(tool.handler):
                result = await tool.handler(**inputs)
            else:
                result = tool.handler(**inputs)
            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(success=False, output=None, error_message=str(e))

    @staticmethod
    def _is_async(func: Callable) -> bool:
        """Check if a callable is async."""
        import inspect
        return inspect.iscoroutinefunction(func)

    @staticmethod
    def _validate_inputs(tool: ToolDefinition, inputs: Dict[str, Any]) -> None:
        """Basic input validation against tool's input_schema."""
        schema = tool.input_schema
        required = schema.get("required", [])
        schema.get("properties", {})

        for field_name in required:
            if field_name not in inputs:
                raise ValueError(f"Missing required input '{field_name}' for tool '{tool.name}'")

        # Warn about unknown fields in strict mode (optional)
        # strict = tool.metadata.get("strict", False)
        # if strict:
        #     allowed = set(properties.keys())
        #     extra = set(inputs.keys()) - allowed
        #     if extra:
        #         raise ValueError(f"Unknown inputs for tool '{tool.name}': {extra}")

    # ─────────────────────────────────────────
    # Reset
    # ─────────────────────────────────────────

    def reset(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()


# Global default registry
_default_tool_registry = ToolRegistry()


def get_default_tool_registry() -> ToolRegistry:
    """Get the global default tool registry."""
    return _default_tool_registry
