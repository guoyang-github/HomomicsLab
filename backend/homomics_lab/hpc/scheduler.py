"""HPC and workflow execution schedulers for HomomicsLab.

Supports three execution backends:
- LocalScheduler: Direct subprocess execution (default, for dev/small jobs)
- SlurmScheduler: SLURM cluster job submission (for HPC environments)
- NextflowRunner: Nextflow workflow engine (for complex pipelines)
"""

import asyncio
import json
import shutil
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from homomics_lab.hpc.pubsub import ExecutionPubSub, get_default_pubsub
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.skills.sandbox import LocalSandbox


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
        working_dir: Path = None,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        pubsub: Optional[ExecutionPubSub] = None,
    ):
        self.working_dir = working_dir or Path.cwd()
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
        working_dir: Path = None,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        pubsub: Optional[ExecutionPubSub] = None,
    ):
        super().__init__(working_dir, progress_callback=progress_callback, pubsub=pubsub)
        self.sandbox = LocalSandbox(working_dir=self.working_dir)

    @classmethod
    def is_available(cls) -> bool:
        return True

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

        try:
            if exec_type == "r":
                result = await self.sandbox.run_r(
                    code, inputs, timeout_seconds=timeout_seconds
                )
            else:
                result = await self.sandbox.run_python(
                    code, inputs, timeout_seconds=timeout_seconds
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
        working_dir: Path = None,
        partition: str = None,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        pubsub: Optional[ExecutionPubSub] = None,
    ):
        super().__init__(working_dir, progress_callback=progress_callback, pubsub=pubsub)
        self.partition = partition

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("sbatch") is not None

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

        # For MVP, poll until job completes (fire-and-forget for async workflows)
        # In production, this would be async with callbacks
        result = await self._poll_job(
            job_id, job_name, timeout_seconds, skill.id, started_at
        )
        return result

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

    async def _poll_job(
        self,
        job_id: str,
        job_name: str,
        timeout_seconds: float,
        phase: str = "",
        started_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Poll SLURM job until completion."""
        start = started_at or datetime.now(timezone.utc)
        poll_interval = 5  # seconds
        status_progress = {
            "PENDING": 10.0,
            "RUNNING": 50.0,
            "COMPLETING": 90.0,
        }

        while True:
            await asyncio.sleep(poll_interval)

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            if elapsed > timeout_seconds:
                # Cancel job on timeout
                await self._cancel_job(job_id)
                self._report_progress(
                    ExecutionState(
                        job_id=job_id,
                        status="CANCELLED",
                        current_phase=phase,
                        progress_pct=0.0,
                        started_at=start,
                        error_message=f"Timed out after {timeout_seconds}s",
                        scheduler_type="slurm",
                    )
                )
                raise TimeoutError(f"SLURM job {job_id} timed out after {timeout_seconds}s")

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
                    return json.loads(result_path.read_text())
                return {"status": "completed", "job_id": job_id}

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
                raise RuntimeError(f"SLURM job {job_id} {slurm_status}: {err_msg}")

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
        working_dir: Path = None,
        config_file: Path = None,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        pubsub: Optional[ExecutionPubSub] = None,
    ):
        super().__init__(working_dir, progress_callback=progress_callback, pubsub=pubsub)
        self.config_file = config_file

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("nextflow") is not None

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
    ) -> Dict[str, Any]:
        job_id = self._new_job_id(f"nf_{skill.id}")
        started_at = datetime.now(timezone.utc)

        script = self._build_nextflow_script(skill, code, inputs)

        nf_file = self.working_dir / f"{skill.id.replace('-', '_')}.nf"
        nf_file.write_text(script)

        cmd = ["nextflow", "run", str(nf_file), "-work-dir", str(self.working_dir / "work")]
        if self.config_file:
            cmd.extend(["-c", str(self.config_file)])

        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status="PENDING",
                current_phase=skill.id,
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

        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status="RUNNING",
                current_phase=skill.id,
                progress_pct=25.0,
                started_at=started_at,
                scheduler_type="nextflow",
            )
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            if proc.returncode is None:
                proc.kill()
            self._report_progress(
                ExecutionState(
                    job_id=job_id,
                    status="CANCELLED",
                    current_phase=skill.id,
                    progress_pct=0.0,
                    started_at=started_at,
                    error_message=f"Timed out after {timeout_seconds}s",
                    scheduler_type="nextflow",
                )
            )
            raise TimeoutError(f"Nextflow execution timed out after {timeout_seconds}s")

        logs = stdout.decode().splitlines()

        if proc.returncode != 0:
            error_message = stderr.decode()
            self._report_progress(
                ExecutionState(
                    job_id=job_id,
                    status="FAILED",
                    current_phase=skill.id,
                    progress_pct=0.0,
                    started_at=started_at,
                    error_message=error_message,
                    logs=logs,
                    scheduler_type="nextflow",
                )
            )
            raise RuntimeError(f"Nextflow failed: {error_message}")

        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status="COMPLETED",
                current_phase=skill.id,
                progress_pct=100.0,
                started_at=started_at,
                logs=logs,
                scheduler_type="nextflow",
            )
        )

        # Read result
        result_path = self.working_dir / "result.json"
        if result_path.exists():
            return json.loads(result_path.read_text())

        return {"raw_output": stdout.decode()}

    async def run_project(
        self,
        nf_file: Path,
        inputs: Dict[str, Any],
        timeout_seconds: float = 3600.0,
        weblog_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a pre-generated Nextflow project/script.

        Args:
            nf_file: Path to the Nextflow script (e.g. main.nf).
            inputs: Input parameters passed via -params-file.
            timeout_seconds: Maximum runtime.
            weblog_url: Optional URL to receive Nextflow weblog events.

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
        if weblog_url:
            cmd.extend(["-with-weblog", weblog_url])

        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status="PENDING",
                current_phase="workflow",
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

        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status="RUNNING",
                current_phase="workflow",
                progress_pct=25.0,
                started_at=started_at,
                scheduler_type="nextflow",
            )
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            if proc.returncode is None:
                proc.kill()
            self._report_progress(
                ExecutionState(
                    job_id=job_id,
                    status="CANCELLED",
                    current_phase="workflow",
                    progress_pct=0.0,
                    started_at=started_at,
                    error_message=f"Timed out after {timeout_seconds}s",
                    scheduler_type="nextflow",
                )
            )
            raise TimeoutError(f"Nextflow execution timed out after {timeout_seconds}s")

        logs = stdout.decode().splitlines()

        if proc.returncode != 0:
            error_message = stderr.decode()
            self._report_progress(
                ExecutionState(
                    job_id=job_id,
                    status="FAILED",
                    current_phase="workflow",
                    progress_pct=0.0,
                    started_at=started_at,
                    error_message=error_message,
                    logs=logs,
                    scheduler_type="nextflow",
                )
            )
            raise RuntimeError(f"Nextflow failed: {error_message}")

        self._report_progress(
            ExecutionState(
                job_id=job_id,
                status="COMPLETED",
                current_phase="workflow",
                progress_pct=100.0,
                started_at=started_at,
                logs=logs,
                scheduler_type="nextflow",
            )
        )

        # Collect monitoring artifacts
        result: Dict[str, Any] = {"raw_output": stdout.decode()}
        if trace_file.exists():
            result["trace"] = trace_file.read_text()
        if timeline_file.exists():
            result["timeline_path"] = str(timeline_file)
        return result


def get_scheduler(
    executor_type: str = "auto",
    working_dir: Path = None,
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
        **kwargs: Additional scheduler-specific options

    Returns:
        BaseScheduler instance
    """
    working_dir = working_dir or Path.cwd()
    scheduler_kwargs = {
        "working_dir": working_dir,
        "progress_callback": progress_callback,
        "pubsub": pubsub,
    }

    if executor_type == "local":
        return LocalScheduler(**scheduler_kwargs)

    elif executor_type == "slurm":
        partition = kwargs.get("partition")
        return SlurmScheduler(partition=partition, **scheduler_kwargs)

    elif executor_type == "nextflow":
        config_file = kwargs.get("config_file")
        return NextflowRunner(config_file=config_file, **scheduler_kwargs)

    elif executor_type == "auto":
        # Prefer SLURM if available, fall back to local
        # Nextflow is only used when explicitly requested (not suitable for single-skill execution)
        if SlurmScheduler.is_available():
            return SlurmScheduler(
                partition=kwargs.get("partition"), **scheduler_kwargs
            )
        else:
            return LocalScheduler(**scheduler_kwargs)

    else:
        raise ValueError(f"Unknown executor type: {executor_type}")
