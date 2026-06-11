"""Models for tool definitions and tool execution results."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class ToolDefinition:
    """Definition of an atomic tool capability.

    Tools are single-call, stateless operations used by agents.
    Unlike skills (multi-step workflows), tools are atomic:
    file_read, shell_exec, pubmed_search, etc.
    """

    name: str
    description: str
    input_schema: Dict[str, Any]  # JSON Schema
    output_schema: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable] = None  # Execution function
    source: str = "builtin"  # "builtin" | "mcp" | "plugin"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.name:
            raise ValueError("Tool name is required")
        if not self.description:
            raise ValueError("Tool description is required")


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    output: Any
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
