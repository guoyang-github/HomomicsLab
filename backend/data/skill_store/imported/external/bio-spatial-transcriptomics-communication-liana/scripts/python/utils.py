"""
Utility Functions for LIANA+ Cell-Cell Communication

Minimal helpers with real added value.
For most operations, use native pandas / scanpy / liana functions directly.

Author: Yang Guo
Date: 2026-05-14
"""

import numpy as np
import pandas as pd
import scanpy as sc
from typing import List, Dict, Optional, Union, Tuple
from scipy.sparse import issparse


def validate_anndata(
    adata: sc.AnnData,
    require_cell_types: bool = True,
    groupby: str = 'cell_type'
) -> bool:
    """
    Validate AnnData object for LIANA analysis.

    Parameters
    ----------
    adata : sc.AnnData
        Input data
    require_cell_types : bool, default=True
        Whether to check for cell type annotations
    groupby : str, default='cell_type'
        Column name to check

    Returns
    -------
    bool
        True if valid

    Raises
    ------
    TypeError, ValueError
        If validation fails
    """
    if not isinstance(adata, sc.AnnData):
        raise TypeError("Input must be an AnnData object")

    if adata.n_obs == 0 or adata.n_vars == 0:
        raise ValueError("AnnData object is empty")

    if require_cell_types:
        if groupby not in adata.obs.columns:
            available = list(adata.obs.columns)
            raise ValueError(
                f"'{groupby}' not found in adata.obs. Available: {available}"
            )

    return True


def filter_cell_types(
    adata: sc.AnnData,
    min_cells: int = 10,
    min_expr_genes: int = 50,
    groupby: str = 'cell_type',
    verbose: bool = True
) -> sc.AnnData:
    """
    Filter cell types by quality criteria.

    Parameters
    ----------
    adata : sc.AnnData
        Input data
    min_cells : int, default=10
        Min cells per cell type
    min_expr_genes : int, default=50
        Min expressed genes per cell
    groupby : str, default='cell_type'
        Cell type column
    verbose : bool, default=True
        Print progress

    Returns
    -------
    sc.AnnData
        Filtered copy
    """
    sc.pp.filter_cells(adata, min_genes=min_expr_genes)

    cell_counts = adata.obs[groupby].value_counts()
    valid_types = cell_counts[cell_counts >= min_cells].index

    if verbose:
        removed = set(cell_counts.index) - set(valid_types)
        print(f"Cell type filtering: {len(cell_counts)} -> {len(valid_types)} types")
        if removed:
            print(f"  Removed: {removed}")

    mask = adata.obs[groupby].isin(valid_types)
    return adata[mask].copy()


def subset_cell_types(
    adata: sc.AnnData,
    cell_types: List[str],
    groupby: str = 'cell_type'
) -> sc.AnnData:
    """
    Subset AnnData to specific cell types.

    Parameters
    ----------
    adata : sc.AnnData
        Input data
    cell_types : List[str]
        Cell types to keep
    groupby : str, default='cell_type'
        Cell type column

    Returns
    -------
    sc.AnnData
        Subsetted copy
    """
    mask = adata.obs[groupby].isin(cell_types)
    return adata[mask].copy()


def get_interaction_matrix(
    liana_res: pd.DataFrame,
    value_col: str = 'magnitude_rank',
    fill_value: float = 0.0
) -> pd.DataFrame:
    """
    Convert LIANA results to source x target interaction matrix.

    Parameters
    ----------
    liana_res : pd.DataFrame
        LIANA results
    value_col : str, default='magnitude_rank'
        Column for matrix values
    fill_value : float, default=0.0
        Fill value for missing pairs

    Returns
    -------
    pd.DataFrame
        Matrix (sources as rows, targets as columns)
    """
    aggregated = liana_res.groupby(['source', 'target'])[value_col].mean().reset_index()
    matrix = aggregated.pivot(index='source', columns='target', values=value_col)
    return matrix.fillna(fill_value)
