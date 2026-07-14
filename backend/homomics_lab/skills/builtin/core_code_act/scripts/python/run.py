"""Core CodeAct skill: generate and execute code for a sub-task.

This skill now delegates code generation to the real LLM-backed path in
``homomics_lab.execution.code_act.generate_code_async``. If no LLM is
configured or the LLM call fails, it falls back to the rule-based templates so
offline and test environments keep working.
"""

import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

from homomics_lab.config import settings
from homomics_lab.execution.code_act import generate_code_async
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.registry import SkillRegistry


def _execute_code(code: str, language: str) -> dict:
    """Execute generated code in a subprocess and return results."""
    if language == "python":
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            script_path = f.name
        cmd = [sys.executable, script_path]
    elif language == "bash":
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write(code)
            script_path = f.name
        cmd = ["bash", script_path]
    elif language == "r":
        with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False) as f:
            f.write(code)
            script_path = f.name
        cmd = ["Rscript", script_path]
    else:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Unsupported language: {language}",
            "exit_code": -1,
        }

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Code execution timed out",
            "exit_code": -1,
        }
    except Exception as exc:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(exc),
            "exit_code": -1,
        }
    finally:
        try:
            Path(script_path).unlink()
        except Exception:
            pass


async def _generate_code(task: str, language: str, context: Dict[str, Any]) -> str:
    """Generate code via the shared CodeAct engine (LLM + retrieval fallback)."""
    llm_client = None
    skill_registry = None
    try:
        if settings.llm_provider:
            llm_client = LLMClient()
    except Exception:
        llm_client = None
    try:
        skill_registry = SkillRegistry()
    except Exception:
        skill_registry = None

    code = await generate_code_async(
        task,
        language,
        context,
        llm_client=llm_client,
        skill_registry=skill_registry,
        retrieval_context=None,
    )
    return code


def main(skill_inputs: dict) -> dict:
    """Generate and execute a code action for the given task."""
    task = skill_inputs["task"]
    language = skill_inputs.get("language", "python")
    context = skill_inputs.get("context", {})

    code = asyncio.run(_generate_code(task, language, context))
    execution = _execute_code(code, language)

    return {
        "code": code,
        "result": {
            "success": execution["success"],
            "language": language,
            "context_keys": list(context.keys()),
            "stdout": execution["stdout"],
            "stderr": execution["stderr"],
            "exit_code": execution["exit_code"],
        },
    }


if __name__ == "__main__":
    skill_inputs = json.loads(sys.argv[1])
    result = main(skill_inputs)
    print(json.dumps(result))
