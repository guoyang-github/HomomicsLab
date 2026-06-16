"""
Hotspot Detection for Spatial Transcriptomics

This module provides hotspot and coldspot detection methods based on
Getis-Ord Gi* statistics. Hotspots represent areas of statistically
significant high values, while coldspots represent areas of low values.

Methods:
    - Getis-Ord Gi*: Identify statistically significant clusters
    - Batch processing: Analyze multiple genes simultaneously
    - Hotspot extraction: Filter and categorize significant spots
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Tuple, Union
import warnings


def compute_getis_ord_gi(
    adata,
    gene: str,
    k: int = 6,
    permutations: int = 999,
    layer: Optional[str] = None
) -> pd.DataFrame:
    """
    Compute Getis-Ord Gi* statistic for hotspot detection.

    Getis-Ord Gi* identifies statistically significant spatial clusters
    of high values (hotspots) or low values (coldspots). Unlike Moran's I
    which measures overall autocorrelation, Gi* identifies specific locations
    that contribute significantly to clustering.

    The Gi* statistic includes the focal location in the neighborhood,
    making it appropriate for identifying cluster centers.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data with coordinates in adata.obsm['spatial']
    gene : str
        Gene to analyze for hotspots
    k : int, default=6
        Number of nearest neighbors for spatial weights
    permutations : int, default=999
        Number of permutations for significance testing
    layer : str, optional
        Which layer to use. If None, uses adata.X

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - spot_id: Spot identifier
        - gi_star: Getis-Ord Gi* statistic
        - p_value: Significance value
        - z_score: Standardized z-score
        - classification: Hotspot classification (Hotspot, Coldspot, Not significant)
        - expression: Expression value at spot

    References
    ----------
    Getis, A., & Ord, J.K. (1992). The analysis of spatial association
    by use of distance statistics. Geographical Analysis, 24(3), 189-206.

    Example
    -------
    >>> results = compute_getis_ord_gi(adata, gene='GeneA', k=6)
    >>> print(results.head())
      spot_id    gi_star   p_value   z_score      classification  expression
    0    spot_0   2.345678  0.000019  3.456789           Hotspot    2.345678
    1    spot_1  -1.987654  0.046543 -1.987654  Not significant    0.123456
    """
    try:
        from libpysal.weights import KNN
        from esda.getisord import G_Local
    except ImportError:
        raise ImportError(
            "libpysal and esda are required for Getis-Ord Gi* computation. "
            "Install: pip install libpysal esda"
        )

    if gene not in adata.var_names:
        raise ValueError(f"Gene '{gene}' not found in adata")

    # Get expression data
    if layer is not None:
        X = adata.layers[layer]
    else:
        X = adata.X

    if hasattr(X, 'toarray'):
        X = X.toarray()

    gene_idx = adata.var_names.get_loc(gene)
    y = X[:, gene_idx]

    # Build spatial weights
    coords = adata.obsm['spatial']
    weights = KNN(coords, k=k)
    weights.transform = 'r'

    # Compute Gi* (star=True includes focal observation)
    g_star = G_Local(y, weights, permutations=permutations, star=True)

    # Classify hotspots based on z-scores
    # Common thresholds: z > 1.96 (hotspot), z < -1.96 (coldspot) at p < 0.05
    classifications = []
    for z, p in zip(g_star.z_sim, g_star.p_sim):
        if p < 0.05 and z > 0:
            classifications.append('Hotspot')
        elif p < 0.05 and z < 0:
            classifications.append('Coldspot')
        else:
            classifications.append('Not significant')

    results = pd.DataFrame({
        'spot_id': adata.obs_names,
        'gi_star': g_star.Gs,
        'p_value': g_star.p_sim,
        'z_score': g_star.z_sim,
        'classification': classifications,
        'expression': y
    })

    return results


def compute_getis_ord_gi_batch(
    adata,
    genes: Optional[List[str]] = None,
    k: int = 6,
    alpha: float = 0.05,
    min_spots: int = 5,
    layer: Optional[str] = None
) -> pd.DataFrame:
    """
    Compute Getis-Ord Gi* for multiple genes and summarize hotspots.

    This batch function runs Gi* analysis on multiple genes and returns
    a summary table showing which genes have significant hotspots/coldspots
    and their spatial extent.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    genes : list, optional
        List of genes to analyze. If None, uses highly variable genes.
    k : int, default=6
        Number of nearest neighbors
    alpha : float, default=0.05
        Significance threshold
    min_spots : int, default=5
        Minimum number of spots to be considered a meaningful hotspot
    layer : str, optional
        Which layer to use

    Returns
    -------
    pd.DataFrame
        Summary DataFrame with columns:
        - gene: Gene name
        - n_hotspots: Number of hotspot spots
        - n_coldspots: Number of coldspot spots
        - hotspot_ratio: Proportion of spots that are hotspots
        - mean_gi_star: Mean Gi* value across all spots
        - max_z_score: Maximum z-score (most significant hotspot)
        - min_z_score: Minimum z-score (most significant coldspot)
        - has_significant_pattern: Whether gene has significant spatial pattern

    Example
    -------
    >>> results = compute_getis_ord_gi_batch(adata, genes=['GeneA', 'GeneB'])
    >>> print(results)
         gene  n_hotspots  n_coldspots  hotspot_ratio  has_significant_pattern
    0  GeneA          45           12           0.15                     True
    1  GeneB           3            8           0.02                    False
    """
    # Determine genes to analyze
    if genes is None:
        if 'highly_variable' in adata.var.columns:
            genes = adata.var_names[adata.var['highly_variable']].tolist()
        else:
            genes = adata.var_names.tolist()
    else:
        genes = [g for g in genes if g in adata.var_names]

    if len(genes) == 0:
        raise ValueError("No valid genes found")

    summaries = []

    for gene in genes:
        try:
            gi_results = compute_getis_ord_gi(adata, gene=gene, k=k, layer=layer)

            n_hotspots = (gi_results['classification'] == 'Hotspot').sum()
            n_coldspots = (gi_results['classification'] == 'Coldspot').sum()
            hotspot_ratio = (n_hotspots + n_coldspots) / len(gi_results)

            # Check if pattern is significant
            has_pattern = (n_hotspots >= min_spots or n_coldspots >= min_spots)

            summary = {
                'gene': gene,
                'n_hotspots': n_hotspots,
                'n_coldspots': n_coldspots,
                'hotspot_ratio': hotspot_ratio,
                'mean_gi_star': gi_results['gi_star'].mean(),
                'max_z_score': gi_results['z_score'].max(),
                'min_z_score': gi_results['z_score'].min(),
                'has_significant_pattern': has_pattern
            }
            summaries.append(summary)

        except Exception as e:
            warnings.warn(f"Failed to compute Gi* for {gene}: {e}")
            summaries.append({
                'gene': gene,
                'n_hotspots': 0,
                'n_coldspots': 0,
                'hotspot_ratio': 0,
                'mean_gi_star': np.nan,
                'max_z_score': np.nan,
                'min_z_score': np.nan,
                'has_significant_pattern': False
            })

    return pd.DataFrame(summaries)


def extract_hotspots(
    gi_results: pd.DataFrame,
    classification: str = 'Hotspot',
    min_z_score: Optional[float] = None
) -> pd.DataFrame:
    """
    Extract specific hotspot or coldspot spots from Gi* results.

    Parameters
    ----------
    gi_results : pd.DataFrame
        Results from compute_getis_ord_gi()
    classification : str, default='Hotspot'
        Which classification to extract ('Hotspot', 'Coldspot', or 'Not significant')
    min_z_score : float, optional
        Minimum absolute z-score for filtering. If None, uses all of specified type.

    Returns
    -------
    pd.DataFrame
        Filtered DataFrame containing only spots of specified type

    Example
    -------
    >>> gi_results = compute_getis_ord_gi(adata, gene='GeneA')
    >>> hotspots = extract_hotspots(gi_results, classification='Hotspot', min_z_score=2.0)
    >>> print(f"Found {len(hotspots)} significant hotspots")
    """
    filtered = gi_results[gi_results['classification'] == classification].copy()

    if min_z_score is not None:
        if classification == 'Hotspot':
            filtered = filtered[filtered['z_score'] >= min_z_score]
        elif classification == 'Coldspot':
            filtered = filtered[filtered['z_score'] <= -min_z_score]
        else:
            filtered = filtered[filtered['z_score'].abs() <= min_z_score]

    return filtered.sort_values('z_score', ascending=(classification == 'Coldspot'))


def plot_hotspots(
    adata,
    gi_results: pd.DataFrame,
    title: str = 'Hotspot Analysis',
    spot_size: float = 10,
    cmap_hot: str = 'Reds',
    cmap_cold: str = 'Blues',
    show_colorbar: bool = True,
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 8)
):
    """
    Plot hotspot analysis results on spatial coordinates.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    gi_results : pd.DataFrame
        Results from compute_getis_ord_gi()
    title : str, default='Hotspot Analysis'
        Plot title
    spot_size : float, default=10
        Size of spots in plot
    cmap_hot : str, default='Reds'
        Colormap for hotspots
    cmap_cold : str, default='Blues'
        Colormap for coldspots
    show_colorbar : bool, default=True
        Whether to show colorbar
    save_path : str, optional
        Path to save figure. If None, displays plot.
    figsize : tuple, default=(10, 8)
        Figure size

    Returns
    -------
    matplotlib.figure.Figure
        Figure object containing the plots

    Example
    -------
    >>> gi_results = compute_getis_ord_gi(adata, gene='GeneA')
    >>> fig = plot_hotspots(adata, gi_results, title='GeneA Hotspots')
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib is required for plotting. Install: pip install matplotlib")

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Get coordinates
    coords = adata.obsm['spatial']

    # Plot 1: Expression values
    ax1 = axes[0]
    scatter1 = ax1.scatter(
        coords[:, 0],
        coords[:, 1],
        c=gi_results['expression'],
        cmap='viridis',
        s=spot_size,
        edgecolors='none'
    )
    ax1.set_title('Expression')
    ax1.set_aspect('equal')
    ax1.invert_yaxis()  # Standard for spatial plots
    if show_colorbar:
        plt.colorbar(scatter1, ax=ax1, label='Expression')

    # Plot 2: Gi* z-scores (hotspot/coldspot)
    ax2 = axes[1]

    # Create color array based on classification
    colors = gi_results['z_score'].values.copy()
    mask_hot = gi_results['classification'] == 'Hotspot'
    mask_cold = gi_results['classification'] == 'Coldspot'
    mask_ns = gi_results['classification'] == 'Not significant'

    # Plot non-significant spots in gray
    if mask_ns.any():
        ax2.scatter(
            coords[mask_ns, 0],
            coords[mask_ns, 1],
            c='lightgray',
            s=spot_size,
            edgecolors='none',
            alpha=0.3,
            label='Not significant'
        )

    # Plot hotspots and coldspots
    if mask_hot.any():
        scatter_hot = ax2.scatter(
            coords[mask_hot, 0],
            coords[mask_hot, 1],
            c=colors[mask_hot],
            cmap=cmap_hot,
            s=spot_size,
            edgecolors='none',
            vmin=0,
            label='Hotspot'
        )

    if mask_cold.any():
        scatter_cold = ax2.scatter(
            coords[mask_cold, 0],
            coords[mask_cold, 1],
            c=colors[mask_cold],
            cmap=cmap_cold,
            s=spot_size,
            edgecolors='none',
            vmax=0,
            label='Coldspot'
        )

    ax2.set_title('Getis-Ord Gi* (z-scores)')
    ax2.set_aspect('equal')
    ax2.invert_yaxis()

    # Add legend
    handles = []
    if mask_hot.any():
        handles.append(plt.Line2D([0], [0], marker='o', color='w',
                                 markerfacecolor='red', markersize=8, label='Hotspot'))
    if mask_cold.any():
        handles.append(plt.Line2D([0], [0], marker='o', color='w',
                                 markerfacecolor='blue', markersize=8, label='Coldspot'))
    if mask_ns.any():
        handles.append(plt.Line2D([0], [0], marker='o', color='w',
                                 markerfacecolor='lightgray', markersize=8, label='Not sig.'))
    ax2.legend(handles=handles, loc='upper right')

    fig.suptitle(title, fontsize=14, fontweight='bold')
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def comprehensive_hotspot_analysis(
    adata,
    genes: List[str],
    k: int = 6,
    alpha: float = 0.05,
    min_hotspot_spots: int = 5,
    layer: Optional[str] = None
) -> Dict:
    """
    Run comprehensive hotspot analysis on multiple genes.

    This function combines batch Gi* computation with summary statistics
    and returns a complete analysis package.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    genes : list
        List of genes to analyze
    k : int, default=6
        Number of nearest neighbors
    alpha : float, default=0.05
        Significance threshold
    min_hotspot_spots : int, default=5
        Minimum spots to consider a pattern significant
    layer : str, optional
        Which layer to use

    Returns
    -------
    dict
        Dictionary containing:
        - 'summary': Batch summary DataFrame
        - 'detailed_results': Dict of detailed Gi* results per gene
        - 'genes_with_hotspots': List of genes with significant hotspots
        - 'genes_with_coldspots': List of genes with significant coldspots
        - 'top_hotspot_genes': Genes ranked by hotspot strength

    Example
    -------
    >>> results = comprehensive_hotspot_analysis(
    ...     adata,
    ...     genes=['GeneA', 'GeneB', 'GeneC'],
    ...     k=6
    ... )
    >>> print("Genes with hotspots:", results['genes_with_hotspots'])
    """
    print(f"Running hotspot analysis on {len(genes)} genes...")

    # Run batch analysis
    summary = compute_getis_ord_gi_batch(
        adata,
        genes=genes,
        k=k,
        alpha=alpha,
        min_spots=min_hotspot_spots,
        layer=layer
    )

    # Get detailed results for significant genes
    significant_genes = summary[summary['has_significant_pattern']]['gene'].tolist()
    detailed_results = {}

    print(f"Computing detailed results for {len(significant_genes)} significant genes...")
    for gene in significant_genes:
        try:
            detailed_results[gene] = compute_getis_ord_gi(adata, gene=gene, k=k, layer=layer)
        except Exception as e:
            warnings.warn(f"Failed to get detailed results for {gene}: {e}")

    # Extract genes with specific patterns
    genes_with_hotspots = summary[
        summary['n_hotspots'] >= min_hotspot_spots
    ]['gene'].tolist()

    genes_with_coldspots = summary[
        summary['n_coldspots'] >= min_hotspot_spots
    ]['gene'].tolist()

    # Rank genes by hotspot strength (max z-score)
    top_hotspot_genes = summary.nlargest(10, 'max_z_score')['gene'].tolist()

    return {
        'summary': summary,
        'detailed_results': detailed_results,
        'genes_with_hotspots': genes_with_hotspots,
        'genes_with_coldspots': genes_with_coldspots,
        'top_hotspot_genes': top_hotspot_genes
    }
