import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict


class LocalSandbox:
    """Execute Python code in a subprocess with resource limits."""

    def __init__(self, working_dir: Path = None):
        self.working_dir = working_dir or Path(tempfile.mkdtemp())
        self.working_dir.mkdir(parents=True, exist_ok=True)

    async def run_python(
        self,
        code: str,
        inputs: Dict[str, Any],
        timeout_seconds: float = 60.0,
    ) -> Dict[str, Any]:
        script = self._build_script(code, inputs)

        script_path = self.working_dir / "__skill_script__.py"
        script_path.write_text(script)

        result_path = self.working_dir / "__skill_result__.json"

        def _set_limits():
            """Set resource limits for the child process."""
            try:
                import resource
                # 512 MB memory limit
                resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
                # 60 seconds CPU time limit
                resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
                # 100 MB file size limit
                resource.setrlimit(resource.RLIMIT_FSIZE, (100 * 1024 * 1024, 100 * 1024 * 1024))
            except (ImportError, OSError, ValueError):
                pass  # resource module not available on non-Unix systems

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.working_dir),
                preexec_fn=_set_limits,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                if proc.returncode is None:
                    proc.kill()
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        pass
                raise TimeoutError(f"Skill execution timed out after {timeout_seconds}s")

            if proc.returncode != 0:
                raise RuntimeError(f"Skill execution failed: {stderr.decode()}")

            if not result_path.exists():
                return {"raw_output": stdout.decode()}

            import json
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

    def _build_script(self, code: str, inputs: Dict[str, Any]) -> str:
        import json
        inputs_json = json.dumps(inputs)

        return f"""import json
import sys
import types

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