"""Bootstrap-time integration helpers for MCP tools into HomomicsLab registries.

The actual registration of enabled MCP servers is now handled by
``homomics_lab.mcp.marketplace.MCPMarketplace``; this module keeps the shared
helpers (risk inference, handler binding, skill wrapping) used by the
marketplace and the skill runtime.
"""

import logging
from typing import Any, Dict, List

from homomics_lab.mcp.client import BioMCPClient
from homomics_lab.skills.models import SkillDefinition, SkillInputSchema, SkillRuntime
from homomics_lab.skills.runtime import SkillRuntimeExecutor
from homomics_lab.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def _infer_risk_level(tool_name: str) -> str:
    """Infer a risk level for an MCP tool based on its name."""
    name_lower = tool_name.lower()
    high_risk = {"delete", "drop", "remove", "write", "exec", "shell", "run", "overwrite"}
    medium_risk = {"fetch", "download", "submit", "update", "modify", "create"}
    if any(k in name_lower for k in high_risk):
        return "high"
    if any(k in name_lower for k in medium_risk):
        return "medium"
    return "low"


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
            metadata={
                "tool_name": tool.name,
                "source": "mcp",
                "namespace": "mcp",
                "trusted": False,
            },
        )
        skill_executor.register_skill(skill)
        skills.append(skill)
        logger.info("Registered MCP skill: %s", skill_id)
    return skills
