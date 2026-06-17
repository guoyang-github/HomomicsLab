"""
Utility functions for cell2location analysis.

Author: Yang Guo
Date: 2026-03-31
"""

from typing import Optional, List
import numpy as np
import pandas as pd
from anndata import AnnData


def validate_inputs(
    spatial_adata: AnnData,
    reference_adata: AnnData,
    cell_type_key: str = 'cell_type',
) -> None:
    """
    Validate inputs for deconvolution.

    Parameters
    ----------
    spatial_adata : AnnData
        Spatial data
    reference_adata : AnnData
        Reference data
    cell_type_key : str, default='cell_type'
        Cell type column

    Raises
    ------
    ValueError
        If validation fails
    """
    # Check cell type key exists
    if cell_type_key not in reference_adata.obs.columns:
        raise ValueError(f"'{cell_type_key}' not found in reference_adata.obs")

    # Check for minimum cells per type
    cell_counts = reference_adata.obs[cell_type_key].value_counts()
    if (cell_counts < 10).any():
        low_count_types = cell_counts[cell_counts < 10].index.tolist()
        raise ValueError(
            f"Cell types with <10 cells: {low_count_types}. "
            "Filter or merge these cell types."
        )

    # Check spatial coordinates
    has_spatial = (
        'spatial' in spatial_adata.obsm or
        'array_row' in spatial_adata.obs.columns
    )
    if not has_spatial:
        raise ValueError("Spatial coordinates not found in spatial_adata")

    # Validate coordinate shape if present in obsm
    if 'spatial' in spatial_adata.obsm:
        coords = spatial_adata.obsm['spatial']
        if coords.ndim != 2 or coords.shape[1] < 2:
            raise ValueError(
                f"spatial_adata.obsm['spatial'] must be 2D with at least 2 columns, "
                f"got shape {coords.shape}"
            )


def filter_low_quality_spots(
    spatial_adata: AnnData,
    min_counts: int = 100,
    min_genes: int = 50,
) -> AnnData:
    """
    Filter low quality spots from spatial data.

    Parameters
    ----------
    spatial_adata : AnnData
        Spatial data
    min_counts : int, default=100
        Minimum UMI counts per spot
    min_genes : int, default=50
        Minimum genes detected per spot

    Returns
    -------
    AnnData
        Filtered data (copy). The input is not modified.
    """
    # Work on a copy to avoid side effects on the input object
    adata = spatial_adata.copy()
    n_before = adata.n_obs

    # Calculate QC metrics if not present
    if 'total_counts' not in adata.obs:
        adata.obs['total_counts'] = np.array(adata.X.sum(axis=1)).flatten()
    if 'n_genes_by_counts' not in adata.obs:
        adata.obs['n_genes_by_counts'] = np.array((adata.X > 0).sum(axis=1)).flatten()

    # Filter
    mask = (
        (adata.obs['total_counts'] >= min_counts) &
        (adata.obs['n_genes_by_counts'] >= min_genes)
    )

    filtered = adata[mask].copy()
    n_after = filtered.n_obs

    print(f"Filtered {n_before - n_after} spots. Remaining: {n_after}")

    return filtered


def estimate_optimal_epochs(
    spatial_adata: AnnData,
    min_epochs: int = 10000,
    max_epochs: int = 50000,
) -> int:
    """
    Estimate optimal training epochs based on data size.

    Parameters
    ----------
    spatial_adata : AnnData
        Spatial data
    min_epochs : int, default=10000
        Minimum epochs
    max_epochs : int, default=50000
        Maximum epochs

    Returns
    -------
    int
        Recommended number of epochs
    """
    n_spots = spatial_adata.n_obs

    # Scale epochs with data size
    if n_spots < 1000:
        epochs = min_epochs
    elif n_spots < 5000:
        epochs = 20000
    elif n_spots < 20000:
        epochs = 30000
    else:
        epochs = max_epochs

    return min(epochs, max_epochs)
