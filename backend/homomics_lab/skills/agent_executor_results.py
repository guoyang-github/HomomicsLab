"""Result post-processing for :class:`AgentSkillExecutor`.

Extracted from ``skills/agent_executor.py`` as a pure code move (no logic
changes): artifact harvesting (tool-call path extraction + bounded directory
scan) and final-output enrichment from generated summary/metrics files.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from homomics_lab.artifacts import build_artifact

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
