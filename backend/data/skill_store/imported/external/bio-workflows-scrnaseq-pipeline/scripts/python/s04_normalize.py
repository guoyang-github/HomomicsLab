"""Step 4: Normalization + HVG — Single-Cell RNA-seq Pipeline (Python)

Reference: scanpy 1.10+

Input State:  [Clean]
Output State: [Normalized] + [HVG]

Supports:
- Log1p normalization + highly_variable_genes (standard)
- shift-log (sc.experimental.pp.normalize) as alternative
"""

import scanpy as sc

from llm_report import generate_llm_report


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Recommend normalization method
# ---------------------------------------------------------------------------

def propose_normalization(adata: sc.AnnData) -> dict:
    """Propose normalization strategy based on data characteristics."""
    n_cells = adata.n_obs
    method = "Log1p"

    justification = (
        "Log1p normalization is the standard for Scanpy workflows: "
        "(1) fast and scalable, (2) well-tested for downstream clustering and integration."
    )

    if n_cells < 1000:
        justification += " Small dataset (<1k cells); results should be interpreted cautiously."

    return {
        "recommendation": {
            "method": method,
            "target_sum": 1e4,
            "n_hvg": 2000,
        },
        "diagnostics": {
            "n_cells": n_cells,
            "n_genes": adata.n_vars,
        },
        "justification": justification,
        "alternatives": {
            "shift_log": "Use for large datasets (>100k cells) where exact normalization is too slow.",
        },
    }


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

def evaluate_normalization_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    """Evaluate normalization proposal before execution.

    Guardrails:
      - n_hvg < 500 or > 5000 -> BLOCK + clamp
      - n_cells < 100 -> CAUTION (too few for reliable HVG selection)
    """
    n_hvg = proposal["recommendation"]["n_hvg"]

    if n_hvg < 500 or n_hvg > 5000:
        clamped = max(500, min(5000, n_hvg))
        return {
            "verdict": "BLOCK",
            "adjusted": True,
            "reason": f"n_hvg = {n_hvg} outside [500, 5000]. Clamped to {clamped}.",
            "adjusted_params": {"n_hvg": clamped},
        }

    n_cells = proposal["diagnostics"]["n_cells"]
    if n_cells < 100:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": f"Only {n_cells} cells. HVG selection may be unreliable.",
        }

    return {"verdict": "PROCEED", "adjusted": False}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE
# ---------------------------------------------------------------------------

def execute_log1p_normalize(adata: sc.AnnData, target_sum: float = 1e4, n_hvg: int = 2000) -> sc.AnnData:
    """Run Log1p normalization + HVG selection.

    Parameters
    ----------
    adata : AnnData [Clean]
    target_sum : Normalization target sum
    n_hvg : Number of highly variable genes

    Returns
    -------
    AnnData [Normalized] + [HVG]
    """
    # Preserve raw counts if not already stored
    if "counts" not in adata.layers:
        adata.layers["counts"] = adata.X.copy()
    sc.pp.normalize_total(adata, target_sum=target_sum)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=n_hvg)

    adata.uns["pipeline_state"] = "Normalized"
    adata.uns["normalization_method"] = "Log1p"

    n_hvg_selected = adata.var["highly_variable"].sum()
    print(f"Log1p normalization complete. HVGs selected: {n_hvg_selected}")

    return adata


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

def report_normalization(adata: sc.AnnData) -> dict:
    """Report normalization results."""
    method = adata.uns.get("normalization_method", "Unknown")
    n_hvg = int(adata.var["highly_variable"].sum())

    status = "PASS" if 1500 <= n_hvg <= 3000 else "CAUTION"

    return {
        "step": "Normalization + HVG",
        "status": status,
        "method": method,
        "n_hvg": n_hvg,
        "recommendation": (
            "HVG count within optimal range (1500-3000). Proceed to integration check."
            if status == "PASS"
            else f"HVG count = {n_hvg}. Consider adjusting n_top_genes if downstream clustering is poor."
        ),
        "next_step": "Step 5: Integration Decision (check for batch effects)",
    }


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

def run_normalization_step(adata: sc.AnnData, method: str = None, auto: bool = False,
                           use_llm: bool = True, prev_reports: dict = None,
                           **kwargs) -> dict:
    """Complete normalization step.

    Parameters
    ----------
    adata : AnnData [Clean]
    method : "Log1p" or None (auto-propose)
    auto : Skip proposal display
    use_llm : If True, generate LLM diagnostic card.
    prev_reports : Previous step reports for cross-step analysis.
    **kwargs : Passed to normalization function

    Returns
    -------
    dict with keys: obj, report, proposal, llm_report
    """
    expected_states = {"Clean", "Filtered"}
    current_state = adata.uns.get("pipeline_state")
    if current_state not in expected_states:
        import warnings
        warnings.warn(
            f"Expected input state 'Clean' for normalization step, got '{current_state}'. "
            "Proceeding anyway, but results may be unexpected."
        )

    proposal = propose_normalization(adata)

    # Evaluate phase: guardrail on HVG target
    evaluation = evaluate_normalization_proposal(proposal, adata)
    if evaluation["adjusted"]:
        print(f"GUARDRAIL: {evaluation['reason']}")
        proposal["recommendation"]["n_hvg"] = evaluation["adjusted_params"]["n_hvg"]
    elif evaluation["verdict"] == "CAUTION":
        print(f"CAUTION: {evaluation['reason']}")

    if method is None:
        method = proposal["recommendation"]["method"]

    if not auto:
        print("\n=== Normalization Proposal ===")
        print(f"Recommended: {method}")
        print(f"Justification: {proposal['justification']}")

    if method == "Log1p":
        adata = execute_log1p_normalize(
            adata,
            target_sum=proposal["recommendation"]["target_sum"],
            n_hvg=proposal["recommendation"]["n_hvg"],
            **kwargs
        )
    else:
        raise ValueError(f"Unknown normalization method: {method}")

    report = report_normalization(adata)

    # LLM enhancement
    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("normalize", adata, proposal, report, prev_reports)
        if not auto:
            print(llm_report)

    return {"obj": adata, "report": report, "proposal": proposal, "llm_report": llm_report}
