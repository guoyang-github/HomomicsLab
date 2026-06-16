"""Step 2: QC Decision — Propose / Execute / Report (Python)

Reference: scanpy 1.10+

Input State:  [Raw]
Output State: [Filtered]

Philosophy: Diagnose first, propose thresholds with justification,
            then execute after user confirmation (or auto-run).
"""

import numpy as np
import scanpy as sc

from llm_report import generate_llm_report


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Diagnose and recommend thresholds
# ---------------------------------------------------------------------------

def propose_qc_thresholds(adata: sc.AnnData) -> dict:
    """Analyze QC distributions and propose data-driven thresholds.

    Parameters
    ----------
    adata : AnnData [Raw]

    Returns
    -------
    dict with proposed thresholds and diagnostic summary
    """
    # Compute QC metrics if not present
    if "pct_counts_mt" not in adata.obs.columns:
        adata.var["mt"] = adata.var_names.str.startswith("MT-")
        sc.pp.calculate_qc_metrics(
            adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True
        )

    n_genes = adata.obs["n_genes_by_counts"]
    n_counts = adata.obs["total_counts"]
    mt = adata.obs["pct_counts_mt"]

    n_genes_q99 = np.percentile(n_genes, 99)
    n_genes_q01 = np.percentile(n_genes, 1)
    mt_median = np.median(mt)

    # Dynamic MT% threshold
    if mt_median > 10:
        mt_threshold = min(25, mt_median + 2 * np.std(mt))
        mt_reason = (
            f"MT% median = {mt_median:.1f}% (high, suggesting tissue dissociation stress). "
            "Conservative threshold recommended."
        )
    elif mt_median > 5:
        mt_threshold = 15.0
        mt_reason = f"MT% median = {mt_median:.1f}% (moderate). Standard threshold applies."
    else:
        mt_threshold = 10.0
        mt_reason = (
            f"MT% median = {mt_median:.1f}% (low, likely nuclei or clean sample). "
            "Stringent threshold OK."
        )

    n_genes_max = max(5000, n_genes_q99 * 1.2)
    n_genes_min = 200
    n_counts_min = max(500, int(np.percentile(n_counts, 1)))

    return {
        "thresholds": {
            "n_genes_by_counts_min": int(n_genes_min),
            "n_genes_by_counts_max": int(n_genes_max),
            "total_counts_min": int(n_counts_min),
            "pct_counts_mt_max": round(float(mt_threshold), 1),
        },
        "diagnostics": {
            "n_cells": adata.n_obs,
            "n_genes_median": int(np.median(n_genes)),
            "n_genes_q99": int(n_genes_q99),
            "n_counts_median": int(np.median(n_counts)),
            "mt_median": round(float(mt_median), 2),
            "mt_q95": round(float(np.percentile(mt, 95)), 2),
        },
        "justification": {
            "n_genes": (
                f"Range {int(n_genes_min)}-{int(n_genes_max)} captures >95% of cells "
                "while removing low-quality / doublet outliers."
            ),
            "n_counts": f"Minimum {int(n_counts_min)} total counts ensures sufficient sequencing depth.",
            "mt": mt_reason,
        },
    }


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

def evaluate_qc_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    """Evaluate QC proposal before execution. Auto-relax if too aggressive.

    Guardrails:
      - Removal > 80% → BLOCK + auto-relax thresholds
      - Removal > 50% → CAUTION
    """
    t = proposal["thresholds"]
    n_before = adata.n_obs

    required_cols = ["n_genes_by_counts", "total_counts", "pct_counts_mt"]
    missing = [c for c in required_cols if c not in adata.obs.columns]
    if missing:
        return {
            "verdict": "PROCEED",
            "adjusted": False,
            "reason": f"Missing QC columns: {missing}. Skipping guardrail.",
        }

    mask = (
        (adata.obs["n_genes_by_counts"] > t["n_genes_by_counts_min"])
        & (adata.obs["n_genes_by_counts"] < t["n_genes_by_counts_max"])
        & (adata.obs["total_counts"] > t["total_counts_min"])
        & (adata.obs["pct_counts_mt"] < t["pct_counts_mt_max"])
    )
    n_after = mask.sum()
    pct_removed = (1 - n_after / n_before) * 100

    if pct_removed > 80:
        adjusted_t = dict(t)
        adjusted_t["n_genes_by_counts_min"] = max(100, int(adjusted_t["n_genes_by_counts_min"] * 0.5))
        adjusted_t["pct_counts_mt_max"] = min(50.0, round(adjusted_t["pct_counts_mt_max"] * 1.5, 1))
        return {
            "verdict": "BLOCK",
            "adjusted": True,
            "reason": (
                f"Proposed thresholds would remove {pct_removed:.1f}% of cells (>80%). "
                f"Auto-relaxing: n_genes_min={adjusted_t['n_genes_by_counts_min']}, "
                f"mt_max={adjusted_t['pct_counts_mt_max']}%"
            ),
            "adjusted_thresholds": adjusted_t,
        }
    elif pct_removed > 50:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": f"Proposed thresholds would remove {pct_removed:.1f}% of cells (>50%). Review carefully.",
        }

    return {"verdict": "PROCEED", "adjusted": False}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — Apply thresholds
# ---------------------------------------------------------------------------

def execute_qc_filter(adata: sc.AnnData, thresholds: dict) -> sc.AnnData:
    """Apply QC thresholds and return filtered object.

    Parameters
    ----------
    adata : AnnData [Raw]
    thresholds : dict from propose_qc_thresholds()

    Returns
    -------
    AnnData [Filtered]
    """
    t = thresholds["thresholds"]

    mask = (
        (adata.obs["n_genes_by_counts"] > t["n_genes_by_counts_min"])
        & (adata.obs["n_genes_by_counts"] < t["n_genes_by_counts_max"])
        & (adata.obs["total_counts"] > t["total_counts_min"])
        & (adata.obs["pct_counts_mt"] < t["pct_counts_mt_max"])
    )

    adata_filtered = adata[mask].copy()
    adata_filtered.uns["pipeline_state"] = "Filtered"
    adata_filtered.uns["qc_thresholds"] = t

    return adata_filtered


# ---------------------------------------------------------------------------
# PHASE 3: REPORT — Summarize results
# ---------------------------------------------------------------------------

def report_qc(adata_before: sc.AnnData, adata_after: sc.AnnData, thresholds: dict) -> dict:
    """Generate QC report with pass/fail assessment."""
    n_before = adata_before.n_obs
    n_after = adata_after.n_obs
    pct_removed = (1 - n_after / n_before) * 100

    if pct_removed > 60:
        status = "WARNING"
    elif pct_removed > 30:
        status = "CAUTION"
    else:
        status = "PASS"

    return {
        "step": "QC Filtering",
        "status": status,
        "cells_before": n_before,
        "cells_after": n_after,
        "pct_removed": round(pct_removed, 1),
        "thresholds_applied": thresholds["thresholds"],
        "recommendation": (
            ">60% cells removed. Consider relaxing thresholds, especially n_genes_by_counts_min or pct_counts_mt_max."
            if status == "WARNING"
            else (
                "30-60% cells removed. Review QC plots; may be acceptable for low-quality samples."
                if status == "CAUTION"
                else "Cell retention looks good. Proceed to Doublet Detection."
            )
        ),
        "next_step": "Step 3: Doublet Detection",
    }


# ---------------------------------------------------------------------------
# Convenience: full step wrapper
# ---------------------------------------------------------------------------

def run_qc_step(adata: sc.AnnData, thresholds: dict = None,
                auto: bool = False, use_llm: bool = True,
                prev_reports: dict = None) -> dict:
    """Run complete QC step: propose, optionally confirm, execute, report.

    Parameters
    ----------
    adata : AnnData [Raw]
    thresholds : If None, auto-propose. If provided, use directly.
    auto : If True, skip proposal display.
    use_llm : If True, generate LLM diagnostic card.

    Returns
    -------
    dict with keys: obj, report, proposal, llm_report
    """
    expected_states = {"Raw", None}
    current_state = adata.uns.get("pipeline_state")
    if current_state not in expected_states:
        import warnings
        warnings.warn(
            f"Expected input state 'Raw' for QC step, got '{current_state}'. "
            "Proceeding anyway, but results may be unexpected."
        )

    proposal = propose_qc_thresholds(adata)

    # Evaluate phase: guardrail on removal percentage
    evaluation = evaluate_qc_proposal(proposal, adata)
    if evaluation["adjusted"]:
        print(f"GUARDRAIL: {evaluation['reason']}")
        proposal["thresholds"] = evaluation["adjusted_thresholds"]
        # Re-evaluate after adjustment
        evaluation2 = evaluate_qc_proposal(proposal, adata)
        if evaluation2["verdict"] == "BLOCK":
            raise RuntimeError(
                "Even after auto-relaxation, QC thresholds would remove >80% of cells. "
                "Manual intervention required."
            )
    elif evaluation["verdict"] == "CAUTION":
        print(f"CAUTION: {evaluation['reason']}")

    if thresholds is None:
        thresholds = proposal

    adata_filtered = execute_qc_filter(adata, thresholds)
    qc_report = report_qc(adata, adata_filtered, thresholds)

    if not auto:
        print("\n=== QC Proposal ===")
        print(f"n_genes_by_counts: {thresholds['thresholds']['n_genes_by_counts_min']} - {thresholds['thresholds']['n_genes_by_counts_max']}")
        print(f"total_counts_min: {thresholds['thresholds']['total_counts_min']}")
        print(f"pct_counts_mt_max: {thresholds['thresholds']['pct_counts_mt_max']}%")
        print(f"\nJustification: {thresholds['justification']['mt']}")
        print(f"\nEstimated removal: ~{qc_report['pct_removed']}% cells")

    # LLM enhancement
    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("qc", adata, proposal, qc_report, prev_reports)
        if not auto:
            print(llm_report)

    return {"obj": adata_filtered, "report": qc_report, "proposal": proposal, "llm_report": llm_report}
