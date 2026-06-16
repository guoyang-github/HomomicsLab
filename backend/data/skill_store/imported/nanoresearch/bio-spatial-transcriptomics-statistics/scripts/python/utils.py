"""
Utility functions for spatial transcriptomics statistics.

This module provides validation and helper functions for spatial data analysis.
"""

import numpy as np
import pandas as pd
from typing import Optional, Union
import warnings


def validate_spatial_data(adata, require_raw: bool = False) -> bool:
    """
    Validate spatial data for statistical analysis.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    require_raw : bool, default=False
        If True, checks that data contains raw counts (non-negative integers)

    Returns
    -------
    bool
        True if validation passes

    Raises
    ------
    ValueError
        If spatial coordinates are missing or contain invalid values
    """
    # Check spatial coordinates exist
    if 'spatial' not in adata.obsm:
        raise ValueError("No spatial coordinates found in adata.obsm['spatial']")

    # Check for NaN/Inf in coordinates
    coords = adata.obsm['spatial']
    if np.isnan(coords).any() or np.isinf(coords).any():
        raise ValueError("Spatial coordinates contain NaN or Inf values")

    # Check data type (raw counts vs normalized)
    if require_raw:
        sample = adata.X[:100, :100] if adata.shape[0] > 100 else adata.X
        if hasattr(sample, 'toarray'):
            sample = sample.toarray()
        if sample.min() < 0:
            raise ValueError("Data appears normalized (negative values). Raw counts required.")
        if not np.allclose(sample, sample.astype(int), rtol=1e-5):
            warnings.warn("Data may not be raw integer counts")

    return True


def check_spatial_neighbors(adata, n_neighbors: int = 6) -> dict:
    """
    Check if spatial neighbors have been computed.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    n_neighbors : int, default=6
        Expected number of neighbors

    Returns
    -------
    dict
        Dictionary with 'has_neighbors', 'n_neighbors', 'method'
    """
    result = {
        'has_neighbors': False,
        'n_neighbors': 0,
        'method': None
    }

    # Check for spatial neighbors in .obsp
    if 'spatial_connectivities' in adata.obsp:
        result['has_neighbors'] = True
        result['method'] = 'precomputed'
        # Estimate n_neighbors from connectivities
        if hasattr(adata.obsp['spatial_connectivities'], 'toarray'):
            result['n_neighbors'] = int(adata.obsp['spatial_connectivities'].sum(axis=1).mean())
    elif 'spatial_distances' in adata.obsp:
        result['has_neighbors'] = True
        result['method'] = 'distances'

    return result


def check_sample_size(adata, statistic_type: str = 'moran') -> dict:
    """
    Check if sample size is adequate for the specified statistic.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    statistic_type : str, default='moran'
        Type of statistic to compute

    Returns
    -------
    dict
        Dictionary with 'adequate', 'n_samples', 'recommended_min', 'warning'
    """
    n_samples = adata.n_obs

    # Minimum sample size recommendations
    min_samples = {
        'moran': 30,
        'geary': 30,
        'lisa': 50,
        'bivariate_moran': 30,
        'getis_ord_gi': 30,
        'join_counts': 20,
        'cooccurrence': 50,
        'ripley': 100,
        'centrality': 20,
        'roe': 50
    }

    recommended = min_samples.get(statistic_type, 30)

    result = {
        'adequate': n_samples >= recommended,
        'n_samples': n_samples,
        'recommended_min': recommended,
        'warning': None
    }

    if n_samples < recommended:
        result['warning'] = (
            f"Sample size ({n_samples}) is below recommended minimum ({recommended}) "
            f"for {statistic_type}. Results may be unreliable."
        )

    return result


def infer_spatial_platform(adata) -> str:
    """
    Infer the spatial transcriptomics platform from data characteristics.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data

    Returns
    -------
    str
        Inferred platform name
    """
    n_obs = adata.n_obs
    coords = adata.obsm.get('spatial', None)

    if coords is None:
        return "unknown"

    # Check coordinate ranges and patterns
    coord_range = np.ptp(coords, axis=0)  # peak-to-peak (max - min)

    # Visium typically has ~3000-5000 spots in a hexagonal pattern
    if 2000 <= n_obs <= 6000 and coord_range[0] / coord_range[1] < 2:
        # Check if coordinates suggest hexagonal packing
        return "visium"

    # Visium HD has many more spots (e.g., 100k+)
    elif n_obs > 50000:
        return "visium_hd"

    # Stereo-seq has very high density in square grid
    elif n_obs > 10000 and hasattr(adata, 'obs') and 'bin_size' in adata.obs.columns:
        return "stereoseq"

    # Slide-seq has circular pattern
    elif n_obs > 10000:
        return "slideseq_or_highres"

    return "unknown"


def suggest_neighbors(adata) -> dict:
    """
    Suggest appropriate number of neighbors based on platform.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data

    Returns
    -------
    dict
        Dictionary with 'n_neighbors', 'platform', 'rationale'
    """
    platform = infer_spatial_platform(adata)

    recommendations = {
        'visium': {
            'n_neighbors': 6,
            'rationale': 'Hexagonal grid has 6 natural neighbors'
        },
        'visium_hd': {
            'n_neighbors': 8,
            'rationale': 'High density data, more neighbors needed for context'
        },
        'stereoseq': {
            'n_neighbors': 4,
            'rationale': 'Square grid - 4 immediate neighbors (8 with diagonals)'
        },
        'slideseq_or_highres': {
            'n_neighbors': 10,
            'rationale': 'Near-single-cell resolution, use distance-based neighbors'
        },
        'unknown': {
            'n_neighbors': 6,
            'rationale': 'Default recommendation - adjust based on visualization'
        }
    }

    result = recommendations.get(platform, recommendations['unknown'])
    result['platform'] = platform

    return result


def convert_to_spatial_weights(adata, k: int = 6):
    """
    Convert spatial neighbors to spatial weights matrix for pysal/esda.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    k : int, default=6
        Number of neighbors

    Returns
    -------
    libpysal.weights.W
        Spatial weights object
    """
    try:
        from libpysal.weights import KNN
    except ImportError:
        raise ImportError("libpysal is required for spatial weights. Install: pip install libpysal")

    coords = adata.obsm['spatial']
    weights = KNN(coords, k=k)

    return weights


def compute_spatial_weights_matrix(adata, n_neighbors: int = 6, method: str = 'knn'):
    """
    Compute spatial weights matrix.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    n_neighbors : int, default=6
        Number of neighbors
    method : str, default='knn'
        Method to construct weights ('knn' or 'distance')

    Returns
    -------
    scipy.sparse matrix
        Spatial weights matrix
    """
    from sklearn.neighbors import kneighbors_graph

    coords = adata.obsm['spatial']

    if method == 'knn':
        weights = kneighbors_graph(coords, n_neighbors=n_neighbors, mode='connectivity')
    elif method == 'distance':
        # Use radius-based neighbors
        from sklearn.neighbors import radius_neighbors_graph
        # Estimate radius from k-th nearest neighbor distance
        from sklearn.neighbors import NearestNeighbors
        nbrs = NearestNeighbors(n_neighbors=n_neighbors + 1).fit(coords)
        distances, _ = nbrs.kneighbors(coords)
        radius = np.median(distances[:, -1])  # median k-th neighbor distance
        weights = radius_neighbors_graph(coords, radius=radius, mode='connectivity')
    else:
        raise ValueError(f"Unknown method: {method}")

    return weights
