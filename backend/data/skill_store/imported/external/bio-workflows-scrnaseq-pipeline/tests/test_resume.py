"""Test Case 5: Resume pipeline from intermediate state (Python, auto mode).

Validates that resume_pipeline() correctly continues from a saved intermediate object.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "python"))

import anndata as ad
from run_pipeline import resume_pipeline
from s04_normalize import run_normalization_step


def test_resume_from_normalization():
    """Load PA08, run through normalization, save, then resume from step 5."""
    data_path = Path(__file__).parent / "PA08_sc_renamed.h5ad"
    assert data_path.exists(), f"Test data not found: {data_path}"

    print(f"\n{'='*60}")
    print("TEST 5: Resume from intermediate state")
    print(f"{'='*60}\n")

    # Phase 1: Run steps 1-4
    print("Phase 1: Running steps 1-4 (Load -> QC -> Doublet -> Normalize)")
    adata = ad.read_h5ad(data_path)

    from s02_qc_decision import run_qc_step
    from s03_doublet import run_doublet_step

    prev_reports = {}
    qc = run_qc_step(adata, auto=True, use_llm=False, prev_reports=prev_reports)
    adata = qc["obj"]
    prev_reports["qc"] = qc["report"]

    dbl = run_doublet_step(adata, auto=True, use_llm=False, prev_reports=prev_reports)
    adata = dbl["obj"]
    prev_reports["doublet"] = dbl["report"]

    norm = run_normalization_step(adata, auto=True, use_llm=False, prev_reports=prev_reports)
    adata = norm["obj"]
    prev_reports["normalization"] = norm["report"]

    # Save intermediate state
    intermediate_path = Path(__file__).parent / "PA08_normalized.h5ad"
    adata.write(intermediate_path)
    print(f"Saved intermediate state: {intermediate_path} (state={adata.uns.get('pipeline_state')})")

    # Phase 2: Resume from step 5
    print("\nPhase 2: Resuming from step 5 (Integration -> Clustering -> Markers -> Annotation)")
    out_dir = Path(__file__).parent / "output_test_resume"

    # Reload from saved state
    adata_resumed = ad.read_h5ad(intermediate_path)

    result = resume_pipeline(
        adata_resumed,
        from_step=5,
        output_dir=str(out_dir),
        mode="auto",
        use_llm=True,
        prev_reports=prev_reports,
        batch_col="patients",
        tissue="Pancreas",
    )

    # Assertions
    assert result["obj"].uns.get("pipeline_state") == "Annotated", \
        f"Expected final state 'Annotated', got {result['obj'].uns.get('pipeline_state')}"

    expected_steps = ["integration", "clustering", "markers", "annotation"]
    for step in expected_steps:
        assert step in result["reports"], f"Missing report for resumed step: {step}"

    # LLM reports should be generated for resumed steps
    assert len(result["llm_reports"]) > 0, "No LLM reports for resumed steps"
    assert (out_dir / "llm_reports" / "combined_report.md").exists(), \
        "Combined LLM report not saved for resumed pipeline"

    print(f"\n{'='*60}")
    print("TEST 5: PASSED")
    print(f"Resumed steps: {list(result['reports'].keys())}")
    print(f"Final cells: {result['obj'].n_obs}")
    print(f"Final state: {result['obj'].uns.get('pipeline_state')}")
    print(f"{'='*60}\n")

    return result


if __name__ == "__main__":
    test_resume_from_normalization()
