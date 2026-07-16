"""CodeAct engine — generate and execute code actions for sub-tasks.

The engine sits inside the runtime and is invoked for skills marked with
``metadata["code_act"] == True``. It produces Python/R/Bash code based on the
task description and available context, then executes the code in a real
subprocess outside the restrictive skill sandbox.

When an LLM is configured, the engine retrieves relevant skill context and
uses the LLM to generate code. Otherwise it falls back to a small set of
rule-based templates for offline / test environments.
"""

import asyncio
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.agent.retrieval import RetrievalContext
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.registry import SkillRegistry
from homomics_lab.tools.registry import ToolRegistry


def generate_code(
    task: str,
    language: str,
    context: Dict[str, Any],
    llm_client: Optional[LLMClient] = None,
    skill_registry: Optional[SkillRegistry] = None,
    retrieval_context: Optional[RetrievalContext] = None,
    max_tokens: int = 4000,
) -> str:
    """Generate a code snippet for the task (synchronous entry point).

    Prefers LLM + retrieval context when available; otherwise uses the
    rule-based fallback so tests and offline usage still work.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # Called from inside an async context without awaiting. Fall back to
        # rule-based generation to avoid blocking the running event loop.
        return _generate_code_rule_based(task, language, context)

    return asyncio.run(
        generate_code_async(
            task, language, context, llm_client, skill_registry, retrieval_context, max_tokens=max_tokens
        )
    )


async def generate_code_async(
    task: str,
    language: str,
    context: Dict[str, Any],
    llm_client: Optional[LLMClient] = None,
    skill_registry: Optional[SkillRegistry] = None,
    retrieval_context: Optional[RetrievalContext] = None,
    use_cache: Optional[bool] = None,
    max_tokens: int = 4000,
) -> str:
    """Async version of ``generate_code`` for use inside async callers.

    ``use_cache=None`` falls back to ``settings.codeact_cache_enabled``;
    callers (e.g. the skill runtime) can force it off for low-trust skills.
    """
    from homomics_lab.config import settings
    from homomics_lab.execution.code_cache import CodeActCache

    if use_cache is None:
        use_cache = settings.codeact_cache_enabled
    cache = CodeActCache(settings.codeact_cache_dir) if use_cache else None
    if cache is not None:
        cached = cache.get(task, language, context, retrieval_context)
        if cached is not None:
            return cached

    if llm_client is not None and llm_client.is_configured():
        code = await _generate_code_with_llm(
            task, language, context, llm_client, skill_registry, retrieval_context, max_tokens=max_tokens
        )
        if code:
            if cache is not None:
                cache.put(task, language, code, context, retrieval_context)
            return code

    code = _generate_code_rule_based(task, language, context)
    if cache is not None:
        cache.put(task, language, code, context, retrieval_context)
    return code


def _retrieve_skill_context(
    task: str,
    skill_registry: Optional[SkillRegistry],
    top_k: int = 3,
) -> str:
    """Retrieve relevant skill descriptions to include in the LLM prompt."""
    if skill_registry is None:
        return ""

    try:
        results = skill_registry.semantic_search(task, top_k=top_k)
    except Exception:
        return ""

    snippets = []
    for skill, score in results[:top_k]:
        instructions = skill.metadata.get("instructions", "")[:800]
        snippets.append(
            f"- {skill.id} (score {score:.2f}): {skill.description}\n{instructions}"
        )

    return "\n".join(snippets)


def _format_retrieval_context(retrieval_context: Optional[RetrievalContext]) -> str:
    """Format retrieval context for the LLM prompt."""
    if retrieval_context is None:
        return ""

    prompt_context = retrieval_context.to_prompt_context()
    sections = []

    skills = prompt_context.get("skills", [])
    if skills:
        sections.append("Relevant skills:")
        for s in skills:
            sections.append(
                f"- {s['id']}: {s['description']} (inputs: {list(s['inputs'].keys())})"
            )

    tools = prompt_context.get("tools", [])
    if tools:
        sections.append("Available tools (call via homomics_tool(name, ...)):")
        for t in tools:
            sections.append(
                f"- {t['name']}: {t['description']} (risk: {t['risk_level']})"
            )

    data_sources = prompt_context.get("data_sources", [])
    if data_sources:
        sections.append("Available data sources:")
        for d in data_sources:
            sections.append(
                f"- {d['id']} ({d['format']}): {d['path']} — {d['description']}"
            )

    sops = prompt_context.get("sops", [])
    if sops:
        sections.append("Lab SOPs:")
        for sop in sops:
            sections.append(f"- {sop['name']}: {sop.get('template', {})}")

    anomalies = prompt_context.get("anomalies", [])
    if anomalies:
        sections.append("Known failure modes:")
        for a in anomalies:
            sections.append(f"- {a['phase_type']}: {a['summary']} ({a['severity']})")

    lore = prompt_context.get("parameter_lore", [])
    if lore:
        sections.append("Proven parameter choices:")
        for e in lore[:3]:
            sections.append(
                f"- {e['skill_id']}.{e['param_name']}={e['param_value']} "
                f"({e['outcome_metric']}={e['outcome_value']})"
            )

    return "\n".join(sections)


async def _generate_code_with_llm(
    task: str,
    language: str,
    context: Dict[str, Any],
    llm_client: LLMClient,
    skill_registry: Optional[SkillRegistry],
    retrieval_context: Optional[RetrievalContext],
    max_tokens: int = 4000,
) -> Optional[str]:
    """Ask an LLM to generate code, seeded with retrieved skill context."""
    # If the caller has already pinned the skill(s) to use (e.g. skill-as-reference
    # mode), skip the expensive semantic search over the registry. This avoids
    # loading sentence-transformers just to retrieve related skills we do not need.
    if context.get("skills_required"):
        skill_context = ""
    else:
        skill_context = _retrieve_skill_context(task, skill_registry)
    rap_context = _format_retrieval_context(retrieval_context)

    system_prompt = f"""You are a senior bioinformatics engineer.
Generate a single {language} code snippet that fulfills the user's task.

Rules:
- Output ONLY the code inside a single markdown ```{language} ... ``` block.
- The code must be self-contained and runnable.
- Assign a JSON-serializable result to a variable named `result` before finishing.
- Use paths from the provided context when available.
- If you need to call an available tool, use `homomics_tool("tool_name", arg1=value1, ...)`.
- Do not include explanations outside the code block.
"""

    user_prompt = f"""Task: {task}
Language: {language}
Context: {json.dumps(context, ensure_ascii=False)}

{rap_context}

Relevant skills from the registry:
{skill_context or '(none found)'}

Generate the {language} code now.
"""

    try:
        response = await llm_client.chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
        )
    except Exception:
        return None

    return _extract_code_block(response, language)


def _extract_code_block(text: str, language: str) -> Optional[str]:
    """Extract the first code block for the given language."""
    pattern = rf"```{language}\s*\n(.*?)\n```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback: any triple-backtick block
    match = re.search(r"```\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    return None


def _extract_input_path_from_context(context: Dict[str, Any]) -> Optional[str]:
    """Find a concrete input file path in the execution context.

    Looks for common keys first, then scans all string values for an existing
    .h5ad (or other data) file.  This keeps the rule-based fallback from
    defaulting to a demo path when the caller has supplied a real file.
    """
    candidates: List[str] = []
    for key in ("input_path", "adata_path", "input_file", "file_path", "file", "data_path", "path"):
        value = context.get(key)
        if isinstance(value, (str, Path)):
            candidates.append(str(value))

    def _is_data_file(p: str) -> bool:
        return Path(p).is_file() and any(p.lower().endswith(ext) for ext in (".h5ad", ".h5", ".csv", ".tsv", ".mtx", ".rds"))

    for p in candidates:
        if _is_data_file(p):
            return p

    # Scan every string value as a last resort.
    for value in context.values():
        if isinstance(value, (str, Path)):
            p = str(value)
            if _is_data_file(p):
                return p
        elif isinstance(value, dict) and "path" in value:
            p = value["path"]
            if isinstance(p, (str, Path)) and _is_data_file(str(p)):
                return str(p)

    return None


def _generate_code_rule_based(task: str, language: str, context: Dict[str, Any]) -> str:
    """Fallback rule-based generator for offline / test environments."""
    task_lower = task.lower()
    input_path = _extract_input_path_from_context(context)
    if input_path is None:
        # No concrete input found — generate a script that expects the user
        # to supply INPUT_PATH, rather than hard-coding a demo dataset.
        input_path = "INPUT_PATH"
    output_path = context.get("output_path") or context.get("output_dir") or "output/result.h5ad"

    if language == "python":
        if any(k in task_lower for k in ("read", "load", "h5ad", "10x", "import")):
            return f"""import scanpy as sc
adata = sc.read_h5ad("{input_path}")
print(f"Loaded {{adata.n_obs}} cells x {{adata.n_vars}} genes")
result = {{"cells": int(adata.n_obs), "genes": int(adata.n_vars), "output_path": "{input_path}"}}
"""
        if any(k in task_lower for k in ("qc", "filter", "quality", "mito")):
            return f"""import scanpy as sc
adata = sc.read_h5ad("{input_path}")
adata.var['mt'] = adata.var_names.str.startswith('MT-')
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], percent_top=None, log1p=False, inplace=True)
adata = adata[adata.obs.n_genes_by_counts > 200, :]
adata = adata[adata.obs.pct_counts_mt < 5, :]
adata.write("{output_path}")
result = {{"output_path": "{output_path}", "cells": int(adata.n_obs)}}
print(f"QC done: {{adata.n_obs}} cells remain")
"""
        if any(k in task_lower for k in ("normalize", "normalization", "log1p")):
            return f"""import scanpy as sc
adata = sc.read_h5ad("{input_path}")
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
adata.write("{output_path}")
result = {{"output_path": "{output_path}"}}
print("Normalization done")
"""
        if any(
            k in task_lower for k in ("cluster", "clustering", "leiden", "umap", "pca")
        ):
            return f"""import scanpy as sc
import numpy as np
adata = sc.read_h5ad("{input_path}")
adata.X = adata.X.astype(np.float32)
n_top_genes = min(2000, adata.n_vars - 1)
sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes)
sc.tl.pca(adata)
sc.pp.neighbors(adata)
sc.tl.umap(adata)
sc.tl.leiden(adata)
adata.write("{output_path}")
result = {{"output_path": "{output_path}"}}
print("Clustering done")
"""
        if any(k in task_lower for k in ("plot", "visualize", "umap", "heatmap")):
            return f"""import scanpy as sc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
adata = sc.read_h5ad("{input_path}")
fig, ax = plt.subplots(figsize=(6, 5))
sc.pl.umap(adata, color='leiden', ax=ax, show=False)
plot_path = "{output_path.replace('.h5ad', '.png')}"
fig.savefig(plot_path)
result = {{"plot_path": plot_path}}
print("Plot saved")
"""
        # Generic fallback
        escaped = task.replace('"', '\\"')
        return f"""print("Executing generic task: {escaped}")
print("Context:", {context})
result = {{"task": "{escaped}"}}
"""

    if language == "bash":
        escaped = task.replace('"', '\\"')
        # Bash tasks may target any path, not only bio data files, so read the
        # raw input path from context before falling back to the data-only
        # extraction used for Python/R templates.
        raw_input_path = (
            context.get("input_path")
            or context.get("path")
            or context.get("file_path")
            or input_path
        )
        if raw_input_path == "INPUT_PATH" or raw_input_path is None:
            target = "."
        else:
            target = str(Path(raw_input_path).parent or ".")
        return f"""echo "Executing shell task: {escaped}"
ls -la {target}
result={{"status": "ok"}}
"""

    if language == "r":
        escaped = task.replace('"', '\\"')
        return f"""cat('Executing R task: {escaped}\\n')
result <- list(status = "ok")
"""

    escaped = task.replace('"', '\\"')
    return f"""print('Unsupported language: {language}')
result = {{"error": "unsupported language {language}", "task": "{escaped}"}}
"""


def _build_python_wrapper(code: str) -> str:
    """Wrap user code so it always produces a __skill_result__.json."""
    return f"""import json

{code}

if 'result' not in locals():
    result = {{}}

with open('__skill_result__.json', 'w') as f:
    json.dump(result, f)
"""


def _build_tool_module(tool_registry: Optional[ToolRegistry]) -> str:
    """Build a Python helper module that exposes registered tools to generated code.

    The generated code can call ``homomics_tool(name, **kwargs)`` to invoke any
    registered tool. High-risk tools are still gated by the ToolRegistry's
    approval flow when invoked through this helper.
    """
    if tool_registry is None:
        return ""

    tool_names = [t.name for t in tool_registry.list_all()]
    if not tool_names:
        return ""

    return f"""# Auto-generated tool bindings for CodeAct
import json as _json
import subprocess as _subprocess
import sys as _sys


def homomics_tool(name: str, **kwargs):
    \"\"\"Invoke a registered HomomicsLab tool by name across sandbox boundaries.

    This helper spawns a fresh Python process that loads the tool registry and
    invokes the requested tool, so it works inside bubblewrap/container
    sandboxes that do not share memory with the parent HomomicsLab process.
    \"\"\"
    cmd = [
        _sys.executable,
        "-m",
        "homomics_lab.tools.invoke_tool",
        name,
        "--args-json",
        _json.dumps(kwargs),
    ]
    try:
        proc = _subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            return {{"error": proc.stderr.strip() or "tool invocation failed"}}
        result = _json.loads(proc.stdout.strip().splitlines()[-1])
        return result.get("output") if result.get("success") else {{"error": result.get("error")}}
    except Exception as exc:
        return {{"error": str(exc)}}


AVAILABLE_TOOLS = {tool_names!r}
"""


async def execute_code(
    code: str,
    language: str,
    working_dir: Optional[Path] = None,
    timeout_seconds: float = 300.0,
    tool_registry: Optional[ToolRegistry] = None,
    save_artifact: bool = True,
) -> Dict[str, Any]:
    """Execute generated code inside the configured skill sandbox.

    CodeAct no longer runs arbitrary code directly on the host. It uses the
    same sandbox backend (bubblewrap/container/local) as regular skills.
    When ``force_sandbox`` is enabled and no isolated backend is available,
    execution is refused.
    """
    from homomics_lab.config import settings
    from homomics_lab.execution.code_safety import CodeSafetyScanner, requires_hitl
    from homomics_lab.skills.sandbox import (
        BubblewrapSandbox,
        ContainerSandbox,
        LocalSandbox,
        Sandbox,
    )

    # Static safety scan and optional HITL gate.
    scanner = CodeSafetyScanner()
    safety = scanner.scan(code, language=language)
    if requires_hitl(safety, min_risk_level=settings.codeact_hitl_level):
        return {
            "success": False,
            "stdout": "",
            "stderr": (
                f"CodeAct execution blocked pending human approval. Risk level: "
                f"{safety.risk_level}. Findings: {safety.findings}"
            ),
            "exit_code": -1,
            "safety": (
                safety.to_dict() if hasattr(safety, "to_dict") else safety.__dict__
            ),
            "result": {},
        }

    workdir = Path(working_dir) if working_dir is not None else Path(tempfile.mkdtemp())
    workdir.mkdir(parents=True, exist_ok=True)

    if language == "python":
        script_path = workdir / "__code_act__.py"
        script_path.write_text(_build_python_wrapper(code), encoding="utf-8")
        interpreter = "python"

        # Inject tool bindings so generated code can call homomics_tool()
        if tool_registry is not None:
            tool_module = workdir / "_homomics_tools.py"
            tool_module.write_text(_build_tool_module(tool_registry), encoding="utf-8")
    elif language == "bash":
        script_path = workdir / "__code_act__.sh"
        script_path.write_text(code, encoding="utf-8")
        interpreter = "bash"
    elif language == "r":
        script_path = workdir / "__code_act__.R"
        script_path.write_text(code, encoding="utf-8")
        interpreter = "Rscript"
    else:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Unsupported language: {language}",
            "exit_code": -1,
            "result": {},
        }

    if save_artifact:
        (workdir / "__code_act_source__.py").write_text(code, encoding="utf-8")

    backend = settings.skill_sandbox_backend
    if settings.force_sandbox and backend == "auto":
        from homomics_lab.skills.sandbox import BubblewrapSandbox, ContainerSandbox

        if not (BubblewrapSandbox.is_available() or ContainerSandbox.is_available()):
            return {
                "success": False,
                "stdout": "",
                "stderr": (
                    "CodeAct execution refused: force_sandbox is enabled and no "
                    "isolated sandbox (bubblewrap/container) is available."
                ),
                "exit_code": -1,
                "result": {},
            }

    sandbox = Sandbox.create(
        backend, workdir, container_image=settings.skill_container_image
    )

    # Map language to sandbox interpreter command.  Bubblewrap/Container bind
    # workdir to /work, while LocalSandbox uses the host path directly.
    if isinstance(sandbox, LocalSandbox):
        script_arg = str(script_path)
    else:
        script_arg = f"/work/{script_path.name}"

    command = f"{interpreter} {script_arg}"

    try:
        output = await sandbox.run_command(
            command, cwd=workdir, timeout_seconds=timeout_seconds
        )
    except TimeoutError:
        return {
            "success": False,
            "stdout": "",
            "stderr": "CodeAct execution timed out",
            "exit_code": -1,
        }
    except Exception as exc:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"CodeAct sandbox execution failed: {exc}",
            "exit_code": -1,
        }

    result_path = workdir / "__skill_result__.json"
    result_data = {}
    if result_path.exists():
        try:
            result_data = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "success": True,
        "stdout": output,
        "stderr": "",
        "exit_code": 0,
        "result": result_data,
    }


async def run_code_act(
    task: str,
    language: str = "python",
    context: Optional[Dict[str, Any]] = None,
    working_dir: Optional[Path] = None,
    llm_client: Optional[LLMClient] = None,
    skill_registry: Optional[SkillRegistry] = None,
    retrieval_context: Optional[RetrievalContext] = None,
    tool_registry: Optional[ToolRegistry] = None,
    use_cache: Optional[bool] = None,
    max_tokens: int = 4000,
) -> Dict[str, Any]:
    """Generate and execute code for a CodeAct task."""
    context = context or {}
    code = await generate_code_async(
        task,
        language,
        context,
        llm_client,
        skill_registry,
        retrieval_context,
        use_cache=use_cache,
        max_tokens=max_tokens,
    )
    execution = await execute_code(
        code, language, working_dir, tool_registry=tool_registry, save_artifact=True
    )

    # Record a regression baseline for successful deterministic runs.
    if execution.get("success") and working_dir is not None:
        _record_regression_baseline(
            task, language, context, execution.get("result", {}), working_dir
        )

    return {
        "code": code,
        "success": execution.get("success", False),
        "stdout": execution.get("stdout", ""),
        "stderr": execution.get("stderr", ""),
        "exit_code": execution.get("exit_code", -1),
        "result": execution.get("result", {}),
    }


def _record_regression_baseline(
    task: str,
    language: str,
    context: Dict[str, Any],
    result: Dict[str, Any],
    working_dir: Path,
) -> None:
    """Record a regression baseline for a successful CodeAct execution."""
    try:
        from homomics_lab.skills.models import (
            SkillDefinition,
            SkillInputSchema,
            SkillOutputSchema,
            SkillRuntime,
        )
        from homomics_lab.stability.regression_tester import RegressionTester

        if not isinstance(result, dict):
            return

        skill = SkillDefinition(
            id=f"codeact:{hashlib.sha256(task.encode()).hexdigest()[:12]}",
            name="codeact_transient",
            description="Auto-generated transient skill from CodeAct",
            category="generated",
            version="1.0.0",
            runtime=SkillRuntime(type="python"),
            input_schema=SkillInputSchema(properties=context),
            output_schema=SkillOutputSchema(
                properties={k: {"type": "unknown"} for k in result.keys()}
            ),
        )
        tester = RegressionTester(working_dir)
        tester.record_baseline(
            skill=skill,
            test_case_id=f"{language}_default",
            test_input=context,
            actual_output=result,
            metadata={"task": task, "language": language},
        )
    except Exception:
        pass
