"""Time the execution-phase LLM call for CellTypist."""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "backend")
os.environ.setdefault("HOMOMICS_DEBUG", "true")

from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.agent_executor import AgentSkillExecutor
from homomics_lab.skills.loader import SkillLoader
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.tools.models import ToolDefinition


def fake_tool(name, desc, schema):
    return ToolDefinition(name=name, description=desc, input_schema=schema, risk_level="low", handler=lambda **kw: {})


async def main():
    skill_dir = Path("skills/bio-single-cell-annotation-celltypist")
    skill = SkillLoader(registry=SkillRegistry()).load_skill(skill_dir)
    tools = {
        "shell_exec": fake_tool("shell_exec", "run shell", {"command": {"type": "string"}, "timeout": {"type": "integer"}}),
        "file_read": fake_tool("file_read", "read file", {"path": {"type": "string"}}),
        "file_list": fake_tool("file_list", "list files", {"directory": {"type": "string"}}),
    }
    system_prompt = AgentSkillExecutor._build_system_prompt(
        skill,
        {"input_file": "/mnt/c/Users/guoyang/Desktop/data/PA12_small.h5ad", "output_dir": "...", "model": "Immune_All_Low.pkl", "target_column": "all_celltype"},
        tools,
    )
    exploration_tool_result = {
        "tool": "shell_exec",
        "arguments": {"command": "..."},
        "success": True,
        "output": {
            "stdout": "shape: (2000, 29057)\nobs columns: ['tissue', 'patients', 'all_celltype', 'n_genes', 'n_counts', 'mito_percent']\nhas all_celltype: True\nall_celltype values: {'CD8T': 742, 'CD4T': 489, 'NK': 410, 'B': 197, 'Myeloid': 99, 'Epi': 31, 'Endo': 19, 'Fibro': 13}\ncelltypist version: 1.7.1\nImmune_All_Low.pkl present: True",
            "stderr": "",
            "returncode": 0,
        },
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Phase 1 inspect."},
        {"role": "assistant", "content": json.dumps({"thought": "inspect", "action": "tool", "tool": "shell_exec", "arguments": {"command": "python3 -c '...'"}})},
        {"role": "user", "content": "Tool result: " + json.dumps(exploration_tool_result)},
        {"role": "user", "content": "Phase 1 inspection complete. Enter Phase 2 — Execute. Write ONE driver script (.py or .R) that calls the helpers, satisfies every clause of the objective, and saves outputs with clear filenames. Then run it with shell_exec and return action: \"final\" listing the output paths."},
    ]
    client = LLMClient()
    await client.reload_config()
    for mt in [2000, 3000, 4000]:
        t0 = time.monotonic()
        text = await client.chat_completion(
            messages, temperature=0.2, max_tokens=mt,
            response_format={"type": "json_object"}, intent_type="code_generation",
        )
        print(f"max_tokens={mt} elapsed={time.monotonic()-t0:.1f}s len={len(text)}")
        print(text[:1500])
        print("---")


if __name__ == "__main__":
    asyncio.run(main())
