"""Fast integration test for CellTypist agent using a 2000-cell subset."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("HOMOMICS_FORCE_SANDBOX", "false")
os.environ.setdefault("HOMOMICS_DEBUG", "true")

from homomics_lab.config import settings
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.agent_executor import AgentSkillExecutor
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.tools.builtin import shell_exec
from homomics_lab.tools.models import ToolDefinition
from homomics_lab.tools.registry import ToolRegistry


async def main():
    skill_dir = Path("/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist")
    data_path = "/mnt/c/Users/guoyang/Desktop/data/PA12_small.h5ad"
    working_dir = Path("/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/tmp_dbg/celltypist_small")
    working_dir.mkdir(parents=True, exist_ok=True)

    registry = SkillRegistry()
    loader = SkillLoader(registry=registry)
    skill = loader.load_skill(skill_dir)
    print(f"Loaded skill: {skill.id}")

    tool_registry = ToolRegistry()
    tool_registry.register(
        ToolDefinition(
            name="shell_exec",
            description="Run a shell command",
            input_schema={"command": {"type": "string"}, "timeout": {"type": "integer"}},
            risk_level="high",
            handler=shell_exec,
        )
    )
    tool_registry.register(
        ToolDefinition(
            name="file_read",
            description="Read a file",
            input_schema={"path": {"type": "string"}},
            risk_level="low",
            handler=lambda **kw: {"content": Path(kw["path"]).read_text(encoding="utf-8", errors="replace")},
        )
    )

    llm_client = LLMClient()
    await llm_client.reload_config()
    print(f"LLM configured: {llm_client.is_configured()}")

    executor = AgentSkillExecutor(
        tool_registry=tool_registry,
        llm_client=llm_client,
        max_iterations=10,
    )

    inputs = {
        "input_file": data_path,
        "output_dir": str(working_dir / "outputs"),
        "model": "Immune_All_Low.pkl",
        "target_column": "all_celltype",
    }

    start = time.monotonic()
    result = await executor.execute(skill, inputs, working_dir=working_dir)
    elapsed = time.monotonic() - start

    print(f"\n=== RESULT (elapsed {elapsed:.1f}s) ===")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
