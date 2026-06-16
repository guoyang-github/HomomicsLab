"""Utility functions for COMPASS metabolic flux analysis.

This module provides helper functions for data preparation,
model exploration, and result interpretation.
"""

import os
import re
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData
from typing import Optional, Union, List, Dict, Any, Tuple, Set
from pathlib import Path


def check_gene_overlap(
    adata: AnnData,
    model_genes: Union[List[str], Set[str]],
    case_sensitive: bool = False
) -> Dict[str, Any]:
    """Check gene overlap between data and metabolic model.

    Args:
        adata: AnnData object
        model_genes: List of genes in the metabolic model
        case_sensitive: Whether to perform case-sensitive matching

    Returns:
        Dictionary with overlap statistics
    """
    data_genes = set(adata.var_names)
    model_genes = set(model_genes)

    if not case_sensitive:
        data_genes_upper = set(g.upper() for g in data_genes)
        model_genes_upper = set(g.upper() for g in model_genes)
        overlap = data_genes_upper & model_genes_upper
        data_only = data_genes_upper - model_genes_upper
        model_only = model_genes_upper - data_genes_upper
    else:
        overlap = data_genes & model_genes
        data_only = data_genes - model_genes
        model_only = model_genes - data_genes

    return {
        'n_data_genes': len(data_genes),
        'n_model_genes': len(model_genes),
        'n_overlap': len(overlap),
        'overlap_fraction': len(overlap) / len(model_genes) if model_genes else 0,
        'data_coverage': len(overlap) / len(data_genes) if data_genes else 0,
        'overlap_genes': list(overlap),
        'data_only_genes': list(data_only),
        'model_only_genes': list(model_only)
    }


def recommend_model(
    species: str = 'human',
    tissue: Optional[str] = None
) -> str:
    """Recommend a metabolic model based on species and tissue.

    Args:
        species: 'human' or 'mouse'
        tissue: Optional tissue type

    Returns:
        Recommended model name
    """
    species = species.lower()

    if species == 'human':
        return 'RECON2_mat'  # Default to RECON2 for human
    elif species in ['mouse', 'mus_musculus']:
        return 'Mouse-GEM'
    else:
        raise ValueError(f"Unknown species: {species}. Choose 'human' or 'mouse'.")


def get_model_catalog() -> pd.DataFrame:
    """Get catalog of available metabolic models.

    Returns:
        DataFrame with model information
    """
    models = [
        {
            'model': 'RECON2_mat',
            'species': 'Homo sapiens',
            'size': 'Large',
            'reactions': '~7440',
            'genes': '~2000',
            'use_case': 'General human metabolism (recommended)',
            'reference': 'Thiele et al., 2013'
        },
        {
            'model': 'RECON1_mat',
            'species': 'Homo sapiens',
            'size': 'Medium',
            'reactions': '~3740',
            'genes': '~1500',
            'use_case': 'Core human metabolism',
            'reference': 'Duarte et al., 2007'
        },
        {
            'model': 'RECON2.2',
            'species': 'Homo sapiens',
            'size': 'Large',
            'reactions': '~7780',
            'genes': '~2100',
            'use_case': 'Updated RECON2 with improved annotations',
            'reference': 'Swainston et al., 2016'
        },
        {
            'model': 'Mouse-GEM',
            'species': 'Mus musculus',
            'size': 'Large',
            'reactions': '~7600',
            'genes': '~1900',
            'use_case': 'General mouse metabolism',
            'reference': ' customized for mouse'
        }
    ]

    return pd.DataFrame(models)


def summarize_compass_results(
    results: Dict[str, pd.DataFrame],
    groupby: Optional[pd.Series] = None
) -> Dict[str, Any]:
    """Generate summary statistics for COMPASS results.

    Args:
        results: Dictionary with COMPASS results
        groupby: Optional grouping for stratified summary

    Returns:
        Dictionary with summary statistics
    """
    summary = {}

    if 'reaction_scores' in results:
        rs = results['reaction_scores']
        summary['reactions'] = {
            'n_reactions': rs.shape[0],
            'n_cells': rs.shape[1],
            'mean_score': rs.values.mean(),
            'median_score': np.median(rs.values),
            'std_score': rs.values.std(),
            'min_score': rs.values.min(),
            'max_score': rs.values.max()
        }

        if groupby is not None:
            summary['reactions']['by_group'] = {}
            for group in groupby.unique():
                group_cells = rs.columns[groupby == group]
                if len(group_cells) > 0:
                    group_scores = rs[group_cells].values
                    summary['reactions']['by_group'][group] = {
                        'n_cells': len(group_cells),
                        'mean_score': group_scores.mean(),
                        'median_score': np.median(group_scores)
                    }

    if 'uptake_scores' in results:
        us = results['uptake_scores']
        summary['uptake'] = {
            'n_metabolites': us.shape[0],
            'mean_score': us.values.mean(),
            'median_score': np.median(us.values)
        }

    if 'secretion_scores' in results:
        ss = results['secretion_scores']
        summary['secretion'] = {
            'n_metabolites': ss.shape[0],
            'mean_score': ss.values.mean(),
            'median_score': np.median(ss.values)
        }

    return summary


def filter_reactions_by_activity(
    reaction_scores: pd.DataFrame,
    min_activity: float = 0.1,
    min_cells: int = 10,
    activity_percentile: Optional[float] = None
) -> pd.DataFrame:
    """Filter reactions by minimum activity level.

    Args:
        reaction_scores: DataFrame with reaction scores
        min_activity: Minimum activity threshold
        min_cells: Minimum number of cells with activity
        activity_percentile: Alternative: use percentile threshold

    Returns:
        Filtered reaction scores DataFrame
    """
    if activity_percentile is not None:
        min_activity = np.percentile(reaction_scores.values, activity_percentile)

    # Count cells above threshold for each reaction
    active_cells = (reaction_scores > min_activity).sum(axis=1)

    # Filter reactions
    active_reactions = active_cells[active_cells >= min_cells].index

    return reaction_scores.loc[active_reactions]


def get_top_reactions(
    reaction_scores: pd.DataFrame,
    n: int = 10,
    by: str = 'mean'
) -> pd.DataFrame:
    """Get top reactions by activity.

    Args:
        reaction_scores: DataFrame with reaction scores
        n: Number of top reactions to return
        by: Metric to use ('mean', 'median', 'max', 'std')

    Returns:
        DataFrame with top reactions
    """
    if by == 'mean':
        scores = reaction_scores.mean(axis=1)
    elif by == 'median':
        scores = reaction_scores.median(axis=1)
    elif by == 'max':
        scores = reaction_scores.max(axis=1)
    elif by == 'std':
        scores = reaction_scores.std(axis=1)
    else:
        raise ValueError(f"Unknown metric: {by}")

    top_reactions = scores.nlargest(n)
    return reaction_scores.loc[top_reactions.index]


def get_top_metabolites(
    uptake_scores: pd.DataFrame,
    secretion_scores: Optional[pd.DataFrame] = None,
    n: int = 10
) -> Dict[str, pd.DataFrame]:
    """Get top metabolites by uptake and secretion scores.

    Args:
        uptake_scores: DataFrame with uptake scores
        secretion_scores: Optional DataFrame with secretion scores
        n: Number of top metabolites to return

    Returns:
        Dictionary with top uptake and secretion metabolites
    """
    results = {}

    # Top uptake
    uptake_mean = uptake_scores.mean(axis=1)
    results['uptake'] = uptake_scores.loc[uptake_mean.nlargest(n).index]

    # Top secretion
    if secretion_scores is not None:
        secretion_mean = secretion_scores.mean(axis=1)
        results['secretion'] = secretion_scores.loc[secretion_mean.nlargest(n).index]

    return results


def estimate_compass_runtime(
    n_cells: int,
    n_processes: int = 4,
    model: str = 'RECON2_mat'
) -> Dict[str, str]:
    """Estimate COMPASS runtime based on dataset size.

    Args:
        n_cells: Number of cells
        n_processes: Number of parallel processes
        model: Metabolic model

    Returns:
        Dictionary with time estimates
    """
    # Rough estimates based on typical performance
    base_time_per_cell = 30  # seconds per cell per process

    if model == 'RECON1_mat':
        base_time_per_cell = 15
    elif model == 'RECON2.2':
        base_time_per_cell = 45

    total_seconds = (n_cells * base_time_per_cell) / n_processes

    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)

    return {
        'estimated_total': f"{hours}h {minutes}m",
        'per_cell': f"{base_time_per_cell} seconds",
        'notes': 'Estimates assume 8GB RAM per process. Larger datasets may require microclustering.'
    }


def convert_ensembl_to_symbols(
    adata: AnnData,
    gene_mapping: Optional[Dict[str, str]] = None,
    biomart_host: str = 'http://www.ensembl.org'
) -> AnnData:
    """Convert ENSEMBL gene IDs to gene symbols.

    Args:
        adata: AnnData with ENSEMBL IDs in var_names
        gene_mapping: Optional pre-computed mapping dictionary
        biomart_host: BioMart host for online conversion

    Returns:
        AnnData with gene symbols
    """
    adata = adata.copy()

    if gene_mapping is not None:
        # Use provided mapping
        adata.var_names = [gene_mapping.get(g, g) for g in adata.var_names]
    else:
        # Try to use pybiomart for conversion
        try:
            import pybiomart
            server = pybiomart.Server(host=biomart_host)
            dataset = server['ENSEMBL_MART_ENSEMBL'].datasets['hsapiens_gene_ensembl']

            results = dataset.query(
                attributes=['ensembl_gene_id', 'external_gene_name'],
                filters={'ensembl_gene_id': adata.var_names.tolist()}
            )

            mapping = dict(zip(results['ensembl_gene_id'], results['external_gene_name']))
            adata.var_names = [mapping.get(g, g) for g in adata.var_names]

        except ImportError:
            raise ImportError("pybiomart not installed. Install with: pip install pybiomart")
        except Exception as e:
            print(f"BioMart conversion failed: {e}")
            print("Please provide a gene_mapping dictionary.")

    # Handle duplicates
    if not adata.var_names.is_unique:
        adata.var_names_make_unique()

    return adata


def create_reaction_subset_file(
    reactions: List[str],
    output_file: str
) -> str:
    """Create a file with selected reactions for COMPASS.

    Args:
        reactions: List of reaction IDs
        output_file: Output file path

    Returns:
        Path to created file
    """
    with open(output_file, 'w') as f:
        for rxn in reactions:
            f.write(f"{rxn}\n")

    return output_file


def create_subsystem_subset_file(
    subsystems: List[str],
    output_file: str
) -> str:
    """Create a file with selected subsystems for COMPASS.

    Args:
        subsystems: List of subsystem names
        output_file: Output file path

    Returns:
        Path to created file
    """
    with open(output_file, 'w') as f:
        for subsys in subsystems:
            f.write(f"{subsys}\n")

    return output_file


def export_compass_results(
    results: Dict[str, pd.DataFrame],
    output_dir: str,
    format: str = 'csv'
) -> Dict[str, str]:
    """Export COMPASS results to various formats.

    Args:
        results: Dictionary with COMPASS results
        output_dir: Output directory
        format: Export format ('csv', 'tsv', 'excel')

    Returns:
        Dictionary with paths to exported files
    """
    os.makedirs(output_dir, exist_ok=True)
    exported = {}

    for key, df in results.items():
        if format == 'csv':
            path = os.path.join(output_dir, f'{key}.csv')
            df.to_csv(path)
        elif format == 'tsv':
            path = os.path.join(output_dir, f'{key}.tsv')
            df.to_csv(path, sep='\t')
        elif format == 'excel':
            path = os.path.join(output_dir, f'{key}.xlsx')
            df.to_excel(path)
        else:
            raise ValueError(f"Unknown format: {format}")

        exported[key] = path

    return exported


def merge_compass_results(
    results_list: List[Dict[str, pd.DataFrame]],
    sample_names: Optional[List[str]] = None
) -> Dict[str, pd.DataFrame]:
    """Merge COMPASS results from multiple samples.

    Args:
        results_list: List of COMPASS result dictionaries
        sample_names: Optional names for each sample

    Returns:
        Merged results dictionary
    """
    merged = {}

    # Get all keys
    all_keys = set()
    for r in results_list:
        all_keys.update(r.keys())

    for key in all_keys:
        dfs = [r[key] for r in results_list if key in r]

        # Add sample prefix if provided
        if sample_names is not None:
            dfs = [
                df.rename(columns=lambda x: f"{sample}_{x}")
                for df, sample in zip(dfs, sample_names)
            ]

        merged[key] = pd.concat(dfs, axis=1)

    return merged


def create_test_data(
    n_cells: int = 100,
    n_genes: int = 500,
    n_cell_types: int = 3,
    random_state: int = 42
) -> AnnData:
    """Create synthetic test data for COMPASS.

    Args:
        n_cells: Number of cells
        n_genes: Number of genes
        n_cell_types: Number of cell types
        random_state: Random seed

    Returns:
        AnnData object with synthetic data
    """
    np.random.seed(random_state)

    # Generate metabolic gene names (common metabolic genes)
    metabolic_genes = [
        'GAPDH', 'LDHA', 'HK1', 'PFKP', 'PKM', 'ENO1', 'PGK1',  # Glycolysis
        'CS', 'ACO2', 'IDH1', 'IDH2', 'OGDH', 'SUCLA2', 'SDHA',  # TCA
        'ATP5F1A', 'ATP5F1B', 'NDUFV1', 'SDHB', 'UQCRC1',  # OXPHOS
        'G6PD', 'PGD', 'TKT',  # PPP
        'ACACA', 'FASN', 'SCD',  # Fatty acid synthesis
        'CPT1A', 'ACADVL',  # Fatty acid oxidation
        'GLS', 'GLUD1', 'GPT', ' GOT1',  # Amino acid metabolism
    ]

    # Fill remaining genes
    genes = metabolic_genes + [f'GENE_{i}' for i in range(len(metabolic_genes), n_genes)]
    genes = genes[:n_genes]

    # Create cell type labels
    cell_types = [f'CellType_{i}' for i in range(n_cell_types)]
    labels = np.random.choice(cell_types, n_cells)

    # Generate expression with cell-type specific patterns
    X = np.zeros((n_cells, n_genes))

    for i, ct in enumerate(cell_types):
        mask = labels == ct
        n_ct = mask.sum()

        # Different metabolic profiles for each cell type
        if i == 0:  # Glycolytic cells
            high_genes = ['GAPDH', 'LDHA', 'HK1', 'PFKP', 'PKM']
        elif i == 1:  # OXPHOS cells
            high_genes = ['ATP5F1A', 'ATP5F1B', 'NDUFV1', 'CS', 'ACO2']
        else:  # Biosynthetic cells
            high_genes = ['G6PD', 'PGD', 'ACACA', 'FASN']

        # Base expression
        X[mask, :] = np.random.lognormal(2, 0.5, (n_ct, n_genes))

        # Boost specific genes
        for g in high_genes:
            if g in genes:
                idx = genes.index(g)
                X[mask, idx] *= 5

    adata = AnnData(
        X=X,
        obs=pd.DataFrame({
            'cell_type': labels,
            'sample': np.random.choice(['Sample_A', 'Sample_B'], n_cells)
        }, index=[f'cell_{i}' for i in range(n_cells)]),
        var=pd.DataFrame(index=genes)
    )

    return adata


def validate_compass_installation() -> Dict[str, Any]:
    """Validate COMPASS installation and dependencies.

    Returns:
        Dictionary with validation results
    """
    results = {
        'compass_installed': False,
        'cplex_installed': False,
        'python_version': None,
        'errors': [],
        'warnings': []
    }

    import sys
    results['python_version'] = sys.version

    # Check COMPASS
    try:
        import compass
        results['compass_installed'] = True
        results['compass_version'] = compass.__version__
    except ImportError:
        results['errors'].append("COMPASS not installed. Install with: pip install compass-sc")

    # Check CPLEX
    try:
        import cplex
        results['cplex_installed'] = True
        results['cplex_version'] = cplex.__version__
    except ImportError:
        results['errors'].append("CPLEX not installed. CPLEX is required for COMPASS.")
        results['errors'].append("Download from: https://www.ibm.com/products/ilog-cplex-optimization-studio")

    # Check other dependencies
    try:
        import scanpy
        results['scanpy_version'] = scanpy.__version__
    except ImportError:
        results['warnings'].append("scanpy not installed (optional)")

    return results
