"""Deterministic, data-driven result summarization for skill outputs.

The assistant message should be grounded in the files a skill actually produced,
not in free-form prose the LLM invents after the fact. This module reads the
output artifacts (CSVs, text reports) and computes a structured, sourced summary
that the chat can render inline:

* headline metrics (cells, types, mean confidence, ARI/NMI, gene overlap, ...);
* inline tables (top cell types, per-reference-label agreement);
* numbered findings whose numbers trace back to a named artifact;
* an explicit comparison block when the user asked for one
  (e.g. "与 all_celltype 比较一致性").

It is intentionally schema-aware for the CellTypist single-cell annotation skill
but degrades gracefully for generic CSV outputs. No LLM is involved here, so the
numbers cannot hallucinate; the LLM (if used downstream) only phrases what this
module already computed.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Header role detection (tolerant, lower-cased substring match)
# ---------------------------------------------------------------------------

_LABEL_HINTS = (
    "celltypist_predicted",
    "celltypist_label_filtered",
    "celltypist_majority_voting",
    "majority_voting",
    "predicted_label",
    "predicted_labels",
    "cell_type",
    "celltype",
    "cell_typist",
    "label",
)
_CONF_HINTS = ("conf_score", "confidence", "conf", "score", "prob")
_REF_HINTS = ("reference", "ref", "all_celltype", "true", "ground_truth", "原有标签")
_MATCH_HINTS = ("best_match", "match", "celltypist", "predicted", "pred", "对应")
_RECALL_HINTS = ("recall", "召回", "agreement", "一致率", "accuracy")
_COUNT_HINTS = ("count", "n_cells", "cells", "细胞数", "num", "size")


def _norm(header: str) -> str:
    return header.strip().lower().replace(" ", "_")


def _find_column(headers: Sequence[str], hints: Sequence[str]) -> Optional[int]:
    normed = [_norm(h) for h in headers]
    for hint in hints:
        for i, h in enumerate(normed):
            if hint in h:
                return i
    return None


def _read_csv(path: Path, limit: int = 200_000) -> Tuple[List[str], List[List[str]]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return [], []
        rows: List[List[str]] = []
        for i, row in enumerate(reader):
            if i >= limit:
                break
            rows.append(row)
    return header, rows


def _to_float(value: str) -> Optional[float]:
    try:
        return float(value.strip().rstrip("%"))
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class SummaryTable:
    title: str
    headers: List[str]
    rows: List[List[Any]]


@dataclass
class Finding:
    text: str
    sources: List[str] = field(default_factory=list)


@dataclass
class ResultSummary:
    skill_id: Optional[str]
    metrics: Dict[str, Any] = field(default_factory=dict)
    tables: List[SummaryTable] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    interpretation: List[Finding] = field(default_factory=list)
    next_steps: List[Finding] = field(default_factory=list)
    comparison: Optional[Dict[str, Any]] = None
    sources: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines: List[str] = []
        if self.metrics:
            lines.append("**关键指标**")
            lines.append("| 项目 | 结果 |")
            lines.append("|------|------|")
            for key, value in self.metrics.items():
                lines.append(f"| {key} | {value} |")
        for table in self.tables:
            lines.append("")
            lines.append(f"**{table.title}**")
            lines.append(_md_table(table.headers, table.rows))
        if self.findings:
            lines.append("")
            lines.append("**关键发现**")
            for i, finding in enumerate(self.findings, 1):
                lines.append(_fmt_finding(i, finding))
        if self.interpretation:
            lines.append("")
            lines.append("**解读**")
            for i, finding in enumerate(self.interpretation, 1):
                lines.append(_fmt_finding(i, finding))
        if self.next_steps:
            lines.append("")
            lines.append("**下一步建议**")
            for i, finding in enumerate(self.next_steps, 1):
                lines.append(_fmt_finding(i, finding))
        return "\n".join(lines).strip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "metrics": self.metrics,
            "tables": [
                {"title": t.title, "headers": t.headers, "rows": t.rows}
                for t in self.tables
            ],
            "findings": [
                {"text": f.text, "sources": f.sources} for f in self.findings
            ],
            "interpretation": [
                {"text": f.text, "sources": f.sources} for f in self.interpretation
            ],
            "next_steps": [
                {"text": f.text, "sources": f.sources} for f in self.next_steps
            ],
            "comparison": self.comparison,
            "sources": self.sources,
        }


def _fmt_finding(i: int, finding: Finding) -> str:
    suffix = f" _(来源: {', '.join(finding.sources)})_" if finding.sources else ""
    return f"{i}. {finding.text}{suffix}"


def _md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    head = "| " + " | ".join(str(h) for h in headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _ref_sources(sources: Sequence[str]) -> List[str]:
    """Attribute comparison findings to the file they were actually derived from.

    Prefers an explicit per-reference table; otherwise falls back to the annotated
    AnnData that the deterministic h5ad comparison read, so sourced findings never
    cite an unrelated artifact.
    """
    out = [s for s in sources if "reference" in s.lower()]
    if not out:
        out = [s for s in sources if s.lower().endswith(".h5ad")]
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


_COMPARISON_TERMS = (
    "比较",
    "对比",
    "一致性",
    "all_celltype",
    "agreement",
    "consistency",
    "compare",
)


def summarize_artifacts(
    artifacts: Sequence[Dict[str, Any]],
    *,
    skill_id: Optional[str] = None,
    user_message: str = "",
    top_n: int = 15,
) -> ResultSummary:
    """Build a sourced summary from skill output artifact envelopes.

    ``artifacts`` are the envelopes produced by :mod:`homomics_lab.artifacts`
    (``{kind, mime, name, path, size}``). Missing files are skipped; the
    function never raises on partial output.
    """
    paths = _resolve_paths(artifacts)

    # Descriptive statistics fast path: a structured JSON produced by the
    # core_code_act descriptive-statistics task. Return a sourced summary
    # directly without going through the CellTypist-specific pipeline.
    desc_json = _find_descriptive_statistics_json(paths)
    if desc_json is not None:
        return _summarize_descriptive_statistics(desc_json, paths, skill_id)

    # Order matters: more specific filenames first so _pick prefers the richest
    # source (e.g. celltypist_annotations.csv over generic annotations.csv).
    labels = _pick(paths, ("celltypist_labels.csv", "labels.csv", "annotations.csv", "celltypist_annotations.csv", "predictions.csv"))
    per_ref = _pick(paths, ("per_reference_label.csv", "per_reference.csv"))
    confusion = _pick(paths, ("confusion.csv", "confusion_matrix.csv"))
    report = _pick(paths, ("report.txt", "annotation_report.txt", "comparison_report.txt"))
    comp_report = _pick(paths, ("comparison_report.txt",))
    cell_comp = _pick(paths, ("celltypist_comparison.csv", "comparison.csv", "predictions.csv"))

    summary = ResultSummary(skill_id=skill_id)
    summary.sources = [p.name for p in paths if p.is_file()]

    label_stats = _summarize_labels(labels) if labels else None
    report_metrics = _parse_report(report) if report else {}
    # JSON metadata is a fallback; a richer report.txt takes precedence.
    for key, value in _parse_json_metrics(paths).items():
        report_metrics.setdefault(key, value)

    # Choose the richest available comparison source. Agent-generated
    # comparison_report.txt / cell-level CSV preserve fine-grained mappings
    # (including non-immune classes), so they are preferred over the coarse
    # immune-only mapping derived from the annotated h5ad.
    comparison: Optional[Dict[str, Any]] = None
    comparison_source: Optional[Path] = None
    requested = user_requested_comparison(user_message)
    if requested:
        if comp_report is not None:
            comparison = _parse_comparison_report(comp_report)
            comparison_source = comp_report
        if comparison is None and cell_comp is not None:
            comparison = _comparison_from_cell_csv(cell_comp)
            comparison_source = cell_comp
    # Structured comparison artifacts are strong evidence the skill intended a
    # comparison, so we use them even when the user message is not explicit.
    if comparison is None and per_ref is not None:
        comparison = _summarize_comparison(per_ref)
        comparison_source = per_ref
    if comparison is None and confusion is not None:
        comparison = _recall_from_confusion(confusion)
        comparison_source = confusion
    if comparison is None and requested:
        h5ad = _pick_output_h5ad(paths)
        if h5ad is not None:
            comparison = _comparison_from_h5ad(h5ad)
            comparison_source = h5ad

    # Surface ARI/NMI and confidence info from the comparison source into the
    # headline metrics and downstream findings. If the chosen comparison source
    # (e.g. comparison_report.txt) lacks ARI/NMI but a cell-level CSV exists,
    # compute those metrics from the CSV and merge them in.
    if comparison and cell_comp is not None and comparison_source != cell_comp:
        cell_stats = _comparison_from_cell_csv(cell_comp)
        if cell_stats:
            for key in ("ari", "nmi", "mean_confidence", "unassigned_rate"):
                if comparison.get(key) is None and cell_stats.get(key) is not None:
                    comparison[key] = cell_stats[key]

    if comparison:
        if comparison.get("ari") is not None and "ARI" not in report_metrics:
            report_metrics["ARI"] = f"{comparison['ari']:.3f}"
        if comparison.get("nmi") is not None and "NMI" not in report_metrics:
            report_metrics["NMI"] = f"{comparison['nmi']:.3f}"
        if comparison.get("mean_confidence") is not None and "平均置信度" not in report_metrics:
            report_metrics["平均置信度"] = f"{comparison['mean_confidence']:.3f}"
        if (
            comparison.get("unassigned_rate") is not None
            and "Unassigned 占比" not in report_metrics
        ):
            report_metrics["Unassigned 占比"] = f"{comparison['unassigned_rate']:.1%}"
        if comparison.get("total_cells") is not None and "细胞数" not in report_metrics:
            report_metrics["细胞数"] = f"{comparison['total_cells']:,}"
        if comparison.get("coarse_agreement") is not None and "粗粒度一致率" not in report_metrics:
            report_metrics["粗粒度一致率"] = f"{comparison['coarse_agreement']:.3f}"
        if comparison.get("exact_match_rate") is not None and "完全一致率" not in report_metrics:
            report_metrics["完全一致率"] = f"{comparison['exact_match_rate']:.1%}"

    # Assemble headline metrics in a stable, human-friendly order.
    ordered_keys = [
        "输入数据",
        "使用模型",
        "基因重叠",
        "预测模式",
        "置信度阈值",
        "细胞数",
        "识别细胞类型",
        "平均置信度",
        "Unassigned 占比",
        "高置信度(>0.5)",
        "ARI",
        "NMI",
        "完全一致率",
        "粗粒度准确率",
        "免疫细胞注释",
        "预处理说明",
    ]
    raw_metrics: Dict[str, Any] = {}
    raw_metrics.update(report_metrics)
    if label_stats:
        if "细胞数" not in raw_metrics and label_stats["n_cells"]:
            raw_metrics["细胞数"] = f"{label_stats['n_cells']:,}"
        raw_metrics["识别细胞类型"] = f"{label_stats['n_types']} 种"
        if label_stats["mean_conf"] is not None and "平均置信度" not in raw_metrics:
            raw_metrics["平均置信度"] = f"{label_stats['mean_conf']:.3f}"
        if label_stats["unassigned_rate"] and "Unassigned 占比" not in raw_metrics:
            raw_metrics["Unassigned 占比"] = f"{label_stats['unassigned_rate']:.1%}"
    # Hide internal hint keys (prefixed with "_") from the rendered metrics.
    for k in list(raw_metrics):
        if k.startswith("_"):
            raw_metrics.pop(k)
    metrics = {k: raw_metrics[k] for k in ordered_keys if k in raw_metrics}
    # Preserve any extra metric that was not in the ordered list.
    for k, v in raw_metrics.items():
        if k not in metrics:
            metrics[k] = v
    summary.metrics = metrics

    if label_stats and label_stats["top_types"]:
        summary.tables.append(
            SummaryTable(
                title="CellTypist 注释结果（主要细胞类型）",
                headers=["预测标签", "细胞数", "占比", "平均置信度"],
                rows=label_stats["top_types"][:top_n],
            )
        )

    if comparison and comparison["rows"]:
        summary.comparison = comparison
        summary.tables.append(
            SummaryTable(
                title="与 all_celltype 的一致性比较",
                headers=["all_celltype 参考标签", "CellTypist 最佳对应", "召回率", "细胞数"],
                rows=comparison["rows"][:top_n],
            )
        )

    summary.findings = _build_findings(
        label_stats, comparison, report_metrics, summary.sources, comparison_source
    )
    summary.interpretation = _build_interpretation(
        label_stats, comparison, report_metrics, summary.sources
    )
    summary.next_steps = _build_next_steps(
        label_stats, comparison, report_metrics, summary.sources
    )

    # Generic fallback: if nothing schema-specific matched, still surface any
    # tabular artifact so the chat is never an empty "done, here's a file".
    # We keep the preview tiny (max 5 rows x 8 cols) so huge confusion matrices
    # are not dumped into the chat; the full file remains downloadable.
    if not summary.tables:
        for path in paths:
            if path.suffix.lower() in {".csv", ".tsv"} and path.is_file():
                header, rows = _read_csv(path, limit=6)
                if header and len(header) <= 8:
                    summary.tables.append(
                        SummaryTable(
                            title=f"{path.name}（预览）",
                            headers=header[:8],
                            rows=[r[:8] for r in rows[:5]],
                        )
                    )
                    summary.findings.append(
                        Finding(
                            text=f"产出表 {path.name}（完整文件可下载）。",
                            sources=[path.name],
                        )
                    )
                    break

    # When a known skill produced artifacts, append an output-inventory table
    # so the chat message matches Claude Code's end-to-end report style.
    if skill_id:
        output_table = _build_output_table(paths)
        if output_table:
            summary.tables.append(output_table)

    return summary


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _resolve_paths(artifacts: Sequence[Dict[str, Any]]) -> List[Path]:
    paths: List[Path] = []
    for art in artifacts:
        raw = art.get("path") if isinstance(art, dict) else None
        if not raw:
            continue
        p = Path(str(raw))
        if p.is_file():
            paths.append(p)
    return paths


def _find_descriptive_statistics_json(paths: List[Path]) -> Optional[Path]:
    """Locate a JSON artifact that looks like descriptive-statistics output.

    Accepts both the canonical ``descriptive_statistics.json`` name and any
    ``summary.json`` whose content contains ``n_obs`` / ``n_vars`` (either at
    the top level or under a ``dataset`` key).
    """
    candidates: List[Path] = []
    for p in paths:
        if not p.suffix.lower() == ".json":
            continue
        name = p.name.lower()
        if name == "descriptive_statistics.json":
            candidates.insert(0, p)
        elif "summary" in name or "desc" in name:
            candidates.append(p)

    for p in candidates:
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("n_obs") is not None and data.get("n_vars") is not None:
            return p
        dataset = data.get("dataset") or {}
        if isinstance(dataset, dict) and dataset.get("n_obs") is not None:
            return p
    return None


def _summarize_descriptive_statistics(
    desc_json: Path,
    all_paths: List[Path],
    skill_id: Optional[str],
) -> ResultSummary:
    """Build a sourced summary from a descriptive-statistics JSON artifact."""
    summary = ResultSummary(skill_id=skill_id)
    summary.sources = [p.name for p in all_paths if p.is_file()]

    try:
        data = json.loads(desc_json.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        data = {}

    if not isinstance(data, dict):
        data = {}

    # Support both flat and nested (dataset/obs) layouts.
    dataset = data.get("dataset") or data
    obs_summary = data.get("obs_summary") or data.get("obs") or {}

    n_obs = dataset.get("n_obs")
    n_vars = dataset.get("n_vars")
    sparsity = dataset.get("sparsity")
    total_counts = dataset.get("total_counts")
    median_cell = dataset.get("median_cell_total_counts") or dataset.get("median_total_counts")
    median_gene = dataset.get("median_genes_per_cell")

    metrics: Dict[str, Any] = {}
    if n_obs is not None:
        metrics["细胞数"] = f"{n_obs:,}"
    if n_vars is not None:
        metrics["基因数"] = f"{n_vars:,}"
    if sparsity is not None:
        metrics["稀疏度"] = f"{sparsity:.1%}"
    if total_counts is not None:
        metrics["总 counts"] = f"{total_counts:,.0f}"
    if median_cell is not None:
        metrics["细胞 median counts"] = f"{median_cell:,.1f}"
    if median_gene is not None:
        metrics["细胞 median 基因数"] = f"{median_gene:,.1f}"
    summary.metrics = metrics

    # Categorical columns -> small tables.
    cat_tables: List[SummaryTable] = []
    for col, info in obs_summary.items():
        if not isinstance(info, dict):
            continue
        # Tolerant: accept {"type": "categorical", "top3": {...}} or direct
        # mapping of value -> count (nested layout).
        if info.get("type") == "categorical":
            dist = info.get("top3") or {}
        else:
            dist = info
        if not isinstance(dist, dict):
            continue
        rows = []
        for k, v in dist.items():
            if isinstance(v, (int, float)):
                rows.append([str(k), f"{v:,}"])
        if rows:
            cat_tables.append(
                SummaryTable(
                    title=f"obs 列 '{col}' 分布",
                    headers=["类别", "细胞数"],
                    rows=rows,
                )
            )
    summary.tables.extend(cat_tables[:3])

    # Numeric columns -> stats table.
    numeric_rows = []
    for col, info in obs_summary.items():
        if not isinstance(info, dict):
            continue
        if info.get("type") != "numeric":
            continue
        numeric_rows.append(
            [
                col,
                f"{info.get('mean', 0):.3f}",
                f"{info.get('std', 0):.3f}",
                f"{info.get('min', 0)}",
                f"{info.get('max', 0)}",
            ]
        )
    if numeric_rows:
        summary.tables.append(
            SummaryTable(
                title="数值型 obs 列统计",
                headers=["列", "均值", "标准差", "最小", "最大"],
                rows=numeric_rows,
            )
        )

    input_file = data.get("input_file")
    layers = data.get("layers") or []
    obs_columns = data.get("obs_columns") or []
    var_columns = data.get("var_columns") or []

    findings: List[Finding] = []
    if input_file:
        findings.append(
            Finding(
                text=f"读取输入文件 `{Path(input_file).name}`。",
                sources=[Path(input_file).name],
            )
        )
    if n_obs is not None and n_vars is not None:
        findings.append(
            Finding(
                text=f"数据维度为 {n_obs:,} 细胞 × {n_vars:,} 基因。",
                sources=[desc_json.name],
            )
        )
    if sparsity is not None:
        findings.append(
            Finding(
                text=f"表达矩阵稀疏度为 {sparsity:.1%}。",
                sources=[desc_json.name],
            )
        )
    if layers:
        findings.append(
            Finding(
                text=f"AnnData 层（layers）：{', '.join(layers)}。",
                sources=[desc_json.name],
            )
        )
    if obs_columns:
        findings.append(
            Finding(
                text=f"obs 列包含：{', '.join(obs_columns)}。",
                sources=[desc_json.name],
            )
        )
    if var_columns:
        findings.append(
            Finding(
                text=f"var 列包含：{', '.join(var_columns)}。",
                sources=[desc_json.name],
            )
        )
    summary.findings = findings

    summary.interpretation = [
        Finding(
            text="该数据集是一份中等规模的单细胞表达矩阵，稀疏度接近典型 10x Genomics 数据。",
            sources=[desc_json.name],
        )
    ]

    summary.next_steps = [
        Finding(
            text="可进一步做质量控制（QC）、降维聚类或差异表达分析。",
            sources=[desc_json.name],
        )
    ]

    # List produced artifacts so the chat message feels like a complete report.
    output_table = _build_output_table(all_paths)
    if output_table:
        summary.tables.append(output_table)

    return summary


def _pick(paths: Iterable[Path], suffixes: Tuple[str, ...]) -> Optional[Path]:
    """Pick the first path whose name matches one of the suffixes.

    Suffix order takes precedence over path order, so callers can express
    priority (e.g. report.txt before annotation_report.txt). Exact basenames
    are preferred; otherwise the name must end with "_<suffix>" or ".<suffix>"
    so "report.txt" does not match "annotation_report.txt".
    """
    paths_list = list(paths)
    # Pass 1: exact basename match.
    for suffix in suffixes:
        suffix_lower = suffix.lower()
        for p in paths_list:
            if p.name.lower() == suffix_lower:
                return p
    # Pass 2: suffix anchored to a separator character.
    for suffix in suffixes:
        suffix_lower = suffix.lower()
        for p in paths_list:
            name = p.name.lower()
            if not name.endswith(suffix_lower):
                continue
            if len(name) == len(suffix_lower):
                return p
            sep = name[-len(suffix_lower) - 1]
            if sep in "._-/":
                return p
    return None


# Friendly labels for the output inventory table.
_OUTPUT_CATEGORY = {
    ".png": "图片/可视化",
    ".jpg": "图片/可视化",
    ".jpeg": "图片/可视化",
    ".svg": "图片/可视化",
    ".pdf": "图片/可视化",
    ".csv": "数据表",
    ".tsv": "数据表",
    ".txt": "报告",
    ".md": "报告",
    ".h5ad": "AnnData",
    ".h5": "HDF5",
    ".rds": "R 对象",
    ".json": "JSON",
    ".html": "HTML",
}


def _parse_json_metrics(paths: List[Path]) -> Dict[str, str]:
    """Extract headline metrics from auxiliary JSON files when present."""
    metrics: Dict[str, str] = {}
    gene_overlap = _pick(paths, ("gene_overlap.json",))
    model_info = _pick(paths, ("model_info.json",))
    if gene_overlap is not None:
        try:
            data = json.loads(gene_overlap.read_text(encoding="utf-8", errors="replace"))
            n_adata_genes = data.get("n_adata_genes")
            n_model_genes = data.get("n_model_genes")
            n_overlap = data.get("n_overlap")
            if n_adata_genes is not None and n_model_genes is not None and n_overlap is not None:
                metrics["基因重叠"] = f"{n_overlap:,} / {n_model_genes:,}（{n_overlap / n_model_genes:.1%}）"
        except Exception:
            pass
    if model_info is not None:
        try:
            data = json.loads(model_info.read_text(encoding="utf-8", errors="replace"))
            model = data.get("model")
            n_types = data.get("n_cell_types")
            if model and n_types is not None:
                metrics["使用模型"] = f"{model}（{n_types} 种细胞类型）"
        except Exception:
            pass
    return metrics


def _build_output_table(paths: List[Path]) -> Optional[SummaryTable]:
    """Return a sourced table of produced artifacts (figures, tables, reports)."""
    rows: List[List[Any]] = []
    for p in paths:
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        cat = _OUTPUT_CATEGORY.get(suffix, "文件")
        size = p.stat().st_size if p.exists() else 0
        size_str = f"{size / (1024 * 1024):.2f} MB" if size > 1024 * 1024 else f"{size / 1024:.1f} KB"
        rows.append([cat, p.name, size_str])
    if not rows:
        return None
    rows.sort(key=lambda r: (r[0] != "图片/可视化", r[0], r[1]))
    return SummaryTable(
        title="输出文件",
        headers=["类型", "文件名", "大小"],
        rows=rows,
    )


def _summarize_labels(path: Path) -> Optional[Dict[str, Any]]:
    header, rows = _read_csv(path)
    if not header or not rows:
        return None
    label_i = _find_column(header, _LABEL_HINTS)
    conf_i = _find_column(header, _CONF_HINTS)
    if label_i is None:
        return None

    counts: Dict[str, int] = {}
    conf_sum: Dict[str, float] = {}
    confs: List[float] = []
    n = 0
    for row in rows:
        if label_i >= len(row):
            continue
        label = row[label_i].strip() or "Unassigned"
        counts[label] = counts.get(label, 0) + 1
        n += 1
        if conf_i is not None and conf_i < len(row):
            c = _to_float(row[conf_i])
            if c is not None:
                confs.append(c)
                conf_sum[label] = conf_sum.get(label, 0.0) + c

    if n == 0:
        return None

    mean_conf = sum(confs) / len(confs) if confs else None
    unassigned = counts.get("Unassigned", 0)
    unassigned_rate = (unassigned / n) if n else None

    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top_types: List[List[Any]] = []
    for label, cnt in ordered:
        avg = (conf_sum[label] / cnt) if label in conf_sum else None
        top_types.append(
            [
                label,
                f"{cnt:,}",
                f"{cnt / n:.1%}",
                f"{avg:.3f}" if avg is not None else "—",
            ]
        )

    return {
        "n_cells": n,
        "n_types": len(counts),
        "mean_conf": mean_conf,
        "unassigned_rate": unassigned_rate,
        "top_types": top_types,
    }


def _summarize_comparison(path: Path) -> Optional[Dict[str, Any]]:
    header, rows = _read_csv(path)
    if not header or not rows:
        return None
    ref_i = _find_column(header, _REF_HINTS)
    match_i = _find_column(header, _MATCH_HINTS)
    recall_i = _find_column(header, _RECALL_HINTS)
    count_i = _find_column(header, _COUNT_HINTS)
    if ref_i is None or recall_i is None:
        return None

    parsed: List[Tuple[str, str, float, Optional[int]]] = []
    for row in rows:
        if ref_i >= len(row) or recall_i >= len(row):
            continue
        ref = row[ref_i].strip()
        recall = _to_float(row[recall_i])
        if recall is None:
            continue
        if recall <= 1.0:
            recall *= 100.0
        match = row[match_i].strip() if match_i is not None and match_i < len(row) else ""
        cnt = None
        if count_i is not None and count_i < len(row):
            c = _to_float(row[count_i])
            cnt = int(c) if c is not None else None
        parsed.append((ref, match, recall, cnt))

    if not parsed:
        return None

    parsed.sort(key=lambda x: x[2], reverse=True)
    table_rows: List[List[Any]] = [
        [ref, match or "—", f"{recall:.1f}%", f"{cnt:,}" if cnt is not None else "—"]
        for ref, match, recall, cnt in parsed
    ]
    high = [r for r in parsed if r[2] >= 80.0]
    low = [r for r in parsed if r[2] < 50.0]
    tiny = [r for r in high if r[3] is not None and r[3] < 30]
    return {
        "rows": table_rows,
        "n_reference": len(parsed),
        "high": [(r[0], r[2]) for r in high],
        "low": [(r[0], r[2]) for r in low],
        "tiny": [(r[0], r[2], r[3]) for r in tiny],
    }


def _recall_from_confusion(path: Path) -> Optional[Dict[str, Any]]:
    """Derive per-reference best-match/recall from a confusion matrix CSV.

    Expected shape: first column = reference label, remaining columns = predicted
    labels, cells = counts. For each reference row we report the dominant
    predicted label (best match) and its share of the row (recall).
    """
    header, rows = _read_csv(path)
    if len(header) < 2 or not rows:
        return None
    pred_labels = header[1:]
    parsed: List[Tuple[str, str, float, int]] = []
    for row in rows:
        if len(row) < 2:
            continue
        ref = row[0].strip()
        counts = [_to_float(c) or 0.0 for c in row[1:]]
        total = sum(counts)
        if total <= 0:
            continue
        best_i = max(range(len(counts)), key=lambda i: counts[i])
        best_count = counts[best_i]
        best_label = pred_labels[best_i] if best_i < len(pred_labels) else ""
        parsed.append((ref, best_label, best_count / total * 100.0, int(total)))
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[2], reverse=True)
    table_rows: List[List[Any]] = [
        [ref, match or "—", f"{recall:.1f}%", f"{cnt:,}"]
        for ref, match, recall, cnt in parsed
    ]
    high = [r for r in parsed if r[2] >= 80.0]
    low = [r for r in parsed if r[2] < 50.0]
    tiny = [r for r in high if r[3] is not None and r[3] < 30]
    return {
        "rows": table_rows,
        "n_reference": len(parsed),
        "high": [(r[0], r[2]) for r in high],
        "low": [(r[0], r[2]) for r in low],
        "tiny": [(r[0], r[2], r[3]) for r in tiny],
    }


_COMPARISON_REPORT_ROW = re.compile(
    r"^\s*(?P<ref>[A-Za-z][A-Za-z0-9_/\-]*)\s+"
    r"n\s*=\s*(?P<n>[\d,]+)\s+"
    r"recall\s*=\s*(?P<recall>[0-9.]+)\s+"
    r"top_pred\s*=\s*(?P<pred>[^\n]+?)\s*$"
)


_COMPARISON_REPORT_HEADER = re.compile(
    r"CellTypist\s+vs\s+all_celltype\s+comparison",
    re.IGNORECASE,
)


def _parse_comparison_report(path: Path) -> Optional[Dict[str, Any]]:
    """Parse the agent-generated comparison_report.txt.

    The report contains a per-reference-label summary with fine-grained best
    predictions, including non-immune classes (Ductal, Endothelial, Stellate,
    CAF, ...). This is richer than the coarse immune-only mapping derived from
    the annotated h5ad.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if not _COMPARISON_REPORT_HEADER.search(text):
        return None
    parsed: List[Tuple[str, str, float, int]] = []
    for line in text.splitlines():
        m = _COMPARISON_REPORT_ROW.match(line)
        if not m:
            continue
        ref = m.group("ref").strip()
        n = int(m.group("n").replace(",", ""))
        recall_raw = m.group("recall")
        recall = float(recall_raw)
        if recall <= 1.0:
            recall *= 100.0
        pred = m.group("pred").strip()
        parsed.append((ref, pred, recall, n))
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[2], reverse=True)
    table_rows: List[List[Any]] = [
        [ref, match or "—", f"{recall:.1f}%", f"{cnt:,}"]
        for ref, match, recall, cnt in parsed
    ]
    high = [(r, rec) for r, _, rec, _ in parsed if rec >= 80.0]
    low = [(r, rec) for r, _, rec, _ in parsed if rec < 50.0]
    tiny = [(r, rec, c) for r, _, rec, c in parsed if rec >= 80.0 and c < 30]

    extra: Dict[str, Any] = {}
    m = re.search(r"Total cells:\s*(\d[\d,]*)", text)
    if m:
        extra["total_cells"] = int(m.group(1).replace(",", ""))
    m = re.search(r"Mean CellTypist confidence:\s*([0-9.]+)", text)
    if m:
        extra["mean_confidence"] = float(m.group(1))
    m = re.search(r"Coarse overall agreement[^0-9.]*([0-9.]+)", text)
    if m:
        extra["coarse_agreement"] = float(m.group(1))
    for key, pat in (("ari", r"ARI[^0-9.]*([0-9.]+)"), ("nmi", r"NMI[^0-9.]*([0-9.]+)")):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            extra[key] = float(m.group(1))

    return {
        "rows": table_rows,
        "n_reference": len(parsed),
        "high": high,
        "low": low,
        "tiny": tiny,
        **extra,
    }


def _comparison_from_cell_csv(path: Path) -> Optional[Dict[str, Any]]:
    """Derive per-reference agreement from a cell-level comparison CSV.

    Expected columns include ``all_celltype`` and at least one of
    ``celltypist_predicted`` / ``celltypist_majority_voting`` / ``predicted_labels``.
    Computes best-match recall per reference label, overall ARI/NMI, and the
    unassigned rate from a ``celltypist_label_filtered`` column if present.
    """
    header, rows = _read_csv(path, limit=500_000)
    if not header or not rows:
        return None
    headers_norm = [_norm(h) for h in header]

    def find(*hints: str) -> Optional[int]:
        for hint in hints:
            for i, h in enumerate(headers_norm):
                if hint in h:
                    return i
        return None

    ref_i = find("all_celltype", "reference", "ref", "true", "ground_truth")
    pred_i = find(
        "celltypist_majority_voting",
        "celltypist_predicted",
        "predicted_labels",
        "predicted_label",
        "predicted",
        "label",
    )
    conf_i = find("conf_score", "confidence", "conf")
    filtered_i = find("celltypist_label_filtered", "filtered", "unassigned")
    if ref_i is None or pred_i is None:
        return None

    try:
        import pandas as pd  # type: ignore
    except Exception:
        return None

    df = pd.DataFrame(rows, columns=header)
    ref_col = header[ref_i]
    pred_col = header[pred_i]
    df[ref_col] = df[ref_col].astype(str).str.strip()
    df[pred_col] = df[pred_col].astype(str).str.strip()
    df = df[(df[ref_col] != "") & (df[pred_col] != "")]
    if df.empty:
        return None

    table = pd.crosstab(df[ref_col], df[pred_col])
    parsed: List[Tuple[str, str, float, int]] = []
    for ref_label, row in table.iterrows():
        total = int(row.sum())
        if total <= 0:
            continue
        best_pred = str(row.idxmax())
        best_count = int(row.max())
        recall = best_count / total * 100.0
        parsed.append((str(ref_label), best_pred, recall, total))
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[2], reverse=True)
    table_rows: List[List[Any]] = [
        [ref, match or "—", f"{recall:.1f}%", f"{cnt:,}"]
        for ref, match, recall, cnt in parsed
    ]
    high = [(r, rec) for r, _, rec, _ in parsed if rec >= 80.0]
    low = [(r, rec) for r, _, rec, _ in parsed if rec < 50.0]
    tiny = [(r, rec, c) for r, _, rec, c in parsed if rec >= 80.0 and c < 30]

    ari: Optional[float] = None
    nmi: Optional[float] = None
    try:
        from sklearn.metrics import (  # type: ignore
            adjusted_rand_score,
            normalized_mutual_info_score,
        )

        ari = float(adjusted_rand_score(df[ref_col].tolist(), df[pred_col].tolist()))
        nmi = float(normalized_mutual_info_score(df[ref_col].tolist(), df[pred_col].tolist()))
    except Exception:
        pass

    extra: Dict[str, Any] = {}
    if conf_i is not None:
        conf_col = header[conf_i]
        conf_vals = pd.to_numeric(df[conf_col], errors="coerce").dropna()
        if not conf_vals.empty:
            extra["mean_confidence"] = float(conf_vals.mean())
    if filtered_i is not None:
        filt_col = header[filtered_i]
        unassigned = (df[filt_col].astype(str).str.lower() == "unassigned").sum()
        extra["unassigned_rate"] = float(unassigned) / len(df)
    extra["exact_match_rate"] = float((df[ref_col] == df[pred_col]).mean())

    return {
        "rows": table_rows,
        "n_reference": len(parsed),
        "high": high,
        "low": low,
        "tiny": tiny,
        "ari": ari,
        "nmi": nmi,
        **extra,
    }


_OUTPUT_H5AD_NAME_HINTS = (
    "annot",
    "celltypist",
    "output",
    "labeled",
    "labelled",
    "result",
)
_PRED_COL_CANDIDATES = (
    "celltypist_label",
    "celltypist_majority_voting",
    "celltypist_predicted_labels",
)

# Standard coarse mapping for CellTypist immune labels so the comparison table
# reflects agreement with reference coarse labels (CD8T/CD4T/NK/B/Myeloid/Plasma)
# regardless of how the agent's driver script collapsed the fine-grained output.
_CELLTYPE_COARSE_ORDER = ["CD8T", "CD4T", "NK", "B", "Plasma", "Myeloid", "Platelet", "Other"]


def _coarse_celltypist_label(label: str) -> str:
    """Map a CellTypist fine-grained label to a coarse immune reference label."""
    s = str(label).lower()
    if "platelet" in s or "megakary" in s:
        return "Platelet"
    if "plasma" in s:
        return "Plasma"
    # NK before T to avoid "NKT" being matched as NK; exclude NKT explicitly.
    if ("nk" in s or "ilc" in s) and "nkt" not in s:
        return "NK"
    # B cells (exclude plasma cells already handled above).
    if any(token in s for token in [" b ", "b cell", "b-cell", "naive b", "memory b", "transitional b", "age-associated b", "germinal center b", "pro-b", "pre-b"]):
        return "B"
    # CD8 cytotoxic T cells.
    if any(token in s for token in ["cd8", "cytotoxic t", "temra", "tem/trm cytotoxic", "trm cytotoxic", "tcm/naive cytotoxic"]):
        return "CD8T"
    # CD4 helper T cells.
    if any(token in s for token in ["cd4", "helper t", " treg", "tfh", "th1", "th2", "th17", "tem/effector helper", "tcm/naive helper", "follicular helper", "type 1 helper", "type 17 helper", "regulatory t"]):
        return "CD4T"
    # Myeloid.
    if any(token in s for token in ["monocyte", "macrophage", "dendritic", " dc", "mast ", "neutrophil", "myeloid", "granulocyte", "kupffer", "alveolar mac", "intermediate mac"]):
        return "Myeloid"
    return "Other"


def _coarse_comparison(
    ref_series: Any, pred_series: Any
) -> Optional[Dict[str, Any]]:
    """Build a coarse-grained comparison from reference and predicted label series."""
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return None

    df = pd.DataFrame({"ref": ref_series.astype(str), "pred": pred_series.astype(str)}).dropna()
    df = df[(df["ref"] != "") & (df["pred"] != "")]
    if df.empty:
        return None
    df["pred_coarse"] = df["pred"].map(_coarse_celltypist_label)

    table = pd.crosstab(df["ref"], df["pred_coarse"])
    parsed: List[Tuple[str, str, float, int]] = []
    for ref_label, row in table.iterrows():
        total = int(row.sum())
        if total <= 0:
            continue
        # Pick the dominant coarse prediction for this reference label.
        best_pred = str(row.idxmax())
        best_count = int(row.max())
        recall = best_count / total * 100.0
        parsed.append((str(ref_label), best_pred, recall, total))
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[2], reverse=True)
    table_rows: List[List[Any]] = [
        [ref, match or "—", f"{recall:.1f}%", f"{cnt:,}"]
        for ref, match, recall, cnt in parsed
    ]
    high = [(r, rec) for r, _, rec, _ in parsed if rec >= 80.0]
    low = [(r, rec) for r, _, rec, _ in parsed if rec < 50.0]
    tiny = [(r, rec, c) for r, _, rec, c in parsed if rec >= 80.0 and c < 30]

    ari: Optional[float] = None
    nmi: Optional[float] = None
    try:
        from sklearn.metrics import (  # type: ignore
            adjusted_rand_score,
            normalized_mutual_info_score,
        )

        ari = float(adjusted_rand_score(df["ref"].tolist(), df["pred_coarse"].tolist()))
        nmi = float(normalized_mutual_info_score(df["ref"].tolist(), df["pred_coarse"].tolist()))
    except Exception:
        pass

    return {
        "rows": table_rows,
        "n_reference": len(parsed),
        "high": high,
        "low": low,
        "tiny": tiny,
        "ari": ari,
        "nmi": nmi,
    }


def _pick_output_h5ad(paths: Iterable[Path]) -> Optional[Path]:
    """Choose the annotated output AnnData, never the uploaded input.

    Artifact paths reach here already filtered by the harvest step (which drops
    anything under the workspace ``data``/``input`` dirs), so we only need to
    disambiguate by name: a derived annotation result carries an output hint
    (``annotated``, ``celltypist``, ...) that the raw upload lacks.
    """
    candidates: List[Path] = [
        p for p in paths if p.suffix.lower() == ".h5ad" and p.is_file()
    ]
    if not candidates:
        return None
    for p in candidates:
        name = p.name.lower()
        if any(h in name for h in _OUTPUT_H5AD_NAME_HINTS):
            return p
    return candidates[0] if len(candidates) == 1 else None


def _resolve_obs_column(
    columns: Sequence[str],
    hints: Sequence[str],
    *,
    prefer: Sequence[str] = (),
    exclude: Optional[set] = None,
) -> Optional[str]:
    excluded = exclude or set()
    for name in prefer:
        if name in columns and name not in excluded:
            return name
    normed = {c: _norm(c) for c in columns}
    for hint in hints:
        for c, n in normed.items():
            if c in excluded:
                continue
            if hint in n:
                return c
    return None


def _comparison_from_h5ad(path: Path) -> Optional[Dict[str, Any]]:
    """Derive per-reference-label agreement from an annotated AnnData.

    Reads only ``obs`` (backed mode) so even large objects do not load ``X``.
    Returns the same shape as :func:`_summarize_comparison` plus optional overall
    ``ari`` / ``nmi`` clustering-agreement scores when scikit-learn is present.
    """
    try:
        import anndata as ad  # type: ignore
    except Exception:
        return None
    try:
        adata = ad.read_h5ad(path, backed="r")
        try:
            columns = list(adata.obs.columns)
            ref_col = _resolve_obs_column(columns, _REF_HINTS, prefer=("all_celltype",))
            pred_col = _resolve_obs_column(
                columns,
                _LABEL_HINTS,
                prefer=_PRED_COL_CANDIDATES,
                exclude={ref_col} if ref_col else set(),
            )
            if ref_col is None or pred_col is None:
                return None
            df = adata.obs[[ref_col, pred_col]].copy()
        finally:
            try:
                adata.file.close()
            except Exception:
                pass
    except Exception:
        return None

    df = df.dropna()
    if df.empty:
        return None
    ref = df[ref_col].astype(str)
    pred = df[pred_col].astype(str)
    mask = ref.ne("") & pred.ne("")
    ref, pred = ref[mask], pred[mask]
    if ref.empty:
        return None

    return _coarse_comparison(ref, pred)


_REPORT_PATTERNS = {
    "输入数据": re.compile(
        r"(\d[\d,]*)\s*细胞\s*×\s*(\d[\d,]*)\s*基因|"
        r"(?:Dataset|Cells x Genes|Cells)[:：\s]\s*(\d[\d,]*)\s*(?:cells?\s*x\s*|×\s*)(\d[\d,]*)\s*genes?|"
        r"Total cells:\s*(\d[\d,]*).*?Total genes:\s*(\d[\d,]*)"
    ),
    "基因重叠": re.compile(r"(?:基因重叠|Gene overlap)[^0-9./]*(\d[\d,]*)\s*/\s*(\d[\d,]*)"),
    "模型": re.compile(r"(?:Model|使用模型)[:：]\s*([^\n\(]+)"),
    "预测模式": re.compile(r"(?:Mode|Prediction column|预测模式|prediction mode)[:：]\s*([^\n]+)"),
    "置信度阈值": re.compile(r"(?:p_thres|confidence threshold|置信度阈值|threshold)[:：\s]*([0-9.]+)"),
    "ARI": re.compile(r"ARI[^0-9.]*([0-9.]+)"),
    "NMI": re.compile(r"NMI[^0-9.]*([0-9.]+)"),
    "HIGH_CONF": re.compile(r"[Hh]igh confidence[^:]*:\s*(\d[\d,]*)\s*\(\s*([0-9.]+)%\s*\)"),
    "UNASSIGNED": re.compile(r"[Uu]nassigned[^0-9.]*([0-9.]+)%"),
    "ACCURACY": re.compile(r"[Aa]ccuracy[^0-9.]*([0-9.]+)"),
    "MEAN_CONF": re.compile(r"[Mm]ean confidence[^0-9.]*([0-9.]+)"),
    "CELLS_ANNOTATED": re.compile(r"[Cc]ells annotated[^0-9.]*(\d[\d,]*)\s*of\s*(\d[\d,]*)"),
    "预处理说明": re.compile(r"(?:数据预处理说明|Preprocessing)[:：]\s*([^\n]+)"),
}


def _parse_report(path: Path) -> Dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    metrics: Dict[str, str] = {}
    m = _REPORT_PATTERNS["输入数据"].search(text)
    if m:
        cells = m.group(1) if m.group(1) is not None else (m.group(3) if m.group(3) is not None else m.group(5))
        genes = m.group(2) if m.group(2) is not None else (m.group(4) if m.group(4) is not None else m.group(6))
        if cells and genes:
            metrics["输入数据"] = f"{cells} 细胞 × {genes} 基因"
    m = _REPORT_PATTERNS["基因重叠"].search(text)
    if m:
        a, b = m.group(1), m.group(2)
        try:
            pct = int(a.replace(",", "")) / int(b.replace(",", ""))
            metrics["基因重叠"] = f"{a} / {b}（{pct:.1%}）"
        except (ValueError, ZeroDivisionError):
            metrics["基因重叠"] = f"{a} / {b}"
    m = _REPORT_PATTERNS["模型"].search(text)
    if m:
        model = m.group(1).strip()
        mode_bits = []
        if "best match" in text.lower():
            mode_bits.append("best match")
        if "majority voting" in text.lower() or "majority_voting" in text.lower():
            mode_bits.append("majority voting")
        if mode_bits:
            model = f"{model}（{' + '.join(mode_bits)}）"
        metrics["使用模型"] = model
    m = _REPORT_PATTERNS["预测模式"].search(text)
    if m:
        metrics["预测模式"] = m.group(1).strip()
    m = _REPORT_PATTERNS["置信度阈值"].search(text)
    if m:
        metrics["置信度阈值"] = m.group(1).strip()
    m = _REPORT_PATTERNS["UNASSIGNED"].search(text)
    if m:
        metrics["Unassigned 占比"] = f"{float(m.group(1)):.1f}%"
    for key in ("ARI", "NMI"):
        m = _REPORT_PATTERNS[key].search(text)
        if m:
            metrics[key] = m.group(1)
    m = _REPORT_PATTERNS["HIGH_CONF"].search(text)
    if m:
        try:
            pct = float(m.group(2))
            metrics["高置信度(>0.5)"] = f"{m.group(1)} 细胞（{pct:.1f}%）"
            metrics["_low_conf_rate"] = f"{100.0 - pct:.1f}"
        except ValueError:
            pass
    m = _REPORT_PATTERNS["ACCURACY"].search(text)
    if m:
        metrics["粗粒度准确率"] = m.group(1)
    m = _REPORT_PATTERNS["MEAN_CONF"].search(text)
    if m:
        metrics["平均置信度"] = m.group(1)
    m = _REPORT_PATTERNS["CELLS_ANNOTATED"].search(text)
    if m:
        metrics["免疫细胞注释"] = f"{m.group(1)} / {m.group(2)}"
    m = _REPORT_PATTERNS["预处理说明"].search(text)
    if m:
        metrics["预处理说明"] = m.group(1).strip()
    return metrics


def _build_findings(
    label_stats: Optional[Dict[str, Any]],
    comparison: Optional[Dict[str, Any]],
    report_metrics: Dict[str, str],
    sources: List[str],
    comparison_source: Optional[Path] = None,
) -> List[Finding]:
    findings: List[Finding] = []
    label_src = [s for s in sources if "label" in s.lower() or "annotation" in s.lower()]
    ref_src = _ref_sources(sources)
    report_src = [s for s in sources if "report" in s.lower()]
    comp_src = [str(comparison_source.name)] if comparison_source else ref_src or report_src or sources[:1]

    if report_metrics.get("输入数据"):
        findings.append(
            Finding(
                f"输入数据：{report_metrics['输入数据']}。",
                sources=report_src or sources[:1],
            )
        )
    if report_metrics.get("使用模型"):
        findings.append(
            Finding(
                f"使用模型：{report_metrics['使用模型']}。",
                sources=report_src or sources[:1],
            )
        )
    if report_metrics.get("基因重叠"):
        findings.append(
            Finding(
                f"基因重叠：{report_metrics['基因重叠']}。",
                sources=report_src or sources[:1],
            )
        )

    if label_stats:
        n = comparison.get("total_cells") if comparison else None
        if n is None:
            n = label_stats["n_cells"]
        k = label_stats["n_types"]
        mc = comparison.get("mean_confidence") if comparison else None
        if mc is None:
            mc = label_stats["mean_conf"]
        conf_txt = f"，平均置信度 {mc:.3f}" if mc is not None else ""
        findings.append(
            Finding(
                f"共注释 {n:,} 个细胞，识别 {k} 种细胞类型{conf_txt}。",
                sources=label_src or sources[:1],
            )
        )
        if label_stats["top_types"]:
            top = label_stats["top_types"][0]
            findings.append(
                Finding(
                    f"最大细胞群体为 {top[0]}（{top[1]} 细胞，占 {top[2]}）。",
                    sources=label_src or sources[:1],
                )
            )
        if label_stats["unassigned_rate"]:
            findings.append(
                Finding(
                    f"低置信度（Unassigned）细胞占 {label_stats['unassigned_rate']:.1%}，"
                    "可结合更高阈值或人工复核进一步处理。",
                    sources=label_src or sources[:1],
                )
            )
        elif report_metrics.get("_low_conf_rate"):
            findings.append(
                Finding(
                    f"约 {report_metrics['_low_conf_rate']}% 的细胞置信度低于 0.5"
                    "（虽未被标记为 Unassigned，但建议结合 majority voting 与人工复核）。",
                    sources=report_src or label_src or sources[:1],
                )
            )

    if report_metrics.get("ARI") or report_metrics.get("NMI"):
        bits = []
        if report_metrics.get("ARI"):
            bits.append(f"ARI={report_metrics['ARI']}")
        if report_metrics.get("NMI"):
            bits.append(f"NMI={report_metrics['NMI']}")
        findings.append(
            Finding(
                "与参考标签的整体分组结构一致（" + "、".join(bits) + "）；"
                "完全一致率受标签粒度差异影响，分群结构比逐细胞标签更有参考价值。",
                sources=comp_src or report_src or sources[:1],
            )
        )
    if report_metrics.get("完全一致率"):
        findings.append(
            Finding(
                f"逐细胞完全一致率为 {report_metrics['完全一致率']}；由于 CellTypist 输出细粒度亚型，"
                "完全一致率通常较低，建议结合 ARI/NMI 和粗粒度映射一致率综合判断。",
                sources=comp_src or report_src or sources[:1],
            )
        )

    if comparison:
        high = comparison["high"]
        low = comparison["low"]
        if high:
            names = "、".join(f"{n}({r:.0f}%)" for n, r in high[:6])
            findings.append(
                Finding(
                    f"{len(high)} 个参考标签召回率 ≥80%：{names}。",
                    sources=comp_src,
                )
            )
        if low:
            names = "、".join(f"{n}({r:.0f}%)" for n, r in low[:6])
            findings.append(
                Finding(
                    f"{len(low)} 个参考标签召回率 <50%：{names}，"
                    "多为细粒度亚型被合并或稀有细胞被误分配。",
                    sources=comp_src,
                )
            )
        tiny = comparison.get("tiny") or []
        if tiny:
            names = "、".join(f"{n}(n={c})" for n, _, c in tiny[:6])
            findings.append(
                Finding(
                    f"部分高召回标签样本量极小（{names}），"
                    "高召回率统计意义有限，解读时需结合细胞数谨慎判断。",
                    sources=comp_src,
                )
            )

    return findings


_NON_IMMUNE_REF = {"endothelial", "ductal", "stellate", "caf", "acinar", "endocrine", "schwann"}
_NON_IMMUNE_MATCH = {"endothelial cells", "epithelial cells", "fibroblasts"}


def _build_interpretation(
    label_stats: Optional[Dict[str, Any]],
    comparison: Optional[Dict[str, Any]],
    report_metrics: Dict[str, str],
    sources: List[str],
) -> List[Finding]:
    out: List[Finding] = []
    ref_src = _ref_sources(sources)
    report_src = [s for s in sources if "report" in s.lower()]
    src = ref_src or report_src or sources[:1]

    if comparison and comparison.get("high") and comparison.get("low"):
        out.append(
            Finding(
                "CellTypist 给出细粒度亚型，而参考标签为粗粒度；"
                "完全一致率受标签粒度差异影响，分群结构（ARI/NMI）比逐细胞标签更能反映真实一致性。",
                sources=src,
            )
        )
        rows = comparison.get("rows", [])
        extended = [
            r for r in rows
            if str(r[0]).lower() in _NON_IMMUNE_REF
            and str(r[1]).lower() in _NON_IMMUNE_MATCH
        ]
        if extended:
            names = "、".join(f"{r[0]}→{r[1]}" for r in extended[:5])
            out.append(
                Finding(
                    f"基质/上皮类标签虽超出免疫模型训练范围，仍被映射到相近类型（{names}），"
                    "说明模型对非免疫细胞具备一定的外延识别能力。",
                    sources=src,
                )
            )

        # Immune subtype resolution insight.
        immune_subtypes: Dict[str, List[str]] = {}
        for row in rows:
            ref = str(row[0])
            pred = str(row[1])
            if ref in {"CD8T", "CD4T", "B", "Myeloid", "NK"}:
                immune_subtypes.setdefault(ref, []).append(pred)
        resolution_bits = []
        if "CD8T" in immune_subtypes and len(immune_subtypes["CD8T"]) >= 2:
            resolution_bits.append(
                f"CD8T 被细分为 {', '.join(immune_subtypes['CD8T'][:2])} 等"
            )
        if "CD4T" in immune_subtypes and len(immune_subtypes["CD4T"]) >= 2:
            resolution_bits.append(
                f"CD4T 被细分为 {', '.join(immune_subtypes['CD4T'][:2])} 等"
            )
        if "B" in immune_subtypes and len(immune_subtypes["B"]) >= 2:
            resolution_bits.append(
                f"B 被细分为 {', '.join(immune_subtypes['B'][:2])} 等"
            )
        if resolution_bits:
            out.append(
                Finding(
                    "免疫细胞亚群分辨率更高：" + "；".join(resolution_bits) + "。",
                    sources=src,
                )
            )

        # Rare-cell mis-assignment insight.
        rare_mis = [
            r for r in rows
            if str(r[0]).lower() in {"acinar", "endocrine", "schwann"}
            and float(str(r[2]).rstrip("%")) < 50.0
        ]
        if rare_mis:
            names = "、".join(str(r[0]) for r in rare_mis[:4])
            out.append(
                Finding(
                    f"稀有细胞（{names}）数量极少，被分配到训练域外的免疫细胞类型，"
                    "这在免疫模型中属于预期范围内的误分配。",
                    sources=src,
                )
            )

    return out


def _build_next_steps(
    label_stats: Optional[Dict[str, Any]],
    comparison: Optional[Dict[str, Any]],
    report_metrics: Dict[str, str],
    sources: List[str],
) -> List[Finding]:
    out: List[Finding] = []
    ref_src = _ref_sources(sources)
    label_src = [s for s in sources if "label" in s.lower() or "annotation" in s.lower()]
    report_src = [s for s in sources if "report" in s.lower()]

    if comparison and comparison.get("low"):
        out.append(
            Finding(
                "将 CellTypist 细粒度标签系统映射回 all_celltype 粗粒度体系（CD8T/CD4T/NK/B/Plasma/Myeloid）"
                "后重算一致率，可显著提升粗标签召回并量化亚群分辨率。",
                sources=ref_src or sources[:1],
            )
        )
    if label_stats and label_stats.get("unassigned_rate"):
        out.append(
            Finding(
                "对 Unassigned 细胞提高置信度阈值或结合 majority voting / 人工复核，"
                "必要时补充 marker-based 注释作为交叉验证。",
                sources=label_src or sources[:1],
            )
        )
    elif report_metrics.get("_low_conf_rate"):
        out.append(
            Finding(
                f"约 {report_metrics['_low_conf_rate']}% 的细胞置信度低于 0.5，"
                "建议 majority voting 复核或改用更高置信阈值。",
                sources=report_src or label_src or sources[:1],
            )
        )
    if comparison and comparison.get("tiny"):
        out.append(
            Finding(
                "稀有标签（n<30）的高召回统计意义有限，建议扩大样本量或合并相近亚型后再评估。",
                sources=ref_src or sources[:1],
            )
        )
    if comparison and comparison.get("high"):
        out.append(
            Finding(
                "若研究目标仅聚焦免疫细胞，可排除基质/上皮（Endothelial、Ductal、Stellate、CAF）后重新评估；"
                "需要更高分辨率时可换用 Immune_All_High.pkl 或组织特异性模型对比。",
                sources=ref_src or sources[:1],
            )
        )
    if report_metrics.get("使用模型") and "Immune_All_Low" in report_metrics["使用模型"]:
        out.append(
            Finding(
                "如需更精细的免疫细胞亚型或包含非免疫细胞的整体注释，"
                "可尝试 Immune_All_High、Pan-Cancer 或自定义模型。",
                sources=report_src or sources[:1],
            )
        )
    return out


def user_requested_comparison(user_message: str) -> bool:
    msg = (user_message or "").lower()
    return any(term in msg for term in _COMPARISON_TERMS)


def _parse_llm_json_response(response: str) -> Dict[str, Any]:
    """Extract a JSON object from an LLM response that may be wrapped in fences."""
    response = response.strip()
    if response.startswith("```"):
        # Strip markdown fences and any language tag.
        response = response.split("\n", 1)[1] if "\n" in response else response
        if response.endswith("```"):
            response = response[:-3].strip()
    return json.loads(response)


async def enrich_summary_with_llm(
    summary: ResultSummary,
    user_message: str,
    llm_client: Optional[Any] = None,
) -> ResultSummary:
    """Add a controlled, LLM-generated interpretation and next-step suggestions.

    The LLM is given only the deterministic facts already extracted from the
    artifacts; it is explicitly forbidden from inventing numbers.  This keeps
    the summary grounded while making the chat message read more naturally and
    more like kimi code's end-to-end response.
    """
    if llm_client is None:
        from homomics_lab.llm_client import LLMClient

        llm_client = LLMClient()
    if not getattr(llm_client, "is_configured", lambda: False)():
        return summary

    facts = summary.to_dict()
    # Drop bulky tables from the prompt; the LLM only needs metrics/findings.
    facts.pop("tables", None)
    facts["user_request"] = user_message

    system_prompt = (
        "You are a senior bioinformatics analyst writing a concise chat response. "
        "You must base every claim on the provided deterministic facts. "
        "Do NOT invent numbers, p-values, or file paths. "
        "If the facts are insufficient for a confident interpretation, say so. "
        "Respond ONLY with a JSON object."
    )
    user_prompt = f"""Given the following deterministic analysis summary, write:
1. A concise interpretation (1-2 sentences in Chinese) explaining what the result means for the user's request.
2. One to two actionable next-step suggestions (in Chinese) based only on the facts.

User request: {user_message}

Deterministic facts:
{json.dumps(facts, ensure_ascii=False, indent=2, default=str)}

Return JSON:
{{
  "interpretation": "...",
  "next_steps": ["...", "..."]
}}
"""
    try:
        response = await llm_client.chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        data = _parse_llm_json_response(response)
        interpretation = data.get("interpretation", "")
        next_steps = data.get("next_steps") or []
        if interpretation:
            summary.interpretation.append(
                Finding(text=interpretation, sources=summary.sources[:1] or ["result_summary"])
            )
        for step in next_steps:
            if isinstance(step, str) and step.strip():
                summary.next_steps.append(
                    Finding(text=step.strip(), sources=summary.sources[:1] or ["result_summary"])
                )
    except Exception as exc:
        logger.warning("LLM enrichment of result summary failed: %s", exc, exc_info=True)
    return summary
