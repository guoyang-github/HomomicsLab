from pathlib import Path
from typing import Any, Dict
from homics_lab.skills.models import SkillDefinition
from homics_lab.skills.registry import SkillRegistry, get_default_registry
from homics_lab.skills.sandbox import LocalSandbox


class SkillRuntimeExecutor:
    """Executes skills in a sandboxed environment."""

    def __init__(self, registry: SkillRegistry = None, working_dir: Path = None):
        self.registry = registry or get_default_registry()
        self.sandbox = LocalSandbox(working_dir=working_dir)
        self._builtin_code: Dict[str, str] = {}

    def register_builtin(self, skill: SkillDefinition, code: str) -> None:
        """Register a builtin skill with its Python code."""
        self.registry.register(skill)
        self._builtin_code[skill.id] = code

    def _register_builtin_code(self, skill_id: str, code: str) -> None:
        """Internal method for testing."""
        self._builtin_code[skill_id] = code

    async def execute(self, skill_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        skill = self.registry.get(skill_id)
        if skill is None:
            raise ValueError(f"Skill '{skill_id}' not found")

        # Validate inputs
        validated = skill.validate_input(inputs)

        # Get skill code
        if skill.id not in self._builtin_code:
            raise RuntimeError(f"No code registered for skill '{skill_id}'")

        code = self._builtin_code[skill.id]

        # Execute in sandbox
        timeout = self._parse_timeout(skill.runtime.resources.time)
        result = await self.sandbox.run_python(code, validated, timeout_seconds=timeout)

        return result

    def _parse_timeout(self, time_str: str) -> float:
        """Parse time string like '30m' or '1h' into seconds."""
        if time_str.endswith("m"):
            return float(time_str[:-1]) * 60
        elif time_str.endswith("h"):
            return float(time_str[:-1]) * 3600
        elif time_str.endswith("s"):
            return float(time_str[:-1])
        return float(time_str)
