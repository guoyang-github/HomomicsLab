"""LLM Diagnostic Report Generator — Single-Cell RNA-seq Pipeline (Python)

Generates structured markdown "diagnostic cards" that the LLM agent consumes
to provide deep, contextual advice at each pipeline step.

Design: Deterministic rule engine proposes + executes; LLM layer interprets
and contextualizes. No external API calls — the agent itself is the LLM.

Usage:
    llm_report = generate_llm_report("qc", adata, proposal, report, prev_reports)
    print(llm_report)  # Agent reads this and generates analysis
"""

import os
from typing import Any, Dict, List, Optional


def generate_llm_report(
    step_name: str,
    adata: Any,
    proposal: Dict,
    report: Dict,
    prev_reports: Optional[Dict] = None,
) -> str:
    """Generate a markdown diagnostic card for a pipeline step.

    Parameters
    ----------
    step_name : str
        One of: qc, doublet, normalize, integration, cluster, markers, annotation
    adata : AnnData
        Current state object
    proposal : dict
        Proposal from propose_*()
    report : dict
        Report from report_*()
    prev_reports : dict, optional
        Previous step reports for cross-step analysis

    Returns
    -------
    str
        Markdown diagnostic card
    """
    if prev_reports is None:
        prev_reports = {}

    generators = {
        "qc": _llm_report_qc,
        "doublet": _llm_report_doublet,
        "normalize": _llm_report_normalize,
        "integration": _llm_report_integration,
        "cluster": _llm_report_cluster,
        "markers": _llm_report_markers,
        "annotation": _llm_report_annotation,
    }

    gen = generators.get(step_name)
    if gen is None:
        return f"## Unknown Step: {step_name}\n\nNo LLM diagnostic template available."

    return gen(adata, proposal, report, prev_reports)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cross_step(prev_reports: Dict, step_names: List[str]) -> str:
    """Extract relevant context from previous step reports."""
    lines = []
    for sn in step_names:
        if sn in prev_reports:
            r = prev_reports[sn]
            status = r.get("status", "N/A")
            lines.append(f"- **{sn}**: status={status}")
            if "pct_removed" in r:
                lines.append(f"  - Cell removal: {r['pct_removed']:.1f}%")
            if "doublet_rate" in r:
                lines.append(f"  - Doublet rate: {r['doublet_rate']:.1f}%")
            if "n_hvg" in r:
                lines.append(f"  - HVG count: {r['n_hvg']}")
    return "\n".join(lines) if lines else "No previous step data available."


# ---------------------------------------------------------------------------
# D2: QC
# ---------------------------------------------------------------------------


def _llm_report_qc(adata, proposal, report, prev_reports):
    t = proposal["thresholds"]
    d = proposal["diagnostics"]
    j = proposal["justification"]

    return f"""
## [LLM Diagnostic Card] Step 2: QC Filtering

### Data Snapshot
| Metric | Value |
|--------|-------|
| Initial cells | {d['n_cells']} |
| n_genes_by_counts median | {d['n_genes_median']} |
| n_genes_by_counts 99th pct | {d['n_genes_q99']} |
| total_counts median | {d['n_counts_median']} |
| MT% median | {d['mt_median']:.2f}% |
| MT% 95th pct | {d['mt_q95']:.2f}% |

### Rule Proposal
| Threshold | Value | Rationale |
|-----------|-------|-----------|
| n_genes_by_counts min | {t['n_genes_by_counts_min']} | {j['n_genes']} |
| n_genes_by_counts max | {t['n_genes_by_counts_max']} | Captures >95% of cells |
| total_counts min | {t['total_counts_min']} | {j['n_counts']} |
| MT% max | {t['pct_counts_mt_max']:.1f}% | {j['mt']} |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| Cells after filter | {report['cells_after']} |
| Cells removed | {report['pct_removed']:.1f}% |

### Cross-Step Context
{_cross_step(prev_reports, ['qc'])}

### LLM Analysis Task
> Analyze this QC profile and assess whether the proposed thresholds are
> appropriate for downstream analysis. Consider:
> 1. Is the MT% distribution consistent with the expected tissue type?
> 2. Is the removal rate ({report['pct_removed']:.1f}%) reasonable, or does it suggest over/under-filtering?
> 3. Are there any red flags (e.g., bimodal n_genes distribution, extreme MT% outliers)
>    that warrant special attention?
> 4. Should any thresholds be adjusted before proceeding?
""".strip()


# ---------------------------------------------------------------------------
# D3: Doublet
# ---------------------------------------------------------------------------


def _llm_report_doublet(adata, proposal, report, prev_reports):
    return f"""
## [LLM Diagnostic Card] Step 3: Doublet Detection

### Data Snapshot
| Metric | Value |
|--------|-------|
| Cells input | {proposal['params']['n_cells']} |
| Expected doublet rate | ~{proposal['params']['expected_doublet_rate']:.1f}% |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| Doublets detected | {report['doublets_detected']} ({report['doublet_rate']:.1f}%) |
| Cells after removal | {report['cells_after']} |

### Cross-Step Context
{_cross_step(prev_reports, ['qc'])}

### LLM Analysis Task
> Evaluate the doublet detection results:
> 1. Is the detected doublet rate ({report['doublet_rate']:.1f}%) consistent with the expected rate ({proposal['params']['expected_doublet_rate']:.1f}%)?
> 2. If the rate is abnormally high (>15%) or low (<1%), what could explain this?
>    Consider whether QC filtering in the previous step may have pre-removed doublets.
> 3. For multi-sample data: should doublet detection have been run per-sample?
> 4. Is it safe to proceed to normalization?
""".strip()


# ---------------------------------------------------------------------------
# D4: Normalization
# ---------------------------------------------------------------------------


def _llm_report_normalize(adata, proposal, report, prev_reports):
    return f"""
## [LLM Diagnostic Card] Step 4: Normalization + HVG

### Data Snapshot
| Metric | Value |
|--------|-------|
| Cells | {proposal['diagnostics']['n_cells']} |
| Genes | {proposal['diagnostics']['n_genes']} |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Method | {proposal['recommendation']['method']} | {proposal['justification']} |
| Target sum | {proposal['recommendation']['target_sum']:.0e} | CPM normalization |
| Target HVGs | {proposal['recommendation']['n_hvg']} | Standard range |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| HVGs selected | {report['n_hvg']} |

### Cross-Step Context
{_cross_step(prev_reports, ['qc', 'doublet'])}

### LLM Analysis Task
> Assess the normalization setup:
> 1. Is {proposal['recommendation']['method']} appropriate for this dataset size ({proposal['diagnostics']['n_cells']} cells)?
> 2. Is the HVG count ({report['n_hvg']}) within the optimal range (1500-3000)?
> 3. Should additional variables be regressed (e.g., cell cycle, ribosomal %)?
> 4. For Scanpy log1p: is the default target_sum=1e4 appropriate, or should it be adjusted?
""".strip()


# ---------------------------------------------------------------------------
# D5: Integration (Critical)
# ---------------------------------------------------------------------------


def _llm_report_integration(adata, proposal, report, prev_reports):
    d = proposal['diagnostics']
    score_str = f"{d.get('batch_mixing_score', 'N/A (single batch)'):.3f}" if 'batch_mixing_score' in d else "N/A (single batch)"

    return f"""
## [LLM Diagnostic Card] Step 5: Batch Integration Decision [CRITICAL]

### Data Snapshot
| Metric | Value |
|--------|-------|
| Batches detected | {d['n_batches']} |
| Total cells | {d['n_cells']} |
| Batch mixing score | {score_str} |

### Rule Proposal
| Parameter | Value |
|-----------|-------|
| Integrate? | {'YES' if proposal['recommendation']['integrate'] else 'NO'} |
| Method | {proposal['recommendation'].get('method', 'N/A')} |
| Reason | {proposal['justification']} |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| Method applied | {report.get('method', 'None')} |

### Cross-Step Context
{_cross_step(prev_reports, ['qc', 'doublet', 'normalize'])}

### LLM Analysis Task [DECISION POINT]
> This is a critical decision that affects all downstream analysis.
> Evaluate the integration recommendation:
> 1. Is the batch mixing score ({score_str}) interpreted correctly?
>    - <0.3: batches well-mixed, skip integration
>    - 0.3-0.6: moderate effect, integrate
>    - >0.6: strong effect, integrate aggressively
> 2. Is the recommended method ({proposal['recommendation'].get('method', 'N/A')}) appropriate for {d['n_batches']} batches and {d['n_cells']} cells?
>    - Harmony: best for 2-5 batches, <50k cells
>    - Scanorama/scVI: better for many batches or large datasets
> 3. If integration is SKIPPED: are we confident batches are truly well-mixed,
>    or could biological variation be confounded with batch?
> 4. After integration (if applied): should we verify biological signals are
>    preserved by checking known marker expression?
""".strip()


# ---------------------------------------------------------------------------
# D6: Clustering
# ---------------------------------------------------------------------------


def _llm_report_cluster(adata, proposal, report, prev_reports):
    return f"""
## [LLM Diagnostic Card] Step 6: Clustering

### Data Snapshot
| Metric | Value |
|--------|-------|
| Cells | {proposal['diagnostics']['n_cells']} |
| PCs computed | {proposal['recommendation']['n_pcs']} |
| PCs used | {proposal['recommendation']['n_pcs_use']} |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Resolutions | {', '.join(map(str, proposal['recommendation']['resolutions']))} | {proposal['justification']} |
| Default resolution | {proposal['recommendation']['default_resolution']} | Based on dataset size |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| Clusters (default) | {report['n_clusters']} |

### LLM Analysis Task
> Evaluate the clustering results:
> 1. Is {report['n_clusters']} clusters at resolution {report['default_resolution']} reasonable for {proposal['diagnostics']['n_cells']} cells?
>    - <5 clusters: may need higher resolution
>    - >50 clusters: likely over-clustering
> 2. Are the tested resolutions sufficient to capture both broad and fine structure?
> 3. Should we consider running additional resolutions (e.g., 0.1 for very broad types, 1.5-2.0 for subtypes)?
> 4. If batch integration was applied: are clusters driven by biology or residual batch effects?
""".strip()


# ---------------------------------------------------------------------------
# D7: Markers
# ---------------------------------------------------------------------------


def _llm_report_markers(adata, proposal, report, prev_reports):
    return f"""
## [LLM Diagnostic Card] Step 7: Marker Detection

### Data Snapshot
| Metric | Value |
|--------|-------|
| Clusters | {proposal['diagnostics']['n_clusters']} |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Test | {proposal['recommendation']['method']} | Robust for most data |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| Total markers | {report['n_markers']} |
| Avg per cluster | {report['avg_markers_per_cluster']:.1f} |

### Cross-Step Context
{_cross_step(prev_reports, ['qc', 'doublet', 'cluster'])}

### LLM Analysis Task
> Evaluate marker quality:
> 1. Is {report['avg_markers_per_cluster']:.1f} markers per cluster sufficient for annotation?
>    - <5: likely insufficient, may need lower thresholds
>    - 5-20: good range
>    - >50: may include noisy genes
> 2. Are the top markers per cluster showing expected cell-type-specific patterns?
> 3. Should conserved markers be computed if multi-sample?
> 4. Any clusters with very few or no markers? These may be low-quality or doublet clusters.
""".strip()


# ---------------------------------------------------------------------------
# D8: Annotation
# ---------------------------------------------------------------------------


def _llm_report_annotation(adata, proposal, report, prev_reports):
    if "cell_type" in adata.obs.columns:
        tbl = adata.obs['cell_type'].value_counts()
        cell_type_summary = "\n".join(
            [f"- {k}: {v} ({100*v/len(adata):.1f}%)" for k, v in tbl.items()]
        )
    else:
        cell_type_summary = "No cell type assignments available."

    return f"""
## [LLM Diagnostic Card] Step 8: Cell Type Annotation [CRITICAL]

### Data Snapshot
| Metric | Value |
|--------|-------|
| Cells | {proposal['diagnostics']['n_cells']} |
| Clusters | {proposal['diagnostics']['n_clusters']} |
| Tissue hint | {proposal['recommendation'].get('tissue', 'Not provided')} |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Method | {proposal['recommendation']['method']} | {proposal['justification']} |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| Cell types assigned | {report['n_cell_types']} |
| Assignment rate | {report['pct_assigned']:.1f}% |

### Cell Type Distribution
{cell_type_summary}

### Cross-Step Context
{_cross_step(prev_reports, ['qc', 'doublet', 'cluster', 'markers'])}

### LLM Analysis Task [DECISION POINT]
> Evaluate the annotation quality:
> 1. Is {report['pct_assigned']:.1f}% assignment rate acceptable?
>    - >90%: excellent
>    - 70-90%: review unassigned clusters
>    - <70%: method may be inappropriate for this tissue
> 2. Do the assigned cell types match the expected tissue composition ({proposal['recommendation'].get('tissue', 'unknown tissue')})?
> 3. Are there any suspicious annotations (e.g., all cells labeled as one type,
>    or obviously wrong assignments like neurons in blood)?
> 4. Should manual curation be performed for any clusters?
> 5. If annotation confidence is low: should we re-run with a different method?
""".strip()


# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------


def save_llm_reports(llm_reports: Dict[str, str], output_dir: str):
    """Save all LLM diagnostic cards to markdown files.

    Parameters
    ----------
    llm_reports : dict
        Named dict of markdown strings
    output_dir : str
        Directory to save reports
    """
    llm_dir = os.path.join(output_dir, "llm_reports")
    os.makedirs(llm_dir, exist_ok=True)

    for step_name, content in llm_reports.items():
        if content is not None:
            with open(os.path.join(llm_dir, f"{step_name}_diagnostic.md"), "w") as f:
                f.write(content)

    # Combined report
    combined = "# LLM Diagnostic Reports — scRNA-seq Pipeline\n\n"
    combined += "---\n\n".join(
        [v for v in llm_reports.values() if v is not None]
    )
    with open(os.path.join(llm_dir, "combined_report.md"), "w") as f:
        f.write(combined)

    print(f"LLM reports saved to: {llm_dir}")
