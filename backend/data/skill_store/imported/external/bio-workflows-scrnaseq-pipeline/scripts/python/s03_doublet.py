"""Step 3: Doublet Detection — Single-Cell RNA-seq Pipeline (Python)

Reference: scanpy 1.10+ (sc.pp.scrublet)

Input State:  [Filtered]
Output State: [Clean]

Expected doublet rate: ~2-10% for 10X data.
If >15%, check for sample aggregation artifacts.
"""

import scanpy as sc

from llm_report import generate_llm_report


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Estimate expected doublet rate
# ---------------------------------------------------------------------------

def propose_doublet_params(adata: sc.AnnData) -> dict:
    """Propose doublet detection parameters based on cell count."""
    n_cells = adata.n_obs

    # 10X expected doublet rate: ~0.8% per 1,000 cells
    expected_rate = min(0.15, 0.008 * (n_cells / 1000))

    return {
        "params": {
            "n_cells": n_cells,
            "expected_doublet_rate": round(expected_rate * 100, 1),
        },
        "diagnostics": {
            "n_cells": n_cells,
            "note": (
                "Large dataset (>20k cells). Consider running per-sample if multi-sample."
                if n_cells > 20000
                else "Standard size. Single-pass doublet detection is appropriate."
            ),
        },
        "justification": (
            f"Expected doublet rate ~{expected_rate * 100:.1f}% for {n_cells} cells "
            "(10X approximation). Scrublet will adaptively estimate."
        ),
    }


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

def evaluate_doublet_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    """Evaluate doublet proposal before execution.

    Guardrails:
      - Expected doublet rate > 20% → CAUTION (possible sample aggregation)
      - n_cells > 50000 → CAUTION (consider per-sample detection)
    """
    expected_rate_pct = proposal["params"]["expected_doublet_rate"]
    n_cells = proposal["params"]["n_cells"]

    if expected_rate_pct > 20:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": (
                f"Expected doublet rate {expected_rate_pct:.1f}% is very high (>20%). "
                "Possible sample aggregation or barcoding issue. Consider per-sample detection."
            ),
        }

    if n_cells > 50000:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": f"Large dataset ({n_cells} cells). Consider per-sample doublet detection.",
        }

    return {"verdict": "PROCEED", "adjusted": False}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — Run Scrublet
# ---------------------------------------------------------------------------

def execute_doublet_detection(adata: sc.AnnData, sample_col: str = None) -> sc.AnnData:
    """Run Scrublet and add labels to AnnData.

    Parameters
    ----------
    adata : AnnData [Filtered]
    sample_col : Column name for sample ID. If provided, runs per-sample.

    Returns
    -------
    AnnData with 'predicted_doublet' and 'doublet_score' in obs
    """
    if sample_col is not None and sample_col in adata.obs.columns:
        # Run per-sample and merge results
        adata.obs["predicted_doublet"] = False
        adata.obs["doublet_score"] = 0.0
        for sample in adata.obs[sample_col].unique():
            mask = adata.obs[sample_col] == sample
            adata_sub = adata[mask].copy()
            sc.pp.scrublet(adata_sub)
            adata.obs.loc[mask, "predicted_doublet"] = adata_sub.obs["predicted_doublet"].values
            adata.obs.loc[mask, "doublet_score"] = adata_sub.obs["doublet_score"].values
    else:
        sc.pp.scrublet(adata)
    return adata


def remove_doublets(adata: sc.AnnData) -> sc.AnnData:
    """Remove predicted doublets and tag state.

    Parameters
    ----------
    adata : AnnData with predicted_doublet column

    Returns
    -------
    AnnData [Clean]
    """
    n_before = adata.n_obs
    adata_clean = adata[~adata.obs["predicted_doublet"]].copy()
    n_after = adata_clean.n_obs

    adata_clean.uns["pipeline_state"] = "Clean"
    adata_clean.uns["n_doublets_removed"] = n_before - n_after

    print(f"Removed {n_before - n_after} doublets ({(n_before - n_after) / n_before * 100:.1f}%)")
    print(f"Cells after doublet removal: {n_after}")

    return adata_clean


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

def report_doublets(adata_before: sc.AnnData, adata_after: sc.AnnData) -> dict:
    """Generate doublet detection report."""
    n_before = adata_before.n_obs
    n_doublets = adata_before.obs["predicted_doublet"].sum()
    doublet_rate = n_doublets / n_before * 100

    if doublet_rate > 15:
        status = "WARNING"
    elif doublet_rate > 10:
        status = "CAUTION"
    elif doublet_rate < 1:
        status = "CAUTION"
    else:
        status = "PASS"

    return {
        "step": "Doublet Detection",
        "status": status,
        "cells_before": n_before,
        "doublets_detected": int(n_doublets),
        "doublet_rate": round(doublet_rate, 1),
        "cells_after": adata_after.n_obs,
        "recommendation": (
            "Doublet rate >15%. Possible sample aggregation. Consider per-sample detection or re-check data loading."
            if status == "WARNING"
            else (
                "Doublet rate elevated. Acceptable for high-density runs; review if unexpected."
                if status == "CAUTION" and doublet_rate > 10
                else (
                    "Doublet rate unusually low. May indicate over-filtering in QC step."
                    if status == "CAUTION"
                    else "Doublet rate within expected range. Proceed to Normalization."
                )
            )
        ),
        "next_step": "Step 4: Normalization + HVG",
    }


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

def run_doublet_step(adata: sc.AnnData, sample_col: str = None, auto: bool = False,
                     use_llm: bool = True,
                     prev_reports: dict = None) -> dict:
    """Complete doublet detection step.

    Parameters
    ----------
    adata : AnnData [Filtered]
    sample_col : Sample column for per-sample detection
    auto : Skip proposal display
    use_llm : If True, generate LLM diagnostic card.

    Returns
    -------
    dict with keys: obj, report, proposal, llm_report
    """
    expected_states = {"Filtered", "Raw"}
    current_state = adata.uns.get("pipeline_state")
    if current_state not in expected_states:
        import warnings
        warnings.warn(
            f"Expected input state 'Filtered' for doublet step, got '{current_state}'. "
            "Proceeding anyway, but results may be unexpected."
        )

    proposal = propose_doublet_params(adata)

    # Evaluate phase: guardrail on expected doublet rate
    evaluation = evaluate_doublet_proposal(proposal, adata)
    if evaluation["verdict"] == "CAUTION":
        print(f"CAUTION: {evaluation['reason']}")

    if not auto:
        print("\n=== Doublet Detection Proposal ===")
        print(f"Cells: {proposal['params']['n_cells']}")
        print(f"Expected doublet rate: ~{proposal['params']['expected_doublet_rate']}%")
        print(f"Note: {proposal['diagnostics']['note']}")

    adata = execute_doublet_detection(adata, sample_col=sample_col)
    adata_clean = remove_doublets(adata)
    report = report_doublets(adata, adata_clean)

    # LLM enhancement
    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("doublet", adata, proposal, report, prev_reports)
        if not auto:
            print(llm_report)

    return {"obj": adata_clean, "report": report, "proposal": proposal, "llm_report": llm_report}
