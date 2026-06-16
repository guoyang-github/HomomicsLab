"""
Visualization functions for Tangram results.

This module provides plotting utilities for Tangram mapping results,
training diagnostics, and spatial visualizations.

Author: Yang Guo
Date: 2026-04-03
"""

from typing import Optional, List, Tuple, Union
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.gridspec import GridSpec
import numpy as np
import pandas as pd
import scanpy as sc
import seaborn as sns
from anndata import AnnData
import logging

logger = logging.getLogger(__name__)


def check_tangram_installed():
    """Check if tangram is installed. Re-export from core_analysis for convenience."""
    try:
        import tangram as tg
        return tg
    except ImportError:
        raise ImportError("tangram-sc not installed. Run: pip install tangram-sc")


def plot_training_scores(
    adata_map: AnnData,
    bins: int = 10,
    alpha: float = 0.7,
    figsize: Tuple[int, int] = (12, 3),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot 4-panel training diagnosis for training genes.

    Shows training scores vs gene sparsity to diagnose mapping quality.

    Parameters
    ----------
    adata_map : AnnData
        Mapping result from map_cells_to_space
    bins : int, default=10
        Number of bins for histogram
    alpha : float, default=0.7
        Transparency for scatter plots
    figsize : tuple, default=(12, 3)
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure

    Examples
    --------
    >>> fig = plot_training_scores(adata_map)
    >>> fig.savefig('training_scores.png', dpi=300)
    """
    if 'train_genes_df' not in adata_map.uns:
        raise KeyError("'train_genes_df' not found in adata_map.uns. Run map_cells_to_space() first.")

    fig, axs = plt.subplots(1, 4, figsize=figsize, sharey=True)
    df = adata_map.uns["train_genes_df"]
    axs_f = axs.flatten()

    # Set limits for axis
    axs_f[0].set_ylim([0.0, 1.0])
    for i in range(1, len(axs_f)):
        axs_f[i].set_xlim([0.0, 1.0])
        axs_f[i].set_ylim([0.0, 1.0])

    # Training scores histogram
    sns.histplot(data=df, y="train_score", bins=bins, ax=axs_f[0], color="coral")
    axs_f[0].set_xlabel("Count")
    axs_f[0].set_ylabel("Training Score")

    # Score vs sparsity (single cells)
    axs_f[1].set_title("Score vs Sparsity (scRNA-seq)")
    sns.scatterplot(
        data=df, y="train_score", x="sparsity_sc",
        ax=axs_f[1], alpha=alpha, color="coral"
    )
    axs_f[1].set_xlabel("Sparsity (scRNA-seq)")

    # Score vs sparsity (spatial)
    axs_f[2].set_title("Score vs Sparsity (Spatial)")
    sns.scatterplot(
        data=df, y="train_score", x="sparsity_sp",
        ax=axs_f[2], alpha=alpha, color="coral"
    )
    axs_f[2].set_xlabel("Sparsity (Spatial)")

    # Score vs sparsity difference
    axs_f[3].set_title("Score vs Sparsity Difference")
    sns.scatterplot(
        data=df, y="train_score", x="sparsity_diff",
        ax=axs_f[3], alpha=alpha, color="coral"
    )
    axs_f[3].set_xlabel("Sparsity Diff (Spatial - scRNA)")

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_test_scores(
    df_gene_score: pd.DataFrame,
    bins: int = 10,
    alpha: float = 0.7,
    figsize: Tuple[int, int] = (12, 3),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot test gene scores from cross-validation.

    Parameters
    ----------
    df_gene_score : pd.DataFrame
        Output from compare_spatial_geneexp
    bins : int, default=10
        Number of bins for histogram
    alpha : float, default=0.7
        Transparency for scatter plots
    figsize : tuple, default=(12, 3)
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure

    Examples
    --------
    >>> df_compare = compare_spatial_geneexp(adata_ge, adata_sp, adata_sc)
    >>> fig = plot_test_scores(df_compare)
    """
    tg = check_tangram_installed()

    fig = tg.plot_test_scores(df_gene_score, bins=bins, alpha=alpha)

    if save_path and hasattr(fig, 'savefig'):
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_cell_annotation(
    adata_map: AnnData,
    adata_sp: AnnData,
    annotation: str = 'cell_type',
    x: str = 'x',
    y: str = 'y',
    nrows: int = 1,
    ncols: int = 1,
    s: float = 5,
    cmap: str = 'viridis',
    subtitle_add: bool = False,
    robust: bool = False,
    perc: float = 0,
    invert_y: bool = True,
    save_path: Optional[str] = None,
) -> Optional[plt.Figure]:
    """
    Plot cell type annotations projected onto spatial coordinates.

    Creates a grid of spatial plots showing cell type probabilities.
    NOTE: This function uses Tangram's native plotting which manages its own
    figure creation. figsize control is not supported.

    Parameters
    ----------
    adata_map : AnnData
        Mapping result from map_cells_to_space
    adata_sp : AnnData
        Spatial data (modified in-place with projection)
    annotation : str, default='cell_type'
        Column in adata_map.obs to project
    x, y : str, default='x', 'y'
        Columns in adata_map.var for coordinates
    nrows, ncols : int, default=1
        Grid dimensions
    s : float, default=5
        Marker size
    cmap : str, default='viridis'
        Colormap
    subtitle_add : bool, default=False
        Add annotation name as subtitle
    robust : bool, default=False
        Use percentiles for colormap range
    perc : float, default=0
        Percentile for robust colormap
    invert_y : bool, default=True
        Invert y-axis
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure or None
        Current matplotlib figure after plotting

    Examples
    --------
    >>> plot_cell_annotation(
    ...     adata_map, adata_sp, annotation='cell_type',
    ...     nrows=2, ncols=3, s=10
    ... )
    """
    tg = check_tangram_installed()

    tg.plot_cell_annotation(
        adata_map=adata_map,
        adata_sp=adata_sp,
        annotation=annotation,
        x=x, y=y,
        nrows=nrows,
        ncols=ncols,
        s=s,
        cmap=cmap,
        subtitle_add=subtitle_add,
        robust=robust,
        perc=perc,
        invert_y=invert_y,
    )

    if save_path:
        plt.gcf().savefig(save_path, dpi=300, bbox_inches='tight')

    return plt.gcf()


def plot_cell_annotation_sc(
    adata_sp: AnnData,
    annotation_list: List[str],
    x: str = 'x',
    y: str = 'y',
    spot_size: Optional[float] = None,
    scale_factor: Optional[float] = None,
    perc: float = 0,
    alpha_img: float = 1.0,
    bw: bool = False,
    cmap: str = 'viridis',
    figsize: Tuple[int, int] = (8, 8),
    save_path: Optional[str] = None,
) -> None:
    """
    Plot cell type annotations using scanpy's spatial plotting.

    Uses sc.pl.spatial for spatial plotting.
    NOTE: sc.pl.spatial is deprecated in scanpy 1.11+; migrate to sq.pl.spatial_scatter
    when removing spot_size/scale_factor/alpha_img/bw parameters.

    Parameters
    ----------
    adata_sp : AnnData
        Spatial data with tangram_ct_pred in obsm
    annotation_list : List[str]
        Cell types to plot
    x, y : str, default='x', 'y'
        Coordinate columns (for non-Visium data)
    spot_size : float, optional
        Spot size for non-Visium data
    scale_factor : float, optional
        Scale factor for non-Visium data
    perc : float, default=0
        Percentile for clipping
    alpha_img : float, default=1.0
        Image transparency
    bw : bool, default=False
        Plot in black and white
    cmap : str, default='viridis'
        Colormap
    figsize : tuple, default=(8, 8)
        Figure size
    save_path : str, optional
        Path to save figure

    Examples
    --------
    >>> plot_cell_annotation_sc(
    ...     adata_sp, ['Neuron', 'Astrocyte', 'Microglia'],
    ...     spot_size=50
    ... )
    """
    if 'tangram_ct_pred' not in adata_sp.obsm:
        raise KeyError("'tangram_ct_pred' not found. Run project_cell_annotations() first.")

    # Check all annotations exist
    df_pred = adata_sp.obsm['tangram_ct_pred']
    missing = [a for a in annotation_list if a not in df_pred.columns]
    if missing:
        raise ValueError(f"Annotations not found: {missing}")

    # Use temporary column names to avoid clobbering user's original columns
    tmp_prefix = '_tangram_plot_'
    tmp_cols = {ann: f"{tmp_prefix}{ann}" for ann in annotation_list}

    df_plot = df_pred[annotation_list].copy().rename(columns=tmp_cols)

    # Clip and normalize
    if perc > 0:
        df_plot = df_plot.clip(
            df_plot.quantile(perc),
            df_plot.quantile(1 - perc),
            axis=1
        )

    # Normalize with divide-by-zero protection
    rng = df_plot.max() - df_plot.min()
    rng = rng.replace(0, 1)  # avoid division by zero
    df_plot = ((df_plot - df_plot.min()) / rng).fillna(0)

    # Get coordinates (do NOT write into adata_sp.obsm)
    if 'spatial' in adata_sp.obsm:
        coords = adata_sp.obsm['spatial'].copy()
    elif x in adata_sp.obs.columns and y in adata_sp.obs.columns:
        coords = np.column_stack([adata_sp.obs[x].values, adata_sp.obs[y].values])
    else:
        raise ValueError(
            f"No spatial coordinates found. Need either adata_sp.obsm['spatial'] "
            f"or obs columns '{x}' and '{y}'."
        )

    # Plot
    n_annotations = len(annotation_list)
    ncols = min(3, n_annotations)
    nrows = (n_annotations + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    if n_annotations == 1:
        axes = [axes]
    else:
        axes = axes.flatten()

    # Try to get background image
    bg_img = None
    if 'spatial' in adata_sp.uns and alpha_img > 0:
        try:
            library_id = list(adata_sp.uns['spatial'].keys())[0]
            bg_img = adata_sp.uns['spatial'][library_id]['images']['hires']
        except (KeyError, IndexError):
            bg_img = None

    for idx, ann in enumerate(annotation_list):
        ax = axes[idx]
        tmp_col = tmp_cols[ann]
        if bg_img is not None:
            ax.imshow(bg_img, alpha=alpha_img, origin='upper')
        scatter = ax.scatter(
            coords[:, 0], coords[:, 1],
            c=df_plot[tmp_col].values,
            cmap=cmap,
            s=spot_size,
            edgecolors='none'
        )
        ax.set_title(ann)
        ax.set_aspect('equal')
        ax.axis('off')
        plt.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04)

    # Hide unused subplots
    for idx in range(n_annotations, len(axes)):
        axes[idx].set_visible(False)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')


def plot_genes(
    genes: List[str],
    adata_measured: AnnData,
    adata_predicted: AnnData,
    x: str = 'x',
    y: str = 'y',
    s: float = 5,
    log: bool = False,
    cmap: str = 'inferno',
    robust: bool = False,
    perc: float = 0,
    invert_y: bool = True,
    figsize: Optional[Tuple[int, int]] = None,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Compare measured vs predicted gene expression spatially.

    Creates side-by-side plots for each gene.

    Parameters
    ----------
    genes : List[str]
        Genes to plot
    adata_measured : AnnData
        Measured spatial data
    adata_predicted : AnnData
        Predicted spatial data (from project_genes)
    x, y : str, default='x', 'y'
        Coordinate columns
    s : float, default=5
        Marker size
    log : bool, default=False
        Log-transform expression
    cmap : str, default='inferno'
        Colormap
    robust : bool, default=False
        Use percentiles for colormap
    perc : float, default=0
        Percentile for robust mode
    invert_y : bool, default=True
        Invert y-axis
    figsize : tuple, optional
        Figure size (auto-calculated if None)
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure

    Examples
    --------
    >>> fig = plot_genes(
    ...     ['Gene1', 'Gene2'],
    ...     adata_sp, adata_ge,
    ...     s=10, cmap='viridis'
    ... )
    """
    tg = check_tangram_installed()

    if figsize is None:
        figsize = (6, len(genes) * 3)

    fig = tg.plot_genes(
        genes=genes,
        adata_measured=adata_measured,
        adata_predicted=adata_predicted,
        x=x, y=y,
        s=s,
        log=log,
        cmap=cmap,
        robust=robust,
        perc=perc,
        invert_y=invert_y,
    )

    if save_path and fig is not None:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_genes_sc(
    genes: List[str],
    adata_measured: AnnData,
    adata_predicted: AnnData,
    x: str = 'x',
    y: str = 'y',
    spot_size: Optional[float] = None,
    scale_factor: Optional[float] = None,
    cmap: str = 'inferno',
    perc: float = 0,
    alpha_img: float = 1.0,
    bw: bool = False,
    figsize: Optional[Tuple[int, int]] = None,
    save_path: Optional[str] = None,
) -> Optional[plt.Figure]:
    """
    Compare measured vs predicted genes using scanpy spatial plotting.

    Parameters
    ----------
    genes : List[str]
        Genes to plot
    adata_measured : AnnData
        Measured spatial data
    adata_predicted : AnnData
        Predicted spatial data
    x, y : str, default='x', 'y'
        Coordinate columns for non-Visium data
    spot_size : float, optional
        Spot size
    scale_factor : float, optional
        Scale factor
    cmap : str, default='inferno'
        Colormap
    perc : float, default=0
        Percentile for clipping
    alpha_img : float, default=1.0
        Image transparency
    bw : bool, default=False
        Black and white
    figsize : tuple, optional
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure or None
        Matplotlib figure if return_figure=True

    Examples
    --------
    >>> plot_genes_sc(['Gene1', 'Gene2'], adata_sp, adata_ge, spot_size=50)
    """
    tg = check_tangram_installed()

    fig = tg.plot_utils.plot_genes_sc(
        genes=genes,
        adata_measured=adata_measured,
        adata_predicted=adata_predicted,
        x=x, y=y,
        spot_size=spot_size,
        scale_factor=scale_factor,
        cmap=cmap,
        perc=perc,
        alpha_img=alpha_img,
        bw=bw,
        return_figure=(figsize is not None),
    )

    if save_path and fig is not None:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_gene_sparsity(
    adata_1: AnnData,
    adata_2: AnnData,
    xlabel: str = 'adata_1',
    ylabel: str = 'adata_2',
    genes: Optional[List[str]] = None,
    s: float = 1,
    figsize: Tuple[int, int] = (6, 6),
    save_path: Optional[str] = None,
) -> None:
    """
    Compare gene sparsity between two AnnDatas.

    Parameters
    ----------
    adata_1, adata_2 : AnnData
        Data to compare
    xlabel, ylabel : str
        Labels for axes
    genes : List[str], optional
        Genes to compare
    s : float, default=1
        Marker size
    figsize : tuple, default=(6, 6)
        Figure size
    save_path : str, optional
        Path to save figure

    Examples
    --------
    >>> plot_gene_sparsity(adata_sc, adata_sp, 'scRNA-seq', 'Spatial')
    """
    tg = check_tangram_installed()

    # Native tg.plot_gene_sparsity creates its own figure; don't create a wrapper fig
    tg.plot_gene_sparsity(
        adata_1=adata_1,
        adata_2=adata_2,
        xlabel=xlabel,
        ylabel=ylabel,
        genes=genes,
        s=s,
    )

    if save_path:
        plt.gcf().savefig(save_path, dpi=300, bbox_inches='tight')


def plot_annotation_entropy(
    adata_map: AnnData,
    annotation: str = 'cell_type',
    figsize: Tuple[int, int] = (10, 3),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot entropy of cell mapping by annotation.

    Shows how concentrated or dispersed cell mappings are.

    Parameters
    ----------
    adata_map : AnnData
        Mapping result
    annotation : str, default='cell_type'
        Annotation column
    figsize : tuple, default=(10, 3)
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure

    Examples
    --------
    >>> fig = plot_annotation_entropy(adata_map, 'cell_type')
    """
    tg = check_tangram_installed()

    fig = tg.plot_annotation_entropy(adata_map, annotation=annotation)

    if save_path and fig is not None:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_auc(
    df_all_genes: pd.DataFrame,
    test_genes: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (6, 5),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot AUC curve for model evaluation.

    Parameters
    ----------
    df_all_genes : pd.DataFrame
        Output from compare_spatial_geneexp
    test_genes : List[str], optional
        Test genes to highlight
    figsize : tuple, default=(6, 5)
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure

    Examples
    --------
    >>> fig = plot_auc(df_compare)
    """
    tg = check_tangram_installed()

    fig = tg.plot_utils.plot_auc(df_all_genes, test_genes)

    if save_path and fig is not None:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_cell_type_map(
    adata_sp: AnnData,
    cell_type: str,
    annotation_key: str = 'tangram_ct_pred',
    cmap: str = 'viridis',
    size: float = 1.5,
    alpha: float = 0.8,
    show_background: bool = True,
    figsize: Tuple[int, int] = (8, 8),
    title: Optional[str] = None,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot a single cell type's spatial distribution.

    Parameters
    ----------
    adata_sp : AnnData
        Spatial data with projections
    cell_type : str
        Cell type to plot
    annotation_key : str, default='tangram_ct_pred'
        Key with projections
    cmap : str, default='viridis'
        Colormap
    size : float, default=1.5
        Spot size
    alpha : float, default=0.8
        Transparency
    show_background : bool, default=True
        Show tissue background
    figsize : tuple, default=(8, 8)
        Figure size
    title : str, optional
        Plot title
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure

    Examples
    --------
    >>> fig = plot_cell_type_map(adata_sp, 'Neuron', cmap='Reds')
    """
    if annotation_key not in adata_sp.obsm:
        raise KeyError(f"'{annotation_key}' not found. Run project_cell_annotations() first.")

    df_pred = adata_sp.obsm[annotation_key]
    if cell_type not in df_pred.columns:
        raise ValueError(f"'{cell_type}' not found in {annotation_key}")

    fig, ax = plt.subplots(figsize=figsize)

    # Show background
    if show_background and 'spatial' in adata_sp.uns:
        # NOTE: sc.pl.spatial was removed in scanpy 1.12+. Using matplotlib directly.
        try:
            library_id = list(adata_sp.uns['spatial'].keys())[0]
            bg_img = adata_sp.uns['spatial'][library_id]['images']['hires']
            ax.imshow(bg_img, alpha=0.5, origin='upper')
        except (KeyError, IndexError):
            pass  # No image available

    # Get coordinates
    if 'spatial' in adata_sp.obsm:
        coords = adata_sp.obsm['spatial']
    elif 'array_row' in adata_sp.obs and 'array_col' in adata_sp.obs:
        coords = adata_sp.obs[['array_col', 'array_row']].values
    else:
        raise ValueError("No spatial coordinates found")

    values = df_pred[cell_type].values

    # Plot cell type
    scatter = ax.scatter(
        coords[:, 0],
        coords[:, 1],
        c=values,
        cmap=cmap,
        s=size * 100,
        alpha=alpha,
        edgecolors='none',
    )

    ax.set_title(title or f'{cell_type}')
    ax.set_aspect('equal')
    ax.axis('off')
    plt.colorbar(scatter, ax=ax, label='Proportion', fraction=0.046)

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_annotation_comparison(
    adata_sp: AnnData,
    annotation_key: str = 'tangram_ct_pred',
    cell_types: Optional[List[str]] = None,
    n_cols: int = 4,
    cmap: str = 'viridis',
    size: float = 20,
    figsize: Optional[Tuple[int, int]] = None,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot multiple cell types side by side.

    Parameters
    ----------
    adata_sp : AnnData
        Spatial data with projections
    annotation_key : str, default='tangram_ct_pred'
        Key with projections
    cell_types : List[str], optional
        Cell types to plot (all if None)
    n_cols : int, default=4
        Number of columns
    cmap : str, default='viridis'
        Colormap
    size : float, default=20
        Marker size
    figsize : tuple, optional
        Figure size (auto-calculated if None)
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure

    Examples
    --------
    >>> fig = plot_annotation_comparison(adata_sp, n_cols=3)
    """
    if annotation_key not in adata_sp.obsm:
        raise KeyError(f"'{annotation_key}' not found")

    df_pred = adata_sp.obsm[annotation_key]

    if cell_types is None:
        cell_types = df_pred.columns.tolist()

    n_types = len(cell_types)
    n_rows = (n_types + n_cols - 1) // n_cols

    if figsize is None:
        figsize = (n_cols * 3, n_rows * 3)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
    axes = axes.flatten() if n_types > 1 else [axes]

    # Get coordinates
    if 'spatial' in adata_sp.obsm:
        coords = adata_sp.obsm['spatial']
    elif 'array_row' in adata_sp.obs and 'array_col' in adata_sp.obs:
        coords = adata_sp.obs[['array_col', 'array_row']].values
    else:
        raise ValueError("No spatial coordinates found")

    for idx, cell_type in enumerate(cell_types):
        ax = axes[idx]

        if cell_type not in df_pred.columns:
            ax.text(0.5, 0.5, f'{cell_type}\nnot found', ha='center', va='center')
            ax.axis('off')
            continue

        values = df_pred[cell_type].values

        scatter = ax.scatter(
            coords[:, 0],
            coords[:, 1],
            c=values,
            cmap=cmap,
            s=size,
            alpha=0.8,
            edgecolors='none',
        )

        ax.set_title(cell_type, fontsize=10)
        ax.set_aspect('equal')
        ax.axis('off')

    # Hide unused subplots
    for idx in range(n_types, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_deconvolution_results(
    adata_sp: AnnData,
    annotation_key: str = 'tangram_ct_count',
    n_cols: int = 4,
    cmap: str = 'Reds',
    figsize: Optional[Tuple[int, int]] = None,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot cell count deconvolution results.

    Parameters
    ----------
    adata_sp : AnnData
        Spatial data with tangram_ct_count
    annotation_key : str, default='tangram_ct_count'
        Key with cell counts
    n_cols : int, default=4
        Number of columns
    cmap : str, default='Reds'
        Colormap
    figsize : tuple, optional
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure

    Examples
    --------
    >>> fig = plot_deconvolution_results(adata_sp)
    """
    if annotation_key not in adata_sp.obsm:
        raise KeyError(f"'{annotation_key}' not found. Run count_cell_annotations() first.")

    df_count = adata_sp.obsm[annotation_key]

    # Get cell type columns (exclude x, y, cell_n, centroids)
    exclude_cols = ['x', 'y', 'cell_n', 'centroids']
    cell_types = [c for c in df_count.columns if c not in exclude_cols]

    n_types = len(cell_types)
    n_rows = (n_types + n_cols - 1) // n_cols

    if figsize is None:
        figsize = (n_cols * 3, n_rows * 3)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
    axes = axes.flatten() if n_types > 1 else [axes]

    # Get coordinates
    if 'x' in df_count.columns:
        coords = df_count[['x', 'y']].values
    elif 'spatial' in adata_sp.obsm:
        coords = adata_sp.obsm['spatial']
    else:
        logger.warning("No spatial coordinates found (x/y in df_count or adata_sp.obsm['spatial']). Using zeros.")
        coords = np.zeros((len(df_count), 2))

    for idx, cell_type in enumerate(cell_types):
        ax = axes[idx]
        values = df_count[cell_type].values

        scatter = ax.scatter(
            coords[:, 0],
            coords[:, 1],
            c=values,
            cmap=cmap,
            s=20,
            alpha=0.8,
            edgecolors='none',
        )

        ax.set_title(f'{cell_type} (count)')
        ax.set_aspect('equal')
        ax.axis('off')
        plt.colorbar(scatter, ax=ax, fraction=0.046)

    # Hide unused subplots
    for idx in range(n_types, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig
