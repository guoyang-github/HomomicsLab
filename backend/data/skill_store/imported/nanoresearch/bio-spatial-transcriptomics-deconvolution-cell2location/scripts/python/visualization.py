"""
Visualization functions for cell2location results.

Author: Yang Guo
Date: 2026-03-31
"""

from typing import Optional, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData


def plot_proportions_spatial(
    spatial_adata: AnnData,
    cell_types: Optional[List[str]] = None,
    ncols: int = 4,
    figsize: Tuple[int, int] = (16, 12),
    cmap: str = 'viridis',
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot cell type proportions on spatial coordinates.

    Parameters
    ----------
    spatial_adata : AnnData
        Data with cell2location results
    cell_types : List[str], optional
        Cell types to plot. If None, plots all.
    ncols : int, default=4
        Number of columns in subplot grid
    figsize : tuple, default=(16, 12)
        Figure size
    cmap : str, default='viridis'
        Colormap
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure

    Examples
    --------
    >>> fig = plot_proportions_spatial(adata, cell_types=['T_cell', 'B_cell'])
    """
    # Extract proportions
    from .core_analysis import extract_proportions
    props_df, all_cell_types = extract_proportions(spatial_adata)

    if cell_types is None:
        cell_types = all_cell_types

    # Filter to requested cell types
    props_df = props_df[[ct for ct in cell_types if ct in props_df.columns]]

    # Calculate grid size
    n_plots = len(props_df.columns)
    nrows = (n_plots + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    if isinstance(axes, np.ndarray):
        axes = axes.flatten()
    else:
        axes = [axes]

    for idx, cell_type in enumerate(props_df.columns):
        ax = axes[idx]

        # Get coordinates and values
        if 'spatial' in spatial_adata.obsm:
            coords = spatial_adata.obsm['spatial']
        else:
            coords = spatial_adata.obs[['array_row', 'array_col']].values

        values = props_df[cell_type].values

        # Scatter plot
        sc = ax.scatter(
            coords[:, 0],
            coords[:, 1],
            c=values,
            cmap=cmap,
            s=20,
            alpha=0.8
        )

        ax.set_title(cell_type)
        ax.set_aspect('equal')
        ax.axis('off')

        plt.colorbar(sc, ax=ax, fraction=0.046)

    # Hide unused subplots
    for idx in range(n_plots, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved to {save_path}")

    return fig


def plot_cell_type_maps(
    spatial_adata: AnnData,
    cell_type: str,
    figsize: Tuple[int, int] = (12, 5),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot cell type map with comparison of q05/q50/q95 estimates.

    Parameters
    ----------
    spatial_adata : AnnData
        Data with cell2location results
    cell_type : str
        Cell type to visualize
    figsize : tuple, default=(12, 5)
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure
    """
    fig, axes = plt.subplots(1, 3, figsize=figsize)

    quantiles = ['q05', 'q50', 'q95']
    titles = ['5% Quantile', 'Median (50%)', '95% Quantile']

    for ax, q, title in zip(axes, quantiles, titles):
        key = f'{q}_cell_abundance_w_sf'

        if key not in spatial_adata.obsm:
            ax.text(0.5, 0.5, f'{key} not found', ha='center', va='center')
            ax.axis('off')
            continue

        # Get proportions
        props = spatial_adata.obsm[key]
        col = f"{key}_{cell_type}"

        if col not in props.columns:
            ax.text(0.5, 0.5, f'{cell_type} not found', ha='center', va='center')
            ax.axis('off')
            continue

        values = props[col].values

        # Get coordinates
        if 'spatial' in spatial_adata.obsm:
            coords = spatial_adata.obsm['spatial']
        else:
            coords = spatial_adata.obs[['array_row', 'array_col']].values

        sc = ax.scatter(
            coords[:, 0],
            coords[:, 1],
            c=values,
            cmap='viridis',
            s=30,
            alpha=0.8
        )

        ax.set_title(f'{cell_type} - {title}')
        ax.set_aspect('equal')
        ax.axis('off')
        plt.colorbar(sc, ax=ax, fraction=0.046)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_proportion_distribution(
    spatial_adata: AnnData,
    cell_types: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (10, 6),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot distribution of cell type proportions across spots.

    Parameters
    ----------
    spatial_adata : AnnData
        Data with cell2location results
    cell_types : List[str], optional
        Cell types to include
    figsize : tuple, default=(10, 6)
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure
    """
    from .core_analysis import extract_proportions

    props_df, all_cell_types = extract_proportions(spatial_adata)

    if cell_types is None:
        # Select top 8 by mean proportion
        cell_types = props_df.mean().nlargest(8).index.tolist()

    props_df = props_df[[ct for ct in cell_types if ct in props_df.columns]]

    fig, ax = plt.subplots(figsize=figsize)

    # Box plot
    props_df.boxplot(ax=ax, rot=45)
    ax.set_ylabel('Cell Type Proportion')
    ax.set_title('Distribution of Cell Type Proportions')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_dominant_cell_type(
    spatial_adata: AnnData,
    figsize: Tuple[int, int] = (10, 8),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot dominant cell type per spot.

    Parameters
    ----------
    spatial_adata : AnnData
        Data with cell2location results
    figsize : tuple, default=(10, 8)
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure
    """
    from .core_analysis import extract_proportions

    props_df, cell_types = extract_proportions(spatial_adata)

    # Get dominant cell type per spot
    dominant = props_df.idxmax(axis=1)
    max_prop = props_df.max(axis=1)

    # Mark all-zero spots as "None" to avoid misleading dominant assignment
    all_zero_mask = max_prop == 0
    if all_zero_mask.any():
        dominant = dominant.copy()
        dominant[all_zero_mask] = "None"

    # Create color map
    unique_types = props_df.columns.unique().tolist()
    if all_zero_mask.any() and "None" not in unique_types:
        unique_types.append("None")
    colors = plt.cm.tab20(np.linspace(0, 1, len(unique_types)))
    color_map = dict(zip(unique_types, colors))
    # Use gray for "None"
    if "None" in color_map:
        color_map["None"] = (0.7, 0.7, 0.7, 1.0)

    fig, ax = plt.subplots(figsize=figsize)

    # Get coordinates
    if 'spatial' in spatial_adata.obsm:
        coords = spatial_adata.obsm['spatial']
    else:
        coords = spatial_adata.obs[['array_row', 'array_col']].values

    # Plot each spot colored by dominant cell type
    for cell_type in unique_types:
        mask = dominant == cell_type
        if not mask.any():
            continue
        ax.scatter(
            coords[mask, 0],
            coords[mask, 1],
            c=[color_map[cell_type]],
            s=30,
            alpha=0.8,
            label=cell_type
        )

    ax.set_title('Dominant Cell Type per Spot')
    ax.set_aspect('equal')
    ax.axis('off')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def normalize_proportions(props_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize proportions to sum to 1 per spot.

    Parameters
    ----------
    props_df : pd.DataFrame
        DataFrame with cell type proportions (spots x cell_types)

    Returns
    -------
    pd.DataFrame
        Normalized proportions

    Examples
    --------
    >>> props = pd.DataFrame({'A': [1, 2], 'B': [1, 2]})
    >>> normalized = normalize_proportions(props)
    >>> print(normalized.sum(axis=1))  # Should be [1.0, 1.0]
    """
    normalized = props_df.div(props_df.sum(axis=1), axis=0)
    normalized = normalized.fillna(0)
    return normalized
