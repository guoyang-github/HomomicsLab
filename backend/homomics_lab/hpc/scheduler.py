"""HPC and workflow execution schedulers for HomomicsLab.

Supports three execution backends:
- LocalScheduler: Direct subprocess execution (default, for dev/small jobs)
- SlurmScheduler: SLURM cluster job submission (for HPC environments)
- NextflowRunner: Nextflow workflow engine (for complex pipelines)
"""

import asyncio
import json
import logging
import shutil
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from homomics_lab.config import settings
from homomics_lab.hpc.pubsub import ExecutionPubSub, get_default_pubsub
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.skills.environment_manager import EnvironmentManager
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.sandbox import LocalSandbox, Sandbox

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Result of a job execution."""

    def __init__(
        self,
        status: str,  # "completed", "failed", "timeout", "cancelled"
        output: Dict[str, Any],
        job_id: Optional[str] = None,
        error_message: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ):
        self.status = status
        self.output = output
        self.job_id = job_id
        self.error_message = error_message
        self.start_time = start_time or datetime.now(timezone.utc)
        self.end_time = end_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "output": self.output,
            "job_id": self.job_id,
            "error_message": self.error_message,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class BaseScheduler(ABC):
    """Abstract base class for job schedulers."""

    def __init__(
        self,
        working_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        pubsub: Optional[ExecutionPubSub] = None,
    ):
        self.working_dir = (working_dir or Path.cwd()).resolve()
        self.working_dir.mkdir(parents=True, exist_ok=True)
        self._pubsub = pubsub or get_default_pubsub()
        self._progress_callback = progress_callback

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Check if this scheduler is available in the current environment."""
        pass

    @abstractmethod
    async def execute(
        self,
        skill: SkillDefinition,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
    ) -> Dict[str, Any]:
        """Execute a skill and return its output."""
        pass

    @abstractmethod
    async def terminate(self, job_id: str) -> bool:
        """Cancel/terminate a running job. Returns True if action was taken."""
        pass

    def _new_job_id(self, prefix: str = "job") -> str:
        """Generate a unique job id."""
        return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"

    def _report_progress(self, state: ExecutionState) -> None:
        """Publish a state update to the default pubsub and optional callback."""
        self._pubsub.publish(state.job_id, state)
        if self._progress_callback is not None:
            try:
                self._progress_callback(state)
            except Exception:
                # Never break execution because of a monitoring callback.
                pass

    @staticmethod
    def _tail_logs(path: Path, max_lines: int = 50) -> List[str]:
        """Return the last N lines of a log file, if it exists."""
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-max_lines:] if len(lines) > max_lines else lines

    def _parse_time_to_seconds(self, time_str: str) -> int:
        """Parse time string like '30m', '2h', '1d' into seconds."""
        time_str = str(time_str).strip().lower()
        if time_str.endswith("d"):
            return int(float(time_str[:-1]) * 24 * 3600)
        elif time_str.endswith("h"):
            return int(float(time_str[:-1]) * 3600)
        elif time_str.endswith("m"):
            return int(float(time_str[:-1]) * 60)
        elif time_str.endswith("s"):
            return int(float(time_str[:-1]))
        else:
            return int(float(time_str))


class LocalScheduler(BaseScheduler):
    """Execute skills locally using the sandbox."""

    def __init__(
        self,
        working_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        pubsub: Optional[ExecutionPubSub] = None,
        sandbox: Optional[Sandbox] = None,
        env_manager: Optional[EnvironmentManager] = None,
        provenance_recorder: Optional[Any] = None,
    ):
        super().__init__(working_dir, progress_callback=progress_callback, pubsub=pubsub)
        self._sandbox_override = sandbox
        self._last_sandbox: Optional[Sandbox] = None
        self._env_manager = env_manager or EnvironmentManager()
        self._provenance_recorder = provenance_recorder

    def _get_sandbox(self, exec_type: str) -> Sandbox:
        if self._sandbox_override is not None:
            return self._sandbox_override
        container_image = settings.r_container_image if exec_type == "r" else settings.skill_container_image
        sandbox = Sandbox.create(
            settings.skill_sandbox_backend,
            self.working_dir,
            container_image=container_image,
            exec_type=exec_type,
        )
        self._last_sandbox = sandbox
        return sandbox

    @classmethod
    def is_available(cls) -> bool:
        return True

    async def terminate(self, job_id: str) -> bool:
        """Terminate the sandbox subprocess for a running local job."""
        sandbox = self._sandbox_override or self._last_sandbox
        if sandbox is None:
            return False
        return await sandbox.terminate(job_id)

    async def execute(
        self,
        skill: SkillDefinition,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
    ) -> Dict[str, Any]:
        job_id = self._new_job_id(f"local_{skill.id}")
        started_at = datetime.now(timezone.utc)

        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status="PENDING",
                current_phase=skill.id,
                progress_pct=0.0,
                started_at=started_at,
                scheduler_type="local",
            )
        )

        exec_type = skill.runtime.type.lower()

        # Mixed defaults to python unless primary_tool suggests R
        if exec_type == "mixed":
            primary = skill.metadata.get("primary_tool", "").lower()
            r_tools = {
                "seurat", "monocle3", "archr", "signac", "harmony",
                "cellchat", "nichenet", "singler", "scran",
            }
            exec_type = "r" if primary in r_tools else "python"

        # Prepare isolated environment and resolve the right sandbox image.
        scripts_dir = Path(skill.metadata.get("scripts_dir", self.working_dir))
        env_info = self._env_manager.prepare(skill.id, scripts_dir, exec_type)
        sandbox = self._get_sandbox(exec_type)
        # In local-dev mode the host project venv already contains the packages
        # installed by the user (e.g. via uv add / pip install). Reuse it so
        # skills work without waiting for per-skill venv creation.
        if isinstance(sandbox, LocalSandbox):
            env_info.python_path = sys.executable
        sandbox_metadata = sandbox.get_metadata()

        # Static safety scan for Python/R code.
        from homomics_lab.execution.code_safety import CodeSafetyScanner, requires_hitl

        scanner = CodeSafetyScanner()
        safety_result = scanner.scan(code, language=exec_type)
        hitl_required = (
            settings.interactive_mode
            and requires_hitl(safety_result, min_risk_level=settings.codeact_hitl_level)
        )
        if safety_result.risk_level == "critical":
            return {
                "status": "error",
                "error": f"Critical safety findings: {safety_result.findings}",
                "safety_scan": safety_result.to_dict(),
                "_sandbox_metadata": sandbox_metadata,
            }
        if hitl_required:
            return {
                "status": "awaiting_human",
                "error": "High-risk code requires human approval",
                "safety_scan": safety_result.to_dict(),
                "_sandbox_metadata": sandbox_metadata,
            }

        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status="RUNNING",
                current_phase=skill.id,
                progress_pct=10.0,
                started_at=started_at,
                scheduler_type="local",
            )
        )

        def _progress_callback(state: ExecutionState) -> None:
            # Ensure the state carries this scheduler's metadata.
            state.job_id = job_id
            state.current_phase = skill.id
            state.started_at = started_at
            state.scheduler_type = "local"
            self._report_progress(state)

        try:
            if exec_type == "r":
                result = await sandbox.run_r(
                    code,
                    inputs,
                    timeout_seconds=timeout_seconds,
                    progress_callback=_progress_callback,
                    job_id=job_id,
                    current_phase=skill.id,
                    r_executable=env_info.r_executable,
                    r_library_path=env_info.r_library_path,
                )
            else:
                result = await sandbox.run_python(
                    code,
                    inputs,
                    timeout_seconds=timeout_seconds,
                    progress_callback=_progress_callback,
                    job_id=job_id,
                    current_phase=skill.id,
                    python_path=env_info.python_path,
                    unrestricted=skill.metadata.get("trusted", False),
                )
        except Exception as exc:
            self._report_progress(
                ExecutionState(
                    job_id=job_id,
                    status="FAILED",
                    current_phase=skill.id,
                    progress_pct=0.0,
                    started_at=started_at,
                    error_message=str(exc),
                    scheduler_type="local",
                )
            )
            raise

        status = "COMPLETED" if result.get("status") != "error" else "FAILED"
        error_message = result.get("error") if status == "FAILED" else None

        # Attach sandbox metadata for provenance / observability
        if isinstance(result, dict):
            result["_sandbox_metadata"] = sandbox_metadata

        # Record execution provenance (best-effort)
        if self._provenance_recorder is not None and isinstance(result, dict):
            try:
                from homomics_lab.provenance.models import ExecutionProvenance
                from homomics_lab.provenance.recorder import (
                    collect_input_files,
                    collect_output_files,
                )

                ended_at = datetime.now(timezone.utc)
                prov = ExecutionProvenance(
                    execution_id=job_id,
                    skill_id=skill.id,
                    skill_version=skill.metadata.get("version", "1.0.0"),
                    started_at=started_at,
                    ended_at=ended_at,
                    parameters=inputs,
                    input_files=collect_input_files(inputs),
                    output_files=collect_output_files(self.working_dir),
                    sandbox_backend=sandbox_metadata.get("backend", ""),
                    container_image=sandbox_metadata.get("container_image"),
                    container_digest=sandbox_metadata.get("container_digest"),
                    dependency_manifest=env_info.to_dict(),
                    result_summary={"status": status},
                )
                self._provenance_recorder.record(prov)
            except Exception as exc:
                # Provenance failures must not break skill execution.
                logger.warning("Failed to record provenance: %s", exc)

        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status=status,
                current_phase=skill.id,
                progress_pct=100.0,
                started_at=started_at,
                error_message=error_message,
                scheduler_type="local",
            )
        )

        return result


class SlurmScheduler(BaseScheduler):
    """Submit skills as SLURM batch jobs."""

    def __init__(
        self,
        working_dir: Optional[Path] = None,
        partition: Optional[str] = None,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        pubsub: Optional[ExecutionPubSub] = None,
        provenance_recorder: Optional[Any] = None,
    ):
        super().__init__(working_dir, progress_callback=progress_callback, pubsub=pubsub)
        self.partition = partition

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("sbatch") is not None

    async def terminate(self, job_id: str) -> bool:
        """Cancel a running SLURM job."""
        if not shutil.which("scancel"):
            return False
        proc = await asyncio.create_subprocess_exec(
            "scancel", job_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0

    def _build_sbatch_script(
        self,
        skill: SkillDefinition,
        code: str,
        job_name: str,
    ) -> str:
        """Generate an SBATCH script for the skill."""
        resources = skill.runtime.resources
        mem = resources.memory
        cpu = resources.cpu
        time_limit = self._format_slurm_time(resources.time)

        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={job_name}",
            f"#SBATCH --output={self.working_dir}/{job_name}.out",
            f"#SBATCH --error={self.working_dir}/{job_name}.err",
            f"#SBATCH --mem={mem}",
            f"#SBATCH --cpus-per-task={cpu}",
            f"#SBATCH --time={time_limit}",
        ]

        if self.partition:
            lines.append(f"#SBATCH --partition={self.partition}")

        lines.append("")
        lines.append("# Auto-generated by HomomicsLab")
        lines.append("")

        exec_type = skill.runtime.type.lower()
        if exec_type in ("r", "mixed"):
            # For R scripts, wrap with Rscript
            primary = skill.metadata.get("primary_tool", "").lower()
            r_tools = {"seurat", "monocle3", "archr", "signac", "harmony", "cellchat"}
            is_r = exec_type == "r" or primary in r_tools

            if is_r:
                lines.append("module load R >/dev/null 2>&1 || true")
                lines.append("cat > \"$TMPDIR/skill.R\" << 'RSCRIPT_EOF'")
                lines.append(code)
                lines.append("RSCRIPT_EOF")
                lines.append("Rscript \"$TMPDIR/skill.R\"")
            else:
                lines.extend(self._wrap_python(code, job_name))
        else:
            lines.extend(self._wrap_python(code, job_name))

        return "\n".join(lines) + "\n"

    def _wrap_python(self, code: str, job_name: str) -> list[str]:
        """Wrap Python code for batch execution."""
        return [
            "module load python >/dev/null 2>&1 || true",
            "cat > \"$TMPDIR/skill.py\" << 'PYSCRIPT_EOF'",
            code,
            "PYSCRIPT_EOF",
            "python \"$TMPDIR/skill.py\"",
        ]

    def _format_slurm_time(self, time_str: str) -> str:
        """Convert time string to SLURM format HH:MM:SS."""
        seconds = self._parse_time_to_seconds(time_str)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"

    async def execute(
        self,
        skill: SkillDefinition,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
    ) -> Dict[str, Any]:
        """Submit a skill as a SLURM batch job and return a submitted handle.

        The submission is non-blocking: control returns immediately with the
        SLURM job id and a ``submitted`` flag. A background asyncio task polls
        SLURM via ``sacct`` and publishes state updates (PENDING/RUNNING/
        COMPLETED/FAILED) to the configured pub/sub bus. Callers that need the
        final result can either subscribe to the pub/sub channel for this job
        or call ``await poll_job(job_id, ...)`` directly.
        """
        started_at = datetime.now(timezone.utc)
        job_name = f"homomics_{skill.id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        # Write inputs to JSON for the job to read
        inputs_path = self.working_dir / f"{job_name}_inputs.json"
        inputs_path.write_text(json.dumps(inputs))

        # Inject input loading into code
        if skill.runtime.type.lower() == "r":
            code = self._inject_r_inputs(code, str(inputs_path))
        else:
            code = self._inject_python_inputs(code, str(inputs_path))

        script = self._build_sbatch_script(skill, code, job_name)
        script_path = self.working_dir / f"{job_name}.sh"
        script_path.write_text(script)

        # Submit job
        proc = await asyncio.create_subprocess_exec(
            "sbatch", str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"SLURM sbatch failed: {stderr.decode()}")

        # Parse job ID from "Submitted batch job 12345"
        stdout_text = stdout.decode().strip()
        try:
            job_id = stdout_text.split()[-1]
        except IndexError:
            job_id = "unknown"

        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status="PENDING",
                current_phase=skill.id,
                progress_pct=5.0,
                started_at=started_at,
                scheduler_type="slurm",
            )
        )

        # Start an event-driven background monitor instead of blocking the caller.
        asyncio.create_task(
            self._monitor_slurm_job(
                job_id=job_id,
                job_name=job_name,
                timeout_seconds=timeout_seconds,
                phase=skill.id,
                started_at=started_at,
            )
        )

        return {
            "status": "submitted",
            "job_id": job_id,
            "job_name": job_name,
            "scheduler": "slurm",
            "started_at": started_at.isoformat(),
        }

    def _inject_python_inputs(self, code: str, inputs_path: str) -> str:
        """Prepend code to load inputs from JSON file."""
        return f"""import json
with open('{inputs_path}') as f:
    __inputs__ = json.load(f)
locals().update(__inputs__)

{code}
"""

    def _inject_r_inputs(self, code: str, inputs_path: str) -> str:
        """Prepend code to load inputs from JSON file."""
        return f"""library(jsonlite)
skill_inputs <- fromJSON("{inputs_path}", simplifyVector = TRUE)
for (var_name in names(skill_inputs)) {{
  assign(var_name, skill_inputs[[var_name]], envir = .GlobalEnv)
}}

{code}
"""

    async def _monitor_slurm_job(
        self,
        job_id: str,
        job_name: str,
        timeout_seconds: float,
        phase: str = "",
        started_at: Optional[datetime] = None,
    ) -> None:
        """Background monitor for a submitted SLURM job.

        Polls ``sacct`` and publishes ExecutionState events to the pub/sub bus
        until the job reaches a terminal state. Errors are reported as events
        and logged; they do not propagate to the original caller.
        """
        try:
            await self._poll_job(
                job_id=job_id,
                job_name=job_name,
                timeout_seconds=timeout_seconds,
                phase=phase,
                started_at=started_at,
                raise_on_error=False,
            )
        except Exception:
            logger.exception("SLURM monitor failed for job %s", job_id)

    async def _poll_job(
        self,
        job_id: str,
        job_name: str,
        timeout_seconds: float,
        phase: str = "",
        started_at: Optional[datetime] = None,
        raise_on_error: bool = True,
    ) -> Dict[str, Any]:
        """Poll SLURM job until completion.

        Args:
            raise_on_error: If False, terminal failures are reported as events
                and returned instead of raising. This is used by the background
                event-driven monitor so exceptions do not kill the task.
        """
        start = started_at or datetime.now(timezone.utc)
        poll_interval = 5  # seconds
        status_progress = {
            "PENDING": 10.0,
            "RUNNING": 50.0,
            "COMPLETING": 90.0,
        }
        pending_reported = False

        while True:
            await asyncio.sleep(poll_interval)

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            if elapsed > timeout_seconds:
                # Cancel job on timeout
                await self._cancel_job(job_id)
                error_message = f"Timed out after {timeout_seconds}s"
                self._report_progress(
                    ExecutionState(
                        job_id=job_id,
                        status="CANCELLED",
                        current_phase=phase,
                        progress_pct=0.0,
                        started_at=start,
                        error_message=error_message,
                        scheduler_type="slurm",
                    )
                )
                if raise_on_error:
                    raise TimeoutError(f"SLURM job {job_id} timed out after {timeout_seconds}s")
                return {"status": "cancelled", "job_id": job_id, "error": error_message}

            # Check job status
            proc = await asyncio.create_subprocess_exec(
                "sacct", "-j", job_id, "--format=State", "--noheader", "--parsable2",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            slurm_status = stdout.decode().strip().split("|")[0].strip() if stdout else "UNKNOWN"
            progress_pct = status_progress.get(slurm_status, 10.0)
            logs = self._tail_logs(self.working_dir / f"{job_name}.out")

            if slurm_status == "RUNNING":
                self._report_progress(
                    ExecutionState(
                        job_id=job_id,
                        status="RUNNING",
                        current_phase=phase,
                        progress_pct=progress_pct,
                        started_at=start,
                        logs=logs,
                        scheduler_type="slurm",
                    )
                )
            elif slurm_status == "PENDING" and not pending_reported:
                pending_reported = True
                self._report_progress(
                    ExecutionState(
                        job_id=job_id,
                        status="PENDING",
                        current_phase=phase,
                        progress_pct=progress_pct,
                        started_at=start,
                        logs=logs,
                        scheduler_type="slurm",
                    )
                )
            elif slurm_status in ("COMPLETED",):
                self._report_progress(
                    ExecutionState(
                        job_id=job_id,
                        status="COMPLETED",
                        current_phase=phase,
                        progress_pct=100.0,
                        started_at=start,
                        logs=logs,
                        scheduler_type="slurm",
                    )
                )
                # Read output
                result_path = self.working_dir / f"{job_name}_result.json"
                if result_path.exists():
                    result = json.loads(result_path.read_text())
                else:
                    result = {"status": "completed", "job_id": job_id}
                return result

            elif slurm_status in ("FAILED", "CANCELLED", "TIMEOUT"):
                err_path = self.working_dir / f"{job_name}.err"
                err_msg = err_path.read_text() if err_path.exists() else f"Job {slurm_status}"
                self._report_progress(
                    ExecutionState(
                        job_id=job_id,
                        status="FAILED" if slurm_status != "CANCELLED" else "CANCELLED",
                        current_phase=phase,
                        progress_pct=0.0,
                        started_at=start,
                        error_message=err_msg,
                        logs=logs,
                        scheduler_type="slurm",
                    )
                )
                error_message = f"SLURM job {job_id} {slurm_status}: {err_msg}"
                if raise_on_error:
                    raise RuntimeError(error_message)
                return {"status": "failed", "job_id": job_id, "error": error_message}

            # Otherwise: PENDING, etc. — keep polling

    async def _cancel_job(self, job_id: str) -> None:
        """Cancel a running SLURM job."""
        proc = await asyncio.create_subprocess_exec(
            "scancel", job_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()


class NextflowRunner(BaseScheduler):
    """Execute skills via Nextflow workflow engine."""

    def __init__(
        self,
        working_dir: Optional[Path] = None,
        config_file: Optional[Path] = None,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        pubsub: Optional[ExecutionPubSub] = None,
        weblog_url: Optional[str] = None,
        provenance_recorder: Optional[Any] = None,
    ):
        super().__init__(working_dir, progress_callback=progress_callback, pubsub=pubsub)
        self.config_file = config_file
        self.weblog_url = weblog_url
        self._running: Dict[str, asyncio.subprocess.Process] = {}

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("nextflow") is not None

    async def terminate(self, job_id: str) -> bool:
        """Kill a running Nextflow process."""
        proc = self._running.pop(job_id, None)
        if proc is None or proc.returncode is not None:
            return False
        try:
            proc.kill()
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return True
        except (asyncio.TimeoutError, ProcessLookupError):
            return False

    def _build_process_config(self, skill: SkillDefinition) -> str:
        """Generate Nextflow process configuration."""
        resources = skill.runtime.resources
        mem_gb = self._parse_memory_to_gb(resources.memory)
        cpus = resources.cpu
        time_nf = self._to_nextflow_time(resources.time)

        return f"""
process {{
    memory = {mem_gb}.GB
    cpus = {cpus}
    time = {time_nf}
}}
"""

    def _to_nextflow_time(self, time_str: str) -> str:
        """Convert time string to Nextflow duration format."""
        time_str = str(time_str).strip().lower()
        if time_str.endswith("d"):
            return f"{time_str[:-1]}.d"
        elif time_str.endswith("h"):
            return f"{time_str[:-1]}.h"
        elif time_str.endswith("m"):
            return f"{time_str[:-1]}.m"
        elif time_str.endswith("s"):
            return f"{time_str[:-1]}.s"
        else:
            return f"{time_str}.m"

    def _parse_memory_to_gb(self, mem_str: str) -> int:
        """Parse memory string to GB."""
        mem_str = str(mem_str).strip().upper()
        if mem_str.endswith("GB") or mem_str.endswith("G"):
            return int(float(mem_str.rstrip("BG").rstrip("B").rstrip("G")))
        elif mem_str.endswith("MB") or mem_str.endswith("M"):
            return max(1, int(float(mem_str.rstrip("MB").rstrip("B").rstrip("M")) / 1024))
        elif mem_str.endswith("TB") or mem_str.endswith("T"):
            return int(float(mem_str.rstrip("TB").rstrip("B").rstrip("T")) * 1024)
        else:
            return int(float(mem_str))

    def _build_nextflow_script(
        self,
        skill: SkillDefinition,
        code: str,
        inputs: Dict[str, Any],
    ) -> str:
        """Generate a minimal Nextflow script for a single process."""
        process_name = skill.id.replace("-", "_").replace(".", "_")

        exec_type = skill.runtime.type.lower()
        if exec_type in ("r", "mixed"):
            primary = skill.metadata.get("primary_tool", "").lower()
            r_tools = {"seurat", "monocle3", "archr", "signac", "harmony", "cellchat"}
            is_r = exec_type == "r" or primary in r_tools
            script_body = self._build_r_process(code, inputs) if is_r else self._build_python_process(code, inputs)
        else:
            script_body = self._build_python_process(code, inputs)

        header = "#!/usr/bin/env nextflow\n\n"
        header += "nextflow.enable.dsl = 2\n\n"
        header += f"process {process_name} {{\n"
        config = self._build_process_config(skill)
        body = '\n    output:\n'
        body += '        path "result.json"\n\n'
        body += '    script:\n'
        body += '    """\n'
        body += script_body + '\n'
        body += '    """\n'
        footer = '}\n\n'
        footer += f'workflow {{\n    {process_name}()\n}}\n'
        return header + config + body + footer

    def _build_python_process(self, code: str, inputs: Dict[str, Any]) -> str:
        """Build a Python script block for Nextflow."""
        inputs_json = json.dumps(inputs)
        return f"""cat << 'EOF' > script.py
import json
inputs = json.loads('{inputs_json}')
locals().update(inputs)
{code}
with open('result.json', 'w') as f:
    json.dump(result if 'result' in locals() else {{}}, f)
EOF
python script.py"""

    def _build_r_process(self, code: str, inputs: Dict[str, Any]) -> str:
        """Build an R script block for Nextflow."""
        inputs_json = json.dumps(inputs)
        return f"""cat << 'EOF' > script.R
library(jsonlite)
skill_inputs <- fromJSON('{inputs_json}', simplifyVector = TRUE)
for (var_name in names(skill_inputs)) {{
  assign(var_name, skill_inputs[[var_name]], envir = .GlobalEnv)
}}
{code}
if (!exists("result")) result <- list()
write_json(result, "result.json", auto_unbox = TRUE)
EOF
Rscript script.R"""

    async def execute(
        self,
        skill: SkillDefinition,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
        resume: bool = True,
    ) -> Dict[str, Any]:
        job_id = self._new_job_id(f"nf_{skill.id}")
        started_at = datetime.now(timezone.utc)

        script = self._build_nextflow_script(skill, code, inputs)

        nf_file = self.working_dir / f"{skill.id.replace('-', '_')}.nf"
        nf_file.write_text(script)

        cmd = [
            "nextflow", "run", str(nf_file),
            "-work-dir", str(self.working_dir / "work"),
        ]
        if resume:
            cmd.append("-resume")
        if self.config_file:
            cmd.extend(["-c", str(self.config_file)])

        trace_file = self.working_dir / f"{skill.id.replace('-', '_')}_trace.txt"
        timeline_file = self.working_dir / f"{skill.id.replace('-', '_')}_timeline.html"
        cmd.extend([
            "-with-trace", str(trace_file),
            "-with-timeline", str(timeline_file),
        ])
        if self.weblog_url:
            cmd.extend(["-with-weblog", self.weblog_url])

        result = await self._run_with_streaming(
            cmd=cmd,
            job_id=job_id,
            current_phase=skill.id,
            started_at=started_at,
            timeout_seconds=timeout_seconds,
            result_path=self.working_dir / "result.json",
        )
        if trace_file.exists():
            result["trace"] = trace_file.read_text()
        if timeline_file.exists():
            result["timeline_path"] = str(timeline_file)
        return result

    async def run_project(
        self,
        nf_file: Path,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
        weblog_url: Optional[str] = None,
        resume: bool = True,
    ) -> Dict[str, Any]:
        """Run a pre-generated Nextflow project/script.

        Args:
            nf_file: Path to the Nextflow script (e.g. main.nf).
            inputs: Input parameters passed via -params-file.
            timeout_seconds: Maximum runtime.
            weblog_url: Optional URL to receive Nextflow weblog events.
            resume: If True, pass ``-resume`` to reuse cached task results.

        Returns:
            Execution result dict.
        """
        job_id = self._new_job_id("nf_project")
        started_at = datetime.now(timezone.utc)

        cmd = [
            "nextflow",
            "run",
            str(nf_file),
            "-work-dir",
            str(self.working_dir / "work"),
        ]
        if resume:
            cmd.append("-resume")
        if self.config_file:
            cmd.extend(["-c", str(self.config_file)])

        # Write inputs as params file
        params_file = self.working_dir / "params.json"
        params_file.write_text(json.dumps(inputs))
        cmd.extend(["-params-file", str(params_file)])

        # Enable native Nextflow monitoring
        trace_file = self.working_dir / "trace.txt"
        timeline_file = self.working_dir / "timeline.html"
        cmd.extend([
            "-with-trace", str(trace_file),
            "-with-timeline", str(timeline_file),
        ])
        if weblog_url or self.weblog_url:
            cmd.extend(["-with-weblog", str(weblog_url or self.weblog_url)])

        result = await self._run_with_streaming(
            cmd=cmd,
            job_id=job_id,
            current_phase="workflow",
            started_at=started_at,
            timeout_seconds=timeout_seconds,
        )
        if trace_file.exists():
            result["trace"] = trace_file.read_text()
        if timeline_file.exists():
            result["timeline_path"] = str(timeline_file)
        return result

    async def _run_with_streaming(
        self,
        cmd: List[str],
        job_id: str,
        current_phase: str,
        started_at: datetime,
        timeout_seconds: float,
        result_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Run a Nextflow command and stream stdout/stderr progress updates."""
        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status="PENDING",
                current_phase=current_phase,
                progress_pct=5.0,
                started_at=started_at,
                scheduler_type="nextflow",
            )
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.working_dir),
        )
        self._running[job_id] = proc

        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status="RUNNING",
                current_phase=current_phase,
                progress_pct=25.0,
                started_at=started_at,
                scheduler_type="nextflow",
            )
        )

        stdout_lines: List[str] = []
        stderr_lines: List[str] = []

        async def _read_stream(stream, lines: List[str]) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                lines.append(line.decode(errors="replace").rstrip("\n"))

        stdout_task = asyncio.create_task(_read_stream(proc.stdout, stdout_lines))
        stderr_task = asyncio.create_task(_read_stream(proc.stderr, stderr_lines))

        async def _progress_reporter() -> None:
            while proc.returncode is None:
                await asyncio.sleep(2.0)
                if proc.returncode is not None:
                    break
                self._report_progress(
                    ExecutionState(
                        job_id=job_id,
                        status="RUNNING",
                        current_phase=current_phase,
                        progress_pct=min(25.0 + len(stdout_lines) * 2.0, 90.0),
                        started_at=started_at,
                        logs=(stdout_lines + stderr_lines)[-50:],
                        scheduler_type="nextflow",
                    )
                )

        reporter_task = asyncio.create_task(_progress_reporter())

        try:
            try:
                await asyncio.wait_for(proc.wait(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                if proc.returncode is None:
                    proc.kill()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        pass
                self._report_progress(
                    ExecutionState(
                        job_id=job_id,
                        status="CANCELLED",
                        current_phase=current_phase,
                        progress_pct=0.0,
                        started_at=started_at,
                        error_message=f"Timed out after {timeout_seconds}s",
                        scheduler_type="nextflow",
                    )
                )
                raise TimeoutError(f"Nextflow execution timed out after {timeout_seconds}s")

            await asyncio.gather(stdout_task, stderr_task)

            if proc.returncode != 0:
                error_message = "\n".join(stderr_lines)
                self._report_progress(
                    ExecutionState(
                        job_id=job_id,
                        status="FAILED",
                        current_phase=current_phase,
                        progress_pct=0.0,
                        started_at=started_at,
                        error_message=error_message,
                        logs=stdout_lines,
                        scheduler_type="nextflow",
                    )
                )
                raise RuntimeError(f"Nextflow failed: {error_message}")

            self._report_progress(
                ExecutionState(
                    job_id=job_id,
                    status="COMPLETED",
                    current_phase=current_phase,
                    progress_pct=100.0,
                    started_at=started_at,
                    logs=stdout_lines,
                    scheduler_type="nextflow",
                )
            )

            if result_path is not None and result_path.exists():
                return json.loads(result_path.read_text())

            return {"raw_output": "\n".join(stdout_lines)}
        finally:
            self._running.pop(job_id, None)
            reporter_task.cancel()
            try:
                await reporter_task
            except asyncio.CancelledError:
                pass

    async def run_plan(
        self,
        plan,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
        weblog_url: Optional[str] = None,
        resume: bool = True,
    ) -> Dict[str, Any]:
        """Translate a PlanResult into a Nextflow project and run it.

        Args:
            plan: A PlanResult (or any object with a ``phases`` attribute).
            inputs: Top-level inputs for the workflow.
            timeout_seconds: Maximum runtime.
            weblog_url: Optional URL for Nextflow weblog events.
            resume: If True, pass ``-resume`` to reuse cached task results.

        Returns:
            Execution result dict including the generated ``main.nf`` path.
        """
        from homomics_lab.hpc.nf_translator import SimpleNFTranslator

        translator = SimpleNFTranslator(working_dir=self.working_dir)
        nf_file = translator.translate(plan, inputs)
        result = await self.run_project(
            nf_file,
            inputs,
            timeout_seconds=timeout_seconds,
            weblog_url=weblog_url or self.weblog_url,
            resume=resume,
        )
        result["nf_file"] = str(nf_file)
        return result

    async def run_pipeline_dir(
        self,
        pipeline_dir: Path,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
        weblog_url: Optional[str] = None,
        profiles: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        resume: bool = True,
    ) -> Dict[str, Any]:
        """Run a full Nextflow pipeline directory (e.g. nf-core pipeline).

        Unlike ``run_project``, this keeps all relative imports/modules intact
        by pointing Nextflow at the directory instead of copying ``main.nf``.
        """
        job_id = self._new_job_id("nf_pipeline")
        started_at = datetime.now(timezone.utc)

        main_nf = pipeline_dir / "main.nf"
        if not main_nf.exists():
            raise FileNotFoundError(f"No main.nf found in {pipeline_dir}")

        cmd = [
            "nextflow",
            "run",
            str(pipeline_dir),
            "-work-dir",
            str(self.working_dir / "work"),
        ]
        if resume:
            cmd.append("-resume")
        if self.config_file:
            cmd.extend(["-c", str(self.config_file)])
        if profiles:
            cmd.extend(["-profile", ",".join(profiles)])

        params_file = self.working_dir / "params.json"
        params_file.write_text(json.dumps(inputs))
        cmd.extend(["-params-file", str(params_file)])

        trace_file = self.working_dir / "trace.txt"
        timeline_file = self.working_dir / "timeline.html"
        cmd.extend([
            "-with-trace", str(trace_file),
            "-with-timeline", str(timeline_file),
        ])
        if weblog_url or self.weblog_url:
            cmd.extend(["-with-weblog", str(weblog_url or self.weblog_url)])

        result = await self._run_with_streaming(
            cmd=cmd,
            job_id=job_id,
            current_phase="workflow",
            started_at=started_at,
            timeout_seconds=timeout_seconds,
        )
        if trace_file.exists():
            result["trace"] = trace_file.read_text()
        if timeline_file.exists():
            result["timeline_path"] = str(timeline_file)
        result["pipeline_dir"] = str(pipeline_dir)

        # Auto-ingest nf-core results into the workspace when a project is known.
        if result.get("status") == "completed" and project_id:
            try:
                from homomics_lab.workspace.manager import WorkspaceManager
                from homomics_lab.nfcore_results import NFCoreResultIngester

                outdir = None
                if isinstance(inputs, dict):
                    outdir = inputs.get("outdir")
                if outdir:
                    output_dir = Path(outdir)
                else:
                    output_dir = self.working_dir / "results"
                    if not output_dir.exists():
                        output_dir = self.working_dir

                workspace = WorkspaceManager(
                    base_dir=settings.data_dir,
                    project_id=project_id,
                )
                ingester = NFCoreResultIngester(workspace)
                artifacts = ingester.ingest(
                    output_dir=output_dir,
                    task_id=job_id,
                    source_task=str(pipeline_dir.name),
                )
                result["ingested_artifacts"] = artifacts
                multiqc_summary = ingester.ingest_multiqc_summary(output_dir)
                if multiqc_summary:
                    result["multiqc_summary"] = multiqc_summary
            except Exception as exc:
                # Ingestion failure must not mask pipeline success.
                result["ingestion_error"] = str(exc)

        return result

    async def run_template(
        self,
        template_path,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
        weblog_url: Optional[str] = None,
        resume: bool = True,
    ) -> Dict[str, Any]:
        """Run a curated Nextflow template with user inputs.

        Args:
            template_path: Path to the template ``main.nf``.
            inputs: Top-level inputs for the workflow (becomes params).
            timeout_seconds: Maximum runtime.
            weblog_url: Optional URL for Nextflow weblog events.
            resume: If True, pass ``-resume`` to reuse cached task results.

        Returns:
            Execution result dict.
        """
        import shutil

        project_dir = self.working_dir / "nf_project"
        if project_dir.exists():
            shutil.rmtree(project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)

        nf_file = project_dir / "main.nf"
        nf_file.write_text(template_path.read_text(), encoding="utf-8")

        result = await self.run_project(
            nf_file,
            inputs,
            timeout_seconds=timeout_seconds,
            weblog_url=weblog_url or self.weblog_url,
            resume=resume,
        )
        result["nf_file"] = str(nf_file)
        result["template"] = str(template_path)
        return result


def get_scheduler(
    executor_type: str = "auto",
    working_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[ExecutionState], None]] = None,
    pubsub: Optional[ExecutionPubSub] = None,
    **kwargs,
) -> BaseScheduler:
    """Factory function to get the appropriate scheduler.

    Args:
        executor_type: "auto", "local", "slurm", or "nextflow"
        working_dir: Working directory for job files
        progress_callback: Optional callback for ExecutionState updates
        pubsub: Optional pubsub instance for execution events
        **kwargs: Additional scheduler-specific options. Supported:
            - partition: SLURM partition
            - config_file: Nextflow config file
            - weblog_url: URL for Nextflow weblog events
            - plan: PlanResult for auto backend selection
            - data_state: DataState for auto backend selection

    Returns:
        BaseScheduler instance
    """
    working_dir = working_dir or Path.cwd()
    scheduler_kwargs: Dict[str, Any] = {
        "working_dir": working_dir,
        "progress_callback": progress_callback,
        "pubsub": pubsub,
        "provenance_recorder": kwargs.get("provenance_recorder"),
    }

    resolved_type = executor_type
    if executor_type == "auto":
        plan = kwargs.get("plan")
        data_state = kwargs.get("data_state")
        if plan is not None and data_state is not None:
            from homomics_lab.hpc.router import select_execution_backend

            resolved_type = select_execution_backend(plan, data_state)
        elif SlurmScheduler.is_available():
            resolved_type = "slurm"
        else:
            resolved_type = "local"

    if resolved_type == "local":
        return LocalScheduler(**scheduler_kwargs)

    elif resolved_type == "slurm":
        partition = kwargs.get("partition")
        return SlurmScheduler(partition=partition, **scheduler_kwargs)

    elif resolved_type == "nextflow":
        config_file = kwargs.get("config_file")
        weblog_url = kwargs.get("weblog_url")
        return NextflowRunner(
            config_file=config_file,
            weblog_url=weblog_url,
            **scheduler_kwargs,
        )

    else:
        raise ValueError(f"Unknown executor type: {resolved_type}")
