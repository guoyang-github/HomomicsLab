"""Step 5: Integration Decision — Propose / Execute / Report (Python)

Reference: scanpy 1.10+, scvi-tools (optional)

Input State:  [Normalized] + [HVG]
Output State: [Integrated] (if needed) or [Normalized] (if skipped)

Critical decision point: diagnose batch effects BEFORE integration.
Strategy: quick PCA+UMAP without integration → assess → recommend.
"""

import numpy as np
import scanpy as sc
from sklearn.metrics import silhouette_score

from llm_report import generate_llm_report


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Diagnose batch effects and recommend
# ---------------------------------------------------------------------------

def propose_integration(adata: sc.AnnData, batch_col: str = "sample_id") -> dict:
    """Diagnose batch effects and propose integration strategy.

    Parameters
    ----------
    adata : AnnData [Normalized]
    batch_col : Column name for batch/sample identifier

    Returns
    -------
    dict with recommendation and diagnostics
    """
    if batch_col not in adata.obs.columns:
        return {
            "recommendation": {
                "integrate": False,
                "method": None,
                "reason": f"No '{batch_col}' column found. Single-sample analysis — integration not needed.",
            },
            "diagnostics": {"n_batches": 1},
            "justification": "Single sample detected.",
        }

    batches = adata.obs[batch_col].unique()
    n_batches = len(batches)

    if n_batches <= 1:
        return {
            "recommendation": {
                "integrate": False,
                "method": None,
                "reason": "Only one batch detected. Integration not needed.",
            },
            "diagnostics": {"n_batches": n_batches},
            "justification": "Single batch. Proceed directly to clustering.",
        }

    # Quick PCA for diagnostic
    adata_tmp = adata.copy()
    adata_tmp = adata_tmp[:, adata_tmp.var["highly_variable"]]
    sc.pp.scale(adata_tmp, max_value=10)
    sc.tl.pca(adata_tmp, n_comps=30)
    sc.pp.neighbors(adata_tmp, n_neighbors=15, n_pcs=20)
    sc.tl.umap(adata_tmp)

    # Compute batch mixing via silhouette (lower = better mixing)
    try:
        batch_labels = adata_tmp.obs[batch_col].astype("category").cat.codes
        embeddings = adata_tmp.obsm["X_umap"]
        sil_score = silhouette_score(embeddings, batch_labels)
        # Normalize: silhouette ranges -1 to 1, we want 0 = perfect mixing
        batch_score = (sil_score + 1) / 2  # Scale to 0-1
    except Exception:
        batch_score = 0.5  # Default to moderate if computation fails

    # Score interpretation
    if batch_score < 0.3:
        integrate = False
        reason = (
            f"Batch mixing score = {batch_score:.2f} (<0.3). "
            "Batches are already well-mixed. Integration may over-correct biological variation."
        )
        method = None
    elif batch_score < 0.6:
        integrate = True
        reason = (
            f"Batch mixing score = {batch_score:.2f} (0.3-0.6). "
            "Moderate batch effect detected. Integration recommended."
        )
        method = "harmony"
    else:
        integrate = True
        reason = (
            f"Batch mixing score = {batch_score:.2f} (>0.6). "
            "Strong batch effect detected. Integration strongly recommended."
        )
        method = "harmony"  # Scanpy has harmony via sc.external

    return {
        "recommendation": {
            "integrate": integrate,
            "method": method,
            "batch_col": batch_col,
            "reason": reason,
            "n_batches": n_batches,
        },
        "diagnostics": {
            "n_batches": n_batches,
            "n_cells": adata.n_obs,
            "batch_mixing_score": round(batch_score, 3),
        },
        "justification": reason,
        "alternatives": {
            "harmony": "Fast, works for most cases (2-5 batches, <50k cells).",
            "scanorama": "Good for large datasets with many batches.",
            "scvi": "Deep learning-based, best for >50k cells or complex batch structures.",
        },
    }


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

def evaluate_integration_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    """Evaluate integration proposal before execution.

    Guardrails:
      - Single batch / integrate=False → PROCEED (skip)
      - batch_mixing_score < 0.1 → BLOCK (already well-mixed)
      - batch_mixing_score > 0.9 → CAUTION (extremely strong batch)
    """
    rec = proposal["recommendation"]

    if not rec["integrate"]:
        return {
            "verdict": "PROCEED",
            "adjusted": False,
            "reason": "Single batch or integration not recommended. Skipping execution.",
        }

    score = proposal["diagnostics"].get("batch_mixing_score")

    if score is not None and score < 0.1:
        return {
            "verdict": "BLOCK",
            "adjusted": True,
            "reason": (
                f"Batch mixing score = {score:.3f} (<0.1). Already perfectly mixed. "
                "Integration may remove biological signal. Forcing skip."
            ),
            "adjusted_recommendation": {"integrate": False, "method": None},
        }

    if score is not None and score > 0.9:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": (
                f"Batch mixing score = {score:.3f} (>0.9). Extremely strong batch effect. "
                "Verify samples are comparable."
            ),
        }

    return {"verdict": "PROCEED", "adjusted": False}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — Run integration if recommended
# ---------------------------------------------------------------------------

def execute_integration(adata: sc.AnnData, method: str = "harmony",
                        batch_col: str = "sample_id", **kwargs) -> sc.AnnData:
    """Run batch integration with specified method.

    Parameters
    ----------
    adata : AnnData [Normalized]
    method : "harmony" or "scanorama"
    batch_col : Column name for batch
    **kwargs : Additional args passed to integration function

    Returns
    -------
    AnnData [Integrated]
    """
    if method == "harmony":
        try:
            # Backup original PCA before overwriting
            adata.obsm["X_pca_pre_harmony"] = adata.obsm["X_pca"].copy()
            sc.external.pp.harmony_integrate(adata, key=batch_col, **kwargs)
            adata.obsm["X_pca"] = adata.obsm["X_pca_harmony"]
            adata.uns["integration_reduction"] = "pca_harmony"
        except ImportError:
            raise ImportError(
                "Harmony integration requires harmonypy. "
                "Install: pip install harmonypy"
            )

    elif method == "scanorama":
        try:
            import scanorama
            batches = []
            batch_names = adata.obs[batch_col].unique()
            # Save original cell order for reordering after integration
            original_order = adata.obs_names.copy()
            batch_cell_order = []
            for b in batch_names:
                mask = adata.obs[batch_col] == b
                batches.append(adata[mask].copy())
                batch_cell_order.extend(adata.obs_names[mask].tolist())
            integrated, genes = scanorama.integrate_scanpy(batches)
            # Verify output aligns with input
            if len(integrated) != len(batches):
                raise ValueError("Scanorama output batch count mismatch")
            corrected = np.vstack(integrated)
            if corrected.shape[0] != adata.n_obs:
                raise ValueError(
                    f"Scanorama output cell count ({corrected.shape[0]}) "
                    f"does not match input ({adata.n_obs})"
                )
            # Reorder to match original cell order (O(n) via dict mapping)
            order_map = {c: i for i, c in enumerate(batch_cell_order)}
            reorder_idx = [order_map[c] for c in original_order]
            corrected = corrected[reorder_idx, :]
            # Backup original PCA before overwriting
            adata.obsm["X_pca_pre_scanorama"] = adata.obsm["X_pca"].copy()
            adata.obsm["X_scanorama"] = corrected
            adata.obsm["X_pca"] = adata.obsm["X_scanorama"]
            adata.uns["integration_reduction"] = "scanorama"
        except ImportError:
            raise ImportError("Scanorama integration requires scanorama. Install: pip install scanorama")

    else:
        raise ValueError(f"Unknown integration method: {method}")

    adata.uns["pipeline_state"] = "Integrated"
    adata.uns["integration_method"] = method
    print(f"Integration complete: {method}")

    return adata


def skip_integration(adata: sc.AnnData) -> sc.AnnData:
    """Tag object as proceeding without integration."""
    adata.uns["pipeline_state"] = "Normalized"
    adata.uns["integration_method"] = "None"
    adata.uns["integration_reduction"] = "pca"
    return adata


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

def report_integration(adata: sc.AnnData, proposal: dict) -> dict:
    """Report integration results."""
    method = adata.uns.get("integration_method", "Unknown")

    if method == "None":
        return {
            "step": "Batch Integration",
            "status": "SKIPPED",
            "method": "None",
            "reason": proposal["recommendation"]["reason"],
            "recommendation": "Integration not needed. Proceed to clustering using PCA embeddings.",
            "next_step": "Step 6: Dimensionality Reduction + Clustering",
        }
    else:
        return {
            "step": "Batch Integration",
            "status": "PASS",
            "method": method,
            "n_batches": proposal["diagnostics"]["n_batches"],
            "recommendation": (
                f"Integration with {method} complete. "
                f"Use '{adata.uns.get('integration_reduction', 'pca')}' for downstream clustering."
            ),
            "next_step": "Step 6: Dimensionality Reduction + Clustering",
        }


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

def run_integration_step(adata: sc.AnnData, batch_col: str = "sample_id",
                         method: str = None, auto: bool = False,
                         use_llm: bool = True,
                         prev_reports: dict = None, **kwargs) -> dict:
    """Complete integration decision step.

    Parameters
    ----------
    adata : AnnData [Normalized]
    batch_col : Batch column name
    method : Override proposed method (None = auto)
    auto : Skip proposal display
    use_llm : If True, generate LLM diagnostic card.
    **kwargs : Passed to execute_integration

    Returns
    -------
    dict with keys: obj, report, proposal, llm_report
    """
    expected_states = {"Normalized"}
    current_state = adata.uns.get("pipeline_state")
    if current_state not in expected_states:
        import warnings
        warnings.warn(
            f"Expected input state 'Normalized' for integration step, got '{current_state}'. "
            "Proceeding anyway, but results may be unexpected."
        )

    proposal = propose_integration(adata, batch_col=batch_col)

    # Evaluate phase: guardrail on batch mixing score
    evaluation = evaluate_integration_proposal(proposal, adata)
    if evaluation["adjusted"]:
        print(f"GUARDRAIL: {evaluation['reason']}")
        proposal["recommendation"] = evaluation["adjusted_recommendation"]
    elif evaluation["verdict"] == "CAUTION":
        print(f"CAUTION: {evaluation['reason']}")

    if not auto:
        print("\n=== Integration Proposal ===")
        print(f"Batches detected: {proposal['diagnostics']['n_batches']}")
        if "batch_mixing_score" in proposal["diagnostics"]:
            print(f"Batch mixing score: {proposal['diagnostics']['batch_mixing_score']:.3f}")
        print(f"Recommendation: {proposal['justification']}")
        if proposal["recommendation"]["integrate"]:
            print(f"Suggested method: {proposal['recommendation']['method']}")

    if method is None:
        integrate = proposal["recommendation"]["integrate"]
        method = proposal["recommendation"]["method"]
    else:
        integrate = method != "None"

    if integrate:
        adata = execute_integration(adata, method=method, batch_col=batch_col, **kwargs)
    else:
        adata = skip_integration(adata)

    report = report_integration(adata, proposal)

    # LLM enhancement
    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("integration", adata, proposal, report, prev_reports)
        if not auto:
            print(llm_report)

    return {"obj": adata, "report": report, "proposal": proposal, "llm_report": llm_report}
