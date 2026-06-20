"""Bootstrap-time integration of MCP tools into HomomicsLab registries."""

import logging
from typing import Any, Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.mcp.client import BioMCPClient
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema, SkillRuntime
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.tools.models import ToolDefinition
from homomics_lab.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


async def register_mcp_tools(tool_registry: ToolRegistry) -> Optional[BioMCPClient]:
    """Register MCP tools into the ToolRegistry with bound handlers.

    Returns the MCP client so the caller can close it on shutdown.
    """
    if not settings.mcp_enabled:
        return None

    try:
        client = BioMCPClient(mode=settings.mcp_mode)
        await client.connect()
    except Exception as exc:
        logger.warning(
            "Failed to initialize MCP client (mode=%s): %s. MCP tools will not be available.",
            settings.mcp_mode,
            exc,
        )
        return None

    try:
        tools = await client.list_tools()
    except Exception as exc:
        logger.warning("Failed to list MCP tools: %s", exc)
        await client.close() if hasattr(client, "close") else None
        return None

    for tool_desc in tools:
        name = tool_desc["name"]
        schema = tool_desc.get("parameters") or tool_desc.get("inputSchema", {"type": "object"})
        tool = ToolDefinition(
            name=name,
            description=tool_desc.get("description", ""),
            input_schema=schema,
            source="mcp",
            metadata={
                "mcp_mode": settings.mcp_mode,
                "mcp_server": "homomics-bio",
            },
            handler=_make_tool_handler(client, name),
        )
        tool_registry.register(tool)
        logger.info("Registered MCP tool: %s", name)

    return client


def _make_tool_handler(client: BioMCPClient, tool_name: str):
    """Return an async handler for a specific MCP tool."""

    async def handler(**inputs: Any) -> Dict[str, Any]:
        return await client.call_tool(tool_name, inputs)

    handler.__name__ = f"mcp_{tool_name}"
    return handler


def register_mcp_skills(
    skill_executor: SkillRuntimeExecutor,
    tool_registry: ToolRegistry,
) -> List[SkillDefinition]:
    """Wrap registered MCP tools as lightweight skills so the planner can use them."""
    skills: List[SkillDefinition] = []
    for tool in tool_registry.list_by_source("mcp"):
        skill_id = f"mcp_{tool.name}"
        skill = SkillDefinition(
            id=skill_id,
            name=tool.name,
            version="1.0",
            category="mcp",
            author="mcp",
            description=tool.description,
            input_schema=SkillInputSchema(
                type="object",
                properties=tool.input_schema.get("properties", {}),
                required=tool.input_schema.get("required", []),
            ),
            runtime=SkillRuntime(
                type="mcp",
                executor="auto",
            ),
            metadata={"tool_name": tool.name, "source": "mcp", "namespace": "mcp"},
        )
        skill_executor.register_skill(skill)
        skills.append(skill)
        logger.info("Registered MCP skill: %s", skill_id)
    return skills
