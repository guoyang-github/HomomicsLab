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
        """Execute Python code and return the 'result' variable."""
        script = self._build_script(code, inputs)

        script_path = self.working_dir / "__skill_script__.py"
        script_path.write_text(script)

        result_path = self.working_dir / "__skill_result__.json"

        try:
            proc = await asyncio.create_subprocess_exec(
                "python", str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.working_dir),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )

            if proc.returncode != 0:
                raise RuntimeError(f"Skill execution failed: {stderr.decode()}")

            if not result_path.exists():
                return {"raw_output": stdout.decode()}

            import json
            return json.loads(result_path.read_text())

        except asyncio.TimeoutError:
            raise TimeoutError(f"Skill execution timed out after {timeout_seconds}s")

    def _build_script(self, code: str, inputs: Dict[str, Any]) -> str:
        import json
        inputs_json = json.dumps(inputs)
        result_path = str(self.working_dir / "__skill_result__.json")

        return f"""import json
import sys

# Inject inputs
__inputs__ = json.loads({repr(inputs_json)})
locals().update(__inputs__)

# Run skill code
{code}

# Serialize result
if 'result' not in locals():
    result = {{}}

with open({repr(result_path)}, 'w') as f:
    json.dump(result, f)
"""