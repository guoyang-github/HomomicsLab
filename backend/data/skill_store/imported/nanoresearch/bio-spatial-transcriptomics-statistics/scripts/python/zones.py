"""
Zone Analysis for Spatial Transcriptomics

This module provides methods for defining and analyzing spatial zones:
- Anchor zones: Define regions around specific cell types
- Neural zones: Create distance-based layers from reference cells
- Ro/e analysis: Ratio of observed to expected cell type distribution
- Niche enrichment: Statistical testing for niche composition

Methods:
    - define_anchor_zones: Create zones around anchor cell types
    - define_neural_zones: Create distance-based zones from neurons
    - compute_roe: Ratio of observed/expected analysis
    - compute_niche_enrichment_stats: Statistical niche analysis
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Tuple, Union
import warnings
from scipy import stats


def define_anchor_zones(
    adata,
    anchor_cells: np.ndarray,
    n_layers: int = 5,
    max_distance: Optional[float] = None
) -> pd.DataFrame:
    """
    Define concentric zones around anchor cells.

    Creates distance-based zones (layers) around specified anchor cells.
    Useful for analyzing gradients away from reference structures.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    anchor_cells : np.ndarray
        Boolean mask or indices of anchor cells
    n_layers : int, default=5
        Number of concentric zones to create
    max_distance : float, optional
        Maximum distance to consider. If None, uses max distance to anchor.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - spot_id: Spot identifier
        - distance_to_anchor: Euclidean distance to nearest anchor
        - zone_id: Zone assignment (0 = anchor, 1 = closest, etc.)
        - zone_label: Human-readable zone label

    Example
    -------
    >>> # Define zones around tumor cells
    >>> tumor_mask = adata.obs['cell_type'] == 'Tumor'
    >>> zones = define_anchor_zones(adata, tumor_mask, n_layers=5)
    >>> adata.obs['zone'] = zones['zone_label']
    """
    coords = adata.obsm['spatial']

    # Convert anchor_cells to indices if boolean
    if anchor_cells.dtype == bool:
        anchor_indices = np.where(anchor_cells)[0]
    else:
        anchor_indices = anchor_cells

    # Compute distance to nearest anchor for each spot
    anchor_coords = coords[anchor_indices]
    distances = np.sqrt(((coords[:, None, :] - anchor_coords[None, :, :]) ** 2).sum(axis=2))
    min_distances = distances.min(axis=1)

    # Determine max distance
    if max_distance is None:
        max_distance = min_distances.max()

    # Create zone boundaries
    zone_boundaries = np.linspace(0, max_distance, n_layers + 1)

    # Assign zones
    zone_ids = np.digitize(min_distances, zone_boundaries[1:])

    # Create labels
    zone_labels = []
    for zid in zone_ids:
        if zid == 0:
            zone_labels.append('Anchor')
        else:
            zone_labels.append(f'Zone_{zid}')

    results = pd.DataFrame({
        'spot_id': adata.obs_names,
        'distance_to_anchor': min_distances,
        'zone_id': zone_ids,
        'zone_label': zone_labels
    })

    return results


def define_neural_zones(
    adata,
    neural_cell_type: str = 'Neuron',
    cluster_key: str = 'cell_type',
    n_layers: int = 5,
    max_distance: Optional[float] = None,
    layer_names: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Define distance-based zones from neural cells.

    Creates concentric layers radiating outward from neural cells,
    useful for analyzing neural invasion patterns.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    neural_cell_type : str, default='Neuron'
        Cell type identifier for neural cells
    cluster_key : str, default='cell_type'
        Column containing cell type annotations
    n_layers : int, default=5
        Number of zones to create
    max_distance : float, optional
        Maximum distance from neural cells
    layer_names : list, optional
        Custom names for layers. If None, uses numeric labels.

    Returns
    -------
    pd.DataFrame
        DataFrame with zone assignments for each spot

    Example
    -------
    >>> zones = define_neural_zones(adata, neural_cell_type='Neuron', n_layers=5)
    >>> adata.obs['neural_zone'] = zones['zone_label']
    """
    if cluster_key not in adata.obs.columns:
        raise ValueError(f"Column '{cluster_key}' not found in adata.obs")

    # Identify neural cells
    neural_mask = adata.obs[cluster_key] == neural_cell_type

    if neural_mask.sum() == 0:
        warnings.warn(f"No cells found with type '{neural_cell_type}'")
        return pd.DataFrame({
            'spot_id': adata.obs_names,
            'distance_to_neural': np.nan,
            'zone_id': -1,
            'zone_label': ['No_neural'] * adata.n_obs
        })

    # Use general anchor zone function
    zones = define_anchor_zones(adata, neural_mask, n_layers, max_distance)

    # Rename columns and apply custom layer names
    zones = zones.rename(columns={
        'distance_to_anchor': 'distance_to_neural'
    })

    if layer_names is not None and len(layer_names) == n_layers + 1:
        zone_label_map = {i: name for i, name in enumerate(layer_names)}
        zones['zone_label'] = zones['zone_id'].map(zone_label_map)
    else:
        # Default neural-specific labels
        def relabel(row):
            if row['zone_id'] == 0:
                return 'Neural_core'
            elif row['zone_id'] == 1:
                return 'Neural_proximal'
            elif row['zone_id'] == n_layers:
                return 'Distal'
            else:
                return f'Zone_{row["zone_id"]}'

        zones['zone_label'] = zones.apply(relabel, axis=1)

    return zones


def analyze_zone_composition(
    adata,
    zone_key: str = 'zone',
    cluster_key: str = 'cell_type'
) -> pd.DataFrame:
    """
    Analyze cell type composition within each zone.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data with zone annotations
    zone_key : str, default='zone'
        Column containing zone labels
    cluster_key : str, default='cell_type'
        Column containing cell type annotations

    Returns
    -------
    pd.DataFrame
        Composition matrix (zones x cell_types) with proportions

    Example
    -------
    >>> composition = analyze_zone_composition(adata, zone_key='neural_zone')
    >>> print(composition)
                   Tumor  Macrophage  T_cell
    Neural_core      0.1         0.3     0.6
    Zone_1           0.3         0.4     0.3
    """
    if zone_key not in adata.obs.columns:
        raise ValueError(f"Column '{zone_key}' not found in adata.obs")
    if cluster_key not in adata.obs.columns:
        raise ValueError(f"Column '{cluster_key}' not found in adata.obs")

    # Create crosstab
    composition = pd.crosstab(
        adata.obs[zone_key],
        adata.obs[cluster_key],
        normalize='index'
    )

    return composition


def compare_zone_gradients(
    adata,
    zone_key: str = 'zone',
    genes: Optional[List[str]] = None,
    layer: Optional[str] = None
) -> pd.DataFrame:
    """
    Compare expression gradients across zones.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    zone_key : str, default='zone'
        Column containing zone labels
    genes : list, optional
        Genes to analyze. If None, uses HVGs.
    layer : str, optional
        Layer to use for expression

    Returns
    -------
    pd.DataFrame
        DataFrame with mean expression per zone for each gene

    Example
    -------
    >>> gradients = compare_zone_gradients(adata, zone_key='neural_zone', genes=['GeneA'])
    >>> print(gradients)
                 GeneA
    Neural_core   2.34
    Zone_1        1.56
    Zone_2        0.89
    """
    if zone_key not in adata.obs.columns:
        raise ValueError(f"Column '{zone_key}' not found in adata.obs")

    # Get expression data
    if layer is not None:
        X = adata.layers[layer]
    else:
        X = adata.X

    if hasattr(X, 'toarray'):
        X = X.toarray()

    # Determine genes
    if genes is None:
        if 'highly_variable' in adata.var.columns:
            genes = adata.var_names[adata.var['highly_variable']].tolist()
        else:
            genes = adata.var_names.tolist()
    else:
        genes = [g for g in genes if g in adata.var_names]

    # Get gene indices
    gene_indices = [adata.var_names.get_loc(g) for g in genes]

    # Compute mean expression per zone
    zones = adata.obs[zone_key].unique()
    results = []

    for zone in zones:
        mask = adata.obs[zone_key] == zone
        mean_expr = X[mask][:, gene_indices].mean(axis=0)
        results.append(pd.Series(mean_expr, index=genes, name=zone))

    return pd.DataFrame(results)


def compute_roe(
    adata,
    cell_type_key: str = 'cell_type',
    niche_key: str = 'zone',
    method: str = 'chi2'
) -> pd.DataFrame:
    """
    Compute Ro/e (Ratio of observed to expected) analysis.

    Ro/e quantifies whether a cell type is enriched or depleted in a niche
    compared to random expectation. Widely used in spatial niche analysis.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    cell_type_key : str, default='cell_type'
        Column containing cell type annotations
    niche_key : str, default='zone'
        Column containing niche/zone annotations
    method : str, default='chi2'
        Method for computing expected values ('chi2', 'random', 'proportional')

    Returns
    -------
    pd.DataFrame
        DataFrame with Ro/e values (cell_types x niches)
        - Ro/e > 1: Enriched in niche
        - Ro/e < 1: Depleted in niche
        - Ro/e = 1: As expected

    References
    ----------
    Moncada et al. (2020). Integrating microarray-based spatial transcriptomics
    and single-cell RNA-seq reveals tissue architecture in pancreatic ductal
    adenocarcinomas. Nature Biotechnology, 38(3), 333-342.

    Example
    -------
    >>> roe = compute_roe(adata, cell_type_key='cell_type', niche_key='neural_zone')
    >>> print(roe)
                  Neural_core   Zone_1   Zone_2
    Tumor             0.523    1.234    2.456
    Macrophage        1.234    0.876    0.654
    >>> # Tumor is depleted in neural core (0.523 < 1) but enriched in distal zones
    """
    if cell_type_key not in adata.obs.columns:
        raise ValueError(f"Column '{cell_type_key}' not found in adata.obs")
    if niche_key not in adata.obs.columns:
        raise ValueError(f"Column '{niche_key}' not found in adata.obs")

    # Create contingency table
    observed = pd.crosstab(
        adata.obs[cell_type_key],
        adata.obs[niche_key]
    )

    # Compute expected values
    if method == 'chi2':
        # Chi-square expected: (row_total * col_total) / grand_total
        row_totals = observed.sum(axis=1).values.reshape(-1, 1)
        col_totals = observed.sum(axis=0).values.reshape(1, -1)
        grand_total = observed.values.sum()
        expected = (row_totals @ col_totals) / grand_total

    elif method == 'proportional':
        # Each niche has same proportional composition as overall
        overall_props = observed.sum(axis=1) / observed.values.sum()
        niche_totals = observed.sum(axis=0)
        expected = pd.DataFrame(
            np.outer(overall_props, niche_totals),
            index=observed.index,
            columns=observed.columns
        )

    else:
        raise ValueError(f"Unknown method: {method}")

    # Compute Ro/e
    roe = observed / (expected + 1e-10)

    return roe


def interpret_roe_results(
    roe_df: pd.DataFrame,
    enrichment_threshold: float = 1.2,
    depletion_threshold: float = 0.8
) -> pd.DataFrame:
    """
    Generate interpretation of Ro/e results.

    Parameters
    ----------
    roe_df : pd.DataFrame
        Results from compute_roe()
    enrichment_threshold : float, default=1.2
        Ro/e value above which to call enrichment
    depletion_threshold : float, default=0.8
        Ro/e value below which to call depletion

    Returns
    -------
    pd.DataFrame
        DataFrame with interpretation strings for each cell type-niche pair

    Example
    -------
    >>> roe = compute_roe(adata)
    >>> interpretation = interpret_roe_results(roe)
    >>> print(interpretation)
    """
    interpretations = []

    for cell_type in roe_df.index:
        for niche in roe_df.columns:
            roe_val = roe_df.loc[cell_type, niche]

            if roe_val > enrichment_threshold:
                interpretation = f"Enriched (Ro/e={roe_val:.2f})"
            elif roe_val < depletion_threshold:
                interpretation = f"Depleted (Ro/e={roe_val:.2f})"
            else:
                interpretation = f"Neutral (Ro/e={roe_val:.2f})"

            interpretations.append({
                'cell_type': cell_type,
                'niche': niche,
                'roe': roe_val,
                'interpretation': interpretation
            })

    return pd.DataFrame(interpretations)


def plot_roe_heatmap(
    roe_df: pd.DataFrame,
    title: str = 'Ro/e Analysis',
    cmap: str = 'RdYlBu_r',
    center: float = 1.0,
    figsize: Tuple[int, int] = (10, 8),
    save_path: Optional[str] = None
):
    """
    Plot Ro/e results as a heatmap.

    Parameters
    ----------
    roe_df : pd.DataFrame
        Ro/e matrix from compute_roe()
    title : str, default='Ro/e Analysis'
        Plot title
    cmap : str, default='RdYlBu_r'
        Colormap (red for high, blue for low)
    center : float, default=1.0
        Center value for colormap (neutral Ro/e)
    figsize : tuple, default=(10, 8)
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    matplotlib.axes.Axes
        Axes object with heatmap

    Example
    -------
    >>> roe = compute_roe(adata)
    >>> ax = plot_roe_heatmap(roe, title='Cell Type by Neural Zone')
    """
    try:
        import seaborn as sns
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("seaborn and matplotlib are required for plotting")

    fig, ax = plt.subplots(figsize=figsize)

    # Create heatmap
    sns.heatmap(
        roe_df,
        annot=True,
        fmt='.2f',
        cmap=cmap,
        center=center,
        vmin=0,
        vmax=max(2, roe_df.values.max()),
        cbar_kws={'label': 'Ro/e (Observed/Expected)'},
        ax=ax
    )

    ax.set_xlabel('Niche/Zone', fontsize=12)
    ax.set_ylabel('Cell Type', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return ax


def compute_niche_enrichment_stats(
    adata,
    cell_type_key: str = 'cell_type',
    niche_key: str = 'zone',
    test_method: str = 'chi2'
) -> Dict:
    """
    Compute statistical enrichment of cell types in niches.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    cell_type_key : str, default='cell_type'
        Column containing cell type annotations
    niche_key : str, default='zone'
        Column containing niche annotations
    test_method : str, default='chi2'
        Statistical test ('chi2', 'fisher', 'hypergeometric')

    Returns
    -------
    dict
        Dictionary containing:
        - roe: Ro/e matrix
        - observed: Observed counts
        - expected: Expected counts
        - p_values: P-value matrix
        - significant: Boolean matrix of significant enrichments

    Example
    -------
    >>> results = compute_niche_enrichment_stats(adata)
    >>> print(results['roe'])
    >>> print("Significant enrichments:", results['significant'].sum().sum())
    """
    if cell_type_key not in adata.obs.columns:
        raise ValueError(f"Column '{cell_type_key}' not found in adata.obs")
    if niche_key not in adata.obs.columns:
        raise ValueError(f"Column '{niche_key}' not found in adata.obs")

    # Ro/e analysis
    roe = compute_roe(adata, cell_type_key, niche_key)

    # Observed and expected counts
    observed = pd.crosstab(adata.obs[cell_type_key], adata.obs[niche_key])
    row_totals = observed.sum(axis=1).values.reshape(-1, 1)
    col_totals = observed.sum(axis=0).values.reshape(1, -1)
    grand_total = observed.values.sum()
    expected = (row_totals @ col_totals) / grand_total

    # Statistical testing
    if test_method == 'chi2':
        # Chi-square test for each cell type-niche pair
        p_values = pd.DataFrame(
            np.zeros_like(roe.values),
            index=roe.index,
            columns=roe.columns
        )

        for i, cell_type in enumerate(roe.index):
            for j, niche in enumerate(roe.columns):
                # 2x2 contingency table for this specific cell type and niche
                a = observed.iloc[i, j]  # In niche and is cell type
                b = row_totals[i] - a    # Not in niche but is cell type
                c = col_totals[0, j] - a # In niche but not cell type
                d = grand_total - a - b - c  # Neither

                table = [[a, b[0]], [c, d]]

                try:
                    _, p_val, _, _ = stats.chi2_contingency(table)
                except ValueError:
                    p_val = 1.0

                p_values.iloc[i, j] = p_val

        # Bonferroni correction
        n_tests = p_values.size
        p_values_corrected = p_values * n_tests
        p_values_corrected = p_values_corrected.clip(upper=1.0)

    else:
        raise ValueError(f"Unknown test method: {test_method}")

    # Significance matrix (enriched and significant)
    significant = (roe > 1.2) & (p_values_corrected < 0.05)

    return {
        'roe': roe,
        'observed': observed,
        'expected': pd.DataFrame(expected, index=observed.index, columns=observed.columns),
        'p_values': p_values_corrected,
        'significant': significant
    }


def analyze_spatial_zones(
    adata,
    anchor_cell_type: Optional[str] = None,
    anchor_cells: Optional[np.ndarray] = None,
    cell_type_key: str = 'cell_type',
    n_layers: int = 5,
    zone_type: str = 'anchor'
) -> Dict:
    """
    Comprehensive spatial zone analysis.

    This function combines zone definition, composition analysis, and Ro/e testing.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    anchor_cell_type : str, optional
        Cell type to use as anchor (for zone_type='neural')
    anchor_cells : np.ndarray, optional
        Boolean mask for anchor cells (for zone_type='anchor')
    cell_type_key : str, default='cell_type'
        Column containing cell type annotations
    n_layers : int, default=5
        Number of zones to create
    zone_type : str, default='anchor'
        Type of zones ('anchor' or 'neural')

    Returns
    -------
    dict
        Dictionary containing:
        - zones: Zone assignments DataFrame
        - composition: Cell type composition per zone
        - roe: Ro/e analysis results
        - enrichment: Statistical enrichment results

    Example
    -------
    >>> results = analyze_spatial_zones(
    ...     adata,
    ...     anchor_cell_type='Neuron',
    ...     zone_type='neural',
    ...     n_layers=5
    ... )
    >>> print(results['composition'])
    >>> print(results['roe'])
    """
    # Define zones
    if zone_type == 'neural':
        if anchor_cell_type is None:
            raise ValueError("anchor_cell_type required for neural zones")
        zones = define_neural_zones(
            adata,
            neural_cell_type=anchor_cell_type,
            cluster_key=cell_type_key,
            n_layers=n_layers
        )
    elif zone_type == 'anchor':
        if anchor_cells is None:
            raise ValueError("anchor_cells required for anchor zones")
        zones = define_anchor_zones(adata, anchor_cells, n_layers)
    else:
        raise ValueError(f"Unknown zone_type: {zone_type}")

    # Add zones to adata temporarily
    zone_column = f"{zone_type}_zone"
    adata.obs[zone_column] = zones['zone_label'].values

    # Analyze composition
    composition = analyze_zone_composition(adata, zone_column, cell_type_key)

    # Ro/e analysis
    roe_results = compute_niche_enrichment_stats(adata, cell_type_key, zone_column)

    return {
        'zones': zones,
        'composition': composition,
        'roe': roe_results['roe'],
        'observed': roe_results['observed'],
        'expected': roe_results['expected'],
        'p_values': roe_results['p_values'],
        'significant_enrichments': roe_results['significant']
    }
