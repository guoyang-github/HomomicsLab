#!/usr/bin/env python3
"""
Utility Functions for GraphST Spatial Domain Analysis

Helper functions for data preparation, result processing, and analysis.
These utilities complement the native GraphST package functions.

Author: Yang Guo
Date: 2026-04-07
"""

import numpy as np
import pandas as pd
import scanpy as sc
from typing import Optional, List, Dict, Tuple


def validate_graphst_data(adata: sc.AnnData) -> Dict:
    """
    Validate input data for GraphST analysis.

    Parameters
    ----------
    adata : AnnData
        AnnData object to validate

    Returns
    -------
    dict
        Validation results with keys:
        - 'valid': bool, whether data is valid
        - 'errors': list of error messages
        - 'warnings': list of warning messages
        - 'n_spots': number of spots
        - 'n_genes': number of genes
        - 'has_spatial': whether spatial coordinates exist
    """
    errors = []
    warnings = []

    # Check basic structure
    if adata.n_obs == 0:
        errors.append("No spots in data")
    if adata.n_vars == 0:
        errors.append("No genes in data")

    # Check spatial coordinates
    if 'spatial' not in adata.obsm:
        errors.append("Spatial coordinates not found in adata.obsm['spatial']")
    else:
        spatial = adata.obsm['spatial']
        if spatial.shape[1] != 2:
            errors.append(f"Spatial coordinates must be 2D, got shape {spatial.shape}")
        if np.any(np.isnan(spatial)):
            warnings.append("Spatial coordinates contain NaN values")

    # Check for highly variable genes
    if 'highly_variable' not in adata.var.columns:
        warnings.append("Highly variable genes not computed. GraphST will compute them.")

    # Check gene expression
    if hasattr(adata.X, 'toarray'):
        data = adata.X.toarray()
    else:
        data = adata.X

    if np.all(data == 0):
        errors.append("Expression matrix is all zeros")

    if np.any(np.isnan(data)):
        warnings.append("Expression matrix contains NaN values")

    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'n_spots': adata.n_obs,
        'n_genes': adata.n_vars,
        'has_spatial': 'spatial' in adata.obsm
    }


def print_validation_results(results: Dict) -> None:
    """
    Print validation results in a formatted way.

    Parameters
    ----------
    results : dict
        Validation results from validate_graphst_data()
    """
    if results['valid']:
        print("Validation: PASSED")
    else:
        print("Validation: FAILED")

    print(f"  Spots: {results['n_spots']}")
    print(f"  Genes: {results['n_genes']}")
    print(f"  Spatial coordinates: {'Yes' if results['has_spatial'] else 'No'}")

    if results['errors']:
        print("\nErrors:")
        for error in results['errors']:
            print(f"  - {error}")

    if results['warnings']:
        print("\nWarnings:")
        for warning in results['warnings']:
            print(f"  - {warning}")


def create_test_data(
    n_spots: int = 200,
    n_genes: int = 500,
    n_domains: int = 4,
    seed: int = 42
) -> sc.AnnData:
    """
    Create synthetic spatial data for testing.

    Parameters
    ----------
    n_spots : int
        Number of spots
    n_genes : int
        Number of genes
    n_domains : int
        Number of spatial domains
    seed : int
        Random seed

    Returns
    -------
    AnnData
        Synthetic spatial transcriptomics data
    """
    np.random.seed(seed)

    # Create spatial coordinates
    grid_size = int(np.sqrt(n_spots)) + 1
    x = np.repeat(np.arange(1, grid_size + 1), grid_size)[:n_spots]
    y = np.tile(np.arange(1, grid_size + 1), grid_size)[:n_spots]

    # Create expression matrix
    counts = np.random.poisson(lam=2, size=(n_spots, n_genes)).astype(float)

    # Add domain-specific patterns
    domain_labels = np.zeros(n_spots, dtype=int)
    genes_per_domain = n_genes // n_domains

    for i in range(n_spots):
        # Assign domain based on position
        xi, yi = x[i], y[i]

        if n_domains <= 4:
            # Quadrant assignment for small n_domains
            if xi <= grid_size // 2 and yi <= grid_size // 2:
                domain = 0
            elif xi > grid_size // 2 and yi <= grid_size // 2:
                domain = 1
            elif xi <= grid_size // 2 and yi > grid_size // 2:
                domain = 2
            else:
                domain = min(3, n_domains - 1)
        else:
            # Strip assignment for larger n_domains
            domain = min(int((xi - 1) * n_domains / grid_size), n_domains - 1)

        domain_labels[i] = domain

        # Add markers
        marker_start = domain * genes_per_domain
        marker_end = min(marker_start + genes_per_domain, n_genes)
        counts[i, marker_start:marker_end] += np.random.poisson(10, marker_end - marker_start)

    # Create AnnData
    adata = sc.AnnData(X=counts)
    adata.obs_names = [f"Spot_{i:04d}" for i in range(n_spots)]
    adata.var_names = [f"Gene_{i:04d}" for i in range(n_genes)]
    adata.obsm['spatial'] = np.column_stack([x, y])
    adata.obs['ground_truth'] = [f"Domain_{d}" for d in domain_labels]

    return adata


def summarize_graphst_results(adata: sc.AnnData) -> Dict:
    """
    Summarize GraphST analysis results.

    Parameters
    ----------
    adata : AnnData
        AnnData with GraphST results

    Returns
    -------
    dict
        Summary statistics
    """
    summary = {
        'n_spots': adata.n_obs,
        'n_genes': adata.n_vars,
    }

    # Domain information
    if 'domain' in adata.obs:
        domains = adata.obs['domain']
        summary['n_domains'] = domains.nunique()
        summary['domain_sizes'] = domains.value_counts().to_dict()

    # Embedding information
    if 'emb' in adata.obsm:
        emb = adata.obsm['emb']
        summary['embedding_dim'] = emb.shape[1]
        summary['embedding_mean'] = float(np.mean(emb))
        summary['embedding_std'] = float(np.std(emb))

    return summary


def export_graphst_results(
    adata: sc.AnnData,
    output_dir: str,
    prefix: str = "graphst",
    export_embeddings: bool = True,
    export_domains: bool = True,
    export_adata: bool = True
) -> None:
    """
    Export GraphST results to files.

    Parameters
    ----------
    adata : AnnData
        AnnData with GraphST results
    output_dir : str
        Output directory path
    prefix : str
        File prefix
    export_embeddings : bool
        Whether to export embeddings
    export_domains : bool
        Whether to export domain assignments
    export_adata : bool
        Whether to save AnnData
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Export domains
    if export_domains and 'domain' in adata.obs:
        try:
            domains_df = adata.obs[['domain']].copy()
            domains_df.to_csv(os.path.join(output_dir, f"{prefix}_domains.csv"))
            print(f"Exported: {prefix}_domains.csv")
        except Exception as e:
            print(f"Failed to export domains: {e}")

    # Export embeddings
    if export_embeddings and 'emb' in adata.obsm:
        try:
            emb_df = pd.DataFrame(
                adata.obsm['emb'],
                index=adata.obs_names
            )
            emb_df.to_csv(os.path.join(output_dir, f"{prefix}_embeddings.csv"))
            print(f"Exported: {prefix}_embeddings.csv")
        except Exception as e:
            print(f"Failed to export embeddings: {e}")

    # Save AnnData
    if export_adata:
        try:
            adata.write_h5ad(os.path.join(output_dir, f"{prefix}_results.h5ad"))
            print(f"Exported: {prefix}_results.h5ad")
        except Exception as e:
            print(f"Failed to save AnnData: {e}")


def compare_clustering_methods(
    adata: sc.AnnData,
    methods: List[str] = ['mclust', 'leiden', 'louvain'],
    n_clusters: int = 7
) -> pd.DataFrame:
    """
    Compare different clustering methods.

    Parameters
    ----------
    adata : AnnData
        AnnData with embeddings
    methods : list
        List of clustering methods to compare
    n_clusters : int
        Target number of clusters

    Returns
    -------
    DataFrame
        Comparison of clustering results
    """
    from GraphST.utils import clustering
    import pandas as pd

    results = {}

    for method in methods:
        try:
            clustering(adata, n_clusters=n_clusters, method=method, refinement=False)
            # GraphST stores mclust results under 'mclust', others under 'domain'
            result_key = 'mclust' if method == 'mclust' else 'domain'
            results[method] = adata.obs[result_key].copy()
        except Exception as e:
            print(f"Method {method} failed: {e}")

    return pd.DataFrame(results)


def calculate_domain_metrics(adata: sc.AnnData) -> pd.DataFrame:
    """
    Calculate metrics for each spatial domain.

    Parameters
    ----------
    adata : AnnData
        AnnData with domain assignments

    Returns
    -------
    DataFrame
        Domain metrics
    """
    if 'domain' not in adata.obs:
        raise ValueError("Domain assignments not found in adata.obs['domain']")
    if 'spatial' not in adata.obsm:
        raise ValueError("Spatial coordinates not found in adata.obsm['spatial']")

    metrics = []
    spatial = adata.obsm['spatial']

    for domain in adata.obs['domain'].unique():
        mask = adata.obs['domain'] == domain
        spots = spatial[mask]

        metrics.append({
            'domain': domain,
            'n_spots': mask.sum(),
            'mean_x': spots[:, 0].mean(),
            'mean_y': spots[:, 1].mean(),
            'std_x': spots[:, 0].std(),
            'std_y': spots[:, 1].std()
        })

    return pd.DataFrame(metrics)


def prepare_visium_data(
    path: str,
    count_file: str = "filtered_feature_bc_matrix.h5",
    library_id: Optional[str] = None
) -> sc.AnnData:
    """
    Load and prepare 10X Visium data for GraphST.

    Parameters
    ----------
    path : str
        Path to Visium data directory
    count_file : str
        Name of count file
    library_id : str, optional
        Library ID

    Returns
    -------
    AnnData
        Prepared AnnData object
    """
    adata = sc.read_visium(
        path=path,
        count_file=count_file,
        library_id=library_id
    )

    # Basic preprocessing
    sc.pp.filter_genes(adata, min_cells=1)

    print(f"Loaded Visium data: {adata.n_obs} spots x {adata.n_vars} genes")
    print(f"Spatial coordinates: {adata.obsm['spatial'].shape}")

    return adata


def select_optimal_clusters(
    adata: sc.AnnData,
    min_clusters: int = 2,
    max_clusters: int = 15,
    method: str = 'leiden'
) -> Tuple[int, pd.DataFrame]:
    """
    Select optimal number of clusters using silhouette score.

    Parameters
    ----------
    adata : AnnData
        AnnData with embeddings
    min_clusters : int
        Minimum number of clusters to test
    max_clusters : int
        Maximum number of clusters to test
    method : str
        Clustering method

    Returns
    -------
    tuple
        (optimal_n_clusters, metrics_df)
    """
    from sklearn.metrics import silhouette_score
    from GraphST.utils import clustering

    scores = []

    for n in range(min_clusters, max_clusters + 1):
        try:
            clustering(adata, n_clusters=n, method=method, refinement=False)
            labels = adata.obs['domain'].astype('category').cat.codes

            if len(np.unique(labels)) > 1:
                score = silhouette_score(adata.obsm['emb'], labels)
                scores.append({
                    'n_clusters': n,
                    'silhouette_score': score
                })
        except Exception as e:
            print(f"Failed for n={n}: {e}")

    scores_df = pd.DataFrame(scores)
    if scores_df.empty:
        return min_clusters, scores_df

    optimal = scores_df.loc[scores_df['silhouette_score'].idxmax(), 'n_clusters']

    return int(optimal), scores_df
