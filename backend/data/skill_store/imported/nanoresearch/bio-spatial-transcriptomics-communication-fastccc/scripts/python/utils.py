"""Utility functions for FastCCC cell-cell communication analysis.

This module provides helper functions for data preparation,
result interpretation, and analysis utilities.
"""

import os
import re
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData
from typing import Optional, Union, List, Dict, Any, Tuple, Set
from pathlib import Path
from collections import defaultdict


def check_lr_gene_overlap(
    adata: AnnData,
    database_file_path: str,
    convert_type: str = 'hgnc_symbol'
) -> Dict[str, Any]:
    """Check gene overlap between data and LR database.

    Args:
        adata: AnnData object
        database_file_path: Path to LR interaction database
        convert_type: Gene ID type in database

    Returns:
        Dictionary with overlap statistics
    """
    try:
        from fastccc import preprocess
    except ImportError:
        raise ImportError("FastCCC not installed.")

    # Load gene table from database
    gene_table = pd.read_csv(os.path.join(database_file_path, 'gene_table.csv'))
    protein_table = pd.read_csv(os.path.join(database_file_path, 'protein_table.csv'))
    gene_table = gene_table.merge(protein_table, left_on='protein_id', right_on='id_protein')

    db_genes = set(gene_table[convert_type].unique())
    data_genes = set(adata.var_names)

    # Case-insensitive overlap
    db_genes_upper = set(g.upper() for g in db_genes)
    data_genes_upper = set(g.upper() for g in data_genes)

    overlap = db_genes_upper & data_genes_upper

    return {
        'n_data_genes': len(data_genes),
        'n_db_genes': len(db_genes),
        'n_overlap': len(overlap),
        'overlap_fraction': len(overlap) / len(db_genes) if db_genes else 0,
        'overlap_genes': list(overlap),
        'data_only_genes': list(data_genes - db_genes),
        'db_only_genes': list(db_genes - data_genes)
    }


def get_database_info(database_file_path: str) -> Dict[str, Any]:
    """Get information about LR interaction database.

    Args:
        database_file_path: Path to database directory

    Returns:
        Dictionary with database information
    """
    try:
        from fastccc import preprocess
        interactions = preprocess.get_interactions(database_file_path)
    except ImportError:
        raise ImportError("FastCCC not installed.")

    # Count interactions
    n_interactions = len(interactions)

    # Count unique ligands and receptors
    ligands = set(interactions['multidata_1_id'].unique())
    receptors = set(interactions['multidata_2_id'].unique())

    # Get gene info
    gene_table = pd.read_csv(os.path.join(database_file_path, 'gene_table.csv'))
    n_genes = gene_table['protein_id'].nunique()

    return {
        'n_interactions': n_interactions,
        'n_ligands': len(ligands),
        'n_receptors': len(receptors),
        'n_genes': n_genes,
        'database_name': os.path.basename(database_file_path)
    }


def summarize_fastccc_results(
    pvals: pd.DataFrame,
    interactions_strength: pd.DataFrame,
    pval_threshold: float = 0.05
) -> Dict[str, Any]:
    """Generate summary statistics for FastCCC results.

    Args:
        pvals: DataFrame with p-values
        interactions_strength: DataFrame with interaction strengths
        pval_threshold: P-value threshold for significance

    Returns:
        Dictionary with summary statistics
    """
    sig_mask = pvals < pval_threshold

    summary = {
        'n_cell_pairs': pvals.shape[0],
        'n_interactions': pvals.shape[1],
        'n_significant': sig_mask.sum().sum(),
        'significance_rate': sig_mask.sum().sum() / (pvals.shape[0] * pvals.shape[1]),
        'mean_strength': interactions_strength.values.mean(),
        'median_strength': np.median(interactions_strength.values),
        'significant_by_cellpair': sig_mask.sum(axis=1).to_dict(),
        'significant_by_interaction': sig_mask.sum(axis=0).to_dict()
    }

    return summary


def filter_interactions(
    pvals: pd.DataFrame,
    interactions_strength: pd.DataFrame,
    pval_threshold: float = 0.05,
    min_strength: Optional[float] = None,
    cell_pairs: Optional[List[str]] = None,
    interactions: Optional[List[str]] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Filter interactions by various criteria.

    Args:
        pvals: DataFrame with p-values
        interactions_strength: DataFrame with interaction strengths
        pval_threshold: P-value threshold
        min_strength: Minimum interaction strength
        cell_pairs: List of cell pairs to include
        interactions: List of interaction IDs to include

    Returns:
        Tuple of filtered (pvals, interactions_strength) DataFrames
    """
    pvals_filtered = pvals.copy()
    strength_filtered = interactions_strength.copy()

    # Filter by cell pairs
    if cell_pairs is not None:
        pvals_filtered = pvals_filtered.loc[pvals_filtered.index.intersection(cell_pairs)]
        strength_filtered = strength_filtered.loc[strength_filtered.index.intersection(cell_pairs)]

    # Filter by interactions
    if interactions is not None:
        pvals_filtered = pvals_filtered[pvals_filtered.columns.intersection(interactions)]
        strength_filtered = strength_filtered[strength_filtered.columns.intersection(interactions)]

    # Filter by p-value and strength
    if min_strength is not None:
        strength_mask = strength_filtered >= min_strength
        pvals_filtered = pvals_filtered.where(strength_mask, other=1.0)

    return pvals_filtered, strength_filtered


def get_top_cell_pairs(
    pvals: pd.DataFrame,
    interactions_strength: pd.DataFrame,
    n_top: int = 10,
    by: str = 'n_significant',
    pval_threshold: float = 0.05
) -> pd.DataFrame:
    """Get top cell type pairs by number of significant interactions.

    Args:
        pvals: DataFrame with p-values
        interactions_strength: DataFrame with interaction strengths
        n_top: Number of top pairs to return
        by: Metric to use ('n_significant', 'mean_strength', 'max_strength')
        pval_threshold: P-value threshold

    Returns:
        DataFrame with top cell pairs
    """
    results = []

    for cell_pair in pvals.index:
        pair_pvals = pvals.loc[cell_pair]
        pair_strength = interactions_strength.loc[cell_pair]

        n_sig = (pair_pvals < pval_threshold).sum()
        mean_strength = pair_strength.mean()
        max_strength = pair_strength.max()

        results.append({
            'cell_pair': cell_pair,
            'n_significant': n_sig,
            'mean_strength': mean_strength,
            'max_strength': max_strength
        })

    results_df = pd.DataFrame(results)

    if by == 'n_significant':
        results_df = results_df.nlargest(n_top, 'n_significant')
    elif by == 'mean_strength':
        results_df = results_df.nlargest(n_top, 'mean_strength')
    elif by == 'max_strength':
        results_df = results_df.nlargest(n_top, 'max_strength')

    return results_df


def extract_ligand_receptor_names(
    interaction_ids: List[str],
    database_file_path: str
) -> pd.DataFrame:
    """Extract ligand and receptor gene names from interaction IDs.

    Args:
        interaction_ids: List of interaction IDs
        database_file_path: Path to database

    Returns:
        DataFrame with ligand and receptor names
    """
    try:
        from fastccc import preprocess
        interactions = preprocess.get_interactions(database_file_path)
    except ImportError:
        raise ImportError("FastCCC not installed.")

    # Load gene mapping
    gene_table = pd.read_csv(os.path.join(database_file_path, 'gene_table.csv'))
    protein_table = pd.read_csv(os.path.join(database_file_path, 'protein_table.csv'))
    gene_table = gene_table.merge(protein_table, left_on='protein_id', right_on='id_protein')

    id_to_symbol = dict(zip(gene_table['protein_multidata_id'], gene_table['hgnc_symbol']))

    results = []
    for iid in interaction_ids:
        if iid in interactions.index:
            ligand_id = interactions.loc[iid, 'multidata_1_id']
            receptor_id = interactions.loc[iid, 'multidata_2_id']

            results.append({
                'interaction_id': iid,
                'ligand': id_to_symbol.get(ligand_id, ligand_id),
                'receptor': id_to_symbol.get(receptor_id, receptor_id)
            })

    return pd.DataFrame(results)


def estimate_fastccc_runtime(
    n_cells: int,
    n_celltypes: int,
    n_interactions: int = 2000,
    use_cauchy: bool = False,
    n_methods: int = 12
) -> Dict[str, str]:
    """Estimate FastCCC runtime based on dataset size.

    Args:
        n_cells: Number of cells
        n_celltypes: Number of cell types
        n_interactions: Number of interactions in database
        use_cauchy: Whether using Cauchy combination
        n_methods: Number of methods for Cauchy combination

    Returns:
        Dictionary with time estimates
    """
    # Rough estimates based on typical performance
    base_time = 1  # minute base time
    cell_factor = n_cells / 1000  # per 1000 cells
    celltype_factor = (n_celltypes * n_celltypes) / 100  # cell type pairs

    total_minutes = base_time + cell_factor * 0.5 + celltype_factor * 0.3

    if use_cauchy:
        total_minutes *= n_methods * 0.3  # Each method adds ~30% time

    if total_minutes < 1:
        time_str = f"{int(total_minutes * 60)} seconds"
    elif total_minutes < 60:
        time_str = f"{int(total_minutes)} minutes"
    else:
        hours = int(total_minutes // 60)
        mins = int(total_minutes % 60)
        time_str = f"{hours}h {mins}m"

    return {
        'estimated_total': time_str,
        'per_cell': f"~{total_minutes * 60 / n_cells:.2f} seconds",
        'notes': 'Estimates assume 8GB RAM. Larger datasets may take longer due to I/O.'
    }


def prepare_anndata_for_fastccc(
    adata: AnnData,
    groupby: str,
    min_cells: int = 10
) -> AnnData:
    """Prepare AnnData for FastCCC analysis.

    Args:
        adata: Input AnnData
        groupby: Cell type column
        min_cells: Minimum cells per cell type

    Returns:
        Filtered AnnData
    """
    adata = adata.copy()

    # Filter cell types with too few cells
    cell_counts = adata.obs[groupby].value_counts()
    valid_celltypes = cell_counts[cell_counts >= min_cells].index

    adata = adata[adata.obs[groupby].isin(valid_celltypes)]

    # Ensure sparse matrix
    if not hasattr(adata.X, 'toarray'):
        from scipy.sparse import csr_matrix
        adata.X = csr_matrix(adata.X)

    # Filter genes with no expression
    sc.pp.filter_genes(adata, min_cells=1)

    return adata


def create_interaction_network_data(
    pvals: pd.DataFrame,
    interactions_strength: pd.DataFrame,
    pval_threshold: float = 0.05
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Create node and edge DataFrames for network visualization.

    Args:
        pvals: DataFrame with p-values
        interactions_strength: DataFrame with interaction strengths
        pval_threshold: P-value threshold

    Returns:
        Tuple of (node_df, edge_df) for network visualization
    """
    try:
        from fastccc import visualize as fastccc_viz
    except ImportError:
        raise ImportError("FastCCC not installed.")

    # This would use fastccc.visualize functions
    # For now, create basic network data

    nodes = set()
    edges = []

    sig_mask = pvals < pval_threshold

    for cell_pair in sig_mask.index:
        source, target = cell_pair.split('|')
        nodes.add(source)
        nodes.add(target)

        # Count significant interactions
        n_sig = sig_mask.loc[cell_pair].sum()
        total_strength = interactions_strength.loc[cell_pair][sig_mask.loc[cell_pair]].sum()

        edges.append({
            'source': source,
            'target': target,
            'weight': n_sig,
            'strength': total_strength
        })

    node_df = pd.DataFrame({'id': list(nodes)})
    edge_df = pd.DataFrame(edges)

    return node_df, edge_df


def export_results_to_cellchat_format(
    pvals: pd.DataFrame,
    interactions_strength: pd.DataFrame,
    output_dir: str,
    database_file_path: Optional[str] = None
) -> Dict[str, str]:
    """Export FastCCC results to CellChat-compatible format.

    Args:
        pvals: DataFrame with p-values
        interactions_strength: DataFrame with interaction strengths
        output_dir: Output directory
        database_file_path: Path to database for annotation

    Returns:
        Dictionary with paths to exported files
    """
    os.makedirs(output_dir, exist_ok=True)
    exported = {}

    # Export as CSV
    pvals.to_csv(os.path.join(output_dir, 'pvals.csv'))
    interactions_strength.to_csv(os.path.join(output_dir, 'interaction_strength.csv'))

    exported['pvals'] = os.path.join(output_dir, 'pvals.csv')
    exported['strength'] = os.path.join(output_dir, 'interaction_strength.csv')

    # Create summary
    summary = summarize_fastccc_results(pvals, interactions_strength)
    summary_df = pd.DataFrame([summary])
    summary_df.to_csv(os.path.join(output_dir, 'summary.csv'), index=False)
    exported['summary'] = os.path.join(output_dir, 'summary.csv')

    return exported


def validate_fastccc_installation() -> Dict[str, Any]:
    """Validate FastCCC installation and dependencies.

    Returns:
        Dictionary with validation results
    """
    results = {
        'fastccc_installed': False,
        'scanpy_installed': False,
        'python_version': None,
        'errors': [],
        'warnings': []
    }

    import sys
    results['python_version'] = sys.version

    # Check FastCCC
    try:
        import fastccc
        results['fastccc_installed'] = True
        results['fastccc_version'] = getattr(fastccc, '__version__', 'unknown')
    except ImportError:
        results['errors'].append("FastCCC not installed. Install with: pip install fastccc")

    # Check scanpy
    try:
        import scanpy
        results['scanpy_installed'] = True
        results['scanpy_version'] = scanpy.__version__
    except ImportError:
        results['errors'].append("scanpy not installed")

    # Check scipy (for sparse matrices)
    try:
        import scipy
        results['scipy_installed'] = True
    except ImportError:
        results['errors'].append("scipy not installed")

    return results
