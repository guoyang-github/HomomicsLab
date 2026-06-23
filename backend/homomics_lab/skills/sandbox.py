"""Skill sandbox implementations.

Provides a uniform abstraction for executing Python/R skill code and shell
commands with varying isolation levels:

- ``LocalSandbox``: subprocess with resource limits (dev/default)
- ``BubblewrapSandbox``: Linux namespace filesystem/network isolation using ``bwrap``
- ``ContainerSandbox``: Docker/Podman container isolation

Selection is controlled by ``settings.skill_sandbox_backend`` (``auto`` picks
the most secure available backend).
"""

import asyncio
import json
import shutil
import sys
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import resource as _resource_module
except ImportError:
    _resource_module = None

from homomics_lab.config import settings
from homomics_lab.hpc.state import ExecutionState


class Sandbox(ABC):
    """Abstract protocol for skill execution sandboxes."""

    def __init__(self, working_dir: Path):
        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Return True if this sandbox backend can be used on the host."""
        pass

    @abstractmethod
    async def run_python(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        job_id: Optional[str] = None,
        current_phase: Optional[str] = None,
        python_path: Optional[str] = None,
        unrestricted: bool = False,
    ) -> Dict[str, Any]:
        """Execute Python code and return its result dictionary."""
        pass

    @abstractmethod
    async def run_r(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        job_id: Optional[str] = None,
        current_phase: Optional[str] = None,
        r_executable: Optional[str] = None,
        r_library_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute R code and return its result dictionary."""
        pass

    @abstractmethod
    async def run_command(
        self,
        command: str,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 30.0,
    ) -> str:
        """Run a shell command and return stdout/stderr text."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about this sandbox backend for provenance."""
        pass

    @staticmethod
    def create(
        backend: str,
        working_dir: Path,
        container_image: Optional[str] = None,
        exec_type: Optional[str] = None,
    ) -> "Sandbox":
        """Factory for sandboxes.

        Args:
            backend: ``auto``, ``local``, ``bubblewrap``, ``container``.
            working_dir: Directory for inputs/outputs.
            container_image: Image for ``container`` backend.
            exec_type: ``python`` or ``r``; used to pick a default container image.
        """
        if backend == "auto":
            # Prefer container isolation when available, then bwrap, then local.
            for cls in (ContainerSandbox, BubblewrapSandbox, LocalSandbox):
                candidate = cls(
                    working_dir,
                    container_image=container_image,
                    exec_type=exec_type,
                )
                if candidate.is_available():
                    return candidate
            return LocalSandbox(working_dir)

        mapping: Dict[str, type] = {
            "local": LocalSandbox,
            "bubblewrap": BubblewrapSandbox,
            "container": ContainerSandbox,
        }
        try:
            return mapping[backend](
                working_dir,
                container_image=container_image,
                exec_type=exec_type,
            )
        except KeyError as exc:
            raise ValueError(f"Unknown sandbox backend: {backend}") from exc


class LocalSandbox(Sandbox):
    """Execute Python or R code in a subprocess with resource limits."""

    def __init__(
        self,
        working_dir: Optional[Path] = None,
        container_image: Optional[str] = None,
        exec_type: Optional[str] = None,
    ):
        super().__init__(working_dir or Path(tempfile.mkdtemp()))

    @classmethod
    def is_available(cls) -> bool:
        return True

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "backend": "local",
            "container_image": None,
            "container_digest": None,
            "resource_limits": {
                "memory_mb": 2048,
                "cpu_time_seconds": 120,
                "file_size_mb": 100,
            },
        }

    async def run_python(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        job_id: Optional[str] = None,
        current_phase: Optional[str] = None,
        python_path: Optional[str] = None,
        unrestricted: bool = False,
    ) -> Dict[str, Any]:
        """Execute Python code in a subprocess with resource limits."""
        inputs_json = json.dumps(inputs)
        script = self._build_python_script(code, inputs, unrestricted=unrestricted)

        script_path = self.working_dir / "__skill_script__.py"
        script_path.write_text(script)

        result_path = self.working_dir / "__skill_result__.json"
        executable = python_path or "python"

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                executable, str(script_path), inputs_json,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.working_dir),
            )

            stdout_lines, stderr_lines = await self._stream_subprocess(
                proc=proc,
                timeout_seconds=timeout_seconds,
                progress_callback=progress_callback,
                job_id=job_id,
                current_phase=current_phase,
            )

            if proc.returncode != 0:
                error_text = "\n".join(stderr_lines)
                raise RuntimeError(f"Skill execution failed: {error_text}")

            if not result_path.exists():
                return {"raw_output": "\n".join(stdout_lines)}

            result_text = result_path.read_text()
            # Limit result size to 10MB
            if len(result_text) > 10 * 1024 * 1024:
                raise RuntimeError("Skill result exceeds 10MB limit")

            return json.loads(result_text)

        finally:
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except (asyncio.TimeoutError, ProcessLookupError):
                    pass

    async def run_r(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        job_id: Optional[str] = None,
        current_phase: Optional[str] = None,
        r_executable: Optional[str] = None,
        r_library_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute R code in a subprocess with resource limits."""
        extra_libs = [r_library_path] if r_library_path else []
        script = self._build_r_script(code, inputs, extra_library_paths=extra_libs)

        script_path = self.working_dir / "__skill_script__.R"
        script_path.write_text(script)

        result_path = self.working_dir / "__skill_result__.json"
        executable = r_executable or "Rscript"

        def _set_limits():
            """Set resource limits for the child process."""
            if _resource_module is None:
                return
            try:
                # 2048 MB memory limit
                _resource_module.setrlimit(
                    _resource_module.RLIMIT_AS, (2048 * 1024 * 1024, 2048 * 1024 * 1024)
                )
                # 120 seconds CPU time limit
                _resource_module.setrlimit(_resource_module.RLIMIT_CPU, (120, 120))
                # 100 MB file size limit
                _resource_module.setrlimit(
                    _resource_module.RLIMIT_FSIZE, (100 * 1024 * 1024, 100 * 1024 * 1024)
                )
            except (OSError, ValueError):
                pass

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                executable, str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.working_dir),
                preexec_fn=_set_limits,
            )

            stdout_lines, stderr_lines = await self._stream_subprocess(
                proc=proc,
                timeout_seconds=timeout_seconds,
                progress_callback=progress_callback,
                job_id=job_id,
                current_phase=current_phase,
            )

            if proc.returncode != 0:
                error_text = "\n".join(stderr_lines)
                raise RuntimeError(f"R skill execution failed: {error_text}")

            if not result_path.exists():
                return {"raw_output": "\n".join(stdout_lines)}

            result_text = result_path.read_text()
            # Limit result size to 10MB
            if len(result_text) > 10 * 1024 * 1024:
                raise RuntimeError("Skill result exceeds 10MB limit")

            return json.loads(result_text)

        finally:
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except (asyncio.TimeoutError, ProcessLookupError):
                    pass

    async def run_command(
        self,
        command: str,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 30.0,
    ) -> str:
        """Run a shell command locally."""
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd or self.working_dir),
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds,
        )
        output = stdout.decode(errors="replace")
        if stderr:
            output += "\n" + stderr.decode(errors="replace")
        return output.strip()

    async def _stream_subprocess(
        self,
        proc: asyncio.subprocess.Process,
        timeout_seconds: float,
        progress_callback: Optional[Callable[[ExecutionState], None]],
        job_id: Optional[str],
        current_phase: Optional[str],
    ) -> tuple[List[str], List[str]]:
        """Read stdout/stderr incrementally and optionally report progress."""
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
            if progress_callback is None or proc.stdout is None:
                return
            while not proc.returncode == 0 and not proc.stdout.at_eof():
                await asyncio.sleep(1.0)
                if proc.returncode is not None:
                    break
                logs = (stdout_lines + stderr_lines)[-50:]
                progress_callback(
                    ExecutionState(
                        job_id=job_id or "unknown",
                        status="RUNNING",
                        current_phase=current_phase,
                        progress_pct=min(10.0 + len(stdout_lines) * 2.0, 90.0),
                        logs=logs,
                        scheduler_type="local",
                    )
                )

        reporter_task = asyncio.create_task(_progress_reporter())

        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            reporter_task.cancel()
            try:
                await reporter_task
            except asyncio.CancelledError:
                pass
            if proc.returncode is None:
                proc.kill()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
            raise TimeoutError(f"Skill execution timed out after {timeout_seconds}s")

        reporter_task.cancel()
        try:
            await reporter_task
        except asyncio.CancelledError:
            pass

        await asyncio.gather(stdout_task, stderr_task)
        return stdout_lines, stderr_lines

    _RESOURCE_LIMITS_SNIPPET = """\
try:
    import resource
    # 2048 MB memory limit (statsmodels/patsy imports need >512 MB)
    resource.setrlimit(resource.RLIMIT_AS, (2048 * 1024 * 1024, 2048 * 1024 * 1024))
    # 120 seconds CPU time limit
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    # 100 MB file size limit
    resource.setrlimit(resource.RLIMIT_FSIZE, (100 * 1024 * 1024, 100 * 1024 * 1024))
except Exception:
    pass
"""

    def _build_python_script(self, code: str, inputs: Dict[str, Any], unrestricted: bool = False) -> str:
        inputs_json = json.dumps(inputs)
        limits = self._RESOURCE_LIMITS_SNIPPET

        if unrestricted:
            return f"""import json

{limits}
# Inject inputs
__inputs__ = json.loads({repr(inputs_json)})
locals().update(__inputs__)

# Run skill code
{code}

# Serialize result
if 'result' not in locals():
    result = {{}}

with open('__skill_result__.json', 'w') as f:
    json.dump(result, f)
"""

        return f"""import json
import sys
import types

{limits}
# Delete dangerous modules if they were pre-loaded
for _mod in ['os', 'subprocess', 'socket', 'urllib', 'http', 'ftplib',
              'telnetlib', 'smtplib', 'poplib', 'imaplib', 'nntplib',
              'ssl', 'importlib', 'ctypes', 'mmap']:
    if _mod in sys.modules:
        del sys.modules[_mod]

# Block dangerous imports
_BLOCKED = frozenset(['os', 'subprocess', 'socket', 'urllib', 'http', 'ftplib',
                      'telnetlib', 'smtplib', 'poplib', 'imaplib', 'nntplib',
                      'ssl', 'importlib', 'ctypes', 'mmap', 'builtins'])

_original_import = __builtins__.__import__

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    base = name.split('.')[0]
    if base in _BLOCKED:
        raise ImportError(f"Module '{{name}}' is restricted in skill sandbox")
    return _original_import(name, globals, locals, fromlist, level)

__builtins__.__import__ = _safe_import

# Also restrict __import__ attribute access
class _RestrictedBuiltins(dict):
    def __getitem__(self, key):
        if key == '__import__':
            return _safe_import
        return super().__getitem__(key)

# Inject inputs
__inputs__ = json.loads({repr(inputs_json)})
locals().update(__inputs__)

# Run skill code
{code}

# Serialize result
if 'result' not in locals():
    result = {{}}

with open('__skill_result__.json', 'w') as f:
    json.dump(result, f)
"""

    def _build_r_script(
        self, code: str, inputs: Dict[str, Any], extra_library_paths: Optional[List[str]] = None
    ) -> str:
        inputs_json = json.dumps(inputs)
        lib_paths = extra_library_paths or []
        lib_paths_setup = ""
        if lib_paths:
            paths_str = ", ".join(f'"{p}"' for p in lib_paths)
            lib_paths_setup = f".libPaths(c({paths_str}, .libPaths()))\n"

        template = """# Load inputs from JSON
{lib_paths_setup}inputs_json <- '{inputs_json}'

# Try jsonlite first, fall back to basic parsing
if (requireNamespace("jsonlite", quietly = TRUE)) {{
  skill_inputs <- jsonlite::fromJSON(inputs_json, simplifyVector = TRUE)
}} else {{
  # Fallback: use Python to parse JSON and generate R assignments
  # This should not happen in normal operation
  stop("jsonlite package is required for skill execution")
}}

# Inject inputs into the environment
for (var_name in names(skill_inputs)) {{
  assign(var_name, skill_inputs[[var_name]], envir = .GlobalEnv)
}}

# Run skill code
{code}

# Serialize result
if (!exists("result")) {{
  result <- list()
}}

if (requireNamespace("jsonlite", quietly = TRUE)) {{
  jsonlite::write_json(result, "__skill_result__.json", auto_unbox = TRUE, pretty = TRUE)
}} else {{
  # Basic fallback for simple types
  result_str <- paste0("{{", paste0(sapply(names(result), function(k) paste0('"', k, '": "', as.character(result[[k]]), '"')), collapse = ", "), "}}")
  writeLines(result_str, "__skill_result__.json")
}}
"""
        return template.format(
            lib_paths_setup=lib_paths_setup,
            inputs_json=inputs_json.replace("'", "\\'"),
            code=code,
        )


class BubblewrapSandbox(Sandbox):
    """Filesystem/network isolation via Linux user namespaces (``bwrap``).

    Uses the host Python/R interpreter and installed packages, but restricts
    the process to a read-only root filesystem and a writable working directory.
    """

    def __init__(
        self,
        working_dir: Path,
        container_image: Optional[str] = None,
        exec_type: Optional[str] = None,
    ):
        super().__init__(working_dir)
        self._bwrap = shutil.which("bwrap")

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("bwrap") is not None

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "backend": "bubblewrap",
            "container_image": None,
            "container_digest": None,
            "bwrap_path": self._bwrap,
        }

    def _base_args(self, cwd: Path) -> List[str]:
        """Build the shared bubblewrap argument list."""
        return [
            str(self._bwrap),
            "--ro-bind", "/", "/",
            "--bind", str(self.working_dir), "/work",
            "--dir", "/tmp",
            "--proc", "/proc",
            "--dev", "/dev",
            "--unshare-user", "--unshare-ipc", "--unshare-pid",
            "--unshare-net", "--unshare-uts",
            "--chdir", "/work",
        ]

    async def run_python(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        job_id: Optional[str] = None,
        current_phase: Optional[str] = None,
        python_path: Optional[str] = None,
        unrestricted: bool = False,
    ) -> Dict[str, Any]:
        inputs_json = json.dumps(inputs)
        script = LocalSandbox(self.working_dir)._build_python_script(code, inputs, unrestricted=unrestricted)
        script_path = self.working_dir / "__skill_script__.py"
        script_path.write_text(script)

        result_path = self.working_dir / "__skill_result__.json"
        interpreter = python_path if python_path and python_path.startswith("/") else "python"
        args = self._base_args(self.working_dir) + [
            interpreter, "/work/__skill_script__.py", inputs_json,
        ]
        return await self._run_in_sandbox(
            args,
            result_path,
            timeout_seconds=timeout_seconds,
            progress_callback=progress_callback,
            job_id=job_id,
            current_phase=current_phase,
        )

    async def run_r(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        job_id: Optional[str] = None,
        current_phase: Optional[str] = None,
        r_executable: Optional[str] = None,
        r_library_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        extra_libs = [r_library_path] if r_library_path else []
        script = LocalSandbox(self.working_dir)._build_r_script(code, inputs, extra_library_paths=extra_libs)
        script_path = self.working_dir / "__skill_script__.R"
        script_path.write_text(script)

        result_path = self.working_dir / "__skill_result__.json"
        args = self._base_args(self.working_dir) + [
            r_executable or "Rscript", "/work/__skill_script__.R",
        ]
        return await self._run_in_sandbox(
            args,
            result_path,
            timeout_seconds=timeout_seconds,
            progress_callback=progress_callback,
            job_id=job_id,
            current_phase=current_phase,
        )

    async def run_command(
        self,
        command: str,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 30.0,
    ) -> str:
        run_cwd = Path(cwd or self.working_dir)
        args = self._base_args(run_cwd) + ["/bin/sh", "-c", command]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        output = stdout.decode(errors="replace")
        if stderr:
            output += "\n" + stderr.decode(errors="replace")
        return output.strip()

    async def _run_in_sandbox(
        self,
        args: List[str],
        result_path: Path,
        timeout_seconds: float,
        progress_callback: Optional[Callable[[ExecutionState], None]],
        job_id: Optional[str],
        current_phase: Optional[str],
    ) -> Dict[str, Any]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_lines, stderr_lines = await LocalSandbox(self.working_dir)._stream_subprocess(
            proc=proc,
            timeout_seconds=timeout_seconds,
            progress_callback=progress_callback,
            job_id=job_id,
            current_phase=current_phase,
        )

        if proc.returncode != 0:
            error_text = "\n".join(stderr_lines)
            raise RuntimeError(f"Sandbox execution failed: {error_text}")

        if not result_path.exists():
            return {"raw_output": "\n".join(stdout_lines)}

        result_text = result_path.read_text()
        if len(result_text) > 10 * 1024 * 1024:
            raise RuntimeError("Skill result exceeds 10MB limit")
        return json.loads(result_text)


class ContainerSandbox(Sandbox):
    """Docker/Podman container isolation.

    The container image must contain the skill's language runtime and
    dependencies. Use ``settings.skill_container_image`` to override the
    default ``python:3.10-slim`` image.
    """

    _digest_cache: Dict[str, Optional[str]] = {}

    def __init__(
        self,
        working_dir: Path,
        container_image: Optional[str] = None,
        exec_type: Optional[str] = None,
    ):
        super().__init__(working_dir)
        if container_image is None:
            if exec_type == "r":
                container_image = settings.r_container_image
            else:
                container_image = settings.skill_container_image
        self.container_image = container_image
        self._engine = self._detect_engine()

    @classmethod
    def is_available(cls) -> bool:
        return cls._detect_engine() is not None

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "backend": "container",
            "engine": self._engine,
            "container_image": self.container_image,
            "container_digest": self._get_image_digest(),
            "network": "none",
            "resource_limits": {
                "memory_mb": settings.skill_container_memory_mb,
                "cpus": settings.skill_container_cpus,
                "pids_limit": settings.skill_container_pids_limit,
                "readonly_root": settings.skill_container_readonly_root,
            },
        }

    def _resource_args(self) -> List[str]:
        """Build Docker/Podman resource-limit flags."""
        args = [
            "--memory", f"{settings.skill_container_memory_mb}m",
            "--cpus", str(settings.skill_container_cpus),
            "--pids-limit", str(settings.skill_container_pids_limit),
            "--stop-timeout", "10",
            "--init",
        ]
        if settings.skill_container_readonly_root:
            args.extend(["--read-only", "--tmpfs", "/tmp:noexec,nosuid,size=100m"])
        return args

    def _get_image_digest(self) -> Optional[str]:
        """Return the image digest if available, with caching."""
        if self.container_image in self._digest_cache:
            return self._digest_cache[self.container_image]
        digest = None
        if self._engine is not None:
            try:
                import subprocess

                result = subprocess.run(
                    [self._engine, "inspect", "--format", "{{index .RepoDigests 0}}", self.container_image],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                )
                if result.returncode == 0:
                    digest = result.stdout.decode().strip() or None
            except Exception:
                digest = None
        self._digest_cache[self.container_image] = digest
        return digest

    @staticmethod
    def _detect_engine() -> Optional[str]:
        for engine in ("docker", "podman"):
            if shutil.which(engine):
                return engine
        return None

    async def run_python(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        job_id: Optional[str] = None,
        current_phase: Optional[str] = None,
        python_path: Optional[str] = None,
        unrestricted: bool = False,
    ) -> Dict[str, Any]:
        engine = self._engine
        if engine is None:
            raise RuntimeError("No container engine available")

        # Container paths differ from the host. Remap source_dir and
        # workspace_base to dedicated container mounts so the skill script
        # can find its own package and write outputs to the workspace.
        container_inputs = dict(inputs)
        extra_mounts: List[str] = []

        source_dir = container_inputs.get("source_dir")
        if source_dir:
            extra_mounts.extend(["-v", f"{Path(source_dir).resolve()}:/skill_source:ro"])
            container_inputs["source_dir"] = "/skill_source"

        workspace_base = container_inputs.get("workspace_base")
        if workspace_base:
            extra_mounts.extend(["-v", f"{Path(workspace_base).resolve()}:/workspace"])
            container_inputs["workspace_base"] = "/workspace"

        # Keep host inputs for path remapping after execution.
        host_inputs = inputs
        inputs_json = json.dumps(container_inputs)
        script = LocalSandbox(self.working_dir)._build_python_script(code, container_inputs, unrestricted=unrestricted)
        script_path = self.working_dir / "__skill_script__.py"
        script_path.write_text(script)

        result_path = self.working_dir / "__skill_result__.json"

        # Prefer a cached per-skill venv when available. Venvs created on the
        # host often have a python binary that symlinks to a host interpreter,
        # which does not exist inside the container. We therefore mount the
        # site-packages directory and run the container's own interpreter with
        # PYTHONPATH instead.
        venv_python = "python"
        venv_mount_args: List[str] = []
        pythonpath_args: List[str] = []
        if (
            settings.skill_container_venv_mount
            and python_path
            and Path(python_path).is_file()
        ):
            venv_root = Path(python_path).parent.parent
            py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
            site_packages = venv_root / "lib" / f"python{py_version}" / "site-packages"
            if site_packages.is_dir():
                venv_mount_args = ["-v", f"{site_packages}:/skill_pkgs:ro"]
                pythonpath_args = ["-e", "PYTHONPATH=/skill_pkgs"]
            else:
                # Fallback to mounting the whole venv and hoping the python
                # binary is portable (e.g. built from a portable Python build).
                venv_mount_args = ["-v", f"{venv_root}:/skill_venv:ro"]
                venv_python = "/skill_venv/bin/python"

        args = [
            engine,
            "run", "--rm",
            *self._resource_args(),
            "--network", "none",
            *extra_mounts,
            *venv_mount_args,
            *pythonpath_args,
            "-v", f"{self.working_dir}:/work",
            "-w", "/work",
            self.container_image,
            venv_python, "/work/__skill_script__.py", inputs_json,
        ]
        result = await self._run_in_container(
            args,
            result_path,
            timeout_seconds=timeout_seconds,
            progress_callback=progress_callback,
            job_id=job_id,
            current_phase=current_phase,
        )
        return self._remap_container_paths(result, host_inputs)

    def _remap_container_paths(
        self, result: Any, host_inputs: Dict[str, Any]
    ) -> Any:
        """Translate container paths inside a skill result back to host paths.

        Skills receive ``source_dir`` and ``workspace_base`` as dedicated
        container mounts; any paths they return must be converted back so that
        the host API layer can read and register artifacts.
        """
        mapping: Dict[str, str] = {}
        source_dir = host_inputs.get("source_dir")
        if source_dir:
            mapping["/skill_source"] = str(Path(source_dir).resolve())
        workspace_base = host_inputs.get("workspace_base")
        if workspace_base:
            mapping["/workspace"] = str(Path(workspace_base).resolve())
        mapping["/work"] = str(self.working_dir.resolve())

        def _walk(value: Any) -> Any:
            if isinstance(value, str):
                for container_path, host_path in mapping.items():
                    if value.startswith(container_path):
                        return host_path + value[len(container_path) :]
                return value
            if isinstance(value, dict):
                return {k: _walk(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_walk(v) for v in value]
            return value

        return _walk(result)

    async def run_r(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        job_id: Optional[str] = None,
        current_phase: Optional[str] = None,
        r_executable: Optional[str] = None,
        r_library_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        script = LocalSandbox(self.working_dir)._build_r_script(code, inputs)
        script_path = self.working_dir / "__skill_script__.R"
        script_path.write_text(script)

        result_path = self.working_dir / "__skill_result__.json"
        engine = self._engine
        if engine is None:
            raise RuntimeError("No container engine available")
        args = [
            engine,
            "run", "--rm",
            "--network", "none",
            "-v", f"{self.working_dir}:/work",
            "-w", "/work",
            self.container_image,
            r_executable or "Rscript", "/work/__skill_script__.R",
        ]
        return await self._run_in_container(
            args,
            result_path,
            timeout_seconds=timeout_seconds,
            progress_callback=progress_callback,
            job_id=job_id,
            current_phase=current_phase,
        )

    async def run_command(
        self,
        command: str,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 30.0,
    ) -> str:
        run_cwd = Path(cwd or self.working_dir)
        engine = self._engine
        if engine is None:
            raise RuntimeError("No container engine available")
        args = [
            engine,
            "run", "--rm",
            "--network", "none",
            "-v", f"{run_cwd}:/work",
            "-w", "/work",
            self.container_image,
            "/bin/sh", "-c", command,
        ]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        output = stdout.decode(errors="replace")
        if stderr:
            output += "\n" + stderr.decode(errors="replace")
        return output.strip()

    async def _run_in_container(
        self,
        args: List[str],
        result_path: Path,
        timeout_seconds: float,
        progress_callback: Optional[Callable[[ExecutionState], None]],
        job_id: Optional[str],
        current_phase: Optional[str],
    ) -> Dict[str, Any]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_lines, stderr_lines = await LocalSandbox(self.working_dir)._stream_subprocess(
            proc=proc,
            timeout_seconds=timeout_seconds,
            progress_callback=progress_callback,
            job_id=job_id,
            current_phase=current_phase,
        )

        if proc.returncode != 0:
            error_text = "\n".join(stderr_lines)
            raise RuntimeError(f"Container execution failed: {error_text}")

        if not result_path.exists():
            return {"raw_output": "\n".join(stdout_lines)}

        result_text = result_path.read_text()
        if len(result_text) > 10 * 1024 * 1024:
            raise RuntimeError("Skill result exceeds 10MB limit")
        return json.loads(result_text)
