"""Test Case 1: Single-sample full pipeline (Python, auto mode).

Validates end-to-end correctness on PA08_sc.h5ad.
Expected: All 8 steps complete, output files generated, PASS statuses.
"""

import sys
from pathlib import Path

# Add pipeline scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "python"))

from run_pipeline import run_pipeline


def test_single_sample_auto():
    """Run full pipeline on PA08 in auto mode."""
    data_path = Path(__file__).parent / "PA08_sc_renamed.h5ad"
    out_dir = Path(__file__).parent / "output_test_single"

    assert data_path.exists(), f"Test data not found: {data_path}. Run prepare_test_data.py first."

    print(f"\n{'='*60}")
    print("TEST 1: Single-sample full pipeline (auto mode)")
    print(f"Input: {data_path}")
    print(f"Output: {out_dir}")
    print(f"{'='*60}\n")

    result = run_pipeline(
        data_path=str(data_path),
        output_dir=str(out_dir),
        mode="auto",
        batch_col="patients",
        tissue="Pancreas",
        use_llm=True,
    )

    adata = result["obj"]
    reports = result["reports"]
    llm_reports = result["llm_reports"]

    # --- Assertions ---

    # 1. Final object state
    assert adata.n_obs > 0, "Final object has no cells"
    assert adata.n_vars > 0, "Final object has no genes"
    assert adata.uns.get("pipeline_state") == "Annotated", f"Expected state 'Annotated', got {adata.uns.get('pipeline_state')}"

    # 2. Step reports exist
    expected_steps = ["qc", "doublet", "normalization", "integration", "clustering", "markers", "annotation"]
    for step in expected_steps:
        assert step in reports, f"Missing report for step: {step}"
        assert "status" in reports[step], f"Missing 'status' in {step} report"
        print(f"  {step}: {reports[step]['status']}")

    # 3. QC step specifics
    qc = reports["qc"]
    assert qc["cells_before"] == 25524, f"Expected 25524 cells before QC, got {qc['cells_before']}"
    assert qc["pct_removed"] < 50, f"QC removed too many cells: {qc['pct_removed']}%"

    # 4. Doublet step
    dbl = reports["doublet"]
    assert 1 <= dbl["doublet_rate"] <= 15, f"Doublet rate out of expected range: {dbl['doublet_rate']}%"

    # 5. Integration step (single sample -> should skip)
    integ = reports["integration"]
    assert integ["status"] == "SKIPPED", f"Single-sample should skip integration, got: {integ['status']}"

    # 6. Clustering
    clust = reports["clustering"]
    assert 5 <= clust["n_clusters"] <= 50, f"Cluster count unreasonable: {clust['n_clusters']}"

    # 7. Markers
    markers = reports["markers"]
    assert markers["n_markers"] > 0, "No markers found"

    # 8. Annotation
    annot = reports["annotation"]
    assert annot["pct_assigned"] > 50, f"Low assignment rate: {annot['pct_assigned']}%"
    assert "cell_type" in adata.obs.columns, "Missing cell_type column"

    # 9. LLM reports
    assert len(llm_reports) > 0, "No LLM reports generated"
    llm_dir = out_dir / "llm_reports"
    assert llm_dir.exists(), f"LLM reports directory not created: {llm_dir}"
    assert (llm_dir / "combined_report.md").exists(), "Combined LLM report not saved"

    # 10. Output files
    assert (out_dir / "adata_annotated.h5ad").exists(), "Final h5ad not saved"
    assert (out_dir / "all_markers.csv").exists(), "Markers CSV not saved"
    assert (out_dir / "plots" / "umap_annotated.pdf").exists(), "UMAP plot not saved"

    print(f"\n{'='*60}")
    print("TEST 1: PASSED")
    print(f"Final cells: {adata.n_obs}")
    print(f"Clusters: {clust['n_clusters']}")
    print(f"Cell types: {annot['n_cell_types']}")
    print(f"{'='*60}\n")

    return result


if __name__ == "__main__":
    test_single_sample_auto()
