"""Test Case 4: LLM enhancement toggle (Python, auto mode).

Compares pipeline runs with use_llm=True vs use_llm=False.
Validates that diagnostic cards are only generated when enabled.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "python"))

from run_pipeline import run_pipeline


def test_llm_on():
    """Run with LLM enabled."""
    data_path = Path(__file__).parent / "PA08_sc_renamed.h5ad"
    out_dir = Path(__file__).parent / "output_test_llm_on"

    result = run_pipeline(
        data_path=str(data_path),
        output_dir=str(out_dir),
        mode="auto",
        use_llm=True,
    )

    # LLM reports should exist
    llm_dir = out_dir / "llm_reports"
    assert llm_dir.exists(), "LLM reports directory missing with use_llm=True"
    assert (llm_dir / "combined_report.md").exists(), "Combined report missing"

    # Individual step reports
    expected_files = ["qc_diagnostic.md", "doublet_diagnostic.md", "normalization_diagnostic.md",
                      "integration_diagnostic.md", "cluster_diagnostic.md", "markers_diagnostic.md",
                      "annotation_diagnostic.md"]
    for f in expected_files:
        assert (llm_dir / f).exists(), f"Missing LLM report: {f}"

    # Result dict should contain llm_reports
    assert "llm_reports" in result, "Result missing llm_reports key"
    assert len(result["llm_reports"]) > 0, "llm_reports is empty"

    print(f"LLM ON:  {len(result['llm_reports'])} diagnostic cards saved to {llm_dir}")
    return result


def test_llm_off():
    """Run with LLM disabled."""
    data_path = Path(__file__).parent / "PA08_sc_renamed.h5ad"
    out_dir = Path(__file__).parent / "output_test_llm_off"

    result = run_pipeline(
        data_path=str(data_path),
        output_dir=str(out_dir),
        mode="auto",
        use_llm=False,
    )

    # LLM reports should NOT exist
    llm_dir = out_dir / "llm_reports"
    assert not llm_dir.exists(), "LLM reports directory should not exist with use_llm=False"

    # Result dict should still have llm_reports key but empty
    assert "llm_reports" in result, "Result missing llm_reports key"
    # All values should be None
    non_none = [k for k, v in result["llm_reports"].items() if v is not None]
    assert len(non_none) == 0, f"Unexpected LLM reports generated: {non_none}"

    print(f"LLM OFF: No diagnostic cards generated (as expected)")
    return result


def test_llm_toggle():
    print(f"\n{'='*60}")
    print("TEST 4: LLM enhancement toggle")
    print(f"{'='*60}\n")

    result_on = test_llm_on()
    result_off = test_llm_off()

    # Both should produce same final object shape
    assert result_on["obj"].n_obs == result_off["obj"].n_obs, \
        "LLM toggle affected cell count (should be deterministic)"
    assert result_on["obj"].n_vars == result_off["obj"].n_vars, \
        "LLM toggle affected gene count (should be deterministic)"

    print(f"\n{'='*60}")
    print("TEST 4: PASSED")
    print("use_llm=True: diagnostic cards generated")
    print("use_llm=False: no diagnostic cards, same deterministic output")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    test_llm_toggle()
