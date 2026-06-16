"""
Utility functions for SpaGCN analysis.

Author: Yang Guo
Date: 2026-04-03
"""

from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData
from scipy.sparse import issparse


# ==============================================================================
# Moran's I Calculation
# ==============================================================================

def calculate_moran_i(
    adata: AnnData,
    gene: str,
    x_column: str = "array_col",
    y_column: str = "array_row",
    k: int = 5,
    knn: bool = True
) -> float:
    """
    Calculate Moran's I statistic for spatial autocorrelation of a gene.

    Moran's I measures the degree of spatial clustering of a variable.
    Values range from -1 (dispersed) to 1 (clustered), with 0 indicating
    random spatial distribution.

    This wraps SpaGCN's native Moran_I, which requires a DataFrame of gene
    expression and spatial coordinates (not an adjacency matrix).

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    gene : str
        Gene name to calculate Moran's I for
    x_column : str, default="array_col"
        Column name for x coordinates
    y_column : str, default="array_row"
        Column name for y coordinates
    k : int, default=5
        Number of nearest neighbors for spatial weights
    knn : bool, default=True
        Use k-nearest neighbors (True) or distance threshold (False)

    Returns
    -------
    float
        Moran's I statistic for the gene

    Examples
    --------
    >>> mi = calculate_moran_i(adata, gene="GFAP")
    >>> print(f"Moran's I: {mi:.3f}")
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    if gene not in adata.var_names:
        raise ValueError(f"Gene {gene} not found in data")

    # Extract expression as DataFrame (required by SpaGCN.Moran_I)
    exp = adata[:, gene].X
    if hasattr(exp, 'toarray'):
        exp = exp.toarray()
    exp = np.array(exp).flatten()

    genes_exp = pd.DataFrame({gene: exp}, index=adata.obs_names)

    x = adata.obs[x_column].tolist()
    y = adata.obs[y_column].tolist()

    result = spg.Moran_I(genes_exp, x, y, k=k, knn=knn)
    return float(result[gene])


def calculate_moran_i_genes(
    adata: AnnData,
    genes: Optional[List[str]] = None,
    x_column: str = "array_col",
    y_column: str = "array_row",
    k: int = 5,
    knn: bool = True,
    n_top: int = 100
) -> pd.DataFrame:
    """
    Calculate Moran's I for multiple genes.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    genes : List[str], optional
        Genes to calculate (default: all variable genes)
    x_column : str, default="array_col"
        Column name for x coordinates
    y_column : str, default="array_row"
        Column name for y coordinates
    k : int, default=5
        Number of nearest neighbors for spatial weights
    knn : bool, default=True
        Use k-nearest neighbors (True) or distance threshold (False)
    n_top : int, default=100
        Number of top genes to return

    Returns
    -------
    pd.DataFrame
        DataFrame with genes and Moran's I values
    """
    if genes is None:
        genes = adata.var_names.tolist()

    results = []

    for gene in genes:
        if gene not in adata.var_names:
            continue

        # Calculate Moran's I
        mi = calculate_moran_i(
            adata, gene,
            x_column=x_column, y_column=y_column,
            k=k, knn=knn
        )

        results.append({
            'gene': gene,
            'moran_i': mi
        })

    df = pd.DataFrame(results)
    df = df.sort_values('moran_i', ascending=False)

    return df.head(n_top)


# ==============================================================================
# Neighbor Analysis
# ==============================================================================

def find_neighbor_clusters(
    adata: AnnData,
    target_domain: Union[int, str],
    domain_column: str = "pred",
    x_column: str = "array_col",
    y_column: str = "array_row",
    radius: float = 3.0,
    ratio: float = 0.5
) -> List:
    """
    Find neighboring domains of a target domain.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    target_domain : int or str
        Target domain to find neighbors for
    domain_column : str, default="pred"
        Column with domain labels
    x_column : str, default="array_col"
        Column name for x coordinates
    y_column : str, default="array_row"
        Column name for y coordinates
    radius : float, default=3.0
        Search radius
    ratio : float, default=0.5
        Minimum ratio of boundary spots to consider as neighbor

    Returns
    -------
    List
        List of neighboring domain IDs
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    x = adata.obs[x_column].tolist()
    y = adata.obs[y_column].tolist()

    neighbors = spg.find_neighbor_clusters(
        target_cluster=target_domain,
        cell_id=adata.obs.index.tolist(),
        x=x,
        y=y,
        pred=adata.obs[domain_column].tolist(),
        radius=radius,
        ratio=ratio
    )

    return neighbors


def search_optimal_radius(
    adata: AnnData,
    target_domain: Union[int, str],
    domain_column: str = "pred",
    x_column: str = "array_col",
    y_column: str = "array_row",
    num_min: int = 8,
    num_max: int = 15,
    max_run: int = 100
) -> float:
    """
    Search for optimal radius for neighbor detection.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    target_domain : int or str
        Target domain
    domain_column : str, default="pred"
        Column with domain labels
    x_column : str, default="array_col"
        Column name for x coordinates
    y_column : str, default="array_row"
        Column name for y coordinates
    num_min : int, default=8
        Minimum number of neighbors
    num_max : int, default=15
        Maximum number of neighbors
    max_run : int, default=100
        Maximum iterations

    Returns
    -------
    float
        Optimal radius
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    # Calculate 2D adjacency
    x = adata.obs[x_column].tolist()
    y = adata.obs[y_column].tolist()

    adj_2d = spg.calculate_adj_matrix(x=x, y=y, histology=False)

    # Define search range
    start = np.quantile(adj_2d[adj_2d != 0], q=0.001)
    end = np.quantile(adj_2d[adj_2d != 0], q=0.1)

    radius = spg.search_radius(
        target_cluster=target_domain,
        cell_id=adata.obs.index.tolist(),
        x=x,
        y=y,
        pred=adata.obs[domain_column].tolist(),
        start=start,
        end=end,
        num_min=num_min,
        num_max=num_max,
        max_run=max_run
    )

    return radius


# ==============================================================================
# Differential Expression
# ==============================================================================

def rank_genes_groups(
    adata: AnnData,
    target_domain: Union[int, str],
    neighbor_domains: List,
    domain_column: str = "pred",
    adj_nbr: bool = True,
    log: bool = True
) -> pd.DataFrame:
    """
    Rank genes for a target domain compared to neighboring domains.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    target_domain : int or str
        Target domain
    neighbor_domains : List
        List of neighboring domains to compare against
    domain_column : str, default="pred"
        Column with domain labels
    adj_nbr : bool, default=True
        Only compare with neighboring domains (not all others)
    log : bool, default=True
        Whether data is log-transformed

    Returns
    -------
    pd.DataFrame
        DataFrame with DE results:
        - genes: Gene names
        - in_group_fraction: Fraction in target domain
        - out_group_fraction: Fraction in neighbors
        - in_out_group_ratio: Ratio of fractions
        - fold_change: Expression fold change
        - pvals_adj: Adjusted p-values
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    results = spg.rank_genes_groups(
        input_adata=adata,
        target_cluster=target_domain,
        nbr_list=neighbor_domains,
        label_col=domain_column,
        adj_nbr=adj_nbr,
        log=log
    )

    return results


# ==============================================================================
# Subcluster Detection
# ==============================================================================

def detect_subclusters(
    adata: AnnData,
    target_domain: Union[int, str],
    domain_column: str = "pred",
    x_column: str = "array_col",
    y_column: str = "array_row",
    radius: float = 3.0,
    resolution: float = 0.2
) -> List:
    """
    Detect subclusters within a spatial domain.

    This function identifies subdomains within a given domain by
    analyzing the spatial neighborhood structure.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    target_domain : int or str
        Domain to detect subclusters in
    domain_column : str, default="pred"
        Column with domain labels
    x_column : str, default="array_col"
        Column name for x coordinates
    y_column : str, default="array_row"
        Column name for y coordinates
    radius : float, default=3.0
        Neighborhood radius
    resolution : float, default=0.2
        Louvain resolution for subclustering

    Returns
    -------
    List
        Subcluster labels for all spots (-1 for spots not in target domain)
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    x = adata.obs[x_column].tolist()
    y = adata.obs[y_column].tolist()

    subclusters = spg.detect_subclusters(
        cell_id=adata.obs.index.tolist(),
        x=x,
        y=y,
        pred=adata.obs[domain_column].tolist(),
        target_cluster=target_domain,
        radius=radius,
        res=resolution
    )

    return subclusters


# ==============================================================================
# Expression Utilities
# ==============================================================================

def get_domain_expression(
    adata: AnnData,
    domain_column: str = "pred",
    domain: Optional[Union[int, str]] = None,
    genes: Optional[List[str]] = None,
    aggregation: str = "mean"
) -> pd.DataFrame:
    """
    Get expression statistics by domain.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    domain_column : str, default="pred"
        Column with domain labels
    domain : int or str, optional
        Specific domain (default: all domains)
    genes : List[str], optional
        Genes to include (default: all)
    aggregation : str, default="mean"
        Aggregation method ("mean", "median", "sum")

    Returns
    -------
    pd.DataFrame
        Expression matrix (domains x genes)
    """
    if genes is not None:
        adata = adata[:, genes]

    if domain is not None:
        adata = adata[adata.obs[domain_column] == domain]

    domains = sorted(adata.obs[domain_column].unique())
    gene_names = adata.var_names.tolist()

    results = []

    for d in domains:
        domain_data = adata[adata.obs[domain_column] == d]

        if hasattr(domain_data.X, 'toarray'):
            X = domain_data.X.toarray()
        else:
            X = domain_data.X

        if aggregation == "mean":
            values = X.mean(axis=0)
        elif aggregation == "median":
            values = np.median(X, axis=0)
        elif aggregation == "sum":
            values = X.sum(axis=0)
        else:
            raise ValueError(f"Unknown aggregation: {aggregation}")

        results.append(values.flatten() if hasattr(values, 'flatten') else values)

    df = pd.DataFrame(results, index=domains, columns=gene_names)
    return df


def get_top_genes_per_domain(
    adata: AnnData,
    domain_column: str = "pred",
    n_genes: int = 10,
    method: str = "mean"
) -> Dict:
    """
    Get top expressed genes for each domain.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    domain_column : str, default="pred"
        Column with domain labels
    n_genes : int, default=10
        Number of top genes per domain
    method : str, default="mean"
        Method for ranking ("mean" or "fold_change")

    Returns
    -------
    Dict
        Dictionary mapping domain to list of top genes
    """
    expression_df = get_domain_expression(adata, domain_column)

    top_genes = {}

    for domain in expression_df.index:
        if method == "mean":
            genes = expression_df.loc[domain].nlargest(n_genes).index.tolist()
        elif method == "fold_change":
            # Calculate fold change vs other domains
            other_mean = expression_df.drop(index=domain).mean()
            fold_change = expression_df.loc[domain] / (other_mean + 1e-10)
            genes = fold_change.nlargest(n_genes).index.tolist()
        else:
            raise ValueError(f"Unknown method: {method}")

        top_genes[domain] = genes

    return top_genes


# ==============================================================================
# Result Export
# ==============================================================================

def export_domain_results(
    adata: AnnData,
    output_prefix: str,
    domain_column: str = "pred",
    include_expression: bool = False
):
    """
    Export domain identification results.

    Parameters
    ----------
    adata : AnnData
        Spatial data with domain predictions
    output_prefix : str
        Prefix for output files
    domain_column : str, default="pred"
        Column with domain labels
    include_expression : bool, default=False
        Whether to export expression matrix
    """
    # Export domain labels
    if domain_column not in adata.obs.columns:
        raise ValueError(f"'{domain_column}' not found in adata.obs")
    domain_df = adata.obs[[domain_column]].copy()
    domain_df.to_csv(f"{output_prefix}_domains.csv")

    # Export domain statistics
    stats = pd.DataFrame({
        'n_spots': adata.obs[domain_column].value_counts(),
        'proportion': adata.obs[domain_column].value_counts(normalize=True)
    })
    stats.to_csv(f"{output_prefix}_domain_stats.csv")

    # Export coordinates with domains
    coord_cols = ['array_row', 'array_col'] if 'array_row' in adata.obs.columns else []
    if coord_cols:
        coord_df = adata.obs[coord_cols + [domain_column]].copy()
        coord_df.to_csv(f"{output_prefix}_domain_coords.csv")

    # Export expression if requested
    if include_expression:
        if hasattr(adata.X, 'toarray'):
            exp_df = pd.DataFrame(
                adata.X.toarray(),
                index=adata.obs_names,
                columns=adata.var_names
            )
        else:
            exp_df = pd.DataFrame(
                adata.X,
                index=adata.obs_names,
                columns=adata.var_names
            )
        exp_df.to_csv(f"{output_prefix}_expression.csv")

    print(f"Results exported to {output_prefix}_*.csv")


def load_and_merge_domains(
    adata: AnnData,
    domain_file: str,
    domain_column: str = "pred"
) -> AnnData:
    """
    Load domain labels from file and merge with AnnData.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    domain_file : str
        Path to CSV file with domain labels
    domain_column : str, default="pred"
        Column name for domains

    Returns
    -------
    AnnData
        Data with merged domain labels
    """
    domain_df = pd.read_csv(domain_file, index_col=0)

    # Check index match
    if not all(idx in adata.obs_names for idx in domain_df.index):
        raise ValueError("Domain file index does not match AnnData observations")

    # Check column exists
    if domain_column not in domain_df.columns:
        raise ValueError(
            f"'{domain_column}' not found in domain file columns: {list(domain_df.columns)}"
        )

    # Merge
    adata.obs[domain_column] = domain_df[domain_column]
    adata.obs[domain_column] = adata.obs[domain_column].astype('category')

    return adata
