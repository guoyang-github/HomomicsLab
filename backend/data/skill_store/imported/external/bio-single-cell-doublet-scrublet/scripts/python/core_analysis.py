#!/usr/bin/env python3
"""
Scrublet wrapper for doublet detection in single-cell RNA-seq data.
"""

import numpy as np
import pandas as pd


def run_scrublet(
    adata,
    expected_doublet_rate=None,
    sim_doublet_ratio=2.0,
    n_neighbors=None,
    min_counts=2,
    min_cells=3,
    min_gene_variability_pctl=85,
    n_prin_comps=30,
    synthetic_doublet_umi_subsampling=1.0,
    use_approx_neighbors=True,
    random_state=42,
    verbose=True,
    layer=None
):
    """
    Run Scrublet doublet detection on single-cell data.

    Args:
        adata: AnnData object with raw counts
        expected_doublet_rate: Expected doublet rate (default: auto-calculate as n_cells/1000 * 0.008)
        sim_doublet_ratio: Number of simulated doublets relative to observed cells (default: 2.0)
        n_neighbors: Number of neighbors for KNN (default: round(0.5 * sqrt(n_cells)))
        min_counts: Minimum counts for gene filtering (default: 2)
        min_cells: Minimum cells for gene filtering (default: 3)
        min_gene_variability_pctl: Keep top percentile of variable genes (default: 85)
        n_prin_comps: Number of principal components (default: 30)
        synthetic_doublet_umi_subsampling: UMI subsampling rate for synthetic doublets (default: 1.0)
        use_approx_neighbors: Use approximate nearest neighbors (default: True)
        random_state: Random seed (default: 42)
        verbose: Print progress (default: True)
        layer: Layer to use (default: None, uses .X)

    Returns:
        tuple: (adata with doublet scores added, scrublet object)
    """
    try:
        import scrublet as scr
    except ImportError:
        raise ImportError(
            "scrublet is required for doublet detection. "
            "Install with: pip install scrublet"
        )

    # Get count matrix
    if layer is not None:
        X = adata.layers[layer]
    else:
        X = adata.X

    n_cells = adata.n_obs

    # Calculate expected doublet rate if not provided
    if expected_doublet_rate is None:
        expected_doublet_rate = n_cells / 1000 * 0.008
        if verbose:
            print(f"Auto-calculated expected doublet rate: {expected_doublet_rate:.3f}")

    # Initialize Scrublet
    scrub = scr.Scrublet(
        X,
        expected_doublet_rate=expected_doublet_rate,
        sim_doublet_ratio=sim_doublet_ratio,
        n_neighbors=n_neighbors,
        random_state=random_state
    )

    # Run doublet detection
    doublet_scores, predicted_doublets = scrub.scrub_doublets(
        min_counts=min_counts,
        min_cells=min_cells,
        min_gene_variability_pctl=min_gene_variability_pctl,
        n_prin_comps=n_prin_comps,
        synthetic_doublet_umi_subsampling=synthetic_doublet_umi_subsampling,
        use_approx_neighbors=use_approx_neighbors,
        verbose=verbose
    )

    # Add results to AnnData
    adata.obs['doublet_score'] = doublet_scores
    adata.obs['predicted_doublet'] = predicted_doublets

    # Store scrublet threshold
    adata.uns['scrublet'] = {
        'threshold': scrub.threshold_,
        'expected_doublet_rate': expected_doublet_rate,
        'sim_doublet_ratio': sim_doublet_ratio
    }

    if verbose:
        print(f"Detected {sum(predicted_doublets)} doublets "
              f"({100*sum(predicted_doublets)/len(predicted_doublets):.1f}%)")
        print(f"Scrublet threshold: {scrub.threshold_:.3f}")

    return adata, scrub


def filter_doublets(adata, threshold=None, inplace=False):
    """
    Filter out predicted doublets from AnnData.

    Args:
        adata: AnnData with doublet predictions
        threshold: Optional custom threshold (default: use scrublet's threshold)
        inplace: Filter in place (default: False)

    Returns:
        Filtered AnnData if inplace=False, else None
    """
    if 'predicted_doublet' not in adata.obs.columns:
        raise ValueError("'predicted_doublet' not found in adata.obs. Run run_scrublet first.")

    if threshold is not None:
        # Recalculate predictions with custom threshold
        predicted_doublets = adata.obs['doublet_score'] > threshold
        n_doublets = predicted_doublets.sum()
    else:
        predicted_doublets = adata.obs['predicted_doublet']
        n_doublets = predicted_doublets.sum()

    if inplace:
        # In-place subset: _inplace_subset_obs is AnnData internal API.
        # Available in anndata < 0.10; may be removed in future versions.
        if hasattr(adata, '_inplace_subset_obs'):
            adata._inplace_subset_obs(~predicted_doublets)
        else:
            # Fallback for anndata >= 0.10: return filtered copy with a warning
            import warnings
            warnings.warn(
                "AnnData >= 0.10 does not support in-place subset. "
                "Returning filtered copy.",
                UserWarning
            )
            return adata[~predicted_doublets].copy()
        return None
    else:
        return adata[~predicted_doublets].copy()


def calculate_doublet_rate(n_cells, rate_per_1000=0.008):
    """
    Calculate expected doublet rate based on cell count.

    Default rate is 0.8% per 1000 cells (10x Genomics estimate).

    Args:
        n_cells: Number of cells
        rate_per_1000: Doublet rate per 1000 cells (default: 0.008)

    Returns:
        Expected doublet rate
    """
    return n_cells / 1000 * rate_per_1000
