"""
Gene Set Enrichment Analysis (GSEA) using gseapy.

Author: Yang Guo
Date: 2026-03-31
"""

import warnings
from typing import Optional, List, Dict, Union, Tuple
import pandas as pd
import numpy as np
from scipy import sparse

import scanpy as sc
from anndata import AnnData
import gseapy as gp


def prepare_ranked_list(
    adata: AnnData,
    group: str,
    deg_key: str = 'rank_genes_groups',
    ranking_method: str = 'logfoldchanges',
) -> pd.Series:
    """
    Prepare ranked gene list from DEG results.

    Parameters
    ----------
    adata : AnnData
        Data with rank_genes_groups
    group : str
        Cluster/group name
    deg_key : str, default='rank_genes_groups'
        Key in adata.uns
    ranking_method : str, default='logfoldchanges'
        Method to rank genes ('logfoldchanges', 'scores', or '-log10(pvals)')

    Returns
    -------
    pd.Series
        Gene names as index, ranking scores as values
    """
    if deg_key not in adata.uns:
        raise KeyError(f"'{deg_key}' not found in adata.uns")

    deg_results = adata.uns[deg_key]
    genes = deg_results['names'][group]

    if ranking_method == 'logfoldchanges':
        scores = deg_results['logfoldchanges'][group]
    elif ranking_method == 'scores':
        scores = deg_results['scores'][group]
    elif ranking_method == '-log10(pvals)':
        scores = -np.log10(deg_results['pvals'][group] + 1e-300)
    else:
        raise ValueError(f"Unknown ranking_method: {ranking_method}")

    # Create series and sort
    ranked = pd.Series(scores, index=genes)

    # Drop NaN/Inf values — common after sc.pp.scale() causes log2(negative) in rank_genes_groups
    ranked = ranked.replace([np.inf, -np.inf], np.nan).dropna()
    if len(ranked) == 0:
        raise ValueError(f"No valid ranking values for group '{group}' after removing NaN/Inf. "
                         "This often happens when rank_genes_groups is run on scaled data. "
                         "Re-run rank_genes_groups on unscaled (log-normalized) data.")

    ranked = ranked.sort_values(ascending=False)

    return ranked


def run_prerank(
    ranked_list: pd.Series,
    gene_sets: Union[str, List[str]] = 'KEGG_2021_Human',
    permutation_num: int = 100,
    outdir: Optional[str] = None,
    min_size: int = 5,
    max_size: int = 500,
    weight: float = 1.0,
    threads: int = 4,
    seed: int = 42,
) -> gp.Prerank:
    """
    Run preranked GSEA on a pre-sorted gene list.

    Parameters
    ----------
    ranked_list : pd.Series
        Gene rankings (gene names as index, scores as values)
    gene_sets : str or List[str], default='KEGG_2021_Human'
        Gene set database(s)
    permutation_num : int, default=100
        Number of permutations for significance testing
    outdir : str, optional
        Output directory for results
    min_size : int, default=5
        Minimum gene set size
    max_size : int, default=500
        Maximum gene set size
    weight : float, default=1.0
        Weighted score type for enrichment (0=classic, 1=weighted, 1.5, 2)
    threads : int, default=4
        Number of threads for parallel processing
    seed : int, default=42
        Random seed

    Returns
    -------
    Prerank
        GSEApy Prerank object with results

    Examples
    --------
    >>> ranked = pd.Series({'TP53': 5.2, 'BRCA1': 4.8, ...})
    >>> pre_res = run_prerank(ranked, gene_sets='MSigDB_Hallmark_2020')
    >>> print(pre_res.res2d.head())
    """
    pre_res = gp.prerank(
        rnk=ranked_list,
        gene_sets=gene_sets,
        permutation_num=permutation_num,
        outdir=outdir,
        min_size=min_size,
        max_size=max_size,
        weight=weight,
        threads=threads,
        seed=seed,
    )

    return pre_res


def run_gsea(
    adata: AnnData,
    groupby: str,
    group1: str,
    group2: Optional[str] = None,
    gene_sets: Union[str, List[str]] = 'KEGG_2021_Human',
    layer: Optional[str] = None,
    **kwargs
) -> gp.Prerank:
    """
    Run preranked GSEA comparing two groups from single-cell data.

    Computes log2 fold change between two groups and runs prerank GSEA.
    Ranking is based on log2FC.

    Parameters
    ----------
    adata : AnnData
        Input data (normalized, unscaled expression recommended)
    groupby : str
        Column in adata.obs for grouping
    group1 : str
        First group name (treatment)
    group2 : str, optional
        Second group name (control). If None, uses all other cells.
    gene_sets : str or List[str], default='KEGG_2021_Human'
        Gene set database
    layer : str, optional
        Layer to use for expression values
    **kwargs
        Additional arguments for run_prerank (e.g., permutation_num, min_size)

    Returns
    -------
    Prerank
        GSEA results

    Examples
    --------
    >>> results = run_gsea(adata, groupby='condition', group1='treatment', group2='control')
    """
    # Get expression data
    if layer is not None:
        expr = adata.layers[layer]
    else:
        expr = adata.X

    # Subset groups (convert masks to numpy arrays for sparse matrix compatibility)
    mask1 = (adata.obs[groupby] == group1).to_numpy()
    if group2 is not None:
        mask2 = (adata.obs[groupby] == group2).to_numpy()
    else:
        mask2 = ~mask1

    group1_data = expr[mask1]
    group2_data = expr[mask2]

    # Calculate log2 fold change
    g1_mean = np.array(group1_data.mean(axis=0)).flatten()
    g2_mean = np.array(group2_data.mean(axis=0)).flatten()
    log2fc = np.log2((g1_mean + 1) / (g2_mean + 1))

    # Create ranked list
    genes = adata.var_names
    ranked = pd.Series(log2fc, index=genes)
    ranked = ranked.sort_values(ascending=False)

    return run_prerank(ranked, gene_sets=gene_sets, **kwargs)


def run_gsea_per_cluster(
    adata: AnnData,
    cluster_key: str = 'leiden',
    control_cluster: Optional[str] = None,
    gene_sets: Union[str, List[str]] = 'KEGG_2021_Human',
) -> Dict[str, gp.Prerank]:
    """
    Run GSEA for each cluster against control or all others.

    Parameters
    ----------
    adata : AnnData
        Input data
    cluster_key : str, default='leiden'
        Cluster column
    control_cluster : str, optional
        Control cluster. If None, each cluster vs rest.
    gene_sets : str or List[str], default='KEGG_2021_Human'
        Gene set database

    Returns
    -------
    Dict[str, Prerank]
        Results per cluster
    """
    clusters = adata.obs[cluster_key].unique()
    results = {}

    if control_cluster is not None:
        # Each cluster vs control
        for cluster in clusters:
            if cluster != control_cluster:
                try:
                    results[cluster] = run_gsea(
                        adata,
                        groupby=cluster_key,
                        group1=cluster,
                        group2=control_cluster,
                        gene_sets=gene_sets,
                    )
                except Exception as e:
                    warnings.warn(f"GSEA failed for {cluster}: {e}")
    else:
        # Each cluster vs rest
        for cluster in clusters:
            try:
                results[cluster] = run_gsea(
                    adata,
                    groupby=cluster_key,
                    group1=cluster,
                    group2=None,
                    gene_sets=gene_sets,
                )
            except Exception as e:
                warnings.warn(f"GSEA failed for {cluster}: {e}")

    return results
