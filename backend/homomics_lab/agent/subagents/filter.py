"""Tool-filtering helpers for role-based sub-agents."""

from typing import Any, List, Set

from homomics_lab.tools.registry import ToolRegistry


# Tools that can mutate state or execute code. Critics never get these.
_WRITE_OR_EXECUTE_TOOLS: Set[str] = {
    "shell_exec",
    "file_write",
    "file_edit",
    "file_delete",
    "execute_code",
    "run_skill",
}


def _tool_matches_skill(tool_name: str, skill_glob: str) -> bool:
    """Simple glob: ``bio-single-cell-*`` matches ``bio-single-cell-annotation``."""
    if skill_glob.endswith("*"):
        return tool_name.startswith(skill_glob[:-1])
    return tool_name == skill_glob


def filter_tools_by_role(
    registry: ToolRegistry,
    role: Any,
    read_only: bool = False,
) -> List[str]:
    """Return the list of tool names a sub-agent with ``role`` may use.

    If ``read_only`` is True, high-risk and write/execute tools are removed
    regardless of role permissions. Unknown roles default to low-risk builtins.
    """
    allowed_tools: Set[str] = set()
    allowed_skills: Set[str] = set()

    if role is not None:
        raw_tools = getattr(role, "allowed_tools", None) or []
        raw_skills = getattr(role, "allowed_skills", None) or []
        allowed_tools = {str(t) for t in raw_tools}
        allowed_skills = {str(s) for s in raw_skills}

    def permitted(tool_def: Any) -> bool:
        name = tool_def.name
        if read_only:
            if name in _WRITE_OR_EXECUTE_TOOLS:
                return False
            if getattr(tool_def, "risk_level", None) in ("medium", "high"):
                return False
        if not allowed_tools and not allowed_skills:
            # No role restrictions -> all (or all read-only) tools.
            return True
        if name in allowed_tools:
            return True
        return any(_tool_matches_skill(name, pattern) for pattern in allowed_skills)

    return [t.name for t in registry.list_all() if permitted(t)]


def read_only_tools(registry: ToolRegistry) -> List[str]:
    """All low-risk tools that cannot mutate state or execute arbitrary code."""
    return filter_tools_by_role(registry, role=None, read_only=True)
