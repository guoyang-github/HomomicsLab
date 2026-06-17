"""
Utility functions for enrichment analysis.

Author: Yang Guo
Date: 2026-03-31
"""

from typing import List, Optional
import pandas as pd
import numpy as np
from anndata import AnnData


def prepare_gene_list(
    adata: AnnData,
    group: Optional[str] = None,
    key: str = 'rank_genes_groups',
    pval_cutoff: float = 0.05,
    log2fc_cutoff: float = 0.25,
    top_n: Optional[int] = None,
    direction: str = 'both',
) -> List[str]:
    """
    Prepare gene list from DEG results for enrichment analysis.

    Parameters
    ----------
    adata : AnnData
        Data with rank_genes_groups results
    group : str, optional
        Specific group. If None, uses first group.
    key : str, default='rank_genes_groups'
        Key in adata.uns
    pval_cutoff : float, default=0.05
        Adjusted p-value cutoff
    log2fc_cutoff : float, default=0.25
        Log2 fold change cutoff
    top_n : int, optional
        Take top N genes instead of using cutoffs
    direction : str, default='both'
        Direction of regulation ('up', 'down', or 'both')

    Returns
    -------
    List[str]
        List of gene symbols
    """
    if key not in adata.uns:
        raise KeyError(f"'{key}' not found in adata.uns")

    results = adata.uns[key]

    if group is None:
        group = results['names'].dtype.names[0]

    genes = results['names'][group]
    logfc = results['logfoldchanges'][group]
    pvals_adj = results['pvals_adj'][group]

    if top_n is not None:
        if direction == 'up':
            # Filter to upregulated first, then take top N
            up_mask = logfc > 0
            up_genes = genes[up_mask]
            gene_list = up_genes[:top_n].tolist()
        elif direction == 'down':
            down_mask = logfc < 0
            down_genes = genes[down_mask]
            gene_list = down_genes[:top_n].tolist()
        else:  # both
            gene_list = genes[:top_n].tolist()
    else:
        if direction == 'up':
            mask = (pvals_adj < pval_cutoff) & (logfc > log2fc_cutoff)
        elif direction == 'down':
            mask = (pvals_adj < pval_cutoff) & (logfc < -log2fc_cutoff)
        else:  # both
            mask = (pvals_adj < pval_cutoff) & (abs(logfc) > log2fc_cutoff)

        gene_list = genes[mask].tolist()

    return gene_list


def prepare_ranked_list(
    adata: AnnData,
    group: str,
    key: str = 'rank_genes_groups',
    metric: str = 'logfoldchanges',
) -> pd.Series:
    """
    Prepare ranked gene list for GSEA.

    Parameters
    ----------
    adata : AnnData
        Data with DEG results
    group : str
        Group name
    key : str, default='rank_genes_groups'
        Key in adata.uns
    metric : str, default='logfoldchanges'
        Metric to rank by

    Returns
    -------
    pd.Series
        Gene names as index, metric values as values
    """
    if key not in adata.uns:
        raise KeyError(f"'{key}' not found in adata.uns")

    results = adata.uns[key]
    genes = results['names'][group]
    scores = results[metric][group]

    ranked = pd.Series(scores, index=genes)

    # Drop NaN/Inf values — common after sc.pp.scale() causes log2(negative) in rank_genes_groups
    ranked = ranked.replace([np.inf, -np.inf], np.nan).dropna()
    if len(ranked) == 0:
        raise ValueError(f"No valid ranking values for group '{group}' after removing NaN/Inf. "
                         "This often happens when rank_genes_groups is run on scaled data. "
                         "Re-run rank_genes_groups on unscaled (log-normalized) data.")

    ranked = ranked.sort_values(ascending=False)

    return ranked


def filter_gene_sets(
    gene_sets: dict,
    min_genes: int = 5,
    max_genes: int = 500,
    background_genes: Optional[List[str]] = None,
    min_coverage: float = 0.1,
) -> dict:
    """
    Filter gene sets by size and coverage.

    Parameters
    ----------
    gene_sets : dict
        Dictionary of gene sets
    min_genes : int, default=5
        Minimum gene set size
    max_genes : int, default=500
        Maximum gene set size
    background_genes : List[str], optional
        Background gene list for coverage check
    min_coverage : float, default=0.1
        Minimum fraction of genes that must be in background

    Returns
    -------
    dict
        Filtered gene sets
    """
    filtered = {}

    for name, genes in gene_sets.items():
        # Size filter
        if len(genes) < min_genes or len(genes) > max_genes:
            continue

        # Coverage filter
        if background_genes is not None:
            coverage = len(set(genes) & set(background_genes)) / len(genes)
            if coverage < min_coverage:
                continue

        filtered[name] = genes

    return filtered


def load_gene_set(
    filepath: str,
    format: str = 'auto',
) -> dict:
    """
    Load gene sets from file.

    Supports GMT, GMX, and JSON formats.

    Parameters
    ----------
    filepath : str
        Path to gene set file
    format : str, default='auto'
        File format ('gmt', 'gmx', 'json', or 'auto')

    Returns
    -------
    dict
        Gene sets dictionary
    """
    if format == 'auto':
        if filepath.endswith('.gmt'):
            format = 'gmt'
        elif filepath.endswith('.gmx'):
            format = 'gmx'
        elif filepath.endswith('.json'):
            format = 'json'
        else:
            raise ValueError("Cannot detect format. Please specify.")

    gene_sets = {}

    if format == 'gmt':
        with open(filepath) as f:
            for line in f:
                parts = line.strip().split('\t')
                name = parts[0]
                genes = parts[2:]  # Skip description (parts[1])
                gene_sets[name] = genes

    elif format == 'gmx':
        # GMX: tab-separated, first row = set names, subsequent rows = genes
        df = pd.read_csv(filepath, sep='\t')
        for col in df.columns:
            genes = df[col].dropna().astype(str).tolist()
            # Filter out empty strings
            genes = [g for g in genes if g]
            if genes:
                gene_sets[col] = genes

    elif format == 'json':
        import json
        with open(filepath) as f:
            gene_sets = json.load(f)

    return gene_sets
