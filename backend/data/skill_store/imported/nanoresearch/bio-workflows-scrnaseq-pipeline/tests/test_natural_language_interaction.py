"""Natural Language Interaction Test

Simulates a realistic user-agent conversation flow using the SampleSheet input.
Runs the pipeline step-by-step with auto=False (prints proposals + LLM cards)
but without blocking for user input.

Usage:
    python test_natural_language_interaction.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "python"))

from s01_load import load_data
from s02_qc_decision import run_qc_step
from s03_doublet import run_doublet_step
from s04_normalize import run_normalization_step
from s05_integration_decision import run_integration_step
from s06_cluster import run_clustering_step
from s07_markers import run_marker_step
from s08_annotation_decision import run_annotation_step
from llm_report import save_llm_reports

import anndata as ad


def print_agent(msg: str):
    """Print agent message with formatting."""
    print(f"\n[Agent] {msg}")


def print_user(msg: str):
    """Print user message with formatting."""
    print(f"\n[User]  {msg}")


def print_decision_box(title: str, lines: list):
    """Print a formatted decision box."""
    width = max(len(title), max(len(l) for l in lines)) + 4
    print(f"\n  {'─' * width}")
    print(f"  │ {title.ljust(width - 4)} │")
    print(f"  ├{'─' * (width - 2)}┤")
    for line in lines:
        print(f"  │ {line.ljust(width - 4)} │")
    print(f"  {'─' * width}")


def simulate_conversation():
    """Simulate a full user-agent conversation."""

    # ── Scenario Setup ──────────────────────────────────────────────
    samplesheet = Path(__file__).parent / "samplesheet_2patients.csv"
    out_dir = Path(__file__).parent / "output_nl_interaction"
    out_dir.mkdir(exist_ok=True)

    print("=" * 70)
    print("  NATURAL LANGUAGE INTERACTION TEST")
    print("  Skill: bio-workflows-scrnaseq-pipeline")
    print("  Data:  SampleSheet with PA08 + PA12 (PDAC scRNA-seq)")
    print("=" * 70)

    # ── Turn 1: User initiates ──────────────────────────────────────
    print_user(
        'I have two PDAC single-cell samples in a SampleSheet. '
        'Please run the full scRNA-seq pipeline on them.'
    )

    print_agent(
        f'I found your SampleSheet: {samplesheet.name}\n'
        '  Loading samples and preparing the pipeline...'
    )

    # ── Step 1: Load Data ───────────────────────────────────────────
    print_agent('Step 1: Loading data from SampleSheet...')
    adata = load_data(str(samplesheet))

    print_agent(
        f'Loaded 2 samples:\n'
        f'  - PA08: {adata.obs["sample_id"].value_counts().get("PA08", 0)} cells (High_NI)\n'
        f'  - PA12: {adata.obs["sample_id"].value_counts().get("PA12", 0)} cells (Low_NI)\n'
        f'  Total: {adata.n_obs} cells x {adata.n_vars} genes'
    )

    # ── Turn 2: QC Decision Point ───────────────────────────────────
    print_user('What do you recommend for QC?')

    print_agent('Analyzing QC metrics and proposing thresholds...')

    prev_reports = {}
    llm_reports = {}

    qc_result = run_qc_step(adata, auto=False, use_llm=True, prev_reports=prev_reports)
    adata = qc_result["obj"]
    prev_reports["qc"] = qc_result["report"]
    llm_reports["qc"] = qc_result["llm_report"]

    p = qc_result["proposal"]
    r = qc_result["report"]

    print_decision_box(
        "QC Proposal",
        [
            f"n_genes_by_counts: {p['thresholds']['n_genes_by_counts_min']} - {p['thresholds']['n_genes_by_counts_max']}",
            f"total_counts_min: {p['thresholds']['total_counts_min']}",
            f"pct_counts_mt_max: {p['thresholds']['pct_counts_mt_max']}%",
            "",
            f"Justification: {p['justification']['mt'][:60]}...",
            f"Estimated removal: ~{r['pct_removed']}% cells",
            f"Status: {r['status']}",
        ]
    )

    # ── Turn 3: User confirms QC ────────────────────────────────────
    print_user('Looks good, proceed with those thresholds.')
    print_agent(f'QC complete: {r["cells_before"]} → {r["cells_after"]} cells ({r["pct_removed"]}% removed)')

    # ── Turn 4: Doublet Detection ───────────────────────────────────
    print_agent('Step 3: Running doublet detection...')
    dbl_result = run_doublet_step(adata, auto=False, use_llm=True, prev_reports=prev_reports)
    adata = dbl_result["obj"]
    prev_reports["doublet"] = dbl_result["report"]
    llm_reports["doublet"] = dbl_result["llm_report"]

    print_agent(
        f'Doublet detection: {dbl_result["report"]["doublets_detected"]} doublets '
        f'({dbl_result["report"]["doublet_rate"]}%). '
        f'{dbl_result["report"]["cells_after"]} cells remaining.'
    )

    # ── Turn 5: Normalization ───────────────────────────────────────
    print_agent('Step 4: Normalizing and selecting HVGs...')
    norm_result = run_normalization_step(adata, auto=False, use_llm=True, prev_reports=prev_reports)
    adata = norm_result["obj"]
    prev_reports["normalization"] = norm_result["report"]
    llm_reports["normalization"] = norm_result["llm_report"]

    print_agent(
        f'Normalization: {norm_result["report"]["method"]} complete. '
        f'{norm_result["report"]["n_hvg"]} HVGs selected. '
        f'Status: {norm_result["report"]["status"]}'
    )

    # ── Turn 6: Integration Decision Point ──────────────────────────
    print_user('Do these two samples need batch correction?')

    print_agent('Diagnosing batch effects before clustering...')
    int_result = run_integration_step(
        adata, batch_col="sample_id", auto=False, use_llm=True, prev_reports=prev_reports
    )
    adata = int_result["obj"]
    prev_reports["integration"] = int_result["report"]
    llm_reports["integration"] = int_result["llm_report"]

    p = int_result["proposal"]
    r = int_result["report"]

    if p["recommendation"]["integrate"]:
        print_decision_box(
            "Integration Decision [CRITICAL]",
            [
                f"Batches detected: {p['diagnostics']['n_batches']}",
                f"Batch mixing score: {p['diagnostics'].get('batch_mixing_score', 'N/A')}",
                f"Recommendation: INTEGRATE with {p['recommendation']['method']}",
                "",
                f"Justification: {p['justification'][:55]}...",
                f"Status: {r['status']}",
            ]
        )
        print_user('Yes, use Harmony.')
        print_agent(f'Integration complete: {r["method"]} applied to {p["diagnostics"]["n_batches"]} batches.')
    else:
        print_decision_box(
            "Integration Decision [CRITICAL]",
            [
                f"Batches detected: {p['diagnostics']['n_batches']}",
                f"Batch mixing score: {p['diagnostics'].get('batch_mixing_score', 'N/A')}",
                "Recommendation: SKIP integration",
                "",
                f"Justification: {p['justification'][:55]}...",
                f"Status: {r['status']}",
            ]
        )
        print_user('Good, skip integration then.')
        print_agent('Skipping integration. Proceeding with normalized data.')

    # ── Turn 7: Clustering ──────────────────────────────────────────
    print_agent('Step 6: Computing PCA, UMAP, and clustering at multiple resolutions...')
    clust_result = run_clustering_step(adata, auto=False, use_llm=True, prev_reports=prev_reports)
    adata = clust_result["obj"]
    prev_reports["clustering"] = clust_result["report"]
    llm_reports["clustering"] = clust_result["llm_report"]

    print_decision_box(
        "Clustering Proposal",
        [
            f"PCs: {clust_result['proposal']['recommendation']['n_pcs']} computed",
            f"Resolutions: {clust_result['proposal']['recommendation']['resolutions']}",
            f"Default: {clust_result['proposal']['recommendation']['default_resolution']}",
            "",
            f"Result: {clust_result['report']['n_clusters']} clusters at default resolution",
            f"Status: {clust_result['report']['status']}",
        ]
    )
    print_user('14 clusters looks reasonable. Continue.')

    # ── Turn 8: Markers ─────────────────────────────────────────────
    print_agent('Step 7: Finding marker genes for each cluster...')
    marker_result = run_marker_step(adata, auto=False, use_llm=True, prev_reports=prev_reports)
    adata = marker_result["obj"]
    prev_reports["markers"] = marker_result["report"]
    llm_reports["markers"] = marker_result["llm_report"]

    print_agent(
        f'Markers: {marker_result["report"]["n_markers"]} total '
        f'({marker_result["report"]["avg_markers_per_cluster"]} avg per cluster). '
        f'Status: {marker_result["report"]["status"]}'
    )

    # ── Turn 9: Annotation Decision Point ───────────────────────────
    print_user('What cell types do you see?')

    print_agent('Running cell type annotation...')
    annot_result = run_annotation_step(
        adata, tissue="Pancreas", auto=False, use_llm=True, prev_reports=prev_reports
    )
    adata = annot_result["obj"]
    prev_reports["annotation"] = annot_result["report"]
    llm_reports["annotation"] = annot_result["llm_report"]

    p = annot_result["proposal"]
    r = annot_result["report"]

    print_decision_box(
        "Annotation Result [CRITICAL]",
        [
            f"Method: {p['recommendation']['method']}",
            f"Cell types: {r['n_cell_types']}",
            f"Assignment rate: {r['pct_assigned']}%",
            "",
            f"Status: {r['status']}",
        ]
    )

    # Print cell type distribution
    if "cell_type" in adata.obs.columns:
        print_agent("Cell type distribution:")
        for ct, count in adata.obs["cell_type"].value_counts().head(10).items():
            pct = count / adata.n_obs * 100
            print(f"  - {ct}: {count} cells ({pct:.1f}%)")

    # ── Turn 10: Final Summary ──────────────────────────────────────
    print_user('Great! Give me a summary.')

    print_agent(
        '\n' + '═' * 70 + '\n'
        '  PIPELINE COMPLETE\n'
        '═' * 70
    )

    summary_lines = [
        f"  Input:     {prev_reports['qc']['cells_before']} cells (2 samples)",
        f"  QC:        {prev_reports['qc']['cells_after']} retained ({prev_reports['qc']['pct_removed']}% removed) {prev_reports['qc']['status']}",
        f"  Doublet:   {prev_reports['doublet']['doublets_detected']} removed ({prev_reports['doublet']['doublet_rate']}%) {prev_reports['doublet']['status']}",
        f"  Normalize: {prev_reports['normalization']['method']}, {prev_reports['normalization']['n_hvg']} HVGs {prev_reports['normalization']['status']}",
        f"  Integrate: {prev_reports['integration']['method'] if prev_reports['integration']['status'] != 'SKIPPED' else 'Skipped'} {prev_reports['integration']['status']}",
        f"  Cluster:   {prev_reports['clustering']['n_clusters']} clusters {prev_reports['clustering']['status']}",
        f"  Markers:   {prev_reports['markers']['n_markers']} total {prev_reports['markers']['status']}",
        f"  Annotate:  {prev_reports['annotation']['n_cell_types']} types, {prev_reports['annotation']['pct_assigned']}% assigned {prev_reports['annotation']['status']}",
    ]
    for line in summary_lines:
        print(line)
    print('═' * 70)

    # Save results
    print_agent(f'Saving results to {out_dir}...')
    adata.write(str(out_dir / "adata_annotated.h5ad"))
    save_llm_reports(llm_reports, str(out_dir))

    print_agent(
        f'All done!\n'
        f'  - Annotated object: {out_dir}/adata_annotated.h5ad\n'
        f'  - LLM diagnostic cards: {out_dir}/llm_reports/\n'
        f'\nWould you like me to:\n'
        f'  1. Compare cell types between High_NI (PA08) and Low_NI (PA12)\n'
        f'  2. Show top markers for each cluster\n'
        f'  3. Generate UMAP plots colored by cell type'
    )

    return adata, prev_reports, llm_reports


if __name__ == "__main__":
    simulate_conversation()
