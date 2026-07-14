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
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from homomics_lab.config import settings
from homomics_lab.hpc.state import ExecutionState

logger = logging.getLogger(__name__)

try:
    import resource as _resource_module
except ImportError:
    _resource_module = None


class Sandbox(ABC):
    """Abstract protocol for skill execution sandboxes."""

    def __init__(self, working_dir: Path):
        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)
        # Track running subprocesses by job_id so execution can be cancelled.
        self._running: Dict[str, asyncio.subprocess.Process] = {}

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
        parent_job_id: Optional[str] = None,
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
        parent_job_id: Optional[str] = None,
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

    async def terminate(self, job_id: Optional[str] = None) -> bool:
        """Terminate a running sandbox subprocess.

        If ``job_id`` is provided, only that subprocess is killed. Otherwise the
        most recently tracked subprocess is terminated. Returns True if a
        process was actually terminated.
        """
        if job_id is not None and job_id in self._running:
            proc = self._running.pop(job_id)
        elif self._running:
            proc = self._running.popitem()[1]
        else:
            return False

        if proc.returncode is None:
            try:
                proc.kill()
                await asyncio.wait_for(proc.wait(), timeout=5.0)
                return True
            except (asyncio.TimeoutError, ProcessLookupError):
                return False
        return False

    @staticmethod
    def _running_in_venv() -> bool:
        """Return True when the backend process itself is inside a Python venv.

        This is a pragmatic signal for local development: when the API/worker
        was started from a project venv that already contains the required
        packages, preferring ``LocalSandbox`` avoids spinning inside a bare
        container image that lacks project dependencies.

        Also treats conda environments as venvs because ``sys.prefix`` equals
        ``sys.base_prefix`` inside a conda env, but the interpreter still lives
        in an isolated prefix with its own site-packages.
        """
        if hasattr(sys, "base_prefix") and sys.prefix != sys.base_prefix:
            return True
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix and Path(conda_prefix) == Path(sys.prefix):
            return True
        return False

    @staticmethod
    def _venv_env(env: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Prepend the configured skill Python environment to PATH.

        This makes ``python``/``pip`` inside ``shell_exec`` resolve to the
        interpreter configured by ``HOMOMICS_SKILL_PYTHON_PATH`` (or the backend
        process's own venv when unset), so skills find packages already installed
        in that environment.
        """
        python_path = settings.skill_python_path
        if python_path:
            venv_bin = Path(python_path).parent
        elif Sandbox._running_in_venv():
            venv_bin = Path(sys.executable).parent
        else:
            return env
        path = str(venv_bin)
        if env is None:
            base = dict(os.environ)
        else:
            base = dict(env)
        existing = base.get("PATH", "")
        if existing:
            path = f"{path}{os.pathsep}{existing}"
        base["PATH"] = path
        return base

    @staticmethod
    def create(
        backend: str,
        working_dir: Path,
        container_image: Optional[str] = None,
        exec_type: Optional[str] = None,
        allow_local: bool = True,
    ) -> "Sandbox":
        """Factory for sandboxes.

        Args:
            backend: ``auto``, ``local``, ``bubblewrap``, ``container``.
            working_dir: Directory for inputs/outputs.
            container_image: Image for ``container`` backend.
            exec_type: ``python`` or ``r``; used to pick a default container image.
            allow_local: When False, never fall back to ``LocalSandbox``. Used for
                untrusted skills that must run in bubblewrap/container isolation.
        """
        if backend == "auto":
            # When running inside a project venv (typical local dev), the host
            # interpreter already has the dependencies installed by the user.
            # Prefer LocalSandbox in that case so skills work out of the box;
            # production deployments should explicitly set the backend to
            # ``container`` or ``bubblewrap``.
            if Sandbox._running_in_venv():
                candidates = (LocalSandbox, ContainerSandbox, BubblewrapSandbox)
            else:
                candidates = (ContainerSandbox, BubblewrapSandbox, LocalSandbox)
            if not allow_local:
                candidates = tuple(c for c in candidates if c is not LocalSandbox)
            for cls in candidates:
                candidate = cls(
                    working_dir,
                    container_image=container_image,
                    exec_type=exec_type,
                )
                if not candidate.is_available():
                    continue
                # A backend can report "available" yet be non-functional in
                # the current environment (e.g. bwrap present but unable to
                # mount /work under WSL). Probe it and fall back when broken.
                if isinstance(candidate, BubblewrapSandbox) and not candidate.probe():
                    logger.warning(
                        "Bubblewrap sandbox is present but non-functional here; "
                        "falling back to the local sandbox."
                    )
                    continue
                return candidate
            if not allow_local:
                raise RuntimeError(
                    "No isolated sandbox backend (bubblewrap/container) is available "
                    "for this untrusted skill."
                )
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
                "memory_mb": 8192,
                "cpu_time_seconds": 3600,
                "file_size_mb": 1024,
            },
        }

    async def run_python(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        job_id: Optional[str] = None,
        parent_job_id: Optional[str] = None,
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
            # Run Python in unbuffered mode so that skill print() statements are
            # flushed immediately and can be streamed to the frontend as live logs.
            proc = await asyncio.create_subprocess_exec(
                executable, "-u", str(script_path), inputs_json,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.working_dir),
            )
            if job_id:
                self._running[job_id] = proc

            stdout_lines, stderr_lines = await self._stream_subprocess(
                proc=proc,
                timeout_seconds=timeout_seconds,
                progress_callback=progress_callback,
                job_id=job_id,
                parent_job_id=parent_job_id,
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
            if job_id:
                self._running.pop(job_id, None)
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
        parent_job_id: Optional[str] = None,
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
                # 8192 MB memory limit for real single-cell datasets.
                _resource_module.setrlimit(
                    _resource_module.RLIMIT_AS, (8192 * 1024 * 1024, 8192 * 1024 * 1024)
                )
                # 3600 seconds CPU time limit for analysis skills.
                _resource_module.setrlimit(_resource_module.RLIMIT_CPU, (3600, 3600))
                # 1 GB file size limit for output artifacts.
                _resource_module.setrlimit(
                    _resource_module.RLIMIT_FSIZE, (1024 * 1024 * 1024, 1024 * 1024 * 1024)
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
            if job_id:
                self._running[job_id] = proc

            stdout_lines, stderr_lines = await self._stream_subprocess(
                proc=proc,
                timeout_seconds=timeout_seconds,
                progress_callback=progress_callback,
                job_id=job_id,
                parent_job_id=parent_job_id,
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
            if job_id:
                self._running.pop(job_id, None)
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
        job_id: Optional[str] = None,
    ) -> str:
        """Run a shell command locally."""
        run_env = self._venv_env(env)
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd or self.working_dir),
            env=run_env,
        )
        if job_id:
            self._running[job_id] = proc
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
        finally:
            if job_id:
                self._running.pop(job_id, None)
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
        parent_job_id: Optional[str],
        current_phase: Optional[str],
    ) -> tuple[List[str], List[str]]:
        """Read stdout/stderr incrementally and report progress in near real time."""
        stdout_lines: List[str] = []
        stderr_lines: List[str] = []
        # Each new line is pushed onto this queue so the reporter can emit it
        # immediately without waiting for a fixed polling interval.
        line_queue: asyncio.Queue[str] = asyncio.Queue()

        async def _read_stream(stream, lines: List[str], prefix: str) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip("\n")
                lines.append(text)
                await line_queue.put(f"{prefix}{text}")

        stdout_task = asyncio.create_task(_read_stream(proc.stdout, stdout_lines, ""))
        stderr_task = asyncio.create_task(_read_stream(proc.stderr, stderr_lines, "[stderr] "))

        # Progress events use the parent background job id when available so that
        # the frontend's SSE subscription sees them; fall back to the local id.
        progress_job_id = parent_job_id or job_id or "unknown"

        async def _progress_reporter() -> None:
            if progress_callback is None:
                return
            pending_logs: List[str] = []
            last_emit = time.monotonic()

            def _emit() -> None:
                nonlocal last_emit
                if not pending_logs:
                    return
                progress_callback(
                    ExecutionState(
                        job_id=progress_job_id,
                        status="RUNNING",
                        current_phase=current_phase,
                        progress_pct=min(
                            10.0 + (len(stdout_lines) + len(stderr_lines)) * 2.0, 90.0
                        ),
                        logs=pending_logs[:],
                        scheduler_type="local",
                    )
                )
                pending_logs.clear()
                last_emit = time.monotonic()

            try:
                while True:
                    try:
                        # Wait for the next line, but flush buffered lines at least
                        # every 200 ms so the UI feels responsive.
                        line = await asyncio.wait_for(line_queue.get(), timeout=0.2)
                        pending_logs.append(line)
                        # Emit immediately for the first few lines, then batch up
                        # to a handful of lines to avoid flooding the event bus.
                        if len(pending_logs) >= 5 or time.monotonic() - last_emit > 0.5:
                            _emit()
                    except asyncio.TimeoutError:
                        if pending_logs:
                            _emit()
                        # Exit once the process has finished and the readers are done.
                        if proc.returncode is not None and line_queue.empty():
                            break
            finally:
                _emit()

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

        # Wait for the readers to drain their pipes before stopping the reporter.
        await asyncio.gather(stdout_task, stderr_task)
        reporter_task.cancel()
        try:
            await reporter_task
        except asyncio.CancelledError:
            pass

        return stdout_lines, stderr_lines

    _RESOURCE_LIMITS_SNIPPET = """\
try:
    import resource
    # 8192 MB memory limit — single-cell H5AD files decompress to multiple
    # gigabytes in memory; 2 GB is too restrictive for real datasets.
    resource.setrlimit(resource.RLIMIT_AS, (8192 * 1024 * 1024, 8192 * 1024 * 1024))
    # 3600 seconds CPU time limit — analysis skills often run for minutes.
    resource.setrlimit(resource.RLIMIT_CPU, (3600, 3600))
    # 1 GB file size limit for output artifacts.
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
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

        return f"""import builtins
import json
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

_original_import = builtins.__import__

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    base = name.split('.')[0]
    if base in _BLOCKED:
        raise ImportError(f"Module '{{name}}' is restricted in skill sandbox")
    return _original_import(name, globals, locals, fromlist, level)

builtins.__import__ = _safe_import

# Also restrict __import__ attribute access through the builtins dict.
class _RestrictedBuiltins(dict):
    def __getitem__(self, key):
        if key == '__import__':
            return _safe_import
        return super().__getitem__(key)

__builtins__ = _RestrictedBuiltins(dict(builtins.__dict__))

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

    def probe(self) -> bool:
        """Run a trivial command to confirm bwrap actually works here.

        ``is_available`` only checks the binary exists; under WSL and some
        locked-down containers bwrap is present but cannot mount ``/work``
        (``Read-only file system``), which would make every skill fail. This
        probe replicates the real mount layout with a no-op command.
        """
        if not self._bwrap:
            return False
        args = [
            str(self._bwrap),
            "--ro-bind", "/", "/",
            "--bind", str(self.working_dir), "/work",
            "--dir", "/tmp",
            "--proc", "/proc",
            "--dev", "/dev",
            "--unshare-user", "--unshare-ipc", "--unshare-pid",
            "--unshare-net", "--unshare-uts",
            "--chdir", "/work",
            "--", "/bin/echo", "__sandbox_ok__",
        ]
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=10
            )
        except Exception:
            return False
        return result.returncode == 0 and "__sandbox_ok__" in result.stdout

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
        parent_job_id: Optional[str] = None,
        current_phase: Optional[str] = None,
        python_path: Optional[str] = None,
        unrestricted: bool = False,
    ) -> Dict[str, Any]:
        inputs_json = json.dumps(inputs)
        script = LocalSandbox(self.working_dir)._build_python_script(code, inputs, unrestricted=unrestricted)
        script_path = self.working_dir / "__skill_script__.py"
        script_path.write_text(script)

        result_path = self.working_dir / "__skill_result__.json"
        interpreter = (
            python_path
            if python_path and python_path.startswith("/")
            else (settings.skill_python_path if settings.skill_python_path else sys.executable)
        )
        run_env = self._venv_env(None)
        args = self._base_args(self.working_dir) + [
            interpreter, "/work/__skill_script__.py", inputs_json,
        ]
        return await self._run_in_sandbox(
            args,
            result_path,
            timeout_seconds=timeout_seconds,
            progress_callback=progress_callback,
            job_id=job_id,
            parent_job_id=parent_job_id,
            current_phase=current_phase,
            env=run_env,
        )

    async def run_r(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        job_id: Optional[str] = None,
        parent_job_id: Optional[str] = None,
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
            parent_job_id=parent_job_id,
            current_phase=current_phase,
        )

    async def run_command(
        self,
        command: str,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 30.0,
        job_id: Optional[str] = None,
    ) -> str:
        run_cwd = Path(cwd or self.working_dir)
        # Inherit the venv PATH so that `python` inside the sandbox resolves to
        # the same interpreter the backend uses. Bubblewrap binds the host fs as
        # read-only, so the venv packages remain accessible.
        run_env = self._venv_env(env)
        args = self._base_args(run_cwd) + ["/bin/sh", "-c", command]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=run_env,
        )
        if job_id:
            self._running[job_id] = proc
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        finally:
            if job_id:
                self._running.pop(job_id, None)
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
        parent_job_id: Optional[str],
        current_phase: Optional[str],
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        if job_id:
            self._running[job_id] = proc

        try:
            stdout_lines, stderr_lines = await LocalSandbox(self.working_dir)._stream_subprocess(
                proc=proc,
                timeout_seconds=timeout_seconds,
                progress_callback=progress_callback,
                job_id=job_id,
                parent_job_id=parent_job_id,
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
        finally:
            if job_id:
                self._running.pop(job_id, None)


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
        parent_job_id: Optional[str] = None,
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
            parent_job_id=parent_job_id,
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
        parent_job_id: Optional[str] = None,
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
            parent_job_id=parent_job_id,
            current_phase=current_phase,
        )

    async def run_command(
        self,
        command: str,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 30.0,
        job_id: Optional[str] = None,
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
        if job_id:
            self._running[job_id] = proc
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        finally:
            if job_id:
                self._running.pop(job_id, None)
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
        parent_job_id: Optional[str],
        current_phase: Optional[str],
    ) -> Dict[str, Any]:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        if job_id:
            self._running[job_id] = proc

        try:
            stdout_lines, stderr_lines = await LocalSandbox(self.working_dir)._stream_subprocess(
                proc=proc,
                timeout_seconds=timeout_seconds,
                progress_callback=progress_callback,
                job_id=job_id,
                parent_job_id=parent_job_id,
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
        finally:
            if job_id:
                self._running.pop(job_id, None)
