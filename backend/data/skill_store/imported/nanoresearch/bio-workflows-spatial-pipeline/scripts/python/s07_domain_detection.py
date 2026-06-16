"""Step 7: Domain Detection — Spatial Transcriptomics Pipeline (Python)

Reference: scanpy 1.10+, squidpy 1.3+

Input State:  [Spatial-Analyzed] or [Clustered]
Output State: [Domains]

Identifies spatial domains using spatially constrained clustering.
Compares transcriptomic clusters vs spatial domains.
"""

import numpy as np
import scanpy as sc
import squidpy as sq

from llm_report import generate_llm_report


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE
# ---------------------------------------------------------------------------

def propose_domain_method(adata: sc.AnnData) -> dict:
    """Propose domain detection method based on data characteristics."""
    n_spots = adata.n_obs
    n_clusters = adata.obs["leiden"].nunique() if "leiden" in adata.obs.columns else 0

    # Method selection: Python path only supports spatial_leiden and stagate
    # BayesSpace is R-only; default to spatial_leiden for reliability
    method = "spatial_leiden"
    if n_spots > 50000:
        reason = (
            f"Large dataset ({n_spots} spots). Spatial Leiden is fast and scalable. "
            "STAGATE would be too slow; BayesSpace requires R."
        )
    elif n_spots > 10000:
        reason = (
            f"Medium-large dataset ({n_spots} spots). Spatial Leiden balances "
            "speed and accuracy. STAGATE optional for complex architecture."
        )
    else:
        reason = (
            f"Small dataset ({n_spots} spots). Spatial Leiden is reliable. "
            "BayesSpace (R) recommended if uncertainty quantification needed."
        )

    # Resolution for domain detection
    if n_clusters < 5:
        domain_res = 1.0
    elif n_clusters < 15:
        domain_res = 0.8
    else:
        domain_res = 0.5

    return {
        "recommendation": {
            "method": method,
            "resolution": domain_res,
            "comparison_cluster_col": "leiden",
        },
        "diagnostics": {
            "n_spots": n_spots,
            "n_clusters": n_clusters,
        },
        "justification": reason,
        "alternatives": {
            "stagate": "Deep learning method; best for complex tissue but requires PyTorch.",
            "bayesspace": "R-only; provides uncertainty quantification and smoothing.",
            "spatial_leiden_higher": "Use res=1.2+ for more granular domains.",
        },
    }


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

def evaluate_domain_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    """Evaluate domain detection proposal before execution.

    Guardrails:
      - Method not in {spatial_leiden, stagate} → BLOCK + fallback
      - Resolution outside [0.1, 2.0] → BLOCK + clamp
      - No spatial coordinates → BLOCK
    """
    method = proposal["recommendation"]["method"]
    resolution = proposal["recommendation"]["resolution"]

    valid_methods = {"spatial_leiden", "stagate"}
    if method not in valid_methods:
        return {
            "verdict": "BLOCK",
            "adjusted": True,
            "reason": f"Unknown domain method '{method}'. Valid: {valid_methods}.",
            "adjusted_params": {"method": "spatial_leiden"},
        }

    if resolution < 0.1 or resolution > 2.0:
        clamped = max(0.1, min(2.0, resolution))
        return {
            "verdict": "BLOCK",
            "adjusted": True,
            "reason": f"Resolution {resolution} outside [0.1, 2.0]. Clamped to {clamped}.",
            "adjusted_params": {"resolution": clamped},
        }

    if "spatial" not in adata.obsm:
        return {
            "verdict": "BLOCK",
            "adjusted": False,
            "reason": "Spatial coordinates not found in adata.obsm['spatial']. Cannot detect domains.",
        }

    return {"verdict": "PROCEED", "adjusted": False}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE
# ---------------------------------------------------------------------------

def execute_domain_detection(adata: sc.AnnData,
                              method: str = "spatial_leiden",
                              resolution: float = 0.8,
                              cluster_col: str = "leiden",
                              **kwargs) -> sc.AnnData:
    """Run domain detection with specified method.

    Parameters
    ----------
    adata : AnnData
    method : 'spatial_leiden' (default), or 'stagate' if available
    resolution : Leiden resolution for spatially constrained clustering
    cluster_col : Column with transcriptomic clusters for comparison
    **kwargs : Additional args

    Returns
    -------
    AnnData with 'spatial_domain' in obs
    """
    if "spatial" not in adata.obsm:
        raise ValueError("Spatial coordinates not found in adata.obsm['spatial']")

    if method == "spatial_leiden":
        # Ensure spatial neighbors exist
        if "spatial_connectivities" not in adata.obsp:
            sq.gr.spatial_neighbors(adata)

        # Use PCA embeddings + spatial adjacency for domain detection
        # Compute on combined graph: transcriptomic similarity + spatial proximity
        sc.tl.leiden(
            adata,
            resolution=resolution,
            key_added="spatial_domain",
            adjacency=adata.obsp["spatial_connectivities"],
        )

        n_domains = adata.obs["spatial_domain"].nunique()
        print(f"Spatial Leiden domain detection complete: {n_domains} domains")

    elif method == "stagate":
        try:
            import STAGATE
            # STAGATE requires specific input preparation
            sc.pp.scale(adata, max_value=10)
            sc.tl.pca(adata, n_comps=30, use_highly_variable=True)
            STAGATE.Cal_Spatial_Net(adata, rad_cutoff=150)
            STAGATE.Stats_Spatial_Net(adata)
            adata = STAGATE.train_STAGATE(adata, alpha=1.0)
            sc.pp.neighbors(adata, use_rep="STAGATE")
            sc.tl.leiden(adata, resolution=resolution, key_added="spatial_domain")
            n_domains = adata.obs["spatial_domain"].nunique()
            print(f"STAGATE domain detection complete: {n_domains} domains")
        except ImportError:
            raise ImportError(
                "STAGATE not installed. Install: pip install STAGATE-pyG "
                "or use method='spatial_leiden'"
            )
    else:
        raise ValueError(f"Unknown domain detection method: {method}")

    # Compare domains vs clusters
    if cluster_col in adata.obs.columns:
        from sklearn.metrics import adjusted_rand_score
        ari = adjusted_rand_score(
            adata.obs[cluster_col].astype(str),
            adata.obs["spatial_domain"].astype(str)
        )
        adata.uns["domain_cluster_ari"] = round(ari, 3)
        print(f"Domain-cluster ARI: {ari:.3f}")

    adata.uns["pipeline_state"] = "Domains"
    adata.uns["domain_method"] = method
    adata.uns["domain_resolution"] = resolution

    return adata


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

def report_domain_detection(adata: sc.AnnData, proposal: dict) -> dict:
    """Report domain detection results."""
    n_domains = adata.obs["spatial_domain"].nunique() if "spatial_domain" in adata.obs.columns else 0
    method = adata.uns.get("domain_method", "Unknown")
    ari = adata.uns.get("domain_cluster_ari", None)

    # Status: too few or too many domains is suspicious
    if n_domains < 2:
        status = "WARNING"
    elif n_domains > 30:
        status = "CAUTION"
    else:
        status = "PASS"

    return {
        "step": "Domain Detection",
        "status": status,
        "n_domains": n_domains,
        "method": method,
        "domain_cluster_ari": ari,
        "recommendation": (
            "Only 1 domain detected. Check spatial coords and neighbor graph."
            if n_domains < 2
            else (
                f"Many domains ({n_domains}). Consider lower resolution for broader regions."
                if n_domains > 30
                else (
                    f"{n_domains} domains detected. "
                    f"Domain-cluster ARI={ari:.2f} if close to 0, domains capture spatial structure beyond transcriptomics."
                    if ari is not None
                    else f"{n_domains} domains detected. Proceed to interpretation."
                )
            )
        ),
        "next_step": "Optional: Deconvolution / Cell-Cell Communication",
    }


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

def run_domain_detection_step(adata: sc.AnnData,
                               method: str = None,
                               resolution: float = None,
                               auto: bool = False,
                               use_llm: bool = True,
                               prev_reports: dict = None,
                               **kwargs) -> dict:
    """Complete domain detection step."""
    expected_states = {"Spatial-Analyzed", "Clustered"}
    current_state = adata.uns.get("pipeline_state")
    if current_state not in expected_states:
        import warnings
        warnings.warn(
            f"Expected input state 'Spatial-Analyzed' or 'Clustered' for domain step, got '{current_state}'. "
            "Proceeding anyway, but results may be unexpected."
        )

    proposal = propose_domain_method(adata)

    # Evaluate phase: guardrail on method, resolution, and spatial coords
    evaluation = evaluate_domain_proposal(proposal, adata)
    if evaluation["verdict"] == "BLOCK" and not evaluation.get("adjusted", False):
        raise RuntimeError(evaluation["reason"])
    if evaluation["adjusted"]:
        print(f"GUARDRAIL: {evaluation['reason']}")
        if "method" in evaluation.get("adjusted_params", {}):
            proposal["recommendation"]["method"] = evaluation["adjusted_params"]["method"]
        if "resolution" in evaluation.get("adjusted_params", {}):
            proposal["recommendation"]["resolution"] = evaluation["adjusted_params"]["resolution"]
    elif evaluation["verdict"] == "CAUTION":
        print(f"CAUTION: {evaluation['reason']}")

    if method is None:
        method = proposal["recommendation"]["method"]
    if resolution is None:
        resolution = proposal["recommendation"]["resolution"]

    if not auto:
        print("\n=== Domain Detection Proposal ===")
        print(f"Method: {method}")
        print(f"Resolution: {resolution}")
        print(f"Justification: {proposal['justification']}")

    adata = execute_domain_detection(
        adata,
        method=method,
        resolution=resolution,
        cluster_col=proposal["recommendation"]["comparison_cluster_col"],
        **kwargs
    )
    report = report_domain_detection(adata, proposal)

    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("domain", adata, proposal, report, prev_reports)
        if not auto:
            print(llm_report)

    return {"obj": adata, "report": report, "proposal": proposal, "llm_report": llm_report}
