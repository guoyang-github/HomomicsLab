"""Main Pipeline Runner — Single-Cell RNA-seq (Python)

Linear auto-runner for the full pipeline. Does NOT pause for user input.
For interactive per-step execution, call steps individually (Agent model).

Usage:
    from run_pipeline import run_pipeline
    result = run_pipeline(data_path="filtered_feature_bc_matrix.h5", mode="auto")
"""

import os
from pathlib import Path

import matplotlib.pyplot as plt
import scanpy as sc

# Import all step modules
from s01_load import load_data
from s02_qc_decision import run_qc_step
from s03_doublet import run_doublet_step
from s04_normalize import run_normalization_step
from s05_integration_decision import run_integration_step
from s06_cluster import run_clustering_step
from s07_markers import run_marker_step, export_markers
from s08_annotation_decision import run_annotation_step
from llm_report import save_llm_reports


def run_pipeline(
    data_path: str,
    output_dir: str = "pipeline_results",
    mode: str = "auto",
    batch_col: str = "sample_id",
    tissue: str = None,
    groupby: str = "leiden",
    use_llm: bool = True,
):
    """Run the complete single-cell RNA-seq pipeline.

    This is a linear auto-runner. It does NOT pause for user input.
    For interactive execution with per-step decision dialogs, use the
    Agent orchestration model (call steps individually).

    Parameters
    ----------
    data_path : str
        Path to data (10X dir, .h5, .h5ad, or SampleSheet CSV)
    output_dir : str
        Output directory
    mode : str
        "auto" (silent full run) or "verbose" (print proposals to stdout)
    batch_col : str
        Column for batch integration
    tissue : str, optional
        Tissue type hint for annotation
    groupby : str
        Column for marker detection
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
    print("\n========== STEP 1: Load Data ==========")
    adata = load_data(data_path)

    # --- Step 2: QC ---
    print("\n========== STEP 2: QC Filtering ==========")
    qc_result = run_qc_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = qc_result["obj"]
    reports["qc"] = qc_result["report"]
    prev_reports["qc"] = qc_result["report"]
    llm_reports["qc"] = qc_result.get("llm_report")
    print(
        f"[REPORT] {qc_result['report']['step']}: {qc_result['report']['status']} "
        f"({qc_result['report']['cells_before']} -> {qc_result['report']['cells_after']} cells, "
        f"{qc_result['report']['pct_removed']}% removed)"
    )

    # --- Step 3: Doublet ---
    print("\n========== STEP 3: Doublet Detection ==========")
    dbl_result = run_doublet_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = dbl_result["obj"]
    reports["doublet"] = dbl_result["report"]
    prev_reports["doublet"] = dbl_result["report"]
    llm_reports["doublet"] = dbl_result.get("llm_report")
    print(
        f"[REPORT] {dbl_result['report']['step']}: {dbl_result['report']['status']} "
        f"({dbl_result['report']['doublet_rate']}% doublets)"
    )

    # --- Step 4: Normalize ---
    print("\n========== STEP 4: Normalization ==========")
    norm_result = run_normalization_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = norm_result["obj"]
    reports["normalization"] = norm_result["report"]
    prev_reports["normalization"] = norm_result["report"]
    llm_reports["normalization"] = norm_result.get("llm_report")
    print(
        f"[REPORT] {norm_result['report']['step']}: {norm_result['report']['status']} "
        f"(method={norm_result['report']['method']}, HVGs={norm_result['report']['n_hvg']})"
    )

    # --- Step 5: Integration Decision ---
    print("\n========== STEP 5: Integration Decision ==========")
    int_result = run_integration_step(adata, batch_col=batch_col, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = int_result["obj"]
    reports["integration"] = int_result["report"]
    prev_reports["integration"] = int_result["report"]
    llm_reports["integration"] = int_result.get("llm_report")
    print(
        f"[REPORT] {int_result['report']['step']}: {int_result['report']['status']} "
        f"(method={int_result['report'].get('method', 'N/A')})"
    )

    # --- Step 6: Clustering ---
    print("\n========== STEP 6: Clustering ==========")
    clust_result = run_clustering_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = clust_result["obj"]
    reports["clustering"] = clust_result["report"]
    prev_reports["clustering"] = clust_result["report"]
    llm_reports["clustering"] = clust_result.get("llm_report")
    print(
        f"[REPORT] {clust_result['report']['step']}: {clust_result['report']['status']} "
        f"({clust_result['report']['n_clusters']} clusters at res={clust_result['report']['default_resolution']})"
    )

    # --- Step 7: Markers ---
    print("\n========== STEP 7: Marker Detection ==========")
    marker_result = run_marker_step(adata, groupby=groupby, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = marker_result["obj"]
    reports["markers"] = marker_result["report"]
    prev_reports["markers"] = marker_result["report"]
    llm_reports["markers"] = marker_result.get("llm_report")

    # Export markers
    exported = export_markers(adata, output_dir=output_dir)
    print(
        f"[REPORT] {marker_result['report']['step']}: {marker_result['report']['status']} "
        f"({marker_result['report']['n_markers']} markers, "
        f"{marker_result['report']['avg_markers_per_cluster']} avg/cluster)"
    )

    # --- Step 8: Annotation ---
    print("\n========== STEP 8: Cell Type Annotation ==========")
    annot_result = run_annotation_step(adata, tissue=tissue, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
    adata = annot_result["obj"]
    reports["annotation"] = annot_result["report"]
    prev_reports["annotation"] = annot_result["report"]
    llm_reports["annotation"] = annot_result.get("llm_report")
    print(
        f"[REPORT] {annot_result['report']['step']}: {annot_result['report']['status']} "
        f"(method={annot_result['report']['method']}, "
        f"{annot_result['report']['pct_assigned']}% assigned)"
    )

    # --- Save ---
    print("\n========== SAVING RESULTS ==========")
    adata.write(f"{output_dir}/adata_annotated.h5ad")

    # Save LLM reports
    if use_llm:
        save_llm_reports(llm_reports, output_dir)

    # Summary UMAP (save directly to output_dir, not scanpy's figures/ prefix)
    fig, ax = plt.subplots(figsize=(10, 8))
    if "cell_type" in adata.obs.columns:
        sc.pl.umap(adata, color="cell_type", legend_loc="on data", ax=ax, show=False)
        fig.savefig(f"{output_dir}/plots/umap_annotated.pdf", bbox_inches="tight")
    else:
        sc.pl.umap(adata, color="leiden", legend_loc="on data", ax=ax, show=False)
        fig.savefig(f"{output_dir}/plots/umap_clusters.pdf", bbox_inches="tight")
    plt.close(fig)

    # --- Final Report ---
    print("\n========== PIPELINE COMPLETE ==========")
    print(f"Final cells: {adata.n_obs}")
    print(f"Final clusters: {adata.obs['leiden'].nunique()}")
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
    output_dir: str = "pipeline_results",
    mode: str = "auto",
    groupby: str = "leiden",
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
        Step number to resume from (5-8)
    output_dir : str
        Output directory
    mode : str
        "auto" (silent) or "verbose" (print proposals)
    groupby : str
        Column for marker detection
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
        print("\n========== STEP 5: Integration Decision ==========")
        int_result = run_integration_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports, **kwargs)
        adata = int_result["obj"]
        reports["integration"] = int_result["report"]
        prev_reports["integration"] = int_result["report"]
        llm_reports["integration"] = int_result.get("llm_report")

    if from_step <= 6:
        print("\n========== STEP 6: Clustering ==========")
        clust_result = run_clustering_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
        adata = clust_result["obj"]
        reports["clustering"] = clust_result["report"]
        prev_reports["clustering"] = clust_result["report"]
        llm_reports["clustering"] = clust_result.get("llm_report")

    if from_step <= 7:
        print("\n========== STEP 7: Marker Detection ==========")
        marker_result = run_marker_step(adata, groupby=groupby, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports)
        adata = marker_result["obj"]
        reports["markers"] = marker_result["report"]
        prev_reports["markers"] = marker_result["report"]
        llm_reports["markers"] = marker_result.get("llm_report")
        export_markers(adata, output_dir=output_dir)

    if from_step <= 8:
        print("\n========== STEP 8: Cell Type Annotation ==========")
        annot_result = run_annotation_step(adata, auto=(mode == "auto"), use_llm=use_llm, prev_reports=prev_reports, **kwargs)
        adata = annot_result["obj"]
        reports["annotation"] = annot_result["report"]
        prev_reports["annotation"] = annot_result["report"]
        llm_reports["annotation"] = annot_result.get("llm_report")

    adata.write(f"{output_dir}/adata_annotated.h5ad")

    if use_llm:
        save_llm_reports(llm_reports, output_dir)

    print("\n========== RESUME COMPLETE ==========")

    return {"obj": adata, "reports": reports, "llm_reports": llm_reports, "output_dir": output_dir}
