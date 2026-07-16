"""Agent-based executor for declarative / CLI / workflow skills.

Skills that do not ship executable scripts but instead provide structured
instructions (e.g. ``utils-workflow-management-nextflow``) are executed by an
LLM agent that can call tools (file_read, file_write, shell_exec, etc.).

If no LLM is configured, the executor falls back to returning the skill
instructions as a knowledge resource so callers can still use them for
retrieval or manual execution.
"""

import asyncio
import ast
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from homomics_lab.agent.progress_events import (
    build_agent_event,
    subagent_actor,
)
from homomics_lab.artifacts import build_artifact
from homomics_lab.config import settings
from homomics_lab.hpc.state import ExecutionState
from homomics_lab.llm_client import LLMClient
from homomics_lab.skills.models import SkillDefinition
from homomics_lab.tools.approval import ToolApprovalRequired, get_default_approval_store
from homomics_lab.tools.models import ToolResult
from homomics_lab.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


# Common aliases used by community skills (e.g. utils-workflow-management-nextflow)
_TOOL_ALIASES = {
    "read_file": "file_read",
    "write_file": "file_write",
    "edit_file": "file_edit",
    "run_shell_command": "shell_exec",
    "execute_shell": "shell_exec",
}


# Directory names that almost always hold inputs, not skill outputs. When an
# agentic run falls back to a directory scan we skip these so uploaded data is
# not mistaken for a produced artifact.
_INPUT_DIR_NAMES = {"data", "input", "inputs", "raw", "reference", "references"}
_SCAN_SKIP_DIRS = _INPUT_DIR_NAMES | {".git", ".metadata", "__pycache__", ".venv", "node_modules"}
_MAX_SCAN_FILES = 2000

# Convergence guardrails (read from settings with safe fallbacks so tests that
# construct the executor without a fully wired settings object still pass).
def _cfg(name: str, default: Any) -> Any:
    return getattr(settings, name, default)


def _llm_call_timeout() -> float:
    return float(_cfg("agent_llm_call_timeout_seconds", 90.0))


def _max_llm_failures() -> int:
    return int(_cfg("agent_max_consecutive_llm_failures", 3))


def _wall_clock() -> float:
    return float(_cfg("agent_skill_wall_clock_seconds", 1500.0))


def _source_read_hard_limit() -> int:
    return int(_cfg("agent_source_read_hard_limit", 12))


def _auto_run_enabled() -> bool:
    return bool(_cfg("agent_auto_run_script", True))


def _retry_backoff_base() -> float:
    return float(_cfg("agent_retry_backoff_base_seconds", 2.0))


def _max_idle_iterations() -> int:
    return int(_cfg("agent_max_idle_iterations", 3))


def _tool_output_budget(is_error: bool) -> int:
    """Per-field character budget for tool output text.

    Read from settings (``HOMOMICS_AGENT_TOOL_OUTPUT_MAX_CHARS``, default 4000)
    so operators can tune it. Error outputs get a wider budget (1.5x): the tail
    stack trace is the single most useful debugging signal and is worth the
    extra tokens.
    """
    base = max(500, int(_cfg("agent_tool_output_max_chars", 4000)))
    return int(base * 1.5) if is_error else base


def _is_error_tool_output(tool_output: Dict[str, Any]) -> bool:
    """Heuristic: does this record carry an error whose tail must be preserved?"""
    if tool_output.get("success") is False:
        return True
    error_message = tool_output.get("error_message")
    if isinstance(error_message, str) and error_message.strip():
        return True
    output = tool_output.get("output")
    if isinstance(output, dict):
        stderr = output.get("stderr")
        if isinstance(stderr, str) and stderr.strip():
            return True
        returncode = output.get("returncode")
        if isinstance(returncode, int) and not isinstance(returncode, bool) and returncode != 0:
            return True
    return False


def _truncate_text(value: str, budget: int, is_error: bool) -> str:
    """Truncate ``value`` to at most ``budget`` chars, marker included.

    Successful output keeps head+tail halves (initial context plus the final
    status lines). Error output is tail-priority: compile logs and tracebacks
    put the actionable frames at the end, so only a small head is kept for
    context and the rest of the budget goes to the tail.
    """
    if len(value) <= budget:
        return value
    head = budget // 4 if is_error else budget // 2
    # Reserve room for the marker so the result never exceeds the budget.
    # Two passes are enough: the omitted count only grows as the tail shrinks,
    # so its digit width (and thus the marker length) stabilizes immediately.
    tail = budget - head
    for _ in range(2):
        omitted = len(value) - head - tail
        marker_len = len(f"\n... [truncated {omitted} chars] ...\n")
        tail = max(0, budget - head - marker_len)
    omitted = len(value) - head - tail
    tail_text = value[len(value) - tail :] if tail else ""
    return f"{value[:head]}\n... [truncated {omitted} chars] ...\n{tail_text}"


def _compact_tool_output(tool_output: Dict[str, Any]) -> Dict[str, Any]:
    """Bound tool output before it enters the LLM context or persisted results.

    This is the single compaction point for agent tool outputs: the executor
    applies it right after each tool invocation, before the record is appended
    to ``tool_outputs``. That list is both replayed into later prompts and
    serialized into the skill result, so raw multi-megabyte logs must never
    land there. Only long text fields are truncated; structured fields (paths,
    return codes, numbers, short strings) pass through intact so artifact
    harvesting and downstream consumers keep working.

    Strategy: successful output keeps head+tail; error output (``success`` is
    False, an ``error_message``/``stderr`` is present, or the command exited
    non-zero) is tail-priority because stack traces and the failing line sit at
    the end of compile/runtime logs, and gets a 1.5x wider budget.
    """
    is_error = _is_error_tool_output(tool_output)
    budget = _tool_output_budget(is_error)
    compact = dict(tool_output)
    for key in ("output", "error_message", "stderr"):
        value = compact.get(key)
        if isinstance(value, str):
            compact[key] = _truncate_text(value, budget, is_error)
        elif key == "output" and isinstance(value, dict):
            # shell_exec nests stdout/stderr/returncode here: truncate long
            # strings in place, keep structured fields intact.
            trimmed = dict(value)
            for sub_key, sub_val in value.items():
                if isinstance(sub_val, str):
                    trimmed[sub_key] = _truncate_text(sub_val, budget, is_error)
            compact[key] = trimmed
    return compact


_SCRIPT_RUNNERS = {
    ".py": "python",
    ".R": "Rscript",
    ".sh": "bash",
    ".bash": "bash",
}


def _oneliner(text: Any, n: int = 120) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= n else s[: max(0, n - 1)] + "…"


# Per-skill model selection. A skill may pin an explicit model via the
# ``model`` frontmatter key, or ask for a capability tier via ``model_tier``
# (``model: cheap|reasoning|coding`` is accepted as an alias). Tiers map to
# ModelCatalog task types and are resolved through the LLMRouter.
_SKILL_MODEL_TIERS = {"cheap", "reasoning", "coding"}
_TIER_TASK_TYPE = {
    "cheap": "cheap",
    "reasoning": "planning",
    "coding": "code_generation",
}
_DEFAULT_MODEL_WORDS = {"", "default", "inherit"}


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


_SOURCE_READ_PATTERNS = re.compile(
    r"\b(cat|sed|grep|awk|head|tail|less|more|xxd|od|strings|nl|wc)\b"
)


def _is_source_read(tool_name: str, arguments: Dict[str, Any]) -> bool:
    """Return True if the tool call is just inspecting source/text files."""
    canonical = _TOOL_ALIASES.get(tool_name, tool_name)
    if canonical == "file_read":
        return True
    if canonical == "file_list":
        return True
    if canonical == "shell_exec":
        cmd = str(arguments.get("command", "")).lower()
        # A command that only inspects files (cat/grep/head/...) counts as a read.
        if _SOURCE_READ_PATTERNS.search(cmd):
            return True
    return False


def _command_looks_like_driver_script(command: str) -> bool:
    """Return True if a shell_exec command is running a generated driver script."""
    cmd = str(command).strip().lower()
    # Must invoke python on a .py file that looks like a driver script.
    if not cmd.startswith("python") and " python" not in cmd:
        return False
    if ".py" not in cmd:
        return False
    # Exclude simple inspection/installation commands.
    if any(k in cmd for k in ("pip ", "cat ", "ls ", "grep ", "head ", "tail ", "wc ")):
        return False
    return True


def _iter_strings(obj: Any):
    """Yield every string value nested inside dicts/lists."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_strings(v)
    elif isinstance(obj, str):
        yield obj


def _candidate_paths_from_text(text: str) -> List[Path]:
    """Pull path-like tokens (with a known artifact extension) out of text."""
    found: List[Path] = []
    for token in re.split(r"[\s,;`'\"()\[\]{}]+", text):
        if len(token) < 3 or len(token) > 512:
            continue
        if "/" not in token and "\\" not in token:
            continue
        try:
            p = Path(token)
        except (ValueError, OSError):
            continue
        if p.suffix.lower() in {ext for ext in _ARTIFACT_EXTS}:
            found.append(p)
    return found


_ARTIFACT_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".csv", ".tsv", ".html", ".htm", ".pdf", ".json",
    ".h5ad", ".h5", ".txt", ".md", ".log", ".rds",
}


def harvest_agent_artifacts(
    working_dir: Optional[Path],
    tool_outputs: List[Dict[str, Any]],
    ignore_preexisting: Optional[Dict[str, float]] = None,
) -> tuple[List[Dict[str, Any]], List[str]]:
    """Collect files an agentic run actually produced.

    Strategy: trust the agent's own tool calls first (paths that appear in tool
    inputs/outputs and now exist on disk). If none are found, fall back to a
    bounded scan of ``working_dir`` that skips obvious input/hidden directories.

    ``ignore_preexisting`` is a mapping of absolute paths that existed before
    this agent run started to their modification timestamps. Files whose
    timestamp has not changed are treated as stale and skipped; overwritten
    files are kept because their mtime is newer.

    Returns ``(envelopes, output_files)`` where ``envelopes`` are the
    frontend-ready dicts from :func:`build_artifact` and ``output_files`` is the
    plain path-string list (for consumers that key on ``output_files``).
    """
    root = Path(working_dir) if working_dir else None
    ignore_map: Dict[str, float] = ignore_preexisting or {}
    seen: set = set()
    ordered: List[Path] = []

    # Only these tools actually create or modify files. Harvesting paths from
    # file_read / file_list would mistake inputs for outputs (e.g. the uploaded
    # h5ad the agent merely inspected).
    write_tools = {"file_write", "write_file", "file_edit", "edit_file", "shell_exec"}

    def _is_stale(path: Path) -> bool:
        try:
            key = str(path.absolute())
            old_mtime = ignore_map.get(key)
            if old_mtime is None:
                return False
            return path.stat().st_mtime <= old_mtime + 1.0
        except OSError:
            return True

    def add(path: Path, check_ignore: bool = True) -> None:
        try:
            if not path.is_file():
                return
            key = str(path.absolute())
            if key in seen or (check_ignore and _is_stale(path)):
                return
            seen.add(key)
            ordered.append(path)
        except OSError:
            return

    # 1. Paths referenced by the agent's own write/execute tool calls.
    # These are always honored, even if the path existed before the run, because
    # the agent explicitly (re)wrote the file in this run.
    for entry in tool_outputs or []:
        if not isinstance(entry, dict):
            continue
        tool_name = str(entry.get("tool") or entry.get("tool_name") or "")
        canonical = _TOOL_ALIASES.get(tool_name, tool_name)
        if canonical not in write_tools:
            continue
        for text in _iter_strings(entry):
            for cand in _candidate_paths_from_text(text):
                if not cand.is_absolute() and root is not None:
                    cand = root / cand
                add(cand, check_ignore=False)

    # 2. Bounded directory scan to catch files the agent produced but did not
    # explicitly name in tool output (e.g. files written by a driver script).
    if root is not None and root.is_dir():
        count = 0
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in _SCAN_SKIP_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                if count >= _MAX_SCAN_FILES:
                    break
                p = Path(dirpath) / fname
                if p.is_file() and p.suffix.lower() in _ARTIFACT_EXTS:
                    count += 1
                    add(p)
            if count >= _MAX_SCAN_FILES:
                break

    envelopes: List[Dict[str, Any]] = []
    output_files: List[str] = []
    for p in ordered:
        # Never surface files that live in obvious input directories, even if a
        # shell command happened to print their path.
        if root is not None:
            try:
                rel = p.resolve().relative_to(root.resolve())
                if any(part in _INPUT_DIR_NAMES for part in rel.parts):
                    continue
            except ValueError:
                # Outside the workspace: only keep if a write tool named it
                # explicitly (already the case for strategy 1); skip for safety.
                continue
        env = build_artifact(p)
        if env is not None:
            envelopes.append(env)
            output_files.append(str(p))
    return envelopes, output_files


def _is_falsy(value: Any) -> bool:
    """Return True if a metric value should be considered missing/placeholder."""
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return True
    if isinstance(value, (int, float)) and value == 0:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _read_json_metrics(path: Path) -> Dict[str, Any]:
    """Read a summary JSON file and flatten useful metrics."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except Exception:
        return {}

    metrics: Dict[str, Any] = {}
    shape = data.get("shape") or {}
    if isinstance(shape, dict):
        metrics["cell_count"] = shape.get("n_cells", shape.get("n_obs"))
        metrics["gene_count"] = shape.get("n_genes", shape.get("n_vars"))
    if "obs_columns" in data:
        metrics["obs_columns"] = data["obs_columns"]
    if "var_columns" in data:
        metrics["var_columns"] = data["var_columns"]
    if "layers" in data:
        metrics["layers"] = data["layers"]
    for key in ("nnz", "sparsity", "total_counts", "mean_counts_per_cell", "median_genes_per_cell"):
        if key in data:
            metrics[key] = data[key]
    return {k: v for k, v in metrics.items() if v is not None}


def _build_summary_from_metrics(metrics: Dict[str, Any], output_files: List[str]) -> str:
    """Generate a concrete fallback summary from enriched metrics."""
    lines = []
    cell_count = metrics.get("cell_count")
    gene_count = metrics.get("gene_count")
    if cell_count is not None and gene_count is not None:
        lines.append(f"Dataset shape: **{cell_count} cells × {gene_count} genes**.")
    layers = metrics.get("layers")
    if layers:
        lines.append(f"Layers: {', '.join(str(x) for x in layers)}.")
    total_counts = metrics.get("total_counts")
    if total_counts is not None:
        lines.append(f"Total counts: {total_counts:,.0f}.")
    mean_counts = metrics.get("mean_counts_per_cell")
    if mean_counts is not None:
        lines.append(f"Mean counts per cell: {mean_counts:,.1f}.")
    median_genes = metrics.get("median_genes_per_cell")
    if median_genes is not None:
        lines.append(f"Median genes per cell: {median_genes:,.0f}.")
    obs_cols = metrics.get("obs_columns")
    if obs_cols:
        lines.append(f"Obs metadata columns: {', '.join(str(x) for x in obs_cols)}.")
    if output_files:
        lines.append("Generated files: " + ", ".join(Path(p).name for p in output_files) + ".")
    return "\n".join(lines) if lines else ""


def enrich_final_output_from_files(
    final_output: Dict[str, Any],
    output_files: List[str],
) -> Dict[str, Any]:
    """Back-fill final_output.metrics from generated summary/report files.

    Agents sometimes return placeholder zeros or omit concrete numbers in
    final_output.metrics even when the driver script produced a correct summary
    JSON. This helper reads the actual output files, merges real metrics, and
    falls back to a generated concrete summary when the agent's summary is vague.
    """
    if not output_files:
        return final_output

    metrics = dict(final_output.get("metrics", {}))

    for path_str in output_files:
        path = Path(path_str)
        if not path.is_file():
            continue
        if path.name.lower().endswith("summary.json") or path.suffix.lower() == ".json":
            file_metrics = _read_json_metrics(path)
            for key, value in file_metrics.items():
                if _is_falsy(metrics.get(key)) and not _is_falsy(value):
                    metrics[key] = value

    # Always expose core shape metrics even if the agent forgot them.
    for path_str in output_files:
        path = Path(path_str)
        if not path.is_file():
            continue
        if path.name.lower().endswith("summary.json") or path.suffix.lower() == ".json":
            file_metrics = _read_json_metrics(path)
            for key in ("cell_count", "gene_count", "layers", "obs_columns", "var_columns",
                        "total_counts", "mean_counts_per_cell", "median_genes_per_cell"):
                if key not in metrics and not _is_falsy(file_metrics.get(key)):
                    metrics[key] = file_metrics[key]

    final_output["metrics"] = metrics

    summary = final_output.get("summary", "")
    fallback = _build_summary_from_metrics(metrics, output_files)
    # If the agent summary is empty or lacks concrete numbers, append the fallback.
    has_numbers = bool(re.search(r"\d", str(summary)))
    if fallback and (not summary or not has_numbers):
        final_output["summary"] = fallback

    logger.debug(
        "Enriched final_output from %d output files for skill execution",
        len(output_files),
    )
    return final_output


class AgentSkillExecutor:
    """Execute declarative skills via an LLM tool loop.

    The skill's SKILL.md body is treated as the system prompt / specification.
    The LLM may call registered tools to produce files, run commands, or return
    a final result.
    """

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        llm_client: Optional[LLMClient] = None,
        max_iterations: int = 25,
        max_tool_retries: int = 2,
        progress_callback: Optional[Callable[[ExecutionState], None]] = None,
        parent_id: Optional[str] = None,
    ):
        self.tool_registry = tool_registry
        self.llm_client = llm_client
        self.max_iterations = max(max_iterations, 1)
        self.max_tool_retries = max(max_tool_retries, 0)
        self.progress_callback = progress_callback
        self._last_progress_pct: float = 0.0
        # Subagent attribution: when this loop runs as a child execution of a
        # parent job/task, progress events carry actor="subagent:<skill_id>"
        # and parent_id. Top-level executions leave both unset.
        self._parent_id: Optional[str] = parent_id
        # Per-execute() state, (re)assigned at the start of every run so a
        # shared executor instance never leaks one skill's settings into the
        # next (same pattern as _last_progress_pct).
        self._actor: Optional[str] = None
        self._model_override: Optional[str] = None

    def set_parent_context(self, parent_id: Optional[str]) -> None:
        """Set the parent job/task id used to attribute progress events."""
        self._parent_id = parent_id

    async def execute(
        self,
        skill: SkillDefinition,
        inputs: Dict[str, Any],
        working_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Execute a declarative skill (public entry point).

        Wraps :meth:`_execute_impl` and, for child executions, emits exactly
        one terminal progress state (COMPLETED/FAILED) carrying the subagent
        attribution, so consumers can close out the subagent's event group.
        Top-level executions emit no terminal state here — their lifecycle is
        owned by the job runner.
        """
        # Reset per-run state so a shared executor never leaks one skill's
        # settings into the next; _execute_impl (re)assigns both on the agent
        # path. Early knowledge-mode returns leave them unset, so no terminal
        # state is emitted for runs that never published attributed progress.
        self._actor = None
        self._model_override = None
        try:
            result = await self._execute_impl(skill, inputs, working_dir)
        except ToolApprovalRequired:
            # Awaiting human approval pauses the run; it is not terminal.
            raise
        except Exception as exc:
            self._publish_terminal(False, f"子执行失败：{_oneliner(exc, 120)}")
            raise
        self._publish_terminal(
            bool(result.get("success")),
            "子执行完成" if result.get("success") else "子执行失败",
        )
        return result

    def _publish_terminal(self, success: bool, phase: str) -> None:
        """Emit the single terminal state for a child execution.

        No-op for top-level executions: only runs attributed to a parent
        (``actor``/``parent_id`` set) close their event group this way.
        """
        if (
            self._actor is None
            or self._parent_id is None
            or self.progress_callback is None
        ):
            return
        try:
            self.progress_callback(
                ExecutionState(
                    job_id="",
                    status="COMPLETED" if success else "FAILED",
                    current_phase=phase,
                    progress_pct=100.0 if success else self._last_progress_pct,
                    scheduler_type="agent",
                    actor=self._actor,
                    parent_id=self._parent_id,
                )
            )
        except Exception:
            pass

    async def _execute_impl(
        self,
        skill: SkillDefinition,
        inputs: Dict[str, Any],
        working_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Execute a declarative skill.

        Returns:
            On success: ``{"success": True, "mode": "agent|knowledge", ...}``
        """
        instructions = skill.metadata.get("instructions") or skill.description
        # No LLM configured → treat the skill as knowledge.
        if self.llm_client is None or not self.llm_client.is_configured():
            return {
                "success": True,
                "mode": "knowledge",
                "skill_id": skill.id,
                "skill_type": skill.runtime.type,
                "instructions": instructions,
                "inputs": inputs,
                "note": "No LLM configured; returning skill instructions as knowledge.",
            }

        if self.tool_registry is None:
            return {
                "success": False,
                "mode": "knowledge",
                "skill_id": skill.id,
                "error": "Agent skill requires a ToolRegistry but none was provided.",
                "instructions": instructions,
            }

        tools = self._available_tools(skill)
        if not tools:
            return {
                "success": False,
                "skill_id": skill.id,
                "error": (
                    "Skill requested tools that are not registered or all tools were disallowed."
                ),
            }

        # Per-run context: subagent attribution for progress events and the
        # per-skill model selection (frontmatter model / model_tier).
        self._actor = subagent_actor(skill.id) if self._parent_id else None
        self._model_override = self._resolve_skill_model(skill)

        system_prompt = self._build_system_prompt(skill, inputs, tools)

        if not working_dir:
            working_dir = Path.cwd()
        else:
            working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
        # Snapshot files already in the workspace so we do not mistake stale
        # outputs for fresh ones. Bounded to keep startup fast on large dirs.
        # Store mtime so overwritten files are still reported as new outputs.
        preexisting_files: Dict[str, float] = {}
        count = 0
        for dirpath, dirnames, filenames in os.walk(working_dir, topdown=True):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fname in filenames:
                if count >= _MAX_SCAN_FILES:
                    break
                p = Path(dirpath) / fname
                if p.is_file():
                    try:
                        preexisting_files[str(p.absolute())] = p.stat().st_mtime
                    except OSError:
                        pass
                    count += 1
            if count >= _MAX_SCAN_FILES:
                break

        # Optional fast path: single-shot driver-script generation. Enabled by
        # default because it avoids the long-context doom loop for standard
        # analysis tasks while still falling back to the interactive loop when
        # the script fails.
        script_first_result = None
        if bool(_cfg("agent_script_first_enabled", False)):
            script_first_result = await self._script_first_execute(
                skill, inputs, working_dir, tools, preexisting_files=preexisting_files
            )
            if script_first_result is not None and script_first_result.get("success"):
                return script_first_result

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Skill: {skill.id}\n"
                    f"Phase 1 — Inspect first. Read the helper API reference, then briefly "
                    f"inspect the inputs (e.g. list files, read a helper signature, or run a "
                    f"short introspection command). Do NOT write files or return final yet.\n"
                    f"Inputs: {json.dumps(inputs, ensure_ascii=False)}"
                ),
            },
        ]

        tool_outputs: List[Dict[str, Any]] = []
        if script_first_result is not None:
            tool_outputs.extend(script_first_result.get("tool_outputs", []))
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "System note: A previous attempt to run a generated driver script "
                        "failed. Use the normal tool loop to diagnose and fix it. Do not "
                        "start over by reading source files.\n"
                        f"Driver error: {script_first_result.get('error', 'unknown')}"
                    ),
                }
            )
        consecutive_tool_errors = 0
        consecutive_llm_failures = 0
        nudges_used = 0
        deadline = time.monotonic() + max(1.0, _wall_clock())
        max_llm_failures = max(1, _max_llm_failures())
        last_llm_error = ""

        self._publish_progress(
            status="RUNNING",
            phase=f"Executing skill {skill.id}",
            progress_pct=5.0,
            active_task_id=skill.id,
        )

        iteration = 0
        idle_count = 0
        source_read_count = 0
        source_read_hard_limit = max(3, _source_read_hard_limit())
        last_action_key: Optional[str] = None
        exploration_done = bool(script_first_result is not None)
        write_tools = {"file_write", "file_edit", "write_file", "edit_file"}
        while iteration < self.max_iterations:
            # Wall-clock guard: never let a slow/flaky provider hang the job.
            if time.monotonic() > deadline:
                self._publish_progress(
                    status="RUNNING",
                    phase="已达到技能执行时间上限，正在整理已生成的结果",
                    progress_pct=95.0,
                    active_task_id=skill.id,
                )
                break

            progress_pct = min(95.0, 10.0 + (iteration + 1) * (85.0 / max(self.max_iterations, 1)))
            # Surface "the model is thinking" so the UI is never silently stuck
            # during a long LLM round-trip.
            self._publish_progress(
                status="RUNNING",
                phase=f"正在调用模型规划下一步（{iteration + 1}/{self.max_iterations}）",
                progress_pct=progress_pct,
                active_task_id=skill.id,
            )

            # Phase-aware token budget: exploration answers should be short (a single
            # tool call), execution answers may contain a driver script. 8000 tokens
            # gives enough headroom for a compact driver script that also writes an
            # annotated .h5ad for deterministic comparison, without exceeding the
            # provider's reliable output range.
            call_max_tokens = 8000 if exploration_done else 800
            response_text, llm_error = await self._call_llm(
                messages, max_tokens=call_max_tokens
            )
            if llm_error is not None:
                consecutive_llm_failures += 1
                last_llm_error = llm_error
                self._publish_progress(
                    status="RUNNING",
                    phase=(
                        f"模型调用失败/超时（{consecutive_llm_failures}/{max_llm_failures}）"
                    ),
                    progress_pct=progress_pct,
                    active_task_id=skill.id,
                )
                self._publish_tool_event(
                    "llm_retry",
                    error_message=last_llm_error,
                    active_task_id=skill.id,
                )
                if consecutive_llm_failures >= max_llm_failures:
                    return self._llm_unavailable_result(
                        skill,
                        tool_outputs,
                        last_llm_error,
                        working_dir,
                        ignore_preexisting=preexisting_files,
                    )
                # Exponential backoff before retrying; do not consume an iteration
                # on a transient provider failure.
                delay = min(
                    30.0,
                    _retry_backoff_base() * (2 ** (consecutive_llm_failures - 1)),
                )
                await asyncio.sleep(delay)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "System note: 上一次模型调用失败或超时（"
                            + last_llm_error[:200]
                            + "）。请直接输出一个合法的 JSON action，"
                            "优先执行已写好的脚本或返回 action: \"final\"。"
                        ),
                    }
                )
                continue

            consecutive_llm_failures = 0

            action = self._parse_action(response_text)
            if action is None:
                consecutive_llm_failures += 1
                last_llm_error = "non-JSON response"
                self._publish_progress(
                    status="RUNNING",
                    phase=(
                        f"模型调用失败/超时（{consecutive_llm_failures}/{max_llm_failures}）"
                    ),
                    progress_pct=progress_pct,
                    active_task_id=skill.id,
                )
                self._publish_tool_event(
                    "llm_retry",
                    error_message=last_llm_error,
                    active_task_id=skill.id,
                )
                if consecutive_llm_failures >= max_llm_failures:
                    return self._llm_unavailable_result(
                        skill,
                        tool_outputs,
                        last_llm_error,
                        working_dir,
                        ignore_preexisting=preexisting_files,
                    )
                delay = min(
                    30.0,
                    _retry_backoff_base() * (2 ** (consecutive_llm_failures - 1)),
                )
                await asyncio.sleep(delay)
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "System note: 上次输出不是合法 JSON。请仅输出一个 JSON "
                            "对象（action 为 \"tool\" 或 \"final\"），不要包含 markdown。"
                        ),
                    }
                )
                continue

            # Doom-loop / idle detection: same action repeated without progress.
            action_key = self._action_key(action)
            if action_key == last_action_key:
                idle_count += 1
            else:
                idle_count = 0
            last_action_key = action_key
            if idle_count >= _max_idle_iterations():
                return self._llm_unavailable_result(
                    skill,
                    tool_outputs,
                    "agent 连续多步没有实质进展（重复 action 或无工具产出）",
                    working_dir,
                    ignore_preexisting=preexisting_files,
                )
            if idle_count == _max_idle_iterations() - 1:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "System note: 你已重复多步没有实质进展。下一步必须执行一个 "
                            "shell_exec 跑完整 pipeline 或返回 action: \"final\"，"
                            "否则执行将终止。"
                        ),
                    }
                )

            action_type = action.get("action")
            if action_type == "final":
                final_output = action.get("final_output", {})
                artifacts, output_files = harvest_agent_artifacts(
                    working_dir, tool_outputs, ignore_preexisting=preexisting_files
                )
                if output_files:
                    self._publish_tool_event(
                        "artifact",
                        artifacts=output_files,
                        active_task_id=skill.id,
                    )
                validation_errors = self._validate_output(skill, final_output)
                if validation_errors:
                    return {
                        "success": False,
                        "skill_id": skill.id,
                        "error": f"Output validation failed: {'; '.join(validation_errors)}",
                        "final_output": final_output,
                        "artifacts": artifacts,
                        "output_files": output_files,
                        "tool_outputs": tool_outputs,
                    }
                final_output = enrich_final_output_from_files(final_output, output_files)
                return {
                    "success": True,
                    "mode": "agent",
                    "skill_id": skill.id,
                    "final_output": final_output,
                    "artifacts": artifacts,
                    "output_files": output_files,
                    "thought": action.get("thought", ""),
                    "tool_outputs": tool_outputs,
                }

            if action_type != "tool":
                return {
                    "success": False,
                    "skill_id": skill.id,
                    "error": f"Unknown action type: {action_type}",
                    "raw_response": action,
                    "tool_outputs": tool_outputs,
                }

            tool_name = action.get("tool")
            arguments = action.get("arguments", {})
            if tool_name not in tools:
                return {
                    "success": False,
                    "skill_id": skill.id,
                    "error": f"Tool '{tool_name}' is not allowed or not registered.",
                    "tool_outputs": tool_outputs,
                }

            canonical_tool_name = _TOOL_ALIASES.get(tool_name, tool_name)

            # Phase 1 enforcement: the first turn must inspect, not write files or
            # finalize. This prevents the model from trying to emit a long driver
            # script before it has even looked at the helpers or the data.
            if not exploration_done:
                messages.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(action, ensure_ascii=False),
                    }
                )
                if action_type == "final":
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "System note: Phase 1 requires inspection. "
                                "Do not return final yet. Use file_read/file_list/shell_exec "
                                "to check helper signatures and inputs first."
                            ),
                        }
                    )
                    iteration += 1
                    continue
                if canonical_tool_name in write_tools:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "System note: Phase 1 requires inspection. "
                                f"Tool '{canonical_tool_name}' writes files and is not allowed yet. "
                                "Use file_read, file_list, or shell_exec to inspect first. "
                                "Do not write files or run the full pipeline yet."
                            ),
                        }
                    )
                    iteration += 1
                    continue
                if canonical_tool_name == "file_read":
                    path = str(arguments.get("path", ""))
                    try:
                        file_size = Path(path).stat().st_size
                    except Exception:
                        file_size = 0
                    if file_size > 5000:
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "System note: Phase 1 only allows reading short files. "
                                    f"'{path}' is too large ({file_size} bytes). "
                                    "Use the helper API reference in the system prompt instead; "
                                    "do not read whole modules."
                                ),
                            }
                        )
                        iteration += 1
                        continue

            tool_def = self.tool_registry.get(canonical_tool_name)

            # High-risk tool approval in interactive mode.
            if (
                tool_def is not None
                and tool_def.risk_level == "high"
                and settings.interactive_mode
            ):
                approval_store = get_default_approval_store()
                request = approval_store.create_request(
                    tool_name=tool_name,
                    arguments=arguments,
                    risk_level=tool_def.risk_level,
                )
                raise ToolApprovalRequired(
                    call_id=request.call_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    risk_level=tool_def.risk_level,
                )

            arg_summary = self._arg_summary(canonical_tool_name, arguments)
            self._publish_progress(
                status="RUNNING",
                phase=(
                    f"调用工具 {tool_name}"
                    + (f"：{arg_summary}" if arg_summary else "")
                ),
                progress_pct=progress_pct,
                active_task_id=skill.id,
            )
            self._publish_tool_event(
                "tool_start",
                tool=tool_name,
                arguments={"summary": arg_summary} if arg_summary else arguments,
                active_task_id=skill.id,
            )

            tool_output = await self._invoke_tool_with_logging(
                canonical_tool_name, tool_name, arguments
            )
            # Compact BEFORE the record enters tool_outputs: that list is both
            # persisted in the skill result and replayed into later prompts, so
            # raw multi-megabyte logs must never land there. Only long text
            # fields are truncated; paths/structured fields survive for
            # artifact harvesting and the tool events below.
            tool_output = _compact_tool_output(tool_output)
            tool_outputs.append(tool_output)

            result_preview = self._result_preview(tool_output)
            self._publish_progress(
                status="RUNNING",
                phase=(
                    f"工具 {tool_name} 返回"
                    + ("成功" if tool_output.get("success", True) else "失败")
                    + (f"：{result_preview}" if result_preview else "")
                ),
                progress_pct=progress_pct,
                active_task_id=skill.id,
            )
            self._publish_tool_event(
                "tool_end",
                tool=tool_name,
                success=tool_output.get("success", True),
                output=result_preview,
                error_message=tool_output.get("error_message"),
                latency_ms=tool_output.get("latency_ms"),
                active_task_id=skill.id,
            )

            if tool_output.get("success") is False:
                consecutive_tool_errors += 1
                if consecutive_tool_errors > self.max_tool_retries:
                    return {
                        "success": False,
                        "skill_id": skill.id,
                        "error": (
                            f"Tool '{tool_name}' failed {consecutive_tool_errors} times in a row. "
                            "Stopping execution."
                        ),
                        "tool_outputs": tool_outputs,
                    }
            else:
                consecutive_tool_errors = 0

            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(action, ensure_ascii=False),
                }
            )
            messages.append(
                {
                    "role": "user",
                    # tool_output was already compacted at the append site
                    # above; _compact_tool_output is the single source of truth.
                    "content": "Tool result: "
                    + json.dumps(
                        tool_output,
                        ensure_ascii=False,
                        default=str,
                    ),
                }
            )

            if not exploration_done:
                exploration_done = True
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Phase 1 inspection complete. Enter Phase 2 — Execute. "
                            "Write ONE driver script (.py or .R) that calls the helpers, "
                            "satisfies every clause of the objective, and saves outputs "
                            "with clear filenames. Then run it with shell_exec and return "
                            "action: \"final\" listing the output paths."
                        ),
                    }
                )

            # Fast-path finalize: once a driver script has run successfully and
            # produced real outputs, avoid the long-context doom loop by asking
            # the model to verify and finalize in one compact turn. If the model
            # cannot produce a final action, we still return the existing outputs
            # rather than spinning until truncation.
            if (
                exploration_done
                and canonical_tool_name == "shell_exec"
                and tool_output.get("success", True)
                and _command_looks_like_driver_script(str(arguments.get("command", "")))
            ):
                artifacts_now, output_files_now = harvest_agent_artifacts(
                    working_dir, tool_outputs, ignore_preexisting=preexisting_files
                )
                if output_files_now:
                    self._publish_progress(
                        status="RUNNING",
                        phase="驱动脚本已生成结果，正在生成最终总结",
                        progress_pct=92.0,
                        active_task_id=skill.id,
                    )
                    objective = str(inputs.get("user_request", "")) if isinstance(inputs, dict) else ""
                    final_action = await self._compact_finalize(
                        skill, objective, output_files_now
                    )
                    if final_action and final_action.get("action") == "final":
                        final_output = enrich_final_output_from_files(
                            final_action.get("final_output", {}), output_files_now
                        )
                        return {
                            "success": True,
                            "mode": "agent",
                            "skill_id": skill.id,
                            "final_output": final_output,
                            "artifacts": artifacts_now,
                            "output_files": output_files_now,
                            "tool_outputs": tool_outputs,
                            "thought": final_action.get("thought", ""),
                        }
                    final_output = enrich_final_output_from_files(
                        {"note": "驱动脚本执行成功并生成结果文件。", "output_files": output_files_now},
                        output_files_now,
                    )
                    return {
                        "success": True,
                        "mode": "agent",
                        "skill_id": skill.id,
                        "final_output": final_output,
                        "artifacts": artifacts_now,
                        "output_files": output_files_now,
                        "tool_outputs": tool_outputs,
                    }

            # Convergence nudge: steer the agent away from endless exploration
            # and toward executing + finalizing. Deterministic, general, and
            # capped so it cannot dominate the loop.
            nudge = self._loop_nudge(
                tool_outputs,
                working_dir,
                iteration,
                nudges_used,
                ignore_preexisting=preexisting_files,
            )
            if nudge:
                nudges_used += 1
                messages.append({"role": "user", "content": nudge})

            # Hard limit on source-code exploration. Agents repeatedly reading
            # SKILL.md / helper source is the main cause of slow convergence and
            # provider timeouts. After a small budget of reads we force action.
            if _is_source_read(tool_name, arguments):
                source_read_count += 1
                if source_read_count >= source_read_hard_limit:
                    return self._llm_unavailable_result(
                        skill,
                        tool_outputs,
                        "已达到源码/文档阅读上限；请使用上面给出的 helper API 直接写驱动脚本运行。",
                        working_dir,
                        ignore_preexisting=preexisting_files,
                    )
                if source_read_count >= source_read_hard_limit - 1:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "System note: 你已经多次阅读源码/文档。下一步必须写一个 "
                                "driver 脚本并通过 shell_exec 运行它，不要再阅读任何文件，"
                                "除非脚本执行报错需要定位问题。"
                            ),
                        }
                    )

            iteration += 1

        # Deterministic recovery: if the agent wrote a runnable script but never
        # got around to executing it (a common convergence failure under a slow
        # LLM), run it now instead of discarding the work. This does not change
        # the skill — the LLM still authored the script; we only execute it.
        if _auto_run_enabled():
            await self._auto_run_unrun_script(tool_outputs, skill.id)

        artifacts, output_files = harvest_agent_artifacts(
            working_dir, tool_outputs, ignore_preexisting=preexisting_files
        )
        if output_files:
            self._publish_tool_event(
                "artifact",
                artifacts=output_files,
                active_task_id=skill.id,
            )
        if artifacts:
            # The loop did not converge but real outputs exist. Surface them as
            # a partial success instead of discarding the work and reporting a
            # bare failure to the user.
            final_output = enrich_final_output_from_files(
                {"note": "已达到迭代上限，返回执行过程中已生成的部分结果。", "output_files": output_files},
                output_files,
            )
            return {
                "success": True,
                "mode": "agent",
                "partial": True,
                "skill_id": skill.id,
                "final_output": final_output,
                "artifacts": artifacts,
                "output_files": output_files,
                "tool_outputs": tool_outputs,
            }
        return {
            "success": False,
            "skill_id": skill.id,
            "error": "Agent skill exceeded maximum iterations without producing a final result.",
            "artifacts": artifacts,
            "output_files": output_files,
            "tool_outputs": tool_outputs,
        }

    def _resolve_skill_model(self, skill: SkillDefinition) -> Optional[str]:
        """Resolve the model this skill's agent loop should use, if any.

        Honors the skill frontmatter keys ``model`` (explicit model name, or a
        tier alias) and ``model_tier`` (``cheap`` | ``reasoning`` | ``coding``).
        Tiers are resolved to a concrete model through the LLMRouter /
        ModelCatalog. Any resolution failure falls back to the default model
        with a warning, so a bad declaration never breaks execution.

        Returns ``None`` when the default routing should be used.
        """
        metadata = skill.metadata or {}
        raw_model = str(metadata.get("model") or "").strip()
        tier = str(metadata.get("model_tier") or "").strip().lower()

        # ``model: cheap|reasoning|coding`` doubles as a tier declaration.
        if raw_model.lower() in _SKILL_MODEL_TIERS:
            tier = tier or raw_model.lower()
            raw_model = ""

        if raw_model.lower() not in _DEFAULT_MODEL_WORDS:
            return self._resolve_explicit_model(raw_model, skill.id)

        if tier in _DEFAULT_MODEL_WORDS:
            return None
        task_type = _TIER_TASK_TYPE.get(tier)
        if task_type is None:
            logger.warning(
                "Skill '%s' declares unknown model_tier %r; using the default model",
                skill.id,
                tier,
            )
            return None

        router = self._llm_router()
        if router is None:
            logger.warning(
                "Skill '%s' declares model_tier %r but no LLM router is available; "
                "using the default model",
                skill.id,
                tier,
            )
            return None
        try:
            decision = router.select(task_type=task_type, prefer_cheap=(tier == "cheap"))
        except Exception as exc:
            logger.warning(
                "Failed to resolve model_tier %r for skill '%s': %s; using the default model",
                tier,
                skill.id,
                exc,
            )
            return None
        honored = decision.reason.startswith("catalog:") or decision.reason == "cheap"
        if not honored:
            logger.warning(
                "Skill '%s' model_tier %r could not be honored (no configured provider "
                "serves a tier model); using the default model",
                skill.id,
                tier,
            )
            return None
        logger.info(
            "Skill '%s' uses model %r for model_tier %r (%s)",
            skill.id,
            decision.model,
            tier,
            decision.reason,
        )
        return decision.model

    def _resolve_explicit_model(self, model: str, skill_id: str) -> Optional[str]:
        """Validate an explicit ``model`` declaration against configured providers."""
        router = self._llm_router()
        if router is None:
            logger.warning(
                "Skill '%s' declares model %r but no LLM router is available; "
                "using the default model",
                skill_id,
                model,
            )
            return None
        try:
            decision = router.select(model=model)
        except Exception as exc:
            logger.warning(
                "Failed to resolve model %r for skill '%s': %s; using the default model",
                model,
                skill_id,
                exc,
            )
            return None
        if decision.model != model:
            logger.warning(
                "Skill '%s' requested model %r but no configured provider serves it; "
                "using the default model",
                skill_id,
                model,
            )
            return None
        logger.info("Skill '%s' uses explicitly declared model %r", skill_id, model)
        return decision.model

    def _llm_router(self) -> Optional[Any]:
        """Return the LLMRouter backing the configured client, if reachable."""
        if self.llm_client is None:
            return None
        return getattr(self.llm_client, "router", None) or getattr(
            self.llm_client, "_router", None
        )

    def _publish_progress(
        self,
        status: str,
        phase: str,
        progress_pct: float,
        active_task_id: Optional[str] = None,
    ) -> None:
        """Emit a best-effort progress update when a callback is configured."""
        self._last_progress_pct = progress_pct
        if self.progress_callback is None:
            return
        try:
            self.progress_callback(
                ExecutionState(
                    job_id="",
                    status=status,
                    current_phase=phase,
                    progress_pct=progress_pct,
                    scheduler_type="agent",
                    active_task_id=active_task_id,
                    actor=self._actor,
                    parent_id=self._parent_id,
                )
            )
        except Exception:
            pass

    def _publish_tool_event(
        self,
        event_type: str,
        *,
        tool: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        success: Optional[bool] = None,
        output: Optional[str] = None,
        error_message: Optional[str] = None,
        artifacts: Optional[List[str]] = None,
        latency_ms: Optional[float] = None,
        active_task_id: Optional[str] = None,
    ) -> None:
        """Emit a structured agent tool event so the frontend can show live progress.

        Events travel inside ``ExecutionState.resource_usage`` so they do not
        break existing consumers that only look at ``status``/``current_phase``.
        Child executions (subagents) stamp every event with ``actor`` and
        ``parent_id``; see ``homomics_lab.agent.progress_events`` for the
        contract.
        """
        if self.progress_callback is None:
            return
        event = build_agent_event(
            event_type,
            actor=self._actor,
            parent_id=self._parent_id,
            tool=tool,
            arguments=arguments,
            success=success,
            output=output,
            error_message=error_message,
            artifacts=artifacts,
            latency_ms=latency_ms,
        )
        try:
            self.progress_callback(
                ExecutionState(
                    job_id="",
                    status="RUNNING",
                    current_phase=tool or "agent",
                    progress_pct=self._last_progress_pct,
                    scheduler_type="agent",
                    active_task_id=active_task_id,
                    resource_usage={"agent_events": [event]},
                    actor=self._actor,
                    parent_id=self._parent_id,
                )
            )
        except Exception:
            pass

    def _loop_nudge(
        self,
        tool_outputs: List[Dict[str, Any]],
        working_dir: Optional[Path],
        iteration: int,
        nudges_used: int,
        ignore_preexisting: Optional[set] = None,
    ) -> Optional[str]:
        """Return a short steering message, or None.

        Keeps the agent converging: run what it wrote, and finalize once real
        output files exist. Capped at two nudges per run so it guides rather
        than nags.
        """
        if nudges_used >= 2:
            return None

        wrote_script = False
        ran_after_write = False
        last_write_idx = -1
        for i, entry in enumerate(tool_outputs):
            if not isinstance(entry, dict):
                continue
            name = _TOOL_ALIASES.get(
                str(entry.get("tool") or ""), str(entry.get("tool") or "")
            )
            if name in {"file_write", "file_edit"}:
                args = entry.get("arguments", {}) or {}
                path = str(args.get("path", ""))
                if path.endswith((".py", ".R", ".sh", ".bash")):
                    wrote_script = True
                    last_write_idx = i
            if name == "shell_exec" and last_write_idx >= 0 and i > last_write_idx:
                ran_after_write = True

        if wrote_script and not ran_after_write and iteration >= 1:
            return (
                "System note: 你已经写了脚本但还没有运行它。请立即用 `shell_exec` "
                "实际执行该脚本（生成声明的输出文件），不要再继续读取或重写文件，"
                "除非上一次执行报错需要修复。"
            )

        last_tool = tool_outputs[-1] if tool_outputs else None
        last_failed = isinstance(last_tool, dict) and last_tool.get("success") is False

        artifacts, _ = harvest_agent_artifacts(
            working_dir, tool_outputs, ignore_preexisting=ignore_preexisting
        )
        if last_failed:
            preview = _oneliner(last_tool.get("error_message", ""), 120) if isinstance(last_tool, dict) else ""
            return (
                "System note: 上一条 shell_exec 执行失败"
                + (f"：{preview}" if preview else "")
                + "。请诊断错误原因，修复驱动脚本后重新运行。"
                "在满足目标的所有条款之前，不要返回 action: \"final\"。"
            )
        if artifacts:
            names = "、".join(a.get("name", "?") for a in artifacts[:8])
            return (
                "System note: 以下输出文件已经生成：" + names + "。"
                "如果目标的所有条款都已满足，请立即用 `action: \"final\"` 返回，"
                "并在 `final_output` 中列出这些相对路径，不要再调用工具。"
            )
        return None

    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        json_mode: bool = True,
    ) -> Tuple[str, Optional[str]]:
        """Call the LLM with a hard per-call timeout.

        Returns ``(text, None)`` on success, or ``("", error)`` when the call
        times out or raises. The per-call cap keeps a hung provider from blocking
        the whole job; the caller decides how many consecutive failures to tolerate.
        """
        timeout = max(1.0, _llm_call_timeout())
        response_format = {"type": "json_object"} if json_mode else None
        heartbeat_task: Optional[asyncio.Task] = None

        async def _llm_heartbeat() -> None:
            """Keep the UI alive while waiting for the provider."""
            while True:
                await asyncio.sleep(5.0)
                self._publish_progress(
                    status="RUNNING",
                    phase="正在等待模型响应...",
                    progress_pct=self._last_progress_pct,
                )

        try:
            if self.progress_callback is not None:
                heartbeat_task = asyncio.create_task(_llm_heartbeat())
            call_kwargs: Dict[str, Any] = {
                "temperature": 0.2,
                "max_tokens": max_tokens,
                "response_format": response_format,
            }
            if self._model_override:
                # A skill-declared model/tier pins the route; skip complexity
                # routing (which would otherwise ignore the explicit model).
                call_kwargs["model"] = self._model_override
            else:
                call_kwargs["intent_type"] = "code_generation"
            coro = self.llm_client.chat_completion(messages, **call_kwargs)
            text = await asyncio.wait_for(coro, timeout=timeout)
            if _cfg("debug", False):
                print(
                    f"[AGENT-LLM] max_tokens={max_tokens} response_len={len(text)} "
                    f"response_head={text[:2000]!r}"
                )
            return text, None
        except asyncio.TimeoutError:
            return "", f"LLM call timed out after {timeout:.0f}s"
        except Exception as exc:  # provider / auth / network errors
            return "", str(exc)
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    def _llm_unavailable_result(
        self,
        skill: SkillDefinition,
        tool_outputs: List[Dict[str, Any]],
        last_error: str,
        working_dir: Optional[Path],
        ignore_preexisting: Optional[set] = None,
    ) -> Dict[str, Any]:
        """Fail fast with a clear message instead of spinning through the budget."""
        artifacts, output_files = harvest_agent_artifacts(
            working_dir, tool_outputs, ignore_preexisting=ignore_preexisting
        )
        note = "已保留执行过程中生成的部分结果。" if artifacts else ""
        return {
            "success": False,
            "partial": bool(artifacts),
            "skill_id": skill.id,
            "error": (
                f"LLM 提供方连续不可用（已重试 {_max_llm_failures()} 次）："
                f"{last_error[:300]}。请检查模型连接或稍后重试。{note}"
            ),
            "artifacts": artifacts,
            "output_files": output_files,
            "tool_outputs": tool_outputs,
        }

    async def _compact_finalize(
        self,
        skill: SkillDefinition,
        objective: str,
        output_files: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Ask the model once to verify generated outputs and return a final action.

        Uses a compact prompt so the long execution context does not cause
        truncation or empty responses. If the model cannot produce a final
        action, the caller returns the outputs anyway.
        """
        if not output_files:
            return None
        prompt = (
            f"You just ran a driver script for skill '{skill.id}'.\n"
            f"Objective: {objective}\n"
            f"Generated output files:\n" +
            "\n".join(f"- {p}" for p in output_files[:20]) +
            "\n\nVerify the outputs exist and return a single JSON action:\n"
            '{"thought": "...", "action": "final", "final_output": {"summary": "...", "output_files": [...], "metrics": {...}}}}\n'
            "No markdown, no extra text."
        )
        response_text, llm_error = await self._call_llm(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Finalize."},
            ],
            max_tokens=2000,
            json_mode=False,
        )
        if llm_error is not None or not response_text:
            return None
        # The model may wrap JSON in markdown; try to extract it.
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = self._extract_script_from_markdown(cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _action_key(action: Dict[str, Any]) -> str:
        """Stable fingerprint for an action, used to detect idle/doom loops."""
        parts = [str(action.get("action", ""))]
        if action.get("tool"):
            parts.append(str(action["tool"]))
        arguments = action.get("arguments", {})
        if isinstance(arguments, dict):
            parts.append(
                json.dumps(arguments, sort_keys=True, ensure_ascii=False)
            )
        return "|".join(parts)

    @staticmethod
    def _arg_summary(tool_name: str, arguments: Any) -> str:
        if not isinstance(arguments, dict):
            return ""
        if tool_name == "shell_exec":
            return _oneliner(arguments.get("command", ""), 80)
        if tool_name in ("file_write", "file_edit", "file_read"):
            return _oneliner(arguments.get("path", ""), 120)
        if tool_name == "file_list":
            return _oneliner(arguments.get("directory", arguments.get("path", "")), 120)
        return ""

    @staticmethod
    def _result_preview(tool_output: Any) -> str:
        if not isinstance(tool_output, dict):
            return ""
        if tool_output.get("success") is False:
            return _oneliner(tool_output.get("error_message", ""), 120)
        out = tool_output.get("output")
        if isinstance(out, dict):
            for key in ("stdout", "output", "text", "message"):
                val = out.get(key)
                if isinstance(val, str) and val.strip():
                    return _oneliner(val, 120)
            return ""
        if isinstance(out, str):
            return _oneliner(out, 120)
        return ""

    @staticmethod
    def _find_unrun_script(tool_outputs: List[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
        """Return ``(path, runner)`` for a script that was written but never run."""
        last_script: Optional[str] = None
        last_write_idx = -1
        for i, entry in enumerate(tool_outputs or []):
            if not isinstance(entry, dict):
                continue
            name = _TOOL_ALIASES.get(
                str(entry.get("tool") or ""), str(entry.get("tool") or "")
            )
            args = entry.get("arguments") or {}
            if name in ("file_write", "file_edit"):
                path = str(args.get("path", ""))
                if Path(path).suffix in _SCRIPT_RUNNERS:
                    last_script = path
                    last_write_idx = i
            elif name == "shell_exec" and last_script and i > last_write_idx:
                cmd = str(args.get("command", ""))
                if Path(last_script).name in cmd:
                    return None  # the script was already executed
        if last_script is None:
            return None
        runner = _SCRIPT_RUNNERS.get(Path(last_script).suffix)
        if not runner:
            return None
        return last_script, runner

    async def _auto_run_unrun_script(
        self, tool_outputs: List[Dict[str, Any]], skill_id: str
    ) -> Optional[Dict[str, Any]]:
        """Execute a written-but-unrun script via ``shell_exec`` as a last resort."""
        found = self._find_unrun_script(tool_outputs)
        if found is None:
            return None
        path, runner = found
        if self.tool_registry is None or self.tool_registry.get("shell_exec") is None:
            return None
        self._publish_progress(
            status="RUNNING",
            phase=f"自动执行已生成的脚本：{Path(path).name}",
            progress_pct=95.0,
            active_task_id=skill_id,
        )
        output = await self._invoke_tool_with_logging(
            "shell_exec", "shell_exec", {"command": f"{runner} {path}"}
        )
        # Compact before the record joins tool_outputs (persisted + replayed
        # into prompts); see the main loop for the rationale.
        output = _compact_tool_output(output)
        tool_outputs.append(output)
        return output

    async def _script_first_execute(
        self,
        skill: SkillDefinition,
        inputs: Dict[str, Any],
        working_dir: Optional[Path],
        tools: Dict[str, Any],
        preexisting_files: Optional[set] = None,
    ) -> Optional[Dict[str, Any]]:
        """Try to complete the skill in one shot: ask LLM for a driver script and run it.

        This is the fast path for skills that ship helper scripts. It avoids the
        slow multi-turn exploration loop that often times out on slow providers.
        If the generated script fails, the caller falls back to the normal agent
        loop with the error context.
        """
        source_dir = skill.source_dir
        scripts_python = Path(source_dir) / "scripts" / "python" if source_dir else None
        if scripts_python is None or not scripts_python.is_dir():
            return None

        runner = "python"
        import_path = str(scripts_python)
        script_reference = _extract_script_reference(source_dir, max_chars=800)

        objective = str(inputs.get("user_request", "")) if isinstance(inputs, dict) else ""
        input_file = ""
        if isinstance(inputs, dict):
            input_file = str(inputs.get("input_file", ""))
            if not input_file and isinstance(inputs.get("uploaded_files"), list) and inputs["uploaded_files"]:
                input_file = str(inputs["uploaded_files"][0].get("path", ""))

        prompt = (
            f"Write a compact, complete Python driver script for skill '{skill.id}'.\n\n"
            f"## Helpers\n"
            f"```python\nimport sys, os\nsys.path.insert(0, '{import_path}')\n"
            f"from core_analysis import *\nfrom utils import *\n```\n\n"
            f"{script_reference}\n\n"
            f"## Objective\n"
            f"{objective}\n\n"
            f"## Input file\n"
            f"{input_file}\n\n"
            f"## Requirements\n"
            f"- For immune cell annotation with CellTypist, default to model='Immune_All_Low.pkl', "
            f"mode='best match', majority_voting=True, p_thres=0.5. "
            f"Only deviate if the user explicitly names another model/mode.\n"
            f"- Normalize from raw counts (layer='counts') with target_sum=1e4 and log1p if needed.\n"
            f"- Save outputs under {working_dir}/outputs/ with clear filenames.\n"
            f"- Before writing .h5ad, set anndata.settings.allow_write_nullable_strings = True and convert any nullable string index/columns to plain str.\n"
            f"- Required outputs: annotated.h5ad, annotations.csv, celltypist_comparison.csv "
            f"(columns: all_celltype, celltypist_predicted, celltypist_conf_score), "
            f"comparison_report.txt, report.txt.\n"
            f"- CellTypist result objects may expose predicted_labels and a separate probability_matrix. "
            f"If predicted_labels does not contain a 'conf_score' column, derive confidence scores as "
            f"the maximum probability per cell from the probability_matrix. Do not assume 'conf_score' exists.\n"
            f"- report.txt must include: cells x genes, model, gene overlap, mode, threshold, "
            f"Unassigned rate, preprocessing note, ARI/NMI vs all_celltype, per-label agreement.\n"
            f"- Keep under 70 lines, no plots.\n"
            f"- After writing all outputs, also write a JSON manifest at {working_dir}/__skill_outputs__.json "
            f"listing every output file path relative to {working_dir}.\n"
            f"Return only a ```python code block."
        )

        self._publish_progress(
            status="RUNNING",
            phase="正在生成一次性驱动脚本",
            progress_pct=10.0,
            active_task_id=skill.id,
        )
        response_text, llm_error = await self._call_llm(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Generate the driver script."},
            ],
            max_tokens=8000,
            json_mode=False,
        )
        if llm_error is not None:
            return None

        script_code = self._extract_script_from_markdown(response_text)
        expected_outputs: List[str] = []
        if not script_code:
            return None

        # If the extracted script is not valid Python (e.g. truncated), ask the
        # LLM once more to complete/fix it before falling back to the slow loop.
        if not self._is_valid_python(script_code):
            fix_prompt = (
                "The previous driver script was cut off or has a syntax error. "
                "Return the COMPLETE, fixed Python script in a single markdown code block.\n\n"
                "Continue/fix from here:\n"
                f"```python\n{script_code}\n```"
            )
            response_text, llm_error = await self._call_llm(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": fix_prompt},
                ],
                max_tokens=3000,
                json_mode=False,
            )
            if llm_error is None:
                script_code = self._extract_script_from_markdown(response_text)
            if not script_code or not self._is_valid_python(script_code):
                return None

        if not working_dir:
            working_dir = Path.cwd()
        else:
            working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)
        script_path = working_dir / f"__skill_driver_{skill.id}.py"
        script_path.write_text(script_code, encoding="utf-8")

        self._publish_progress(
            status="RUNNING",
            phase=f"正在运行驱动脚本：{script_path.name}",
            progress_pct=50.0,
            active_task_id=skill.id,
        )
        output = await self._invoke_tool_with_logging(
            "shell_exec",
            "shell_exec",
            {"command": f"{runner} {script_path}", "timeout": 600},
        )
        # Compact before the record is persisted in the result or handed to the
        # fallback loop (which extends its tool_outputs from this result).
        # Structured fields (returncode, paths) survive truncation.
        output = _compact_tool_output(output)

        # shell_exec reports tool-level success even when the inner command exits
        # non-zero. Treat a non-zero returncode as a script failure so we fall
        # back or retry instead of claiming success.
        tool_output = output.get("output", {}) if isinstance(output.get("output"), dict) else {}
        command_returncode = tool_output.get("returncode", 0)
        if output.get("success") and command_returncode == 0:
            # Verify expected outputs exist; harvest artifacts.
            artifacts, output_files = harvest_agent_artifacts(
                working_dir, [output], ignore_preexisting=preexisting_files
            )

            # If the driver script wrote a manifest of its outputs, honor it.
            # This avoids losing files when the workspace scan hits its limit or
            # when outputs were overwritten and look stale against preexisting files.
            manifest_path = working_dir / "__skill_outputs__.json"
            if manifest_path.is_file():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest_paths = manifest.get("output_files", []) if isinstance(manifest, dict) else manifest
                    for rel in manifest_paths:
                        if not isinstance(rel, str):
                            continue
                        p = working_dir / rel
                        # The manifest itself is an internal bookkeeping file, not a user-facing output.
                        if p == manifest_path:
                            continue
                        if p.is_file() and str(p) not in output_files:
                            output_files.append(str(p))
                            env = build_artifact(p)
                            if env is not None:
                                artifacts.append(env)
                except Exception:
                    pass

            # Also check expected_outputs explicitly.
            for rel in expected_outputs:
                p = working_dir / rel
                if p.is_file() and str(p) not in output_files:
                    output_files.append(str(p))
                    env = build_artifact(p)
                    if env is not None:
                        artifacts.append(env)
            return {
                "success": True,
                "mode": "agent",
                "skill_id": skill.id,
                "final_output": {
                    "note": "Driver script executed successfully.",
                    "expected_outputs": expected_outputs,
                    "output_files": output_files,
                },
                "artifacts": artifacts,
                "output_files": output_files,
                "tool_outputs": [output],
            }

        # Script failed: return a partial result so the caller can fall back.
        # ``output`` was already compacted above; bound the error string itself
        # too, since it propagates into the job result and the parent agent's
        # context — a raw multi-KB log must not leak through it (tail-priority:
        # the actionable traceback lines sit at the end).
        raw_error = output.get("error_message") or "unknown error"
        if not isinstance(raw_error, str):
            raw_error = str(raw_error)
        return {
            "success": False,
            "partial": False,
            "skill_id": skill.id,
            "error": f"Generated driver script failed: {_truncate_text(raw_error, 2000, is_error=True)}",
            "tool_outputs": [output],
        }

    def _available_tools(self, skill: SkillDefinition) -> Dict[str, Any]:
        """Return the tool schemas available to this skill.

        Honors ``allowed-tools`` and ``disallowed-tools`` from the skill
        frontmatter. Tool specs may be space/comma-separated strings or YAML
        lists, and may include permission globs like ``Bash(git *)``.

        Agentic skills that ship a ``scripts/`` directory automatically get
        ``file_read`` so they can use those scripts as Level 3 reference
        material, unless ``file_read`` is explicitly disallowed.
        """
        if not self.tool_registry:
            return {}

        all_tools = {
            tool.name: tool
            for tool in self.tool_registry.list_all()
        }

        allowed = self._parse_tool_specs(skill.metadata.get("allowed_tools", []))
        disallowed = self._parse_tool_specs(skill.metadata.get("disallowed_tools", []))

        # Remove explicitly disallowed tools.
        canonical_disallowed = {_TOOL_ALIASES.get(name, name) for name in disallowed}
        for name in canonical_disallowed:
            all_tools.pop(name, None)

        if not allowed:
            resolved = dict(all_tools)
        else:
            resolved = {}
            for name in allowed:
                canonical = _TOOL_ALIASES.get(name, name)
                if canonical in all_tools:
                    resolved[name] = all_tools[canonical]

        # Auto-grant file_read to skills with reference scripts (Level 3).
        if (
            skill.has_scripts
            and "file_read" not in canonical_disallowed
            and "file_read" not in resolved
        ):
            file_read_tool = self.tool_registry.get("file_read")
            if file_read_tool is not None:
                resolved["file_read"] = file_read_tool

        return resolved

    @staticmethod
    def _parse_tool_specs(specs: Any) -> List[str]:
        """Normalize a tool-spec list into canonical tool names."""
        if not specs:
            return []
        if isinstance(specs, str):
            return [s.strip() for s in re.split(r"[,\s]+", specs) if s.strip()]
        if isinstance(specs, list):
            return [
                str(item).strip().split("(")[0].split()[0]
                for item in specs
                if str(item).strip()
            ]
        return []

    @staticmethod
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

    @staticmethod
    def _build_system_prompt(
        skill: SkillDefinition,
        inputs: Dict[str, Any],
        tools: Dict[str, Any],
    ) -> str:
        """Build a concise, action-oriented system prompt for the LLM agent."""
        # Use the short description as the objective instead of dumping the entire
        # SKILL.md body. Long SKILL.md files bloat the prompt and slow the provider.
        instructions = skill.description or skill.metadata.get("instructions", "")

        tool_descriptions = [AgentSkillExecutor._tool_summary(tool) for tool in tools.values()]

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

    @staticmethod
    def _is_valid_python(code: str) -> bool:
        """Return True if ``code`` parses as Python without syntax errors."""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    @staticmethod
    def _extract_script_from_markdown(response_text: str) -> str:
        """Extract the first Python code block from an LLM response.

        Handles truncated responses where the closing fence is missing.
        """
        text = response_text.strip()
        # Match ```python ... ``` (closing fence required).
        match = re.search(r"```(?:python)\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Truncated responses may start with ```python but never close.
        if text.startswith("```python"):
            return text[len("```python"):].strip()
        if text.startswith("```"):
            return text[len("```"):].strip()
        # Fallback: return the whole text if it looks like Python.
        if "import " in text or "def " in text or "print(" in text:
            return text
        return ""

    @staticmethod
    def _parse_action(response_text: str) -> Optional[Dict[str, Any]]:
        """Parse an agent action from LLM output, tolerating markdown fences.

        Tries a direct JSON parse first, then strips markdown fences, then
        extracts the first JSON object.
        """
        text = response_text.strip()
        # Strip markdown code fences if present.
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            parsed = json.loads(text, strict=False)
        except json.JSONDecodeError:
            parsed = AgentSkillExecutor._extract_json(text)
        return AgentSkillExecutor._normalize_action(parsed)

    @staticmethod
    def _normalize_action(parsed: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Accept common LLM shorthand shapes and coerce them to actions."""
        if not isinstance(parsed, dict):
            return None

        def inferred_tool(arguments: Dict[str, Any]) -> Optional[str]:
            if "command" in parsed or (
                isinstance(arguments, dict) and "command" in arguments
            ):
                return "shell_exec"
            if isinstance(arguments, dict):
                if "content" in arguments and "path" in arguments:
                    return "file_write"
                if "old_string" in arguments and "new_string" in arguments:
                    return "file_edit"
                if "directory" in arguments:
                    return "file_list"
                if "path" in arguments:
                    return "file_read"
            return None

        if parsed.get("action") == "final":
            return parsed
        if parsed.get("action") == "tool":
            normalized = dict(parsed)
            normalized.setdefault("arguments", {})
            if not normalized.get("tool"):
                tool = inferred_tool(normalized.get("arguments") or {})
                if tool is None:
                    return normalized
                normalized["tool"] = tool
                if tool == "shell_exec" and "command" in normalized:
                    normalized["arguments"] = {
                        "command": normalized["command"],
                        **({"timeout": normalized["timeout"]} if "timeout" in normalized else {}),
                    }
            return normalized
        if "command" in parsed and "tool" not in parsed:
            normalized = dict(parsed)
            normalized["action"] = "tool"
            normalized["tool"] = "shell_exec"
            normalized.setdefault(
                "arguments",
                {
                    "command": parsed["command"],
                    **({"timeout": parsed["timeout"]} if "timeout" in parsed else {}),
                },
            )
            return normalized
        if "tool" in parsed:
            normalized = dict(parsed)
            normalized["action"] = "tool"
            normalized.setdefault("arguments", {})
            return normalized
        if "final_output" in parsed:
            normalized = dict(parsed)
            normalized["action"] = "final"
            return normalized
        # Accept bare file-write/file-edit shapes that some models emit.
        if "path" in parsed and "content" in parsed and "tool" not in parsed:
            return {
                "action": "tool",
                "tool": "file_write",
                "arguments": {
                    "path": parsed["path"],
                    "content": parsed["content"],
                },
            }
        if "path" in parsed and "old_string" in parsed and "new_string" in parsed and "tool" not in parsed:
            return {
                "action": "tool",
                "tool": "file_edit",
                "arguments": {
                    "path": parsed["path"],
                    "old_string": parsed["old_string"],
                    "new_string": parsed["new_string"],
                },
            }
        return None

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Try to extract the first decodable JSON object from a string."""
        decoder = json.JSONDecoder(strict=False)
        start = text.find("{")
        while start != -1:
            try:
                obj, _ = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                start = text.find("{", start + 1)
                continue
            if isinstance(obj, dict):
                return obj
            start = text.find("{", start + 1)
        return None

    async def _invoke_tool_with_logging(
        self,
        canonical_name: str,
        display_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Invoke a tool and return a structured output record."""
        import time

        if self.tool_registry is None:
            raise RuntimeError("ToolRegistry is not available")

        start = time.time()
        heartbeat_task = None
        if self.progress_callback is not None:
            heartbeat_task = asyncio.create_task(
                self._tool_heartbeat(display_name, arguments, start)
            )

        try:
            result = await self.tool_registry.invoke_async(canonical_name, arguments)
            # If the tool itself returns a ToolResult (e.g. a nested handler), use it directly.
            if isinstance(result.output, ToolResult):
                inner = result.output
                output = {
                    "tool": display_name,
                    "arguments": arguments,
                    "success": inner.success,
                    "output": inner.output,
                    "error_message": inner.error_message,
                    "latency_ms": (time.time() - start) * 1000,
                }
            else:
                output = {
                    "tool": display_name,
                    "arguments": arguments,
                    "success": result.success,
                    "output": result.output,
                    "error_message": result.error_message,
                    "latency_ms": (time.time() - start) * 1000,
                }
        except Exception as exc:
            output = {
                "tool": display_name,
                "arguments": arguments,
                "success": False,
                "error_message": str(exc),
                "latency_ms": (time.time() - start) * 1000,
            }
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

        # Best-effort audit log
        try:
            from homomics_lab.tools.audit import log_tool_call

            log_tool_call(
                tool_name=display_name,
                arguments=arguments,
                success=output["success"],
                error_message=output.get("error_message"),
                latency_ms=output.get("latency_ms", 0.0),
            )
        except Exception:
            pass
        return output

    async def _tool_heartbeat(
        self,
        display_name: str,
        arguments: Dict[str, Any],
        start_time: float,
        interval: float = 3.0,
    ) -> None:
        """Emit periodic progress updates while a tool is still running."""
        import time

        if self.progress_callback is None:
            return
        cmd_preview = ""
        if display_name == "shell_exec" and isinstance(arguments, dict):
            cmd = str(arguments.get("command", ""))
            if cmd:
                cmd_preview = _oneliner(cmd, 60)
        count = 0
        while True:
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                return
            count += 1
            elapsed = time.time() - start_time
            phase = f"工具 {display_name} 正在执行"
            if cmd_preview:
                phase += f"：{cmd_preview}"
            phase += f"（已运行 {elapsed:.0f}s）"
            self._publish_progress(
                status="RUNNING",
                phase=phase,
                progress_pct=self._last_progress_pct,
                active_task_id=None,
            )

    @staticmethod
    def _validate_output(skill: SkillDefinition, output: Dict[str, Any]) -> List[str]:
        """Validate agent final output against skill output_schema.

        Skills without an output schema (the common case for agentic skills)
        skip validation entirely rather than crashing.
        """
        schema = getattr(skill, "output_schema", None)
        if schema is None or (not schema.properties and not schema.required):
            return []

        errors = []
        for field_name in schema.required:
            if field_name not in output:
                errors.append(f"Missing required output field: '{field_name}'")

        type_checks = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
        }

        for field_name, value in output.items():
            if field_name in schema.properties:
                prop = schema.properties[field_name]
                expected = prop.get("type")
                if expected and not type_checks.get(expected, lambda _: True)(value):
                    errors.append(
                        f"Type mismatch for field '{field_name}': expected {expected}, got {type(value).__name__}"
                    )
        return errors
