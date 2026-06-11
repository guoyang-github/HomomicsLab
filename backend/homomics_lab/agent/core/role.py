"""RoleDefinition — dynamic agent role configuration.

Replaces hardcoded agent classes (BioinfoAgent, VizAgent, etc.) with
YAML/JSON-configurable roles that determine:
  - what skills/tools an agent can use
  - system prompt template
  - permissions (execute, review, spawn specialists)
  - selection priority for task routing
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RolePermissions(BaseModel):
    can_execute: bool = True
    can_review: bool = False
    can_spawn_specialist: bool = False
    can_access_workspace: bool = True
    can_call_shell: bool = False
    max_concurrent_tasks: int = 1


class RoleDefinition(BaseModel):
    """A configurable agent role."""

    role_id: str
    name: str
    description: str = ""
    agent_type: str = "specialist"  # analyst, specialist, qa, etc.

    # Capability filters
    allowed_skills: List[str] = Field(default_factory=list)
    allowed_skill_categories: List[str] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    blocked_skills: List[str] = Field(default_factory=list)

    # Prompting
    system_prompt: str = "You are a helpful bioinformatics assistant."
    prompt_template: Optional[str] = None

    # Metadata
    permissions: RolePermissions = Field(default_factory=RolePermissions)
    priority: int = 100  # Lower = higher priority for task routing
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def can_handle_skill(self, skill_id: str, skill_category: Optional[str] = None) -> bool:
        """Check if this role can handle a given skill."""
        if any(
            skill_id == s or (s.endswith("*") and skill_id.startswith(s[:-1]))
            for s in self.blocked_skills
        ):
            return False

        if skill_id in self.allowed_skills:
            return True

        if self.allowed_skills and not any(
            skill_id == s or (s.endswith("*") and skill_id.startswith(s[:-1]))
            for s in self.allowed_skills
        ):
            return False

        if skill_category and self.allowed_skill_categories:
            if skill_category not in self.allowed_skill_categories:
                return False

        # If no explicit allowlist, default to True (generalist)
        if not self.allowed_skills and not self.allowed_skill_categories:
            return True

        return True

    def can_use_tool(self, tool_name: str) -> bool:
        """Check if this role can use a given tool."""
        if not self.allowed_tools:
            return True
        return tool_name in self.allowed_tools

    def match_score(self, skill_id: str, skill_category: Optional[str] = None) -> int:
        """Return a match score for task routing. Higher = better match."""
        if not self.can_handle_skill(skill_id, skill_category):
            return -1

        score = 0
        # Direct skill match is best
        if skill_id in self.allowed_skills:
            score += 100
        # Category match
        if skill_category and skill_category in self.allowed_skill_categories:
            score += 50
        # Priority bonus (lower priority value = higher bonus)
        score += max(0, 200 - self.priority)
        return score
