"""
scVelo Visualization Module
============================

Visualization functions for RNA velocity analysis results.
Provides wrappers for scVelo's plotting functions with consistent styling.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Optional, Union, List, Dict, Tuple, Any
import warnings


def plot_velocity_embedding_stream(
    adata,
    basis: str = 'umap',
    color: Optional[str] = None,
    layer: Optional[str] = None,
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (8, 6),
    dpi: int = 100,
    save: Optional[str] = None,
    show: bool = True,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot velocity stream on embedding.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with velocity computed
    basis : str
        Embedding basis ('umap', 'tsne', 'pca', etc.)
    color : str, optional
        Key for coloring cells
    layer : str, optional
        Layer to use for velocity
    title : str, optional
        Plot title
    figsize : tuple
        Figure size (width, height)
    dpi : int
        Figure resolution
    save : str, optional
        Path to save figure
    show : bool
        Whether to show the plot
    **kwargs
        Additional arguments passed to scvelo.pl.velocity_embedding_stream

    Returns
    -------
    axes : matplotlib.axes.Axes or None
        Axes object if show=False
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required for velocity visualization")

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    scv.pl.velocity_embedding_stream(
        adata,
        basis=basis,
        color=color,
        layer=layer,
        ax=ax,
        show=False,
        **kwargs
    )

    if title:
        ax.set_title(title, fontsize=12)

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=dpi, bbox_inches='tight')
        print(f"Figure saved to {save}")

    if show:
        plt.show()
        return None
    else:
        return ax


def plot_velocity_embedding_grid(
    adata,
    basis: str = 'umap',
    color: Optional[str] = None,
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (8, 6),
    dpi: int = 100,
    save: Optional[str] = None,
    show: bool = True,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot velocity grid on embedding (arrows).

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with velocity computed
    basis : str
        Embedding basis
    color : str, optional
        Key for coloring cells
    title : str, optional
        Plot title
    figsize : tuple
        Figure size
    dpi : int
        Figure resolution
    save : str, optional
        Path to save figure
    show : bool
        Whether to show the plot
    **kwargs
        Additional arguments for scvelo.pl.velocity_embedding

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required for velocity visualization")

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    scv.pl.velocity_embedding(
        adata,
        basis=basis,
        color=color,
        ax=ax,
        show=False,
        **kwargs
    )

    if title:
        ax.set_title(title, fontsize=12)

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=dpi, bbox_inches='tight')
        print(f"Figure saved to {save}")

    if show:
        plt.show()
        return None
    else:
        return ax


def plot_phase_portrait(
    adata,
    gene: str,
    color: Optional[str] = None,
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (7, 5),
    dpi: int = 100,
    save: Optional[str] = None,
    show: bool = True,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot phase portrait for a specific gene showing spliced vs unspliced counts.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    gene : str
        Gene name to plot
    color : str, optional
        Key for coloring cells
    title : str, optional
        Plot title (defaults to gene name)
    figsize : tuple
        Figure size
    dpi : int
        Figure resolution
    save : str, optional
        Path to save figure
    show : bool
        Whether to show the plot
    **kwargs
        Additional arguments for scvelo.pl.scatter

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required for phase portrait")

    if gene not in adata.var_names:
        raise ValueError(f"Gene '{gene}' not found in adata.var_names")

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    scv.pl.scatter(
        adata,
        basis=gene,
        color=color or 'velocity',
        ax=ax,
        show=False,
        **kwargs
    )

    if title:
        ax.set_title(title, fontsize=12)

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=dpi, bbox_inches='tight')
        print(f"Figure saved to {save}")

    if show:
        plt.show()
        return None
    else:
        return ax


def plot_velocity_genes(
    adata,
    n_genes: int = 10,
    min_r2: Optional[float] = None,
    mode: str = 'velocity',
    figsize: Tuple[int, int] = (10, 8),
    dpi: int = 100,
    save: Optional[str] = None,
    show: bool = True,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot phase portraits for top velocity genes.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with velocity genes computed
    n_genes : int
        Number of genes to plot
    min_r2 : float, optional
        Minimum R-squared threshold for filtering genes
    mode : str
        Mode for selecting genes ('velocity', 'likelihood', 'variance')
    figsize : tuple
        Figure size
    dpi : int
        Figure resolution
    save : str, optional
        Path to save figure
    show : bool
        Whether to show the plot
    **kwargs
        Additional arguments for scvelo.pl.velocity

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required for velocity genes plot")

    if 'velocity_genes' not in adata.var.columns and 'rank_velocity_genes' not in adata.uns:
        raise ValueError("Velocity genes not computed. Run rank_velocity_genes() first.")

    # Filter genes by R2 if specified
    if min_r2 is not None and 'fit_r2' in adata.var.columns:
        velocity_genes = adata.var['velocity_genes'] & (adata.var['fit_r2'] > min_r2)
        gene_list = adata.var_names[velocity_genes].tolist()[:n_genes]
    else:
        gene_list = adata.var_names[adata.var['velocity_genes']].tolist()[:n_genes]

    if len(gene_list) == 0:
        warnings.warn("No velocity genes found matching criteria")
        return None

    ncols = min(3, len(gene_list))
    nrows = (len(gene_list) + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, dpi=dpi)
    if nrows == 1 and ncols == 1:
        axes = np.array([axes])
    axes = axes.flatten() if hasattr(axes, 'flatten') else [axes]

    for i, gene in enumerate(gene_list):
        scv.pl.scatter(
            adata,
            basis=gene,
            color='velocity',
            ax=axes[i],
            show=False,
            **kwargs
        )
        axes[i].set_title(f'{gene}', fontsize=10)

    # Hide unused subplots
    for i in range(len(gene_list), len(axes)):
        axes[i].set_visible(False)

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=dpi, bbox_inches='tight')
        print(f"Figure saved to {save}")

    if show:
        plt.show()
        return None
    else:
        return axes[0] if len(axes) == 1 else axes


def plot_latent_time(
    adata,
    basis: str = 'umap',
    color: Optional[str] = None,
    title: str = 'Latent Time',
    figsize: Tuple[int, int] = (8, 6),
    dpi: int = 100,
    save: Optional[str] = None,
    show: bool = True,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot latent time on embedding.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with latent time computed
    basis : str
        Embedding basis
    color : str, optional
        Alternative key to color by (defaults to 'latent_time')
    title : str
        Plot title
    figsize : tuple
        Figure size
    dpi : int
        Figure resolution
    save : str, optional
        Path to save figure
    show : bool
        Whether to show the plot
    **kwargs
        Additional arguments for scvelo.pl.scatter

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required for latent time visualization")

    if 'latent_time' not in adata.obs.columns:
        raise ValueError("Latent time not computed. Run compute_latent_time_scvelo() first.")

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    scv.pl.scatter(
        adata,
        basis=basis,
        color=color or 'latent_time',
        color_map='viridis',
        ax=ax,
        show=False,
        **kwargs
    )

    ax.set_title(title, fontsize=12)
    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=dpi, bbox_inches='tight')
        print(f"Figure saved to {save}")

    if show:
        plt.show()
        return None
    else:
        return ax


def plot_paga_velocity(
    adata,
    color: Optional[str] = None,
    title: str = 'PAGA Velocity Graph',
    figsize: Tuple[int, int] = (8, 6),
    dpi: int = 100,
    save: Optional[str] = None,
    show: bool = True,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot PAGA graph with velocity transitions.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with PAGA computed
    color : str, optional
        Key for coloring nodes
    title : str
        Plot title
    figsize : tuple
        Figure size
    dpi : int
        Figure resolution
    save : str, optional
        Path to save figure
    show : bool
        Whether to show the plot
    **kwargs
        Additional arguments for scvelo.pl.paga

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required for PAGA visualization")

    if 'paga' not in adata.uns:
        raise ValueError("PAGA not computed. Run compute_paga_velocity() first.")

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    scv.pl.paga(
        adata,
        color=color,
        ax=ax,
        show=False,
        **kwargs
    )

    ax.set_title(title, fontsize=12)
    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=dpi, bbox_inches='tight')
        print(f"Figure saved to {save}")

    if show:
        plt.show()
        return None
    else:
        return ax


def plot_velocity_confidence(
    adata,
    basis: str = 'umap',
    title: str = 'Velocity Confidence',
    figsize: Tuple[int, int] = (8, 6),
    dpi: int = 100,
    save: Optional[str] = None,
    show: bool = True,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot velocity confidence on embedding.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with velocity_confidence in obs
    basis : str
        Embedding basis
    title : str
        Plot title
    figsize : tuple
        Figure size
    dpi : int
        Figure resolution
    save : str, optional
        Path to save figure
    show : bool
        Whether to show the plot
    **kwargs
        Additional arguments for scvelo.pl.scatter

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required for confidence visualization")

    if 'velocity_confidence' not in adata.obs.columns:
        raise ValueError("Velocity confidence not computed")

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    scv.pl.scatter(
        adata,
        basis=basis,
        color='velocity_confidence',
        color_map='RdYlGn',
        ax=ax,
        show=False,
        **kwargs
    )

    ax.set_title(title, fontsize=12)
    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=dpi, bbox_inches='tight')
        print(f"Figure saved to {save}")

    if show:
        plt.show()
        return None
    else:
        return ax


def plot_terminal_states(
    adata,
    basis: str = 'umap',
    color: Optional[str] = None,
    title: str = 'Terminal States',
    figsize: Tuple[int, int] = (8, 6),
    dpi: int = 100,
    save: Optional[str] = None,
    show: bool = True,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot identified terminal states (root and end points).

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with terminal states computed
    basis : str
        Embedding basis
    color : str, optional
        Key for coloring (defaults to terminal states)
    title : str
        Plot title
    figsize : tuple
        Figure size
    dpi : int
        Figure resolution
    save : str, optional
        Path to save figure
    show : bool
        Whether to show the plot
    **kwargs
        Additional arguments for scvelo.pl.scatter

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required for terminal states visualization")

    if 'root_cells' not in adata.obs.columns and 'end_points' not in adata.obs.columns:
        raise ValueError("Terminal states not computed. Run compute_terminal_states() first.")

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Plot base embedding
    color_key = color or adata.uns.get('velocyto_params', {}).get('groups', 'clusters')
    scv.pl.scatter(
        adata,
        basis=basis,
        color=color_key,
        ax=ax,
        show=False,
        **kwargs
    )

    # Overlay terminal states
    if 'root_cells' in adata.obs.columns:
        root_mask = adata.obs['root_cells'].astype(bool)
        if root_mask.any():
            root_coords = adata.obsm[f'X_{basis}'][root_mask]
            ax.scatter(root_coords[:, 0], root_coords[:, 1],
                      c='green', s=100, marker='*', edgecolors='black',
                      label='Root cells', zorder=5)

    if 'end_points' in adata.obs.columns:
        end_mask = adata.obs['end_points'].astype(bool)
        if end_mask.any():
            end_coords = adata.obsm[f'X_{basis}'][end_mask]
            ax.scatter(end_coords[:, 0], end_coords[:, 1],
                      c='red', s=100, marker='X', edgecolors='black',
                      label='End points', zorder=5)

    ax.set_title(title, fontsize=12)
    ax.legend(loc='best')
    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=dpi, bbox_inches='tight')
        print(f"Figure saved to {save}")

    if show:
        plt.show()
        return None
    else:
        return ax


def plot_velocity_summary(
    adata,
    basis: str = 'umap',
    figsize: Tuple[int, int] = (16, 12),
    dpi: int = 100,
    save: Optional[str] = None,
    show: bool = True
) -> Optional[List[plt.Axes]]:
    """
    Create a comprehensive velocity summary plot with multiple panels.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with velocity computed
    basis : str
        Embedding basis
    figsize : tuple
        Figure size
    dpi : int
        Figure resolution
    save : str, optional
        Path to save figure
    show : bool
        Whether to show the plot

    Returns
    -------
    axes : list of matplotlib.axes.Axes or None
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required for summary visualization")

    # Determine layout based on what's computed
    has_latent_time = 'latent_time' in adata.obs.columns
    has_confidence = 'velocity_confidence' in adata.obs.columns

    n_panels = 3 + has_latent_time + has_confidence
    ncols = 3
    nrows = (n_panels + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, dpi=dpi)
    axes = axes.flatten() if hasattr(axes, 'flatten') else [axes]

    panel = 0

    # Panel 1: Velocity stream
    scv.pl.velocity_embedding_stream(
        adata, basis=basis, ax=axes[panel], show=False,
        title='RNA Velocity (Stream)'
    )
    panel += 1

    # Panel 2: Velocity grid
    scv.pl.velocity_embedding(
        adata, basis=basis, ax=axes[panel], show=False,
        title='RNA Velocity (Arrows)'
    )
    panel += 1

    # Panel 3: Clusters/cell types
    color_key = adata.uns.get('velocyto_params', {}).get('groups', 'clusters')
    if color_key in adata.obs.columns:
        scv.pl.scatter(
            adata, basis=basis, color=color_key, ax=axes[panel], show=False,
            title='Cell Types/Clusters'
        )
    panel += 1

    # Panel 4: Latent time (if available)
    if has_latent_time and panel < len(axes):
        scv.pl.scatter(
            adata, basis=basis, color='latent_time', ax=axes[panel], show=False,
            color_map='viridis', title='Latent Time'
        )
        panel += 1

    # Panel 5: Velocity confidence (if available)
    if has_confidence and panel < len(axes):
        scv.pl.scatter(
            adata, basis=basis, color='velocity_confidence', ax=axes[panel], show=False,
            color_map='RdYlGn', title='Velocity Confidence'
        )
        panel += 1

    # Hide unused panels
    for i in range(panel, len(axes)):
        axes[i].set_visible(False)

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=dpi, bbox_inches='tight')
        print(f"Figure saved to {save}")

    if show:
        plt.show()
        return None
    else:
        return axes


def plot_proportions(
    adata,
    groupby: Optional[str] = None,
    title: str = 'Spliced/Unspliced Proportions',
    figsize: Tuple[int, int] = (8, 6),
    dpi: int = 100,
    save: Optional[str] = None,
    show: bool = True,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot proportions of spliced/unspliced/ambiguous counts.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with spliced/unspliced layers
    groupby : str, optional
        Key to group by (e.g., cell types)
    title : str
        Plot title
    figsize : tuple
        Figure size
    dpi : int
        Figure resolution
    save : str, optional
        Path to save figure
    show : bool
        Whether to show the plot
    **kwargs
        Additional arguments for scvelo.pl.proportions

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required for proportions plot")

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    scv.pl.proportions(
        adata,
        groupby=groupby,
        ax=ax,
        show=False,
        **kwargs
    )

    ax.set_title(title, fontsize=12)
    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=dpi, bbox_inches='tight')
        print(f"Figure saved to {save}")

    if show:
        plt.show()
        return None
    else:
        return ax
