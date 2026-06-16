"""LLM Diagnostic Report Generator — Spatial Transcriptomics Pipeline (Python)

Generates structured markdown "diagnostic cards" that the LLM agent consumes
to provide deep, contextual advice at each pipeline step.

Design: Deterministic rule engine proposes + executes; LLM layer interprets
and contextualizes. No external API calls — the agent itself is the LLM.
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
    """Generate a markdown diagnostic card for a pipeline step."""
    if prev_reports is None:
        prev_reports = {}

    generators = {
        "qc": _llm_report_qc,
        "normalize": _llm_report_normalize,
        "integration": _llm_report_integration,
        "cluster": _llm_report_cluster,
        "spatial": _llm_report_spatial,
        "domain": _llm_report_domain,
    }

    gen = generators.get(step_name)
    if gen is None:
        return f"## Unknown Step: {step_name}\n\nNo LLM diagnostic template available."

    return gen(adata, proposal, report, prev_reports)


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
            if "n_hvg" in r:
                lines.append(f"  - HVG count: {r['n_hvg']}")
    return "\n".join(lines) if lines else "No previous step data available."


def _llm_report_qc(adata, proposal, report, prev_reports):
    t = proposal["thresholds"]
    d = proposal["diagnostics"]
    j = proposal["justification"]

    return f"""
## [LLM Diagnostic Card] Step 2: QC Filtering

### Data Snapshot
| Metric | Value |
|--------|-------|
| Initial spots | {d['n_spots']} |
| n_genes median | {d['n_genes_median']} |
| total_counts median | {d['n_counts_median']} |
| MT% median | {d['mt_median']:.2f}% |
| Tissue coverage | {d.get('tissue_coverage_pct', 'N/A')}% |

### Rule Proposal
| Threshold | Value | Rationale |
|-----------|-------|-----------|
| min_counts | {t['min_counts']} | {j['counts']} |
| min_genes | {t['min_genes']} | {j['genes']} |
| MT% max | {t['max_mt']:.1f}% | {j['mt']} |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| Spots after filter | {report['spots_after']} |
| Spots removed | {report['pct_removed']:.1f}% |

### Cross-Step Context
{_cross_step(prev_reports, ['qc'])}

### LLM Analysis Task
> 1. Is the removal rate ({report['pct_removed']:.1f}%) reasonable for spatial data?
>    - >40%: check if tissue-edge spots were improperly removed
> 2. Do QC metrics show expected spatial patterns (center vs edge)?
> 3. Are image artifacts (folds, bubbles) driving low-quality spots?
""".strip()


def _llm_report_normalize(adata, proposal, report, prev_reports):
    return f"""
## [LLM Diagnostic Card] Step 3: Normalization + HVG

### Data Snapshot
| Metric | Value |
|--------|-------|
| Spots | {proposal['diagnostics']['n_spots']} |
| Genes | {proposal['diagnostics']['n_genes']} |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Method | {proposal['recommendation']['method']} | {proposal['justification']} |
| Target HVGs | {proposal['recommendation']['n_hvg']} | Standard range |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| HVGs selected | {report['n_hvg']} |

### Cross-Step Context
{_cross_step(prev_reports, ['qc'])}

### LLM Analysis Task
> 1. Is HVG count ({report['n_hvg']}) within optimal range (1500-3000)?
> 2. For spatial data: should spatially variable genes (SVGs) be prioritized over HVGs?
> 3. Are there obvious batch effects visible in UMAP (if multi-sample)?
""".strip()


def _llm_report_integration(adata, proposal, report, prev_reports):
    d = proposal['diagnostics']
    score = d.get('batch_mixing_score')
    score_str = f"{score:.3f}" if score is not None else "N/A (single sample)"

    return f"""
## [LLM Diagnostic Card] Step 4: Batch Integration [CRITICAL]

### Data Snapshot
| Metric | Value |
|--------|-------|
| Samples detected | {d['n_samples']} |
| Total spots | {d['n_spots']} |
| Batch mixing score | {score_str} |

### Rule Proposal
| Parameter | Value |
|-----------|-------|
| Integrate? | {'YES' if proposal['recommendation']['integrate'] else 'NO'} |
| Method | {proposal['recommendation'].get('method', 'N/A')} |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| Method applied | {report.get('method', 'None')} |

### Cross-Step Context
{_cross_step(prev_reports, ['qc', 'normalize'])}

### LLM Analysis Task [DECISION POINT]
> 1. For spatial data: does integration preserve spatial coordinates and tissue structure?
> 2. If integration is SKIPPED: are samples truly comparable, or will batch confound downstream domains?
> 3. Should integration be performed in expression space only, preserving spatial graphs per sample?
""".strip()


def _llm_report_cluster(adata, proposal, report, prev_reports):
    return f"""
## [LLM Diagnostic Card] Step 5: Clustering

### Data Snapshot
| Metric | Value |
|--------|-------|
| Spots | {proposal['diagnostics']['n_spots']} |
| PCs used | {report.get('n_pcs_used', 'N/A')} |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| Clusters | {report['n_clusters']} |
| Resolution | {report['resolution']} |

### LLM Analysis Task
> 1. Do clusters correspond to tissue regions (not image artifacts like folds/edges)?
> 2. Is {report['n_clusters']} clusters reasonable for this tissue type?
> 3. Are clusters driven by batch (if multi-sample) or biology?
> 4. Should spatially constrained clustering be used instead of transcriptomic-only?
""".strip()


def _llm_report_spatial(adata, proposal, report, prev_reports):
    return f"""
## [LLM Diagnostic Card] Step 6: Spatial Analysis [CRITICAL]

### Data Snapshot
| Metric | Value |
|--------|-------|
| Spots | {proposal['diagnostics']['n_spots']} |
| Neighbor method | {proposal['recommendation']['neighbor_method']} |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| SVGs detected | {report.get('n_svgs', 'N/A')} |
| Top SVG | {report.get('top_svg', 'N/A')} |

### LLM Analysis Task [DECISION POINT]
> 1. Do top SVGs match expected tissue architecture markers?
> 2. Is the neighbor method ({proposal['recommendation']['neighbor_method']}) appropriate for this platform?
>    - Visium hex grid → grid/6 neighs
>    - Xenium/MERFISH → KNN/radius
> 3. Do neighborhood enrichment patterns match known tissue biology?
> 4. Any clusters with no spatial structure (possible artifacts or dissociation effects)?
""".strip()


def _llm_report_domain(adata, proposal, report, prev_reports):
    return f"""
## [LLM Diagnostic Card] Step 7: Domain Detection [CRITICAL]

### Data Snapshot
| Metric | Value |
|--------|-------|
| Spots | {proposal['diagnostics']['n_spots']} |
| Clusters | {proposal['diagnostics']['n_clusters']} |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Method | {proposal['recommendation']['method']} | {proposal['justification']} |
| Resolution | {proposal['recommendation'].get('resolution', 'N/A')} | Domain granularity |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **{report['status']}** |
| Domains detected | {report['n_domains']} |
| Method | {report['method']} |

### LLM Analysis Task [DECISION POINT]
> 1. Do spatial domains correspond to known histological regions?
> 2. Are domain boundaries sharp and biologically meaningful?
> 3. For method={proposal['recommendation']['method']}: is this the best choice?
>    - Spatial Leiden: fast, good for exploratory
>    - STAGATE: best for complex tissue architecture
>    - BayesSpace: best with uncertainty quantification
> 4. Should domains be used instead of transcriptomic clusters for downstream analysis?
""".strip()


def save_llm_reports(llm_reports: Dict[str, str], output_dir: str):
    """Save all LLM diagnostic cards to markdown files."""
    llm_dir = os.path.join(output_dir, "llm_reports")
    os.makedirs(llm_dir, exist_ok=True)

    for step_name, content in llm_reports.items():
        if content is not None:
            with open(os.path.join(llm_dir, f"{step_name}_diagnostic.md"), "w") as f:
                f.write(content)

    combined = "# LLM Diagnostic Reports — Spatial Transcriptomics Pipeline\n\n"
    combined += "---\n\n".join(
        [v for v in llm_reports.values() if v is not None]
    )
    with open(os.path.join(llm_dir, "combined_report.md"), "w") as f:
        f.write(combined)

    print(f"LLM reports saved to: {llm_dir}")
