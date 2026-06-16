"""Main Pipeline Runner — Spatial Transcriptomics (Python)

Linear auto-runner for the full spatial pipeline. Does NOT pause for user input.
For interactive per-step execution, call steps individually (Agent model).

Usage:
    from run_pipeline import run_pipeline
    result = run_pipeline(data_path="spaceranger_output/", mode="auto")
"""

import os
from pathlib import Path

import matplotlib.pyplot as plt
import scanpy as sc

# Import all step modules
from s01_load_spatial import load_spatial_data
from s02_qc_spatial import run_qc_step
from s03_normalize_spatial import run_normalization_step
from s04_integration_spatial import run_integration_step
from s05_cluster_spatial import run_clustering_step
from s06_spatial_analysis import run_spatial_analysis_step
from s07_domain_detection import run_domain_detection_step
from llm_report import save_llm_reports


def run_pipeline(
    data_path: str,
    output_dir: str = "spatial_results",
    mode: str = "auto",
    sample_col: str = "sample_id",
    use_llm: bool = True,
):
    """Run the complete spatial transcriptomics pipeline.

    This is a linear auto-runner. It does NOT pause for user input.
    For interactive execution with per-step decision dialogs, use the
    Agent orchestration model (call steps individually).

    Parameters
    ----------
    data_path : str
        Path to data (Visium dir, Xenium dir, .h5ad, or SampleSheet CSV)
    output_dir : str
        Output directory
    mode : str
        "auto" (silent full run) or "verbose" (print proposals to stdout)
    sample_col : str
        Column for batch integration
    use_llm : bool
        If True, generate LLM diagnostic cards at each step.

    Returns
    -------
    dict with final object and all step reports
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(f"{output_dir}/plots", exist_ok=True)

    reports = {}
    prev_reports = {}
    llm_reports = {}

    # --- Step 1: Load ---
    print("\n========== STEP 1: Load Spatial Data ==========")
    adata = load_spatial_data(data_path)

    # --- Step 2: QC ---
    print("\n========== STEP 2: QC Filtering ==========")
    qc_result = run_qc_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = qc_result["obj"]
    reports["qc"] = qc_result["report"]
    prev_reports["qc"] = qc_result["report"]
    llm_reports["qc"] = qc_result.get("llm_report")
    print(
        f"[REPORT] {qc_result['report']['step']}: {qc_result['report']['status']} "
        f"({qc_result['report']['spots_before']} -> {qc_result['report']['spots_after']} spots, "
        f"{qc_result['report']['pct_removed']}% removed)"
    )

    # --- Step 3: Normalize ---
    print("\n========== STEP 3: Normalization + HVG ==========")
    norm_result = run_normalization_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = norm_result["obj"]
    reports["normalization"] = norm_result["report"]
    prev_reports["normalization"] = norm_result["report"]
    llm_reports["normalization"] = norm_result.get("llm_report")
    print(
        f"[REPORT] {norm_result['report']['step']}: {norm_result['report']['status']} "
        f"(method={norm_result['report']['method']}, HVGs={norm_result['report']['n_hvg']})"
    )

    # --- Step 4: Integration Decision ---
    print("\n========== STEP 4: Integration Decision ==========")
    int_result = run_integration_step(adata, sample_col=sample_col, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = int_result["obj"]
    reports["integration"] = int_result["report"]
    prev_reports["integration"] = int_result["report"]
    llm_reports["integration"] = int_result.get("llm_report")
    print(
        f"[REPORT] {int_result['report']['step']}: {int_result['report']['status']} "
        f"(method={int_result['report'].get('method', 'N/A')})"
    )

    # --- Step 5: Clustering ---
    print("\n========== STEP 5: Clustering + UMAP ==========")
    clust_result = run_clustering_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = clust_result["obj"]
    reports["clustering"] = clust_result["report"]
    prev_reports["clustering"] = clust_result["report"]
    llm_reports["clustering"] = clust_result.get("llm_report")
    print(
        f"[REPORT] {clust_result['report']['step']}: {clust_result['report']['status']} "
        f"({clust_result['report']['n_clusters']} clusters at res={clust_result['report']['resolution']})"
    )

    # --- Step 6: Spatial Analysis ---
    print("\n========== STEP 6: Spatial Analysis ==========")
    spat_result = run_spatial_analysis_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = spat_result["obj"]
    reports["spatial"] = spat_result["report"]
    prev_reports["spatial"] = spat_result["report"]
    llm_reports["spatial"] = spat_result.get("llm_report")
    print(
        f"[REPORT] {spat_result['report']['step']}: {spat_result['report']['status']} "
        f"(SVGs={spat_result['report'].get('n_svgs', 'N/A')}, "
        f"method={spat_result['report'].get('svg_method', 'N/A')})"
    )

    # --- Step 7: Domain Detection ---
    print("\n========== STEP 7: Domain Detection ==========")
    dom_result = run_domain_detection_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = dom_result["obj"]
    reports["domain"] = dom_result["report"]
    prev_reports["domain"] = dom_result["report"]
    llm_reports["domain"] = dom_result.get("llm_report")
    print(
        f"[REPORT] {dom_result['report']['step']}: {dom_result['report']['status']} "
        f"({dom_result['report']['n_domains']} domains, method={dom_result['report']['method']})"
    )

    # --- Save ---
    print("\n========== SAVING RESULTS ==========")
    adata.write(f"{output_dir}/adata_spatial.h5ad")

    # Save LLM reports
    if use_llm:
        save_llm_reports(llm_reports, output_dir)

    # Summary plots
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    if "leiden" in adata.obs.columns:
        sc.pl.umap(adata, color="leiden", legend_loc="on data", ax=axes[0], show=False)
        axes[0].set_title("Transcriptomic Clusters")
    if "spatial_domain" in adata.obs.columns:
        sc.pl.umap(adata, color="spatial_domain", legend_loc="on data", ax=axes[1], show=False)
        axes[1].set_title("Spatial Domains")
    fig.savefig(f"{output_dir}/plots/umap_comparison.pdf", bbox_inches="tight")
    plt.close(fig)

    # --- Final Report ---
    print("\n========== PIPELINE COMPLETE ==========")
    print(f"Final spots: {adata.n_obs}")
    print(f"Final clusters: {adata.obs['leiden'].nunique() if 'leiden' in adata.obs.columns else 'N/A'}")
    print(f"Final domains: {adata.obs['spatial_domain'].nunique() if 'spatial_domain' in adata.obs.columns else 'N/A'}")
    print(f"Results saved to: {output_dir}")

    return {
        "obj": adata,
        "reports": reports,
        "llm_reports": llm_reports,
        "output_dir": output_dir,
    }


def resume_pipeline(
    adata: sc.AnnData,
    from_step: int = 5,
    output_dir: str = "spatial_results",
    mode: str = "auto",
    use_llm: bool = True,
    prev_reports: dict = None,
    **kwargs
):
    """Resume pipeline from a specific step.

    Parameters
    ----------
    adata : AnnData
        Object with appropriate state
    from_step : int
        Step number to resume from (5-7)
    output_dir : str
        Output directory
    mode : str
        "auto" (silent) or "verbose" (print proposals)
    use_llm : bool
        If True, generate LLM diagnostic cards.
    prev_reports : dict
        Previous step reports for cross-step context.
    **kwargs : Passed to step functions

    Returns
    -------
    dict with final object and reports
    """
    if from_step <= 4:
        raise ValueError("Cannot resume before Step 5. Use run_pipeline() for full run.")

    os.makedirs(output_dir, exist_ok=True)
    reports = {}
    llm_reports = {}
    if prev_reports is None:
        prev_reports = {}

    if from_step <= 5:
        print("\n========== STEP 5: Clustering + UMAP ==========")
        clust_result = run_clustering_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports, **kwargs)
        adata = clust_result["obj"]
        reports["clustering"] = clust_result["report"]
        prev_reports["clustering"] = clust_result["report"]
        llm_reports["clustering"] = clust_result.get("llm_report")

    if from_step <= 6:
        print("\n========== STEP 6: Spatial Analysis ==========")
        spat_result = run_spatial_analysis_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports, **kwargs)
        adata = spat_result["obj"]
        reports["spatial"] = spat_result["report"]
        prev_reports["spatial"] = spat_result["report"]
        llm_reports["spatial"] = spat_result.get("llm_report")

    if from_step <= 7:
        print("\n========== STEP 7: Domain Detection ==========")
        dom_result = run_domain_detection_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports, **kwargs)
        adata = dom_result["obj"]
        reports["domain"] = dom_result["report"]
        prev_reports["domain"] = dom_result["report"]
        llm_reports["domain"] = dom_result.get("llm_report")

    adata.write(f"{output_dir}/adata_spatial.h5ad")

    if use_llm:
        save_llm_reports(llm_reports, output_dir)

    print("\n========== RESUME COMPLETE ==========")

    return {"obj": adata, "reports": reports, "llm_reports": llm_reports, "output_dir": output_dir}
