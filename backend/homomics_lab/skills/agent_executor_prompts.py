"""Prompt construction for :class:`AgentSkillExecutor`.

Extracted from ``skills/agent_executor.py`` as a pure code move (no logic
changes): the system-prompt builder plus the SKILL.md / helper-script
reference compaction helpers it (and the script-first fast path) relies on.
Everything here is pure — no executor state is required.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from homomics_lab.skills.models import SkillDefinition


def _first_doc_line(doc: Optional[str]) -> str:
    if not doc:
        return ""
    line = doc.strip().splitlines()[0]
    return (" — " + line) if line else ""


def _extract_python_api(path: Path) -> List[str]:
    """Return concise ``function(args) -> hint — doc`` lines for a Python module."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    def _unparse(ann: Optional[ast.AST]) -> Optional[str]:
        if ann is None:
            return None
        try:
            return ast.unparse(ann)
        except Exception:
            return None

    api: List[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            if name.startswith("_"):
                continue
            arg_nodes = node.args.args
            defaults = [None] * (len(arg_nodes) - len(node.args.defaults)) + node.args.defaults
            sig_parts = []
            for arg_node, default in zip(arg_nodes, defaults):
                arg_name = arg_node.arg
                if default is not None:
                    sig_parts.append(f"{arg_name}=...")
                else:
                    sig_parts.append(arg_name)
            sig = f"{name}({', '.join(sig_parts)})"
            ret = _unparse(node.returns)
            if ret:
                sig += f" -> {ret}"
            doc = ast.get_docstring(node)
            api.append(f"- {sig}{_first_doc_line(doc)}")
        elif isinstance(node, ast.ClassDef):
            methods = [
                n.name
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not n.name.startswith("_")
            ]
            if methods:
                api.append(f"- class {node.name}: methods {methods}")
    return api


def _extract_r_api(path: Path) -> List[str]:
    """Return concise function signatures from an R script (best-effort regex)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    api: List[str] = []
    for match in re.finditer(r"^\s*([A-Za-z_.][A-Za-z0-9_.]*)\s*<-\s*function\s*\(([^)]*)\)", text, re.MULTILINE):
        name, args = match.group(1), match.group(2)
        if name.startswith("."):
            continue
        api.append(f"- {name}({args.strip()})")
    return api


def _extract_script_reference(source_dir: Optional[Path], max_chars: int = 6000) -> str:
    """Build a reference from helper scripts in a skill's source dir.

    Small helper scripts (<= 300 lines, <= 12 KB) are inlined in full so the
    agent can use them without attempting to read files outside the workspace.
    Larger scripts are summarized as API signatures only. This keeps the prompt
    compact while giving the agent enough information to write a correct driver.
    """
    if not source_dir:
        return ""

    def _is_small_script(path: Path) -> bool:
        try:
            stat = path.stat()
            if stat.st_size > 12_000:
                return False
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for i, _ in enumerate(fh):
                    if i >= 300:
                        return False
            return True
        except Exception:
            return False

    def _read_source(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

    sections: List[str] = []
    python_dir = Path(source_dir) / "scripts" / "python"
    r_dir = Path(source_dir) / "scripts" / "r"

    if python_dir.is_dir():
        entries: List[str] = []
        for py_file in sorted(python_dir.glob("*.py")):
            if _is_small_script(py_file):
                source = _read_source(py_file)
                if source:
                    entries.append(f"### {py_file.name} (full source)\n```python\n{source}\n```")
            else:
                api = _extract_python_api(py_file)
                if api:
                    entries.append(f"### {py_file.name}\n" + "\n".join(api))
        if entries:
            sections.append(
                "## Skill Python helpers (import these; do not read whole files)\n"
                + "\n\n".join(entries)
            )

    if r_dir.is_dir():
        entries = []
        for r_file in sorted(r_dir.glob("*.R")):
            if _is_small_script(r_file):
                source = _read_source(r_file)
                if source:
                    entries.append(f"### {r_file.name} (full source)\n```r\n{source}\n```")
            else:
                api = _extract_r_api(r_file)
                if api:
                    entries.append(f"### {r_file.name}\n" + "\n".join(api))
        if entries:
            sections.append(
                "## Skill R helpers (source these; do not read whole files)\n"
                + "\n\n".join(entries)
            )

    text = "\n\n".join(sections)
    if len(text) > max_chars:
        text = text[:max_chars].rsplit("\n", 1)[0] + "\n... [truncated] ..."
    return text


def _compact_skill_doc(text: str, max_chars: int = 4000) -> str:
    """Bound a SKILL.md body for prompt injection.

    Long skill docs bloat the prompt and slow the provider, so only the head
    (workflow, parameter defaults) and the tail (output contracts and pitfalls
    conventionally live at the end) are kept, with an explicit elision marker.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return text
    head_budget = int(max_chars * 0.6)
    tail_budget = max_chars - head_budget
    head = text[:head_budget].rsplit("\n", 1)[0]
    tail = text[-tail_budget:].split("\n", 1)[-1]
    return f"{head}\n\n... [middle of SKILL.md elided] ...\n\n{tail}"


def _tool_summary(tool: Any) -> str:
    """Return a one-line description with parameter names only."""
    schema = tool.input_schema if hasattr(tool, "input_schema") else {}
    params = []
    if isinstance(schema, dict):
        required = schema.get("required", [])
        props = schema.get("properties", schema)
        for key in sorted(props.keys()):
            marker = "*" if key in required else ""
            params.append(f"{key}{marker}")
    return f"- {tool.name}: {tool.description} ({', '.join(params) if params else 'no args'})"


def build_system_prompt(
    skill: "SkillDefinition",
    inputs: Dict[str, Any],
    tools: Dict[str, Any],
) -> str:
    """Build a concise, action-oriented system prompt for the LLM agent."""
    # Use the short description as the objective instead of dumping the entire
    # SKILL.md body. Long SKILL.md files bloat the prompt and slow the provider.
    instructions = skill.description or skill.metadata.get("instructions", "")

    tool_descriptions = [_tool_summary(tool) for tool in tools.values()]

    source_dir = skill.source_dir
    script_reference = _extract_script_reference(source_dir, max_chars=2500)

    file_read_restriction = ""
    if source_dir and "file_read" in tools:
        file_read_restriction = (
            "\nWhen using file_read, you may only read files under the current "
            "project workspace (input data, existing outputs, etc.). The skill helper "
            "scripts are already provided above; do NOT file_read them.\n"
        )

    scripts_hint = ""
    if source_dir:
        scripts_python = Path(source_dir) / "scripts" / "python"
        scripts_r = Path(source_dir) / "scripts" / "r"
        if scripts_python.is_dir():
            scripts_hint = (
                f"\nTo use the Python helpers, write a driver script that begins with:\n"
                f"import sys, os\n"
                f"sys.path.insert(0, '{scripts_python}')\n"
                f"from <helper_module> import <function>  # import ONLY the helpers listed above; do NOT assume core_analysis.py or run.py exists\n"
            )
        elif scripts_r.is_dir():
            scripts_hint = (
                f"\nTo use the R helpers, write a driver script that begins with:\n"
                f"source('{scripts_r}/<helper>.R')\n"
            )

    return f"""You are an autonomous agent executing the skill "{skill.id}".

## Objective
{instructions}

## User inputs (satisfy every clause)
{json.dumps(inputs, ensure_ascii=False, indent=2)}

{script_reference}
{scripts_hint}
{file_read_restriction}
## Available tools
{chr(10).join(tool_descriptions)}

## Execution workflow (two phases)

Phase 1 — Inspect (your FIRST turn only):
- Review the helper API / full source above; do NOT use file_read on helper scripts.
- Briefly inspect input data to confirm columns, shape, and existing labels.
  For large `.h5ad` files use `anndata.read_h5ad(path, backed='r')` to read metadata
  without loading the full expression matrix into memory.
- Allowed tools: file_read, file_list, shell_exec (short introspection only).
- Do NOT write files, do NOT run a full pipeline, do NOT return action: "final" yet.

Phase 2 — Execute (after Phase 1):
- Write ONE driver script (.py or .R) that imports only the helpers listed in the API
  reference above and satisfies every clause of the objective.
- Run it with a single shell_exec call.
- Save outputs with clear filenames under `outputs/` (e.g. report.txt, summary.csv,
  figures/*.png, summary.json, etc.).
- If the objective includes comparing predictions to reference labels, save both a
  cell-level comparison CSV and a human-readable report.
- BEFORE returning action: "final", use file_read to read the generated report/
  summary files and cite concrete numbers (cell counts, gene counts, accuracy,
  ARI, top categories, etc.) in both `final_output.summary` and `final_output.metrics`.
- Return action: "final" listing the output file paths and concrete metrics.

Rules:
- Treat `inputs.user_request` as the complete objective. Do every requested step.
- If inputs contain a reference/ground-truth column (target_column, reference_column,
  label_column, ground_truth), compare results and report metrics.
- Use the helper API reference above. Prefer high-level helpers when they satisfy the
  objective; do not reimplement helper logic in the driver script.
- Do NOT assume a fixed entrypoint such as `core_analysis.py` or `run.py` exists.
  Import only the helper modules actually present in the API reference.
- Keep the driver script compact and focused: no boilerplate docstrings, minimal
  comments, no dead code.
- Do not save `.h5ad` output unless the user explicitly requests it.
- Satisfy every clause of the objective. If a requested deliverable fails (e.g. a
  comparison or metric), diagnose and fix it; do not return partial success prematurely.
- Do not chase perfect accuracy with iterative manual label remapping. If predicted and
  ground-truth labels differ in granularity, report the raw comparison and note it.
- Inspect actual `adata.obs.columns` / `adata.var.columns` to find column names instead
  of hard-coding defaults.
- If the skill documentation calls for strict input requirements (e.g. a specific
  normalization), perform that step in the driver script rather than assuming existing
  layers already match.
- When saving `.h5ad` files, use `safe_write_h5ad` from the skill's utils if available
  instead of `adata.write_h5ad`, to avoid nullable-string errors.
- Print the absolute paths of all output files the script creates so they can be harvested.
- Prefer one `shell_exec` per pipeline over many small reads.
- On a tool error, diagnose and retry once; do not repeat the same call.
- Tool names must come from Available tools.

## Output format
Respond ONLY with a JSON object:

1. Tool call: {{"thought": "...", "action": "tool", "tool": "tool_name", "arguments": {{...}}}}
2. Final result: {{"thought": "...", "action": "final", "final_output": {{"summary": "...", "output_files": [...], "metrics": {{...}}}}}}

The `final_output.summary` must be a concise but concrete markdown summary. It MUST cite
numerical findings directly from the generated outputs (report.txt, summary.csv, etc.):
cell counts, key proportions, accuracy / ARI / F1 when a comparison was requested, the
model or method used, and any notable disagreements. Do not give a vague high-level description.

No markdown or explanation outside the JSON. Your first response MUST be a Phase 1 inspection tool call.
"""
