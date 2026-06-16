"""Test Case 3: Interactive decision points (Python).

Validates that proposals are generated correctly and diagnostic cards
are readable at each critical decision point.
Runs in auto mode but with use_llm=True to print diagnostic cards.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "python"))

from s02_qc_decision import run_qc_step
from s03_doublet import run_doublet_step
from s04_normalize import run_normalization_step
from s05_integration_decision import run_integration_step
from s06_cluster import run_clustering_step
from s07_markers import run_marker_step
from s08_annotation_decision import run_annotation_step

import anndata as ad


def test_decision_points():
    """Step through pipeline and print proposals + LLM diagnostic cards."""
    data_path = Path(__file__).parent / "PA08_sc_renamed.h5ad"
    assert data_path.exists(), f"Test data not found: {data_path}"

    print(f"\n{'='*60}")
    print("TEST 3: Interactive decision points")
    print(f"{'='*60}\n")

    adata = ad.read_h5ad(data_path)
    prev_reports = {}

    # --- D2: QC Decision ---
    print("\n>>> DECISION POINT: QC Thresholds")
    qc_result = run_qc_step(adata, auto=False, use_llm=True, prev_reports=prev_reports)
    adata = qc_result["obj"]
    prev_reports["qc"] = qc_result["report"]
    print(f"\nProposal: n_genes {qc_result['proposal']['thresholds']['n_genes_by_counts_min']}-"
          f"{qc_result['proposal']['thresholds']['n_genes_by_counts_max']}, "
          f"MT% < {qc_result['proposal']['thresholds']['pct_counts_mt_max']}%")
    print(f"Report: {qc_result['report']['status']} ({qc_result['report']['pct_removed']}% removed)")
    assert qc_result["llm_report"] is not None, "QC LLM report missing"
    assert "[LLM Diagnostic Card]" in qc_result["llm_report"], "Invalid QC LLM report format"

    # --- D3: Doublet Detection ---
    print("\n>>> STEP: Doublet Detection")
    dbl_result = run_doublet_step(adata, auto=False, use_llm=True, prev_reports=prev_reports)
    adata = dbl_result["obj"]
    prev_reports["doublet"] = dbl_result["report"]
    print(f"Proposal: expected ~{dbl_result['proposal']['params']['expected_doublet_rate']}% doublets")
    print(f"Report: {dbl_result['report']['status']} ({dbl_result['report']['doublet_rate']}% detected)")
    assert dbl_result["llm_report"] is not None, "Doublet LLM report missing"

    # --- D4: Normalization ---
    print("\n>>> STEP: Normalization")
    norm_result = run_normalization_step(adata, auto=False, use_llm=True, prev_reports=prev_reports)
    adata = norm_result["obj"]
    prev_reports["normalization"] = norm_result["report"]
    print(f"Proposal: {norm_result['proposal']['recommendation']['method']}")
    print(f"Report: {norm_result['report']['status']} ({norm_result['report']['n_hvg']} HVGs)")
    assert norm_result["llm_report"] is not None, "Normalization LLM report missing"

    # --- D5: Integration Decision ---
    print("\n>>> DECISION POINT: Batch Integration")
    # Add a fake batch column to test integration decision logic
    adata.obs["sample_id"] = "PA08"  # Single batch -> should skip
    int_result = run_integration_step(adata, batch_col="sample_id", auto=False, use_llm=True, prev_reports=prev_reports)
    adata = int_result["obj"]
    prev_reports["integration"] = int_result["report"]
    print(f"Proposal: integrate={int_result['proposal']['recommendation']['integrate']}, "
          f"method={int_result['proposal']['recommendation'].get('method', 'N/A')}")
    print(f"Report: {int_result['report']['status']}")
    assert int_result["llm_report"] is not None, "Integration LLM report missing"
    assert "[CRITICAL]" in int_result["llm_report"] or "Step 5" in int_result["llm_report"], \
        "Integration LLM report missing critical marker"

    # --- D6: Clustering ---
    print("\n>>> DECISION POINT: Clustering Resolution")
    clust_result = run_clustering_step(adata, auto=False, use_llm=True, prev_reports=prev_reports)
    adata = clust_result["obj"]
    prev_reports["clustering"] = clust_result["report"]
    print(f"Proposal: PCs={clust_result['proposal']['recommendation']['n_pcs']}, "
          f"resolutions={clust_result['proposal']['recommendation']['resolutions']}")
    print(f"Report: {clust_result['report']['status']} ({clust_result['report']['n_clusters']} clusters)")
    assert clust_result["llm_report"] is not None, "Clustering LLM report missing"

    # --- D7: Markers ---
    print("\n>>> STEP: Marker Detection")
    marker_result = run_marker_step(adata, auto=False, use_llm=True, prev_reports=prev_reports)
    adata = marker_result["obj"]
    prev_reports["markers"] = marker_result["report"]
    print(f"Proposal: test={marker_result['proposal']['recommendation']['method']}")
    print(f"Report: {marker_result['report']['status']} ({marker_result['report']['n_markers']} markers)")
    assert marker_result["llm_report"] is not None, "Markers LLM report missing"

    # --- D8: Annotation ---
    print("\n>>> DECISION POINT: Cell Type Annotation")
    annot_result = run_annotation_step(adata, tissue="Pancreas", auto=False, use_llm=True, prev_reports=prev_reports)
    adata = annot_result["obj"]
    prev_reports["annotation"] = annot_result["report"]
    print(f"Proposal: {annot_result['proposal']['recommendation']['method']}")
    print(f"Report: {annot_result['report']['status']} ({annot_result['report']['pct_assigned']}% assigned)")
    assert annot_result["llm_report"] is not None, "Annotation LLM report missing"
    assert "[CRITICAL]" in annot_result["llm_report"] or "Step 8" in annot_result["llm_report"], \
        "Annotation LLM report missing critical marker"

    # --- Cross-step context verification ---
    print("\n>>> Cross-step context check")
    # The last LLM report (annotation) should reference previous steps
    last_report = annot_result["llm_report"]
    assert "qc" in last_report.lower() or "doublet" in last_report.lower(), \
        "Annotation LLM report missing cross-step references"

    print(f"\n{'='*60}")
    print("TEST 3: PASSED")
    print("All decision points generated valid proposals + LLM diagnostic cards")
    print(f"{'='*60}\n")

    return adata, prev_reports


if __name__ == "__main__":
    test_decision_points()
