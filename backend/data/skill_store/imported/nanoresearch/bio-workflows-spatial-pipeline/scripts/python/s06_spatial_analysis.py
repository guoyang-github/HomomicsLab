"""Step 6: Spatial Analysis — Spatial Transcriptomics Pipeline (Python)

Reference: scanpy 1.10+, squidpy 1.3+

Input State:  [Clustered] + [UMAP]
Output State: [Spatial-Analyzed]

Computes:
- Spatial neighbors graph (platform-aware)
- Spatially Variable Genes (SVGs) via Moran's I
- Neighborhood enrichment analysis
"""

import numpy as np
import scanpy as sc
import squidpy as sq

from llm_report import generate_llm_report


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE
# ---------------------------------------------------------------------------

def propose_spatial_analysis(adata: sc.AnnData) -> dict:
    """Propose spatial analysis parameters based on platform and data."""
    n_spots = adata.n_obs

    # Infer platform from spatial coord patterns
    coords = adata.obsm.get("spatial")
    if coords is not None:
        # Visium has regular hex grid (~55um spacing), Xenium is dense irregular
        n_unique_x = len(np.unique(coords[:, 0]))
        ratio = n_unique_x / n_spots
        if ratio < 0.1:
            platform_guess = "Visium (regular grid)"
            neighbor_method = "grid"
            n_neighs = 6
            neigh_reason = "Visium hexagonal spot array: each spot has ~6 neighbors."
        else:
            platform_guess = "Xenium/MERFISH (dense irregular)"
            neighbor_method = "KNN"
            n_neighs = 15
            neigh_reason = "Subcellular/dense platform: KNN with 15 neighbors captures local context."
    else:
        platform_guess = "Unknown (no spatial coords)"
        neighbor_method = "KNN"
        n_neighs = 15
        neigh_reason = "No spatial coordinates found. Falling back to KNN."

    # SVG detection: top N genes to test
    n_svg_test = min(3000, adata.n_vars)

    return {
        "recommendation": {
            "neighbor_method": neighbor_method,
            "n_neighs": n_neighs,
            "n_svg_test": n_svg_test,
            "svg_method": "morans_i",
        },
        "diagnostics": {
            "n_spots": n_spots,
            "platform_guess": platform_guess,
            "has_spatial_coords": coords is not None,
        },
        "justification": neigh_reason,
        "alternatives": {
            "radius": "Use fixed radius (e.g. 100um) instead of fixed neighbors.",
            "gearys_c": "Alternative spatial autocorrelation metric; similar results to Moran's I.",
        },
    }


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

def evaluate_spatial_proposal(proposal: dict, adata: sc.AnnData) -> dict:
    """Evaluate spatial analysis proposal before execution.

    Guardrails:
      - No spatial coordinates -> BLOCK
      - n_spots < 100 -> CAUTION (too few for reliable spatial stats)
    """
    has_coords = "spatial" in adata.obsm

    if not has_coords:
        return {
            "verdict": "BLOCK",
            "adjusted": False,
            "reason": "Spatial coordinates not found in adata.obsm['spatial']. Cannot perform spatial analysis.",
        }

    n_spots = proposal["diagnostics"]["n_spots"]
    if n_spots < 100:
        return {
            "verdict": "CAUTION",
            "adjusted": False,
            "reason": f"Only {n_spots} spots. Spatial statistics may be unreliable.",
        }

    return {"verdict": "PROCEED", "adjusted": False}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE
# ---------------------------------------------------------------------------

def execute_spatial_analysis(adata: sc.AnnData,
                              neighbor_method: str = "grid",
                              n_neighs: int = 6,
                              n_svg_test: int = 3000,
                              cluster_col: str = "leiden",
                              **kwargs) -> sc.AnnData:
    """Run spatial analysis: neighbors, SVGs, nhood enrichment.

    Parameters
    ----------
    adata : AnnData
    neighbor_method : 'grid', 'KNN', or 'radius'
    n_neighs : Number of neighbors (for KNN/grid)
    n_svg_test : Number of top HVGs to test for spatial variation
    cluster_col : Column with cluster labels for nhood enrichment
    **kwargs : Additional args

    Returns
    -------
    AnnData with spatial_neighbors, spatial_autocorr, nhood_enrichment in uns
    """
    if "spatial" not in adata.obsm:
        raise ValueError("Spatial coordinates not found in adata.obsm['spatial']")

    # 1. Spatial neighbors (platform-aware)
    if neighbor_method == "grid":
        sq.gr.spatial_neighbors(adata, coord_type="grid", n_rings=1)
    elif neighbor_method == "KNN":
        sq.gr.spatial_neighbors(adata, n_neighs=n_neighs, coord_type="generic")
    elif neighbor_method == "radius":
        sq.gr.spatial_neighbors(adata, radius=kwargs.get("radius", 100.0), coord_type="generic")
    else:
        raise ValueError(f"Unknown neighbor method: {neighbor_method}")

    print(f"Spatial neighbors computed ({neighbor_method}, n={n_neighs})")

    # 2. Spatially Variable Genes (Moran's I)
    # Use HVG subset for speed
    hvg_mask = adata.var["highly_variable"] if "highly_variable" in adata.var.columns else np.ones(adata.n_vars, dtype=bool)
    n_test = min(n_svg_test, hvg_mask.sum())

    # Rank HVGs by dispersion and test top N
    if "dispersions_norm" in adata.var.columns:
        hvg_idx = np.where(hvg_mask)[0]
        disp = adata.var["dispersions_norm"].values[hvg_idx]
        top_idx = hvg_idx[np.argsort(disp)[-n_test:]]
        genes_to_test = adata.var_names[top_idx]
    else:
        genes_to_test = adata.var_names[hvg_mask][:n_test]

    try:
        sq.gr.spatial_autocorr(
            adata,
            mode="moran",
            genes=genes_to_test,
            n_perms=100,
            n_jobs=kwargs.get("n_jobs", 1),
        )
        print(f"SVG detection complete (Moran's I on {len(genes_to_test)} genes)")
    except Exception as e:
        print(f"SVG detection skipped: {e}")
        adata.uns["moranI"] = None

    # 3. Neighborhood enrichment
    if cluster_col in adata.obs.columns:
        try:
            sq.gr.nhood_enrichment(adata, cluster_col=cluster_col)
            print("Neighborhood enrichment computed.")
        except Exception as e:
            print(f"Neighborhood enrichment skipped: {e}")
    else:
        print(f"Skipping nhood enrichment: column '{cluster_col}' not found.")

    adata.uns["pipeline_state"] = "Spatial-Analyzed"
    adata.uns["spatial_neighbor_method"] = neighbor_method
    adata.uns["spatial_n_neighs"] = n_neighs

    return adata


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

def report_spatial_analysis(adata: sc.AnnData, proposal: dict) -> dict:
    """Report spatial analysis results."""
    # SVG results
    svg_df = adata.uns.get("moranI")
    if svg_df is not None and hasattr(svg_df, "shape"):
        n_svgs = len(svg_df)
        # Significant SVGs: pval_norm_fdr_bh < 0.05
        sig_mask = svg_df["pval_norm_fdr_bh"] < 0.05 if "pval_norm_fdr_bh" in svg_df.columns else svg_df["pval_norm"] < 0.05
        n_sig_svgs = int(sig_mask.sum()) if hasattr(sig_mask, "sum") else 0
        top_gene = svg_df.index[0] if n_svgs > 0 else "N/A"
    else:
        n_svgs = 0
        n_sig_svgs = 0
        top_gene = "N/A"

    # Nhood enrichment
    has_nhood = "leiden_nhood_enrichment" in adata.uns

    status = "PASS" if n_sig_svgs >= 10 else "CAUTION"

    return {
        "step": "Spatial Analysis",
        "status": status,
        "n_svgs": n_sig_svgs,
        "top_svg": top_gene,
        "nhood_enrichment": has_nhood,
        "neighbor_method": adata.uns.get("spatial_neighbor_method", "N/A"),
        "recommendation": (
            f"{n_sig_svgs} significant SVGs detected."
            if status == "PASS"
            else "Few significant SVGs. Check tissue quality or platform settings."
        ),
        "next_step": "Step 7: Domain Detection",
    }


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

def run_spatial_analysis_step(adata: sc.AnnData,
                               neighbor_method: str = None,
                               n_neighs: int = None,
                               auto: bool = False,
                               use_llm: bool = True,
                               prev_reports: dict = None,
                               **kwargs) -> dict:
    """Complete spatial analysis step."""
    expected_states = {"Clustered"}
    current_state = adata.uns.get("pipeline_state")
    if current_state not in expected_states:
        import warnings
        warnings.warn(
            f"Expected input state 'Clustered' for spatial analysis step, got '{current_state}'. "
            "Proceeding anyway, but results may be unexpected."
        )

    proposal = propose_spatial_analysis(adata)

    # Evaluate phase: guardrail on spatial data availability
    evaluation = evaluate_spatial_proposal(proposal, adata)
    if evaluation["verdict"] == "BLOCK":
        raise RuntimeError(evaluation["reason"])
    elif evaluation["verdict"] == "CAUTION":
        print(f"CAUTION: {evaluation['reason']}")

    if neighbor_method is None:
        neighbor_method = proposal["recommendation"]["neighbor_method"]
    if n_neighs is None:
        n_neighs = proposal["recommendation"]["n_neighs"]

    if not auto:
        print("\n=== Spatial Analysis Proposal ===")
        print(f"Platform guess: {proposal['diagnostics']['platform_guess']}")
        print(f"Neighbor method: {neighbor_method} (n={n_neighs})")
        print(f"SVG test genes: {proposal['recommendation']['n_svg_test']}")
        print(f"Justification: {proposal['justification']}")

    adata = execute_spatial_analysis(
        adata,
        neighbor_method=neighbor_method,
        n_neighs=n_neighs,
        n_svg_test=proposal["recommendation"]["n_svg_test"],
        **kwargs
    )
    report = report_spatial_analysis(adata, proposal)

    llm_report = None
    if use_llm:
        llm_report = generate_llm_report("spatial", adata, proposal, report, prev_reports)
        if not auto:
            print(llm_report)

    return {"obj": adata, "report": report, "proposal": proposal, "llm_report": llm_report}
