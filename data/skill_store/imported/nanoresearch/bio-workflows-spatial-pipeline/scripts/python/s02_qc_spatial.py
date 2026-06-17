"""Step 2: QC Decision — Spatial Transcriptomics Pipeline (Python)

Reference: scanpy 1.10+, squidpy 1.3+

Input State:  [Raw]
Output State: [Filtered]
"""

import numpy as np
import scanpy as sc
import squidpy as sq

from llm_report import generate_llm_report


def propose_qc_thresholds(adata: sc.AnnData) -> dict:
    """Analyze QC distributions and propose data-driven thresholds."""
    if "pct_counts_mt" not in adata.obs.columns:
        adata.var["mt"] = adata.var_names.str.startswith("MT-")
        sc.pp.calculate_qc_metrics(
            adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True
        )

    n_genes = adata.obs["n_genes_by_counts"]
    n_counts = adata.obs["total_counts"]
    mt = adata.obs["pct_counts_mt"]
    mt_median = np.median(mt)

    # Dynamic MT% threshold
    if mt_median > 10:
        mt_threshold = min(30, mt_median + 2 * np.std(mt))
        mt_reason = (
            f"MT% median = {mt_median:.1f}% (high, suggesting FFPE or tissue stress). "
            "Conservative threshold recommended."
        )
    elif mt_median > 5:
        mt_threshold = 20.0
        mt_reason = f"MT% median = {mt_median:.1f}% (moderate). Standard threshold applies."
    else:
        mt_threshold = 15.0
        mt_reason = f"MT% median = {mt_median:.1f}% (low, likely fresh frozen). Stringent threshold OK."

    # Spatial-specific: estimate tissue coverage from spots with counts > 0
    tissue_coverage = (n_counts > 0).sum() / adata.n_obs * 100

    return {
        "thresholds": {
            "min_counts": int(max(500, np.percentile(n_counts, 1))),
            "min_genes": 200,
            "max_mt": round(float(mt_threshold), 1),
        },
        "diagnostics": {
            "n_spots": adata.n_obs,
            "n_genes_median": int(np.median(n_genes)),
            "n_counts_median": int(np.median(n_counts)),
            "mt_median": round(float(mt_median), 2),
            "tissue_coverage_pct": round(float(tissue_coverage), 1),
        },
        "justification": {
            "counts": f"Minimum {int(max(500, np.percentile(n_counts, 1)))} total counts ensures sufficient depth.",
            "genes": "Minimum 200 genes per spot captures tissue diversity.",
            "mt": mt_reason,
        },
    }


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

def evaluate_qc_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    """Evaluate spatial QC proposal before execution.

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
        (adata.obs["n_genes_by_counts"] >= t["min_genes"])
        & (adata.obs["total_counts"] >= t["min_counts"])
        & (adata.obs["pct_counts_mt"] < t["max_mt"])
    )
    n_after = mask.sum()
    pct_removed = (1 - n_after / n_before) * 100

    if pct_removed > 80:
        adjusted_t = dict(t)
        adjusted_t["min_genes"] = max(50, int(adjusted_t["min_genes"] * 0.5))
        adjusted_t["max_mt"] = min(50.0, round(adjusted_t["max_mt"] * 1.5, 1))
        return {
            "verdict": "BLOCK",
            "adjusted": True,
            "reason": (
                f"Proposed thresholds would remove {pct_removed:.1f}% of spots (>80%). "
                f"Auto-relaxing: min_genes={adjusted_t['min_genes']}, max_mt={adjusted_t['max_mt']}%"
            ),
            "adjusted_thresholds": adjusted_t,
        }
    elif pct_removed > 50:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": f"Proposed thresholds would remove {pct_removed:.1f}% of spots (>50%). Review carefully.",
        }

    return {"verdict": "PROCEED", "adjusted": False}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — Apply thresholds
# ---------------------------------------------------------------------------

def execute_qc_filter(adata: sc.AnnData, thresholds: dict) -> sc.AnnData:
    """Apply QC thresholds and return filtered object."""
    t = thresholds["thresholds"]

    mask = (
        (adata.obs["n_genes_by_counts"] >= t["min_genes"])
        & (adata.obs["total_counts"] >= t["min_counts"])
        & (adata.obs["pct_counts_mt"] < t["max_mt"])
    )

    adata_filtered = adata[mask].copy()
    adata_filtered.uns["pipeline_state"] = "Filtered"
    adata_filtered.uns["qc_thresholds"] = t

    return adata_filtered


def report_qc(adata_before: sc.AnnData, adata_after: sc.AnnData, thresholds: dict) -> dict:
    """Generate QC report with pass/fail assessment."""
    n_before = adata_before.n_obs
    n_after = adata_after.n_obs
    pct_removed = (1 - n_after / n_before) * 100

    if pct_removed > 50:
        status = "WARNING"
    elif pct_removed > 25:
        status = "CAUTION"
    else:
        status = "PASS"

    return {
        "step": "QC Filtering",
        "status": status,
        "spots_before": n_before,
        "spots_after": n_after,
        "pct_removed": round(pct_removed, 1),
        "thresholds_applied": thresholds["thresholds"],
        "recommendation": (
            ">50% spots removed. Check if tissue-edge spots were over-filtered."
            if status == "WARNING"
            else (
                "25-50% spots removed. Review spatial QC plots for artifacts."
                if status == "CAUTION"
                else "Spot retention looks good. Proceed to Normalization."
            )
        ),
        "next_step": "Step 3: Normalization + HVG",
    }


def run_qc_step(adata: sc.AnnData, thresholds: dict = None,
                auto: bool = False, use_llm: bool = True,
                prev_reports: dict = None) -> dict:
    """Run complete QC step: propose, optionally confirm, execute, report."""
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
        evaluation2 = evaluate_qc_proposal(proposal, adata)
        if evaluation2["verdict"] == "BLOCK":
            raise RuntimeError(
                "Even after auto-relaxation, QC thresholds would remove >80% of spots. "
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
        print(f"min_counts: {thresholds['thresholds']['min_counts']}")
        print(f"min_genes: {thresholds['thresholds']['min_genes']}")
        print(f"max_mt: {thresholds['thresholds']['max_mt']}%")
        print(f"\nJustification: {thresholds['justification']['mt']}")
        print(f"\nEstimated removal: ~{qc_report['pct_removed']}% spots")

    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("qc", adata, proposal, qc_report, prev_reports)
        if not auto:
            print(llm_report)

    return {"obj": adata_filtered, "report": qc_report, "proposal": proposal, "llm_report": llm_report}
