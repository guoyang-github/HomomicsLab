"""
Spatial Pattern Analysis for Spatial Transcriptomics

This module provides methods for analyzing spatial patterns including:
- Co-occurrence analysis between cell types
- Join counts for categorical data
- Ripley's K and L statistics for point patterns
- Neighborhood enrichment analysis

Methods:
    - Co-occurrence: Measure spatial overlap between cell types
    - Join Counts: Statistics for categorical spatial autocorrelation
    - Ripley's K/L: Point pattern analysis
    - Neighborhood Enrichment: Local cell-type interactions
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Tuple, Union
import warnings
from scipy import stats


def compute_cooccurrence(
    adata,
    cluster_key: str = 'cell_type',
    n_neighbors: int = 6,
    method: str = 'observed_vs_expected'
) -> pd.DataFrame:
    """
    Compute cell type co-occurrence analysis.

    Co-occurrence measures how often two cell types appear near each other
    compared to random expectation. Values > 1 indicate spatial attraction,
    values < 1 indicate spatial avoidance.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data with cluster annotations
    cluster_key : str, default='cell_type'
        Column in adata.obs containing cluster labels
    n_neighbors : int, default=6
        Number of nearest neighbors for neighborhood definition
    method : str, default='observed_vs_expected'
        Method for co-occurrence calculation:
        - 'observed_vs_expected': Ratio of observed to expected co-occurrence
        - 'jaccard': Jaccard similarity of neighborhoods

    Returns
    -------
    pd.DataFrame
        Co-occurrence matrix with cell types as index and columns.
        Values represent co-occurrence strength between cell type pairs.

    References
    ----------
    Schapiro et al. (2017). histoCAT: analysis of cell phenotypes and
    interactions in multiplex image cytometry data. Nature Methods, 14(9), 873-876.

    Example
    -------
    >>> cooccur = compute_cooccurrence(adata, cluster_key='cell_type', n_neighbors=6)
    >>> print(cooccur.loc['Macrophage', 'T_cell'])
    1.234  # Macrophages co-occur 23% more than expected with T cells
    """
    if cluster_key not in adata.obs.columns:
        raise ValueError(f"Column '{cluster_key}' not found in adata.obs")

    from sklearn.neighbors import kneighbors_graph

    # Get cluster labels
    clusters = adata.obs[cluster_key].astype('category')
    cluster_names = clusters.cat.categories.tolist()
    n_clusters = len(cluster_names)

    # Build k-nearest neighbor graph
    coords = adata.obsm['spatial']
    knn_graph = kneighbors_graph(coords, n_neighbors=n_neighbors, mode='connectivity')

    # Create cluster indicator matrix
    cluster_matrix = np.zeros((adata.n_obs, n_clusters))
    for i, name in enumerate(cluster_names):
        cluster_matrix[:, i] = (clusters == name).astype(int)

    # Compute co-occurrence matrix
    if method == 'observed_vs_expected':
        # Count actual co-occurrences
        observed = cluster_matrix.T @ knn_graph @ cluster_matrix

        # Compute expected under random distribution
        total_neighbors = knn_graph.sum(axis=1).A1
        cluster_props = cluster_matrix.sum(axis=0) / cluster_matrix.sum()
        expected = np.outer(cluster_props, cluster_props) * total_neighbors.sum()

        # Ratio of observed to expected
        cooccur_matrix = observed / (expected + 1e-10)

    elif method == 'jaccard':
        # Jaccard similarity of neighborhoods
        binary_matrix = (cluster_matrix > 0).astype(int)
        intersection = binary_matrix.T @ knn_graph @ binary_matrix
        row_sums = binary_matrix.sum(axis=0)
        union = np.add.outer(row_sums, row_sums) - intersection
        cooccur_matrix = intersection / (union + 1e-10)

    else:
        raise ValueError(f"Unknown method: {method}")

    # Create DataFrame
    cooccur_df = pd.DataFrame(
        cooccur_matrix,
        index=cluster_names,
        columns=cluster_names
    )

    return cooccur_df


def compute_cooccurrence_probability(
    adata,
    cluster_key: str = 'cell_type',
    n_neighbors: int = 6,
    n_permutations: int = 100,
    random_state: int = 42
) -> Dict:
    """
    Compute co-occurrence with significance testing via permutation.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    cluster_key : str, default='cell_type'
        Column containing cluster labels
    n_neighbors : int, default=6
        Number of neighbors
    n_permutations : int, default=100
        Number of permutations for significance testing
    random_state : int, default=42
        Random seed for reproducibility

    Returns
    -------
    dict
        Dictionary containing:
        - 'cooccurrence': Observed co-occurrence matrix
        - 'z_scores': Z-scores (observed - mean(permuted)) / std(permuted)
        - 'p_values': P-values from permutation test
        - 'is_significant': Boolean matrix of significant co-occurrences

    Example
    -------
    >>> result = compute_cooccurrence_probability(adata, cluster_key='cell_type')
    >>> print(result['z_scores'].loc['Macrophage', 'T_cell'])
    3.45  # Highly significant co-occurrence
    """
    # Compute observed co-occurrence
    observed = compute_cooccurrence(adata, cluster_key, n_neighbors)
    cluster_names = observed.index.tolist()

    # Permutation test
    np.random.seed(random_state)
    permuted_values = []

    for _ in range(n_permutations):
        # Shuffle cluster labels
        shuffled_obs = adata.obs.copy()
        shuffled_obs[cluster_key] = np.random.permutation(
            shuffled_obs[cluster_key].values
        )

        # Create temporary adata with shuffled labels
        from anndata import AnnData
        temp_adata = AnnData(
            X=adata.X,
            obs=shuffled_obs,
            obsm=adata.obsm
        )

        permuted_cooccur = compute_cooccurrence(temp_adata, cluster_key, n_neighbors)
        permuted_values.append(permuted_cooccur.values)

    # Compute statistics
    permuted_array = np.array(permuted_values)
    mean_permuted = permuted_array.mean(axis=0)
    std_permuted = permuted_array.std(axis=0)

    z_scores = (observed.values - mean_permuted) / (std_permuted + 1e-10)

    # P-values: proportion of permutations with more extreme values
    p_values = np.mean(
        np.abs(permuted_array - mean_permuted) >=
        np.abs(observed.values - mean_permuted),
        axis=0
    )

    # Create DataFrames
    z_score_df = pd.DataFrame(z_scores, index=cluster_names, columns=cluster_names)
    p_value_df = pd.DataFrame(p_values, index=cluster_names, columns=cluster_names)
    significant_df = p_value_df < 0.05

    return {
        'cooccurrence': observed,
        'z_scores': z_score_df,
        'p_values': p_value_df,
        'is_significant': significant_df
    }


def compute_join_counts(
    adata,
    cluster_key: str = 'cell_type',
    n_neighbors: int = 6
) -> pd.DataFrame:
    """
    Compute Join Counts statistic for categorical spatial autocorrelation.

    Join Counts is a non-parametric method for assessing spatial autocorrelation
    in categorical data. It counts the number of joins (edges) between categories.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    cluster_key : str, default='cell_type'
        Column containing categorical cluster labels
    n_neighbors : int, default=6
        Number of neighbors for spatial weights

    Returns
    -------
    pd.DataFrame
        DataFrame with join count statistics:
        - category: Cell type name
        - observed_joins: Actual number of same-category joins
        - expected_joins: Expected under random distribution
        - variance: Variance of expected joins
        - z_score: Standardized statistic
        - p_value: Two-tailed p-value
        - autocorrelation: 'positive', 'negative', or 'random'

    References
    ----------
    Cliff, A.D., & Ord, J.K. (1981). Spatial Processes: Models & Applications.
    Pion.

    Example
    -------
    >>> jc = compute_join_counts(adata, cluster_key='cell_type')
    >>> print(jc[jc['autocorrelation'] == 'positive'])
          category  observed_joins  z_score  autocorrelation
    0  Macrophage             450     5.23         positive
    """
    if cluster_key not in adata.obs.columns:
        raise ValueError(f"Column '{cluster_key}' not found in adata.obs")

    from sklearn.neighbors import kneighbors_graph

    # Get cluster labels
    clusters = adata.obs[cluster_key]
    categories = clusters.unique()

    # Build adjacency matrix
    coords = adata.obsm['spatial']
    adjacency = kneighbors_graph(coords, n_neighbors=n_neighbors, mode='connectivity')
    n = adata.n_obs

    results = []

    for cat in categories:
        # Binary indicator for this category
        y = (clusters == cat).astype(int).values
        n_c = y.sum()
        p_c = n_c / n

        # Count joins (each join counted twice, so divide by 2)
        observed_joins = (y @ adjacency @ y) / 2

        # Expected joins under random distribution
        n_links = adjacency.sum() / 2
        expected_joins = n_links * p_c ** 2

        # Variance (simplified for k-NN structure)
        # This is an approximation; exact formula depends on weights structure
        variance = n_links * p_c ** 2 * (1 - p_c ** 2)

        # Z-score
        if variance > 0:
            z_score = (observed_joins - expected_joins) / np.sqrt(variance)
        else:
            z_score = 0

        # Two-tailed p-value
        p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))

        # Determine autocorrelation type
        if p_value < 0.05:
            autocorr = 'positive' if z_score > 0 else 'negative'
        else:
            autocorr = 'random'

        results.append({
            'category': cat,
            'observed_joins': observed_joins,
            'expected_joins': expected_joins,
            'variance': variance,
            'z_score': z_score,
            'p_value': p_value,
            'autocorrelation': autocorr
        })

    return pd.DataFrame(results)


def interpret_join_counts(jc_results: pd.DataFrame) -> str:
    """
    Generate human-readable interpretation of join counts results.

    Parameters
    ----------
    jc_results : pd.DataFrame
        Results from compute_join_counts()

    Returns
    -------
    str
        Interpretation string summarizing findings

    Example
    -------
    >>> jc = compute_join_counts(adata, cluster_key='cell_type')
    >>> print(interpret_join_counts(jc))
    Join Counts Analysis:
    - Macrophage shows positive autocorrelation (z=5.23, p<0.001)
    - T_cell shows random distribution (z=0.45, p=0.65)
    """
    lines = ["Join Counts Analysis:"]

    for _, row in jc_results.iterrows():
        cat = row['category']
        auto = row['autocorrelation']
        z = row['z_score']
        p = row['p_value']

        if auto == 'positive':
            lines.append(
                f"- {cat} shows positive autocorrelation "
                f"(z={z:.2f}, p={p:.3e})"
            )
        elif auto == 'negative':
            lines.append(
                f"- {cat} shows negative autocorrelation "
                f"(z={z:.2f}, p={p:.3e})"
            )
        else:
            lines.append(
                f"- {cat} shows random distribution "
                f"(z={z:.2f}, p={p:.3f})"
            )

    return "\n".join(lines)


def compute_neighborhood_enrichment(
    adata,
    cluster_key: str = 'cell_type',
    n_neighbors: int = 6,
    n_permutations: int = 100,
    random_state: int = 42
) -> pd.DataFrame:
    """
    Compute neighborhood enrichment analysis.

    For each cell type, test which other cell types are enriched or depleted
    in its neighborhood compared to random expectation.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    cluster_key : str, default='cell_type'
        Column containing cluster labels
    n_neighbors : int, default=6
        Number of neighbors
    n_permutations : int, default=100
        Number of permutations for significance
    random_state : int, default=42
        Random seed

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - source: Source cell type
        - target: Target cell type
        - observed_freq: Observed neighbor frequency
        - expected_freq: Expected frequency
        - enrichment: Observed / Expected ratio
        - z_score: Standardized enrichment
        - p_value: Significance
        - significance: 'enriched', 'depleted', or 'not_significant'

    References
    ----------
    Goltsev et al. (2018). Deep Profiling of Mouse Splenic Architecture
    with CODEX Multiplexed Imaging. Cell, 174(4), 968-981.

    Example
    -------
    >>> enrichment = compute_neighborhood_enrichment(adata, cluster_key='cell_type')
    >>> # Find what neighbors Macrophages prefer
    >>> macro_enrichment = enrichment[enrichment['source'] == 'Macrophage']
    >>> print(macro_enrichment.nlargest(3, 'enrichment'))
    """
    if cluster_key not in adata.obs.columns:
        raise ValueError(f"Column '{cluster_key}' not found in adata.obs")

    from sklearn.neighbors import kneighbors_graph

    clusters = adata.obs[cluster_key].astype('category')
    categories = clusters.cat.categories.tolist()

    # Build neighborhood graph
    coords = adata.obsm['spatial']
    knn_graph = kneighbors_graph(coords, n_neighbors=n_neighbors, mode='connectivity')

    results = []

    for source_cat in categories:
        # Get spots of this category
        source_mask = clusters == source_cat
        source_indices = np.where(source_mask)[0]

        # Count neighbors of each type
        neighbor_counts = {}
        for target_cat in categories:
            target_mask = clusters == target_cat
            neighbor_counts[target_cat] = 0

            for idx in source_indices:
                neighbors = knn_graph[idx].nonzero()[1]
                neighbor_counts[target_cat] += target_mask.iloc[neighbors].sum()

        total_neighbors = sum(neighbor_counts.values())

        for target_cat, observed in neighbor_counts.items():
            observed_freq = observed / total_neighbors if total_neighbors > 0 else 0

            # Expected frequency under random distribution
            expected_freq = (clusters == target_cat).sum() / len(clusters)

            # Enrichment ratio
            enrichment = observed_freq / (expected_freq + 1e-10)

            results.append({
                'source': source_cat,
                'target': target_cat,
                'observed_freq': observed_freq,
                'expected_freq': expected_freq,
                'enrichment': enrichment,
                'observed_count': observed,
                'total_neighbors': total_neighbors
            })

    results_df = pd.DataFrame(results)

    # Compute z-scores and p-values via permutation
    np.random.seed(random_state)

    enrichment_matrix = results_df.pivot(
        index='source', columns='target', values='enrichment'
    )

    permuted_enrichments = []

    for _ in range(n_permutations):
        # Shuffle labels
        shuffled = np.random.permutation(clusters.values)
        temp_adata = adata.copy()
        temp_adata.obs[cluster_key] = shuffled

        temp_result = compute_neighborhood_enrichment(
            temp_adata, cluster_key, n_neighbors, n_permutations=0
        )
        temp_matrix = temp_result.pivot(
            index='source', columns='target', values='enrichment'
        )
        permuted_enrichments.append(temp_matrix.values)

    permuted_array = np.array(permuted_enrichments)
    mean_permuted = permuted_array.mean(axis=0)
    std_permuted = permuted_array.std(axis=0)

    z_scores = (enrichment_matrix.values - mean_permuted) / (std_permuted + 1e-10)
    z_score_df = pd.DataFrame(
        z_scores,
        index=enrichment_matrix.index,
        columns=enrichment_matrix.columns
    )

    # Add z-scores and significance to results
    results_df['z_score'] = results_df.apply(
        lambda row: z_score_df.loc[row['source'], row['target']],
        axis=1
    )
    results_df['p_value'] = 2 * (1 - stats.norm.cdf(np.abs(results_df['z_score'])))

    # Determine significance
    results_df['significance'] = 'not_significant'
    results_df.loc[results_df['p_value'] < 0.05, 'significance'] = 'enriched'
    results_df.loc[
        (results_df['p_value'] < 0.05) & (results_df['enrichment'] < 1),
        'significance'
    ] = 'depleted'

    return results_df


def extract_enrichment_zscores(
    enrichment_df: pd.DataFrame,
    source: Optional[str] = None,
    significance_threshold: float = 0.05
) -> pd.DataFrame:
    """
    Extract z-score matrix from enrichment results for visualization.

    Parameters
    ----------
    enrichment_df : pd.DataFrame
        Results from compute_neighborhood_enrichment()
    source : str, optional
        If specified, extract only rows for this source cell type
    significance_threshold : float, default=0.05
        P-value threshold for significance

    Returns
    -------
    pd.DataFrame
        Matrix of z-scores (sources x targets)

    Example
    -------
    >>> enrichment = compute_neighborhood_enrichment(adata)
    >>> z_matrix = extract_enrichment_zscores(enrichment)
    >>> sns.heatmap(z_matrix, cmap='RdBu_r', center=0)
    """
    if source is not None:
        df = enrichment_df[enrichment_df['source'] == source]
    else:
        df = enrichment_df

    # Pivot to matrix
    z_matrix = df.pivot(index='source', columns='target', values='z_score')

    # Mask non-significant values (optional, for visualization)
    p_matrix = df.pivot(index='source', columns='target', values='p_value')
    z_matrix_masked = z_matrix.copy()
    z_matrix_masked[p_matrix >= significance_threshold] = 0

    return z_matrix


def compute_ripley_k(
    adata,
    cluster_key: str = 'cell_type',
    cluster_value: Optional[str] = None,
    radii: Optional[np.ndarray] = None,
    n_radii: int = 20,
    boundary_correction: str = ' Ripley'
) -> pd.DataFrame:
    """
    Compute Ripley's K function for point pattern analysis.

    Ripley's K measures the number of points within a given radius of each
    point, normalized by the intensity of points. It detects clustering
    at different spatial scales.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    cluster_key : str, default='cell_type'
        Column containing cell type labels
    cluster_value : str, optional
        Specific cell type to analyze. If None, analyzes all spots.
    radii : np.ndarray, optional
        Array of radii to evaluate. If None, auto-computed.
    n_radii : int, default=20
        Number of radii points if radii not specified
    boundary_correction : str, default='Ripley'
        Boundary correction method

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - radius: Distance radius
        - K: Ripley's K value
        - L: L-function transformation (sqrt(K/pi) - r)
        - H: H-function transformation (L - r)

    References
    ----------
    Ripley, B.D. (1977). Modelling spatial patterns.
    Journal of the Royal Statistical Society B, 39(2), 172-212.

    Example
    -------
    >>> k_results = compute_ripley_k(adata, cluster_key='cell_type', cluster_value='Macrophage')
    >>> plt.plot(k_results['radius'], k_results['K'])
    """
    try:
        from pointpats import ripley
    except ImportError:
        raise ImportError(
            "pointpats is required for Ripley's K computation. "
            "Install: pip install pointpats"
        )

    # Get coordinates
    coords = adata.obsm['spatial']

    # Filter to specific cluster if specified
    if cluster_value is not None:
        mask = adata.obs[cluster_key] == cluster_value
        coords = coords[mask]

    if len(coords) < 10:
        raise ValueError(f"Too few points ({len(coords)}) for Ripley's K")

    # Auto-compute radii if not specified
    if radii is None:
        # Use range up to half the minimum dimension
        ranges = np.ptp(coords, axis=0)
        max_radius = min(ranges) / 2
        radii = np.linspace(0, max_radius, n_radii)[1:]  # Exclude 0

    # Compute Ripley's K
    # Note: pointpats expects (x, y) format
    points = coords[:, :2]  # Use only 2D coordinates

    K_results = ripley(points, radii, mode='ripley')

    # Compute L and H functions
    # L(r) = sqrt(K(r)/pi) - r
    # H(r) = L(r) - r
    area = np.ptp(points[:, 0]) * np.ptp(points[:, 1])
    intensity = len(points) / area

    L_values = np.sqrt(K_results / np.pi) - radii
    H_values = L_values - radii

    results = pd.DataFrame({
        'radius': radii,
        'K': K_results,
        'L': L_values,
        'H': H_values
    })

    return results


def compute_ripley_l(
    adata,
    cluster_key: str = 'cell_type',
    cluster_value: Optional[str] = None,
    radii: Optional[np.ndarray] = None,
    n_radii: int = 20
) -> pd.DataFrame:
    """
    Compute L-function (transformed Ripley's K).

    The L-function linearizes Ripley's K for easier interpretation:
    - L(r) = 0: Complete spatial randomness
    - L(r) > 0: Clustering at radius r
    - L(r) < 0: Dispersion at radius r

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    cluster_key : str, default='cell_type'
        Column containing cell type labels
    cluster_value : str, optional
        Specific cell type to analyze
    radii : np.ndarray, optional
        Array of radii to evaluate
    n_radii : int, default=20
        Number of radii points

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - radius: Distance radius
        - L: L-function value

    Example
    -------
    >>> l_results = compute_ripley_l(adata, cluster_key='cell_type', cluster_value='Macrophage')
    >>> plt.plot(l_results['radius'], l_results['L'])
    >>> plt.axhline(y=0, color='r', linestyle='--')
    """
    k_results = compute_ripley_k(
        adata, cluster_key, cluster_value, radii, n_radii
    )
    return k_results[['radius', 'L']]


def plot_ripley(
    ripley_results: pd.DataFrame,
    metric: str = 'L',
    title: str = "Ripley's Analysis",
    theoretical: bool = True,
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 6)
):
    """
    Plot Ripley's K/L/H function results.

    Parameters
    ----------
    ripley_results : pd.DataFrame
        Results from compute_ripley_k()
    metric : str, default='L'
        Which metric to plot ('K', 'L', or 'H')
    title : str, default="Ripley's Analysis"
        Plot title
    theoretical : bool, default=True
        Whether to show theoretical CSR (Complete Spatial Randomness) line
    save_path : str, optional
        Path to save figure
    figsize : tuple, default=(10, 6)
        Figure size

    Returns
    -------
    matplotlib.figure.Figure
        Figure object

    Example
    -------
    >>> k_results = compute_ripley_k(adata, cluster_key='cell_type', cluster_value='T_cell')
    >>> fig = plot_ripley(k_results, metric='L', title='T_cell Spatial Pattern')
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib is required for plotting")

    fig, ax = plt.subplots(figsize=figsize)

    metric = metric.upper()
    if metric not in ['K', 'L', 'H']:
        raise ValueError("metric must be 'K', 'L', or 'H'")

    radii = ripley_results['radius']
    values = ripley_results[metric]

    ax.plot(radii, values, 'b-', linewidth=2, label=f'{metric}(r)')

    if theoretical:
        if metric == 'K':
            # Theoretical K under CSR: pi*r^2
            theoretical_values = np.pi * radii ** 2
        elif metric == 'L':
            # Theoretical L under CSR: 0
            theoretical_values = np.zeros_like(radii)
        else:  # H
            # Theoretical H under CSR: 0
            theoretical_values = np.zeros_like(radii)

        ax.plot(radii, theoretical_values, 'r--', linewidth=1, label='CSR')

    ax.set_xlabel('Radius (r)', fontsize=12)
    ax.set_ylabel(f'{metric}(r)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def analyze_spatial_patterns(
    adata,
    cluster_key: str = 'cell_type',
    n_neighbors: int = 6,
    n_permutations: int = 50
) -> Dict:
    """
    Run comprehensive spatial pattern analysis.

    This function combines multiple pattern analysis methods:
    - Co-occurrence analysis
    - Join counts
    - Neighborhood enrichment

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    cluster_key : str, default='cell_type'
        Column containing cluster labels
    n_neighbors : int, default=6
        Number of neighbors for local analysis
    n_permutations : int, default=50
        Permutations for significance testing

    Returns
    -------
    dict
        Dictionary containing all analysis results

    Example
    -------
    >>> results = analyze_spatial_patterns(adata, cluster_key='cell_type')
    >>> print("Significant co-occurrences:", results['cooccurrence']['is_significant'].sum().sum())
    """
    print("Running co-occurrence analysis...")
    cooccur = compute_cooccurrence_probability(
        adata, cluster_key, n_neighbors, n_permutations
    )

    print("Computing join counts...")
    join_counts = compute_join_counts(adata, cluster_key, n_neighbors)

    print("Computing neighborhood enrichment...")
    enrichment = compute_neighborhood_enrichment(
        adata, cluster_key, n_neighbors, n_permutations
    )

    # Summary statistics
    n_significant_cooccur = cooccur['is_significant'].sum().sum()
    n_positive_joins = (join_counts['autocorrelation'] == 'positive').sum()
    n_enriched = (enrichment['significance'] == 'enriched').sum()

    return {
        'cooccurrence': cooccur,
        'join_counts': join_counts,
        'neighborhood_enrichment': enrichment,
        'summary': {
            'n_significant_cooccurrences': int(n_significant_cooccur),
            'n_positive_autocorrelation': int(n_positive_joins),
            'n_enriched_interactions': int(n_enriched),
            'n_total_interactions': len(enrichment)
        }
    }
