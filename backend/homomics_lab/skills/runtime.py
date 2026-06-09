import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.registry import SkillRegistry, get_default_registry
from homomics_lab.skills.sandbox import LocalSandbox
from homomics_lab.skills.tracker import SkillPerformanceTracker
from homomics_lab.hpc.scheduler import get_scheduler, BaseScheduler


class SkillRuntimeExecutor:
    """Executes skills in a sandboxed environment with optional HPC backend."""

    def __init__(
        self,
        registry: SkillRegistry = None,
        working_dir: Path = None,
        executor_type: str = "local",
        tracker: SkillPerformanceTracker = None,
    ):
        self.registry = registry or get_default_registry()
        self.working_dir = working_dir
        self._builtin_code: Dict[str, str] = {}
        self._file_based_skills: Dict[str, Path] = {}
        self._executor_type = executor_type
        self._scheduler: Optional[BaseScheduler] = None
        self.tracker = tracker

    def _get_scheduler(self) -> BaseScheduler:
        """Lazy initialization of the scheduler."""
        if self._scheduler is None:
            self._scheduler = get_scheduler(
                self._executor_type,
                working_dir=self.working_dir,
            )
        return self._scheduler

    def register_builtin(self, skill: SkillDefinition, code: str) -> None:
        """Register a builtin skill with its Python code."""
        self.registry.register(skill)
        self._builtin_code[skill.id] = code

    def register_file_skill(self, skill: SkillDefinition, scripts_dir: Path) -> None:
        """Register an external skill from a file system directory."""
        self._file_based_skills[skill.id] = scripts_dir

    def _register_builtin_code(self, skill_id: str, code: str) -> None:
        """Internal method for testing."""
        self._builtin_code[skill_id] = code

    async def execute(self, skill_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        skill = self.registry.get(skill_id)
        if skill is None:
            raise ValueError(f"Skill '{skill_id}' not found")

        # Validate inputs
        validated = skill.validate_input(inputs)

        # Determine execution strategy
        exec_type = self._resolve_execution_type(skill)

        # Track execution metrics
        start_time = time.time()
        success = False
        error_msg = None
        result = None

        try:
            # Get skill code based on type
            if skill.id in self._builtin_code:
                # Built-in skill: code stored in memory
                code = self._builtin_code[skill.id]
                result = await self._execute_builtin(skill, code, validated, exec_type)

            elif skill.id in self._file_based_skills:
                # File-based skill: code on disk
                scripts_dir = self._file_based_skills[skill.id]
                result = await self._execute_file_based(skill, scripts_dir, validated, exec_type)

            elif skill.metadata.get("scripts_dir"):
                # External skill loaded via loader but not explicitly registered as file-based
                scripts_dir = Path(skill.metadata["scripts_dir"])
                if scripts_dir.exists():
                    result = await self._execute_file_based(skill, scripts_dir, validated, exec_type)

            if result is None:
                raise RuntimeError(f"No code or scripts directory available for skill '{skill_id}'")

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

    async def _execute_builtin(
        self,
        skill: SkillDefinition,
        code: str,
        inputs: Dict[str, Any],
        exec_type: str,
    ) -> Dict[str, Any]:
        """Execute a builtin skill via the configured scheduler."""
        timeout = self._parse_timeout(skill.runtime.resources.time)
        scheduler = self._get_scheduler()
        return await scheduler.execute(skill, code, inputs, timeout_seconds=timeout)

    async def _execute_file_based(
        self,
        skill: SkillDefinition,
        scripts_dir: Path,
        inputs: Dict[str, Any],
        exec_type: str,
    ) -> Dict[str, Any]:
        """Execute a file-based skill by reading scripts from disk."""
        timeout = self._parse_timeout(skill.runtime.resources.time)

        # Collect all script files
        if exec_type == "r":
            script_files = sorted(scripts_dir.glob("*.R"))
            if not script_files:
                script_files = sorted(scripts_dir.glob("*.r"))

            if not script_files:
                raise RuntimeError(f"No .R files found in {scripts_dir}")

            # Concatenate R scripts
            code_parts = []
            for f in script_files:
                code_parts.append(f"# --- {f.name} ---")
                code_parts.append(f.read_text(encoding="utf-8"))
            code = "\n".join(code_parts)

        else:
            script_files = sorted(scripts_dir.glob("*.py"))

            if not script_files:
                raise RuntimeError(f"No .py files found in {scripts_dir}")

            # Concatenate Python scripts
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
