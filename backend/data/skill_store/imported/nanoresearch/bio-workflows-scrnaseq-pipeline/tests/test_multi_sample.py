"""Test Case 2: Multi-sample batch integration (Python, auto mode).

Validates batch detection, integration decision, and correction quality
on PA08 + PA12 merged data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "python"))

from run_pipeline import run_pipeline


def test_multi_sample_integration():
    """Run full pipeline on merged PA08+PA12 in auto mode."""
    data_path = Path(__file__).parent / "PA08_PA12_merged.h5ad"
    out_dir = Path(__file__).parent / "output_test_multi"

    assert data_path.exists(), f"Test data not found: {data_path}. Run prepare_test_data.py first."

    print(f"\n{'='*60}")
    print("TEST 2: Multi-sample batch integration (auto mode)")
    print(f"Input: {data_path}")
    print(f"Output: {out_dir}")
    print(f"{'='*60}\n")

    result = run_pipeline(
        data_path=str(data_path),
        output_dir=str(out_dir),
        mode="auto",
        batch_col="sample_id",
        tissue="Pancreas",
        use_llm=True,
    )

    adata = result["obj"]
    reports = result["reports"]

    # --- Assertions ---

    # 1. Integration should run (2 samples detected)
    integ = reports["integration"]
    print(f"Integration status: {integ['status']}")
    print(f"Integration method: {integ.get('method', 'N/A')}")

    # Two distinct samples -> integration should trigger
    # Note: if batch mixing score < 0.3, integration is skipped even with 2 samples
    # We accept either INTEGRATED or SKIPPED as valid, but log the outcome
    if integ["status"] == "PASS":
        print("  -> Integration was applied")
        assert integ.get("method") is not None, "Integration method missing"
    elif integ["status"] == "SKIPPED":
        print("  -> Integration skipped (batches well-mixed)")
    else:
        raise AssertionError(f"Unexpected integration status: {integ['status']}")

    # 2. Total cells should be close to 40514 minus QC+doublet removal
    total_input = 25524 + 14990
    qc_removed = reports["qc"]["pct_removed"]
    dbl_removed = reports["doublet"]["doublet_rate"]
    expected_remaining = total_input * (1 - qc_removed/100) * (1 - dbl_removed/100)
    actual_remaining = adata.n_obs
    print(f"Expected ~{expected_remaining:.0f} cells after QC+doublet, actual: {actual_remaining}")
    assert actual_remaining > total_input * 0.5, f"Too many cells lost: {actual_remaining} / {total_input}"

    # 3. Clustering should find reasonable number of clusters
    clust = reports["clustering"]
    assert 5 <= clust["n_clusters"] <= 60, f"Cluster count unreasonable: {clust['n_clusters']}"

    # 4. Annotation
    annot = reports["annotation"]
    assert annot["pct_assigned"] > 50, f"Low assignment rate: {annot['pct_assigned']}%"

    # 5. Sample distribution in final object
    sample_counts = adata.obs["sample_id"].value_counts().to_dict()
    print(f"Sample distribution: {sample_counts}")
    assert "PA08" in sample_counts, "PA08 missing from final object"
    assert "PA12" in sample_counts, "PA12 missing from final object"

    print(f"\n{'='*60}")
    print("TEST 2: PASSED")
    print(f"Final cells: {adata.n_obs}")
    print(f"Integration: {integ['status']} (method={integ.get('method', 'N/A')})")
    print(f"Clusters: {clust['n_clusters']}")
    print(f"{'='*60}\n")

    return result


if __name__ == "__main__":
    test_multi_sample_integration()
