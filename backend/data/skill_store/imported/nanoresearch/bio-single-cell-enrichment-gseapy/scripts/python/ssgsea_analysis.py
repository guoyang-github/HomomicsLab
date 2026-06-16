"""
Single-Sample GSEA (ssGSEA) for per-cell pathway scoring using gseapy.

Author: Yang Guo
Date: 2026-03-31
"""

import warnings
from typing import Optional, List, Dict, Union
import pandas as pd
import numpy as np
import scanpy as sc
from anndata import AnnData
import gseapy as gp


def run_ssgsea(
    adata: AnnData,
    gene_sets: Union[str, List[str], Dict[str, List[str]]] = 'KEGG_2021_Human',
    layer: Optional[str] = None,
    key_added: str = 'X_ssgsea',
    min_size: int = 5,
    max_size: int = 500,
    sample_norm_method: str = 'rank',
    weight: float = 0.25,
    threads: int = 4,
    inplace: bool = True,
    verbose: bool = True,
) -> Optional[AnnData]:
    """
    Run ssGSEA to compute per-cell pathway enrichment scores.

    This adds pathway activity scores to adata.obsm[key_added] for downstream
    visualization and analysis.

    Parameters
    ----------
    adata : AnnData
        Input single-cell data. Should contain normalized expression.
    gene_sets : str, List[str], or Dict[str, List[str]]
        Gene set database name(s) or custom gene sets dictionary.
        Examples: 'KEGG_2021_Human', 'MSigDB_Hallmark_2020',
        {'My_Set': ['Gene1', 'Gene2', ...]}
    layer : str, optional
        Layer to use. If None, uses adata.X.
    key_added : str, default='X_ssgsea'
        Key in adata.obsm to store ssGSEA scores.
    min_size : int, default=5
        Minimum gene set size.
    max_size : int, default=500
        Maximum gene set size.
    sample_norm_method : str, default='rank'
        Sample normalization method ('rank' or 'log_rank').
    weight : float, default=0.25
        Weighted score type for enrichment score (0=classic, 0.25=default).
    threads : int, default=4
        Number of threads for parallel processing.
    inplace : bool, default=True
        If True, modify adata in place.
    verbose : bool, default=True
        Print progress.

    Returns
    -------
    AnnData or None
        If inplace=False, returns modified copy with ssGSEA scores in
        adata.obsm[key_added] and pathway names in adata.uns[f'{key_added}_names'].

    Examples
    --------
    >>> # Using built-in gene sets
    >>> run_ssgsea(adata, gene_sets='MSigDB_Hallmark_2020')
    >>> print(adata.obsm['X_ssgsea'].shape)  # (n_cells, n_pathways)
    >>> print(adata.uns['X_ssgsea_names'][:5])  # First 5 pathway names

    >>> # Using custom gene sets
    >>> custom_sets = {
    ...     'Apoptosis': ['BAX', 'BAK1', 'CASP3', 'CASP9'],
    ...     'Cell_Cycle': ['CCND1', 'CDK4', 'CDK6', 'E2F1']
    ... }
    >>> run_ssgsea(adata, gene_sets=custom_sets, key_added='X_custom')

    >>> # Visualization
    >>> sc.pp.neighbors(adata, use_rep='X_ssgsea')
    >>> sc.tl.umap(adata)
    >>> sc.pl.umap(adata, color=['Hallmark_TNFA_Signaling_via_NFKB'])
    """
    if not inplace:
        adata = adata.copy()

    if verbose:
        print("Running ssGSEA...")

    # Get expression matrix
    if layer is not None:
        expr = adata.layers[layer]
    else:
        expr = adata.X

    # Convert to DataFrame (genes x cells)
    if hasattr(expr, 'toarray'):
        expr_df = pd.DataFrame(
            expr.toarray().T,
            index=adata.var_names,
            columns=adata.obs_names
        )
    else:
        expr_df = pd.DataFrame(
            expr.T,
            index=adata.var_names,
            columns=adata.obs_names
        )

    # Run ssGSEA
    ssgs = gp.ssgsea(
        data=expr_df,
        gene_sets=gene_sets,
        sample_norm_method=sample_norm_method,
        min_size=min_size,
        max_size=max_size,
        weight=weight,
        threads=threads,
        verbose=verbose,
    )

    if ssgs.res2d is None or len(ssgs.res2d) == 0:
        warnings.warn(
            "ssGSEA returned no results. This usually means no gene sets passed "
            "the size filter (min_size={}, max_size={}). Try lowering min_size or "
            "verify gene symbols match your data's var_names.".format(min_size, max_size)
        )
        adata.obsm[key_added] = np.full((adata.n_obs, 0), np.nan)
        adata.uns[f'{key_added}_names'] = []
        return None if inplace else adata

    # Store results
    # GSEApy ssGSEA returns long-format DataFrame in res2d (columns: Name, Term, ES, NES)
    # Pivot to wide format: cells (Name) x pathways (Term)
    ssgsea_matrix = ssgs.res2d.pivot(
        index='Name', columns='Term', values='NES'
    ).reindex(adata.obs_names)

    adata.obsm[key_added] = ssgsea_matrix.values.astype(float)
    adata.uns[f'{key_added}_names'] = ssgsea_matrix.columns.tolist()

    if verbose:
        print(f"ssGSEA complete. Scores stored in adata.obsm['{key_added}']")
        print(f"Pathways: {len(ssgsea_matrix.columns)}")

    return None if inplace else adata


def run_ssgsea_pseudobulk(
    adata: AnnData,
    groupby: str,
    gene_sets: Union[str, List[str]] = 'KEGG_2021_Human',
    layer: Optional[str] = None,
    min_cells: int = 10,
    **kwargs
) -> pd.DataFrame:
    """
    Run ssGSEA on pseudo-bulk aggregated expression.

    Parameters
    ----------
    adata : AnnData
        Input data
    groupby : str
        Column to group by (e.g., 'cell_type', 'condition')
    gene_sets : str or List[str], default='KEGG_2021_Human'
        Gene set database
    layer : str, optional
        Layer to use
    min_cells : int, default=10
        Minimum cells per group for inclusion
    **kwargs
        Additional arguments for gp.ssgsea

    Returns
    -------
    pd.DataFrame
        Pathway scores in long format (columns: Name, Term, ES, NES, ...)

    Examples
    --------
    >>> scores = run_ssgsea_pseudobulk(adata, groupby='cell_type')
    >>> print(scores.head())
    """
    groups = adata.obs[groupby].unique()
    pseudobulk = {}

    for group in groups:
        mask = adata.obs[groupby] == group
        if mask.sum() < min_cells:
            continue

        group_data = adata[mask]
        if layer is not None:
            expr = group_data.layers[layer]
        else:
            expr = group_data.X

        if hasattr(expr, 'toarray'):
            mean_expr = np.array(expr.mean(axis=0)).flatten()
        else:
            mean_expr = expr.mean(axis=0)

        pseudobulk[group] = mean_expr

    pb_df = pd.DataFrame(pseudobulk, index=adata.var_names)

    # Run ssGSEA
    ssgs = gp.ssgsea(
        data=pb_df,
        gene_sets=gene_sets,
        **kwargs
    )

    return ssgs.res2d


def score_pathway_on_umap(
    adata: AnnData,
    pathway: str,
    ssgsea_key: str = 'X_ssgsea',
    cmap: str = 'viridis',
    **kwargs
):
    """
    Visualize a single pathway score on UMAP.

    Parameters
    ----------
    adata : AnnData
        Data with ssGSEA scores
    pathway : str
        Pathway name to visualize
    ssgsea_key : str, default='X_ssgsea'
        Key in adata.obsm containing scores
    cmap : str, default='viridis'
        Colormap
    **kwargs
        Additional arguments for sc.pl.umap

    Examples
    --------
    >>> score_pathway_on_umap(adata, 'Hallmark_TNFA_Signaling_via_NFKB')
    """
    if ssgsea_key not in adata.obsm:
        raise KeyError(f"'{ssgsea_key}' not found in adata.obsm. Run run_ssgsea() first.")

    pathway_names = adata.uns.get(f'{ssgsea_key}_names', [])

    if pathway not in pathway_names:
        # Try case-insensitive match
        pathway_lower = pathway.lower()
        matches = [p for p in pathway_names if pathway_lower in p.lower()]
        if matches:
            pathway = matches[0]
            print(f"Using: {pathway}")
        else:
            raise ValueError(f"Pathway '{pathway}' not found. Available: {pathway_names[:5]}...")

    # Get scores for this pathway
    pathway_idx = pathway_names.index(pathway)
    scores = adata.obsm[ssgsea_key][:, pathway_idx]

    # Add to obs temporarily
    temp_key = f'pathway_score_{pathway.replace(" ", "_")}'
    adata.obs[temp_key] = scores

    # Plot
    sc.pl.umap(adata, color=temp_key, cmap=cmap, **kwargs)

    # Clean up
    del adata.obs[temp_key]


def compare_pathways_across_groups(
    adata: AnnData,
    groupby: str,
    pathways: List[str],
    ssgsea_key: str = 'X_ssgsea',
) -> pd.DataFrame:
    """
    Compare pathway scores across groups.

    Parameters
    ----------
    adata : AnnData
        Data with ssGSEA scores
    groupby : str
        Column for grouping
    pathways : List[str]
        Pathways to compare
    ssgsea_key : str, default='X_ssgsea'
        Key in adata.obsm

    Returns
    -------
    pd.DataFrame
        Mean scores per group per pathway
    """
    pathway_names = adata.uns.get(f'{ssgsea_key}_names', [])
    results = []

    for pathway in pathways:
        if pathway not in pathway_names:
            warnings.warn(f"Pathway '{pathway}' not found")
            continue

        idx = pathway_names.index(pathway)
        scores = adata.obsm[ssgsea_key][:, idx]

        for group in adata.obs[groupby].unique():
            mask = adata.obs[groupby] == group
            mean_score = scores[mask].mean()
            results.append({
                'pathway': pathway,
                'group': group,
                'mean_score': mean_score,
            })

    return pd.DataFrame(results)
