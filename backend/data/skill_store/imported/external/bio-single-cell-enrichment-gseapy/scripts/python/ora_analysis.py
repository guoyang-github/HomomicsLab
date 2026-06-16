"""
Over-Representation Analysis (ORA) using gseapy.

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


def run_enrichr(
    gene_list: List[str],
    gene_sets: Union[str, List[str]] = 'KEGG_2021_Human',
    organism: str = 'human',
    outdir: Optional[str] = None,
    cutoff: float = 0.05,
) -> pd.DataFrame:
    """
    Run Enrichr ORA analysis on a gene list.

    Parameters
    ----------
    gene_list : List[str]
        List of gene symbols to test for enrichment
    gene_sets : str or List[str], default='KEGG_2021_Human'
        Gene set database(s) to query.
        Popular options: 'KEGG_2021_Human', 'GO_Biological_Process_2021',
        'Reactome_2022', 'MSigDB_Hallmark_2020'
    organism : str, default='human'
        Organism for gene set databases ('human' or 'mouse')
    outdir : str, optional
        Directory to save results. If None, results not saved to file.
    cutoff : float, default=0.05
        Adjusted p-value cutoff for significant results

    Returns
    -------
    pd.DataFrame
        Enrichment results with columns:
        - Term: pathway/gene set name
        - Overlap: overlap ratio (e.g., "5/100")
        - P-value: raw p-value
        - Adjusted P-value: corrected p-value
        - Odds Ratio: enrichment strength
        - Genes: overlapping genes

    Examples
    --------
    >>> gene_list = ['TP53', 'BRCA1', 'EGFR', 'PTEN', 'MYC']
    >>> results = run_enrichr(gene_list, gene_sets='KEGG_2021_Human')
    >>> print(results[results['Adjusted P-value'] < 0.05])
    """
    if not gene_list:
        raise ValueError("gene_list cannot be empty")

    results = gp.enrichr(
        gene_list=gene_list,
        gene_sets=gene_sets,
        organism=organism,
        outdir=outdir,
        cutoff=cutoff,
    )

    return results.results


def run_ora(
    adata: AnnData,
    deg_key: str = 'rank_genes_groups',
    group: Optional[str] = None,
    gene_sets: Union[str, List[str]] = 'KEGG_2021_Human',
    pval_cutoff: float = 0.05,
    log2fc_cutoff: float = 0.25,
    top_n: Optional[int] = None,
) -> pd.DataFrame:
    """
    Run ORA on DEG results from scanpy's rank_genes_groups.

    Parameters
    ----------
    adata : AnnData
        AnnData object with rank_genes_groups results in .uns
    deg_key : str, default='rank_genes_groups'
        Key in adata.uns containing DEG results
    group : str, optional
        Specific group to analyze. If None, uses first group.
    gene_sets : str or List[str], default='KEGG_2021_Human'
        Gene set database(s) for enrichment
    pval_cutoff : float, default=0.05
        Adjusted p-value cutoff for DEG selection
    log2fc_cutoff : float, default=0.25
        Log2 fold change cutoff for DEG selection
    top_n : int, optional
        Use top N genes ranked by log2FC instead of cutoff

    Returns
    -------
    pd.DataFrame
        Enrichment results

    Examples
    --------
    >>> # After running sc.tl.rank_genes_groups()
    >>> results = run_ora(adata, group='cluster_0', gene_sets='GO_Biological_Process_2021')
    """
    if deg_key not in adata.uns:
        raise KeyError(f"'{deg_key}' not found in adata.uns. Run sc.tl.rank_genes_groups() first.")

    deg_results = adata.uns[deg_key]

    if group is None:
        group = deg_results['names'].dtype.names[0]

    # Extract gene names and scores
    genes = deg_results['names'][group]
    logfc = deg_results['logfoldchanges'][group]
    pvals_adj = deg_results['pvals_adj'][group]

    # Select significant genes
    if top_n is not None:
        gene_list = genes[:top_n].tolist()
    else:
        mask = (pvals_adj < pval_cutoff) & (abs(logfc) > log2fc_cutoff)
        gene_list = genes[mask].tolist()

    if len(gene_list) < 5:
        warnings.warn(f"Only {len(gene_list)} genes selected. Need at least 5 for enrichment.")
        return pd.DataFrame()

    return run_enrichr(gene_list, gene_sets=gene_sets)


def run_ora_per_cluster(
    adata: AnnData,
    gene_sets: Union[str, List[str]] = 'KEGG_2021_Human',
    pval_cutoff: float = 0.05,
) -> Dict[str, pd.DataFrame]:
    """
    Run ORA for all clusters.

    Parameters
    ----------
    adata : AnnData
        Data with rank_genes_groups results
    gene_sets : str or List[str], default='KEGG_2021_Human'
        Gene set database
    pval_cutoff : float, default=0.05
        Adjusted p-value cutoff

    Returns
    -------
    Dict[str, pd.DataFrame]
        Dictionary mapping cluster names to enrichment results
    """
    if 'rank_genes_groups' not in adata.uns:
        raise ValueError("Run sc.tl.rank_genes_groups() first")

    groups = adata.uns['rank_genes_groups']['names'].dtype.names
    results = {}

    for group in groups:
        try:
            results[group] = run_ora(
                adata,
                group=group,
                gene_sets=gene_sets,
                pval_cutoff=pval_cutoff,
            )
        except Exception as e:
            warnings.warn(f"Failed for group {group}: {e}")
            results[group] = pd.DataFrame()

    return results
