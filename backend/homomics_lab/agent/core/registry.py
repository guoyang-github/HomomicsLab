"""RoleRegistry — loads and manages dynamic agent role definitions."""

import json
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .role import RoleDefinition


class RoleRegistry:
    """Registry for agent roles. Replaces hardcoded agent class definitions."""

    def __init__(self):
        self._roles: Dict[str, RoleDefinition] = {}

    def register(self, role: RoleDefinition) -> None:
        self._roles[role.role_id] = role

    def get(self, role_id: str) -> Optional[RoleDefinition]:
        return self._roles.get(role_id)

    def list_all(self) -> List[RoleDefinition]:
        return list(self._roles.values())

    def find_for_skill(
        self, skill_id: str, skill_category: Optional[str] = None
    ) -> List[RoleDefinition]:
        """Find roles that can handle a skill, sorted by match score desc."""
        scored = []
        for role in self._roles.values():
            score = role.match_score(skill_id, skill_category)
            if score >= 0:
                scored.append((score, role))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored]

    def find_for_category(self, category: str) -> List[RoleDefinition]:
        """Find roles that allow a given skill category."""
        return [
            r for r in self._roles.values()
            if category in r.allowed_skill_categories
            or (not r.allowed_skill_categories and not r.allowed_skills)
        ]

    def load_role(self, path: Path) -> RoleDefinition:
        """Load a single role from YAML or JSON."""
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
        role = RoleDefinition.model_validate(data)
        self.register(role)
        return role

    def load_all(self, directory: Path) -> int:
        """Load all roles from a directory. Returns count loaded."""
        count = 0
        if not directory.exists():
            return count

        for path in sorted(directory.iterdir()):
            if path.suffix in (".yaml", ".yml", ".json"):
                self.load_role(path)
                count += 1
        return count

    def reset(self) -> None:
        self._roles.clear()
