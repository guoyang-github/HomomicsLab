"""Skill runtime executor with unified execution path for all skills.

All skills (builtin and external) now use the same directory-based layout.
The executor no longer distinguishes between builtin (code strings) and
external (file-based) skills.
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry, get_default_registry
from homomics_lab.skills.sandbox import LocalSandbox
from homomics_lab.skills.tracker import SkillPerformanceTracker
from homomics_lab.hpc.scheduler import get_scheduler, BaseScheduler
from homomics_lab.stability.schema_validator import SchemaValidator


class SkillRuntimeExecutor:
    """Executes skills in a sandboxed environment with optional HPC backend.

    Unified execution: all skills are treated equally, whether builtin or external.
    The skill's metadata["scripts_dir"] determines where code is loaded from.
    """

    def __init__(
        self,
        registry: SkillRegistry = None,
        working_dir: Path = None,
        executor_type: str = "local",
        tracker: SkillPerformanceTracker = None,
        schema_validator: SchemaValidator = None,
    ):
        self.registry = registry or get_default_registry()
        self.working_dir = working_dir
        self._executor_type = executor_type
        self._scheduler: Optional[BaseScheduler] = None
        self.tracker = tracker
        self.schema_validator = schema_validator

    def _get_scheduler(self) -> BaseScheduler:
        """Lazy initialization of the scheduler."""
        if self._scheduler is None:
            self._scheduler = get_scheduler(
                self._executor_type,
                working_dir=self.working_dir,
            )
        return self._scheduler

    def register_skill(self, skill: SkillDefinition) -> None:
        """Register a skill (builtin or external) into the registry.

        All skills are treated uniformly. The skill's scripts_dir in metadata
        determines where code is loaded from at execution time.
        """
        self.registry.register(skill)

    async def execute(self, skill_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a skill by ID.

        Looks up the skill in the registry, determines the execution type
        (python/r), finds scripts_dir from metadata, and delegates to scheduler.
        """
        skill = self.registry.get(skill_id)
        if skill is None:
            raise ValueError(f"Skill '{skill_id}' not found")

        # Schema validation (if validator configured)
        if self.schema_validator is not None:
            validation = self.schema_validator.validate_input(skill, inputs)
            if not validation.passed:
                raise ValueError(
                    f"Input validation failed for skill '{skill_id}': "
                    f"{'; '.join(validation.errors)}"
                )

        # Validate inputs (schema-based defaults)
        validated = skill.validate_input(inputs)

        # Determine execution strategy
        exec_type = self._resolve_execution_type(skill)

        # Resolve scripts directory
        scripts_dir = self._resolve_scripts_dir(skill)
        if scripts_dir is None:
            raise RuntimeError(f"No scripts directory available for skill '{skill_id}'")

        # Track execution metrics
        start_time = time.time()
        success = False
        error_msg = None
        result = None

        try:
            result = await self._execute_from_dir(skill, scripts_dir, exec_type, validated)
            success = True
            return result

        except Exception as e:
            error_msg = str(e)
            raise

        finally:
            # Record metrics
            if self.tracker is not None:
                duration_ms = (time.time() - start_time) * 1000
                output_size = len(str(result)) if result else 0
                self.tracker.record(
                    skill_id=skill_id,
                    duration_ms=duration_ms,
                    success=success,
                    output_size=output_size,
                    executor_type=self._executor_type,
                    error_message=error_msg,
                )

    def _resolve_execution_type(self, skill: SkillDefinition) -> str:
        """Determine the execution type (python or r) for a skill."""
        runtime_type = skill.runtime.type.lower()

        if runtime_type in ("python", "r"):
            return runtime_type

        if runtime_type == "mixed":
            # Choose based on primary_tool
            primary = skill.metadata.get("primary_tool", "").lower()
            r_tools = {
                "seurat", "monocle3", "archr", "signac", "harmony",
                "cellchat", "nichenet", "singleR", "scvi", "scran",
            }
            if primary in r_tools:
                return "r"
            return "python"

        return "python"

    def _resolve_scripts_dir(self, skill: SkillDefinition) -> Optional[Path]:
        """Resolve the scripts directory for a skill.

        Checks metadata['scripts_dir'] first, then falls back to
        finding scripts relative to the skill definition.
        """
        if skill.metadata.get("scripts_dir"):
            scripts_dir = Path(skill.metadata["scripts_dir"])
            if scripts_dir.exists():
                return scripts_dir

        return None

    async def _execute_from_dir(
        self,
        skill: SkillDefinition,
        scripts_dir: Path,
        exec_type: str,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a skill by reading scripts from its directory."""
        timeout = self._parse_timeout(skill.runtime.resources.time)

        # Collect all script files
        if exec_type == "r":
            script_files = sorted(scripts_dir.glob("*.R"))
            if not script_files:
                script_files = sorted(scripts_dir.glob("*.r"))
            if not script_files:
                raise RuntimeError(f"No .R files found in {scripts_dir}")
        else:
            script_files = sorted(scripts_dir.glob("*.py"))
            if not script_files:
                raise RuntimeError(f"No .py files found in {scripts_dir}")

        # Concatenate scripts
        code_parts = []
        for f in script_files:
            code_parts.append(f"# --- {f.name} ---")
            code_parts.append(f.read_text(encoding="utf-8"))
        code = "\n".join(code_parts)

        scheduler = self._get_scheduler()
        return await scheduler.execute(skill, code, inputs, timeout_seconds=timeout)

    def _parse_timeout(self, time_str: str) -> float:
        """Parse time string like '30m' or '1h' into seconds."""
        time_str = str(time_str).strip()
        if time_str.endswith("m"):
            seconds = float(time_str[:-1]) * 60
        elif time_str.endswith("h"):
            seconds = float(time_str[:-1]) * 3600
        elif time_str.endswith("s"):
            seconds = float(time_str[:-1])
        else:
            seconds = float(time_str)

        # Cap at 1 hour for MVP
        return min(seconds, 3600.0)
