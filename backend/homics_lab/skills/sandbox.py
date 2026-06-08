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

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "python", str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.working_dir),
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

# Block dangerous imports
_blocked_modules = ['os', 'subprocess', 'socket', 'urllib', 'http', 'ftplib', 'telnetlib', 'smtplib', 'poplib', 'imaplib', 'nntplib', 'ssl']
_original_import = __builtins__.__import__

def _safe_import(name, *args, **kwargs):
    base = name.split('.')[0]
    if base in _blocked_modules:
        raise ImportError("Import of '" + name + "' is not allowed in skill sandbox")
    return _original_import(name, *args, **kwargs)

__builtins__.__import__ = _safe_import

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