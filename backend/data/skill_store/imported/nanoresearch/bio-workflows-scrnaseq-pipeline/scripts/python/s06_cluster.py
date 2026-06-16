"""Step 6: Dimensionality Reduction + Clustering — Single-Cell RNA-seq Pipeline (Python)

Reference: scanpy 1.10+

Input State:  [Normalized] or [Integrated]
Output State: [Clustered] + [UMAP]
"""

import numpy as np
import scanpy as sc

from llm_report import generate_llm_report


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Recommend PCs and resolution
# ---------------------------------------------------------------------------

def propose_clustering_params(adata: sc.AnnData) -> dict:
    """Propose PCA dimensions and clustering resolutions."""
    n_cells = adata.n_obs
    n_pcs = 50

    # Resolution recommendation based on cell count
    if n_cells < 3000:
        resolutions = [0.3, 0.5, 0.8]
        default_res = 0.5
        res_reason = "Small dataset (<3k cells). Lower resolutions to avoid over-clustering."
    elif n_cells < 20000:
        resolutions = [0.3, 0.5, 0.8, 1.2]
        default_res = 0.8
        res_reason = "Medium dataset. Standard resolution range."
    else:
        resolutions = [0.3, 0.5, 0.8, 1.2, 1.6]
        default_res = 1.2
        res_reason = "Large dataset (>20k cells). Higher resolutions may reveal subtypes."

    return {
        "recommendation": {
            "n_pcs": n_pcs,
            "n_pcs_use": 30,  # Will be refined after PCA
            "resolutions": resolutions,
            "default_resolution": default_res,
        },
        "diagnostics": {
            "n_cells": n_cells,
            "n_genes": adata.n_vars,
        },
        "justification": res_reason,
        "alternatives": {
            "lower_res": "Use 0.2-0.4 for broad cell-type-level clustering.",
            "higher_res": "Use 1.5-2.0 for subtype discovery.",
        },
    }


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

def evaluate_clustering_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    """Evaluate clustering proposal before execution.

    Guardrails:
      - Any resolution outside [0.1, 2.0] -> BLOCK + clamp
      - n_pcs_use < 5 -> CAUTION (too few PCs)
    """
    resolutions = proposal["recommendation"]["resolutions"]

    clamped = [max(0.1, min(2.0, r)) for r in resolutions]
    if clamped != resolutions:
        bad = [r for r in resolutions if r < 0.1 or r > 2.0]
        return {
            "verdict": "BLOCK",
            "adjusted": True,
            "reason": (
                f"Resolutions {bad} outside valid range [0.1, 2.0]. "
                f"Clamped to {list(dict.fromkeys(clamped))}."
            ),
            "adjusted_params": {"resolutions": list(dict.fromkeys(clamped))},
        }

    npcs_use = proposal["recommendation"].get("n_pcs_use")
    if npcs_use is not None and npcs_use < 5:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": f"Only {npcs_use} PCs recommended (<5). Clustering may be unreliable.",
        }

    return {"verdict": "PROCEED", "adjusted": False}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — PCA, UMAP, multi-resolution clustering
# ---------------------------------------------------------------------------

def execute_clustering(adata: sc.AnnData, n_pcs: int = 50,
                       resolutions: list = None, default_res: float = None,
                       **kwargs) -> sc.AnnData:
    """Run full clustering workflow.

    Parameters
    ----------
    adata : AnnData
    n_pcs : Number of PCs to compute
    resolutions : List of clustering resolutions
    default_res : Default resolution to set as primary leiden column
    **kwargs : Additional args

    Returns
    -------
    AnnData with PCA, UMAP, and multiple cluster resolutions
    """
    if resolutions is None:
        resolutions = [0.3, 0.5, 0.8]

    # Scale and PCA (use HVG subset without dropping other genes)
    sc.pp.scale(adata, max_value=10)
    sc.tl.pca(adata, n_comps=n_pcs, use_highly_variable=True)

    # Determine optimal PCs (elbow)
    variance_ratio = adata.uns["pca"]["variance_ratio"]
    threshold = variance_ratio[0] * 0.05
    idx = np.where(variance_ratio < threshold)[0]
    if len(idx) > 0:
        dims_use = min(idx[0] + 1, 50)
    else:
        dims_use = min(len(variance_ratio), 50)
    if dims_use < 10:
        dims_use = min(20, len(variance_ratio))

    # Neighbors + UMAP
    sc.pp.neighbors(adata, n_neighbors=15, n_pcs=dims_use)
    sc.tl.umap(adata)

    # Multi-resolution clustering
    res_key_map = {}
    for res in resolutions:
        res_key = f"leiden_{res:g}"
        sc.tl.leiden(adata, resolution=res, key_added=res_key)
        res_key_map[res] = res_key

    # Set default — use proposal's default_res if provided, else median
    if default_res is not None and default_res in res_key_map:
        adata.obs["leiden"] = adata.obs[res_key_map[default_res]]
    else:
        fallback = resolutions[len(resolutions) // 2] if len(resolutions) > 1 else resolutions[0]
        adata.obs["leiden"] = adata.obs[res_key_map[fallback]]

    adata.uns["pipeline_state"] = "Clustered"
    adata.uns["clustering_resolutions"] = resolutions
    adata.uns["clustering_dims"] = dims_use

    print(f"Clustering complete. PCs used: {dims_use}, Resolutions: {resolutions}")

    return adata


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

def report_clustering(adata: sc.AnnData, proposal: dict) -> dict:
    """Report clustering results."""
    resolutions = proposal["recommendation"]["resolutions"]
    default_res = proposal["recommendation"]["default_resolution"]

    # Count clusters at each resolution
    res_cols = [f"leiden_{r:g}" for r in resolutions if f"leiden_{r:g}" in adata.obs.columns]
    cluster_counts = {col: adata.obs[col].nunique() for col in res_cols}

    default_col = f"leiden_{default_res}"
    if default_col not in adata.obs.columns:
        default_col = res_cols[0] if res_cols else "leiden"

    n_clusters = adata.obs[default_col].nunique()

    status = "CAUTION" if n_clusters < 5 or n_clusters > 50 else "PASS"

    return {
        "step": "Clustering",
        "status": status,
        "n_clusters": n_clusters,
        "default_resolution": default_res,
        "default_column": default_col,
        "all_resolutions": cluster_counts,
        "recommendation": (
            "Too few clusters. Consider higher resolution or check HVG count."
            if n_clusters < 5
            else (
                "Many clusters. May indicate over-clustering; try lower resolution for broad types."
                if n_clusters > 50
                else f"Clustering looks reasonable ({n_clusters} clusters at res={default_res}). Proceed to marker detection."
            )
        ),
        "next_step": "Step 7: Marker Detection",
    }


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

def run_clustering_step(adata: sc.AnnData, n_pcs: int = None,
                        resolutions: list = None, auto: bool = False,
                        use_llm: bool = True,
                        prev_reports: dict = None, **kwargs) -> dict:
    """Complete clustering step.

    Parameters
    ----------
    adata : AnnData [Normalized/Integrated]
    n_pcs : Number of PCs (None = auto)
    resolutions : Clustering resolutions (None = auto)
    auto : Skip proposal display
    use_llm : If True, generate LLM diagnostic card.
    **kwargs : Passed to execute_clustering

    Returns
    -------
    dict with keys: obj, report, proposal, llm_report
    """
    expected_states = {"Normalized", "Integrated"}
    current_state = adata.uns.get("pipeline_state")
    if current_state not in expected_states:
        import warnings
        warnings.warn(
            f"Expected input state 'Normalized' or 'Integrated' for clustering step, got '{current_state}'. "
            "Proceeding anyway, but results may be unexpected."
        )

    proposal = propose_clustering_params(adata)

    # Evaluate phase: guardrail on resolution bounds
    evaluation = evaluate_clustering_proposal(proposal, adata)
    if evaluation["adjusted"]:
        print(f"GUARDRAIL: {evaluation['reason']}")
        proposal["recommendation"]["resolutions"] = evaluation["adjusted_params"]["resolutions"]
    elif evaluation["verdict"] == "CAUTION":
        print(f"CAUTION: {evaluation['reason']}")

    if n_pcs is None:
        n_pcs = proposal["recommendation"]["n_pcs"]
    if resolutions is None:
        resolutions = proposal["recommendation"]["resolutions"]

    if not auto:
        print("\n=== Clustering Proposal ===")
        print(f"PCs to compute: {n_pcs}")
        print(f"Resolutions: {resolutions}")
        print(f"Default resolution: {proposal['recommendation']['default_resolution']}")
        print(f"Justification: {proposal['justification']}")

    adata = execute_clustering(adata, n_pcs=n_pcs, resolutions=resolutions,
                               default_res=proposal["recommendation"]["default_resolution"], **kwargs)
    report = report_clustering(adata, proposal)

    # LLM enhancement
    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("cluster", adata, proposal, report, prev_reports)
        if not auto:
            print(llm_report)

    return {"obj": adata, "report": report, "proposal": proposal, "llm_report": llm_report}
