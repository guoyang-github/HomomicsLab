"""
Visualization functions for STAGATE spatial domain analysis.

Author: Yang Guo
Date: 2026-04-03
Version: 1.1.0
"""

from typing import Optional, List, Dict, Tuple, Union
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.colors import ListedColormap
import seaborn as sns
import scanpy as sc
from anndata import AnnData


# ============================================================================
# Spatial Domain Visualization
# ============================================================================

def plot_domains(
    adata: AnnData,
    domain_key: str = 'mclust',
    spatial_key: str = 'spatial',
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 8),
    palette: str = 'tab20',
    spot_size: float = 1.5,
    save_path: Optional[str] = None,
    ax: Optional[mpl.axes.Axes] = None,
    show_legend: bool = True,
) -> mpl.axes.Axes:
    """
    Plot spatial domains on tissue coordinates.

    Parameters
    ----------
    adata : AnnData
        Data with domain labels
    domain_key : str, default='mclust'
        Key for domain labels in adata.obs
    spatial_key : str, default='spatial'
        Key for spatial coordinates
    title : str, optional
        Plot title
    figsize : tuple, default=(10, 8)
        Figure size
    palette : str, default='tab20'
        Color palette
    spot_size : float, default=1.5
        Spot size
    save_path : str, optional
        Path to save figure
    ax : matplotlib.axes.Axes, optional
        Existing axes
    show_legend : bool, default=True
        Show legend

    Returns
    -------
    matplotlib.axes.Axes
        Axes object

    Examples
    --------
    >>> plot_domains(adata, domain_key='mclust', spot_size=2.0)
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    if domain_key not in adata.obs:
        raise ValueError(f"'{domain_key}' not found in adata.obs")

    if spatial_key not in adata.obsm:
        raise ValueError(f"'{spatial_key}' not found in adata.obsm")

    # Get coordinates and labels
    coords = adata.obsm[spatial_key][:, :2]
    labels = adata.obs[domain_key]

    # Create color map
    unique_labels = sorted(labels.unique())
    n_colors = len(unique_labels)

    if isinstance(palette, str):
        cmap = plt.get_cmap(palette)
        colors = cmap(np.linspace(0, 1, n_colors))
    else:
        colors = palette

    color_dict = {label: colors[i] for i, label in enumerate(unique_labels)}

    # Plot each domain
    for label in unique_labels:
        mask = labels == label
        ax.scatter(
            coords[mask, 0],
            coords[mask, 1],
            c=[color_dict[label]],
            s=spot_size * 50,
            label=str(label),
            alpha=0.9,
            edgecolors='none',
        )

    ax.set_aspect('equal')
    ax.set_xlabel('Spatial X')
    ax.set_ylabel('Spatial Y')
    ax.set_title(title or f'STAGATE Domains ({domain_key})')

    if show_legend:
        ax.legend(loc='best', title='Domain', bbox_to_anchor=(1.05, 1))

    sns.despine(ax=ax)

    if save_path:
        ax.figure.savefig(save_path, dpi=300, bbox_inches='tight')

    return ax


def plot_domains_comparison(
    adata: AnnData,
    domain_keys: List[str],
    spatial_key: str = 'spatial',
    figsize_per_plot: Tuple[int, int] = (8, 6),
    n_cols: int = 2,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Compare multiple domain clusterings side by side.

    Parameters
    ----------
    adata : AnnData
        Data with domain labels
    domain_keys : List[str]
        List of keys for different clusterings
    spatial_key : str, default='spatial'
        Key for spatial coordinates
    figsize_per_plot : tuple, default=(8, 6)
        Size of each subplot
    n_cols : int, default=2
        Number of columns
    save_path : str, optional
        Path to save

    Returns
    -------
    matplotlib.figure.Figure
        Figure object

    Examples
    --------
    >>> plot_domains_comparison(adata, ['mclust', 'leiden', 'louvain'])
    """
    n_plots = len(domain_keys)
    n_rows = (n_plots + n_cols - 1) // n_cols

    figsize = (figsize_per_plot[0] * n_cols, figsize_per_plot[1] * n_rows)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)

    if n_plots == 1:
        axes = np.array([axes])
    else:
        axes = axes.flatten()

    for idx, key in enumerate(domain_keys):
        try:
            plot_domains(
                adata,
                domain_key=key,
                spatial_key=spatial_key,
                ax=axes[idx],
                title=key,
            )
        except Exception as e:
            axes[idx].text(0.5, 0.5, f'Error: {e}', ha='center', transform=axes[idx].transAxes)
            axes[idx].axis('off')

    # Hide extra subplots
    for idx in range(n_plots, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


# ============================================================================
# Embedding Visualization
# ============================================================================

def plot_embedding_umap(
    adata: AnnData,
    embedding_key: str = 'STAGATE',
    color_key: Optional[str] = None,
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 8),
    palette: str = 'tab20',
    save_path: Optional[str] = None,
    ax: Optional[mpl.axes.Axes] = None,
) -> mpl.axes.Axes:
    """
    Plot UMAP of STAGATE embeddings.

    Parameters
    ----------
    adata : AnnData
        Data with embeddings
    embedding_key : str, default='STAGATE'
        Key for embeddings
    color_key : str, optional
        Key for coloring points (e.g., 'mclust')
    title : str, optional
        Plot title
    figsize : tuple, default=(10, 8)
        Figure size
    palette : str, default='tab20'
        Color palette
    save_path : str, optional
        Path to save
    ax : matplotlib.axes.Axes, optional
        Existing axes

    Returns
    -------
    matplotlib.axes.Axes
        Axes object

    Examples
    --------
    >>> plot_embedding_umap(adata, color_key='mclust')
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    if embedding_key not in adata.obsm:
        raise ValueError(f"'{embedding_key}' not found in adata.obsm")

    # Compute UMAP if not exists (work on copy to avoid modifying input)
    adata_plot = adata.copy()
    umap_key = f'X_umap_{embedding_key}'
    if umap_key not in adata_plot.obsm:
        sc.pp.neighbors(adata_plot, n_neighbors=15, use_rep=embedding_key)
        sc.tl.umap(adata_plot)
        adata_plot.obsm[umap_key] = adata_plot.obsm['X_umap']

    coords = adata_plot.obsm[umap_key]

    if color_key and color_key in adata.obs:
        # Plot with colors
        labels = adata.obs[color_key]
        unique_labels = sorted(labels.unique())

        cmap = plt.get_cmap(palette)
        colors = cmap(np.linspace(0, 1, len(unique_labels)))
        color_dict = {label: colors[i] for i, label in enumerate(unique_labels)}

        for label in unique_labels:
            mask = labels == label
            ax.scatter(
                coords[mask, 0],
                coords[mask, 1],
                c=[color_dict[label]],
                s=20,
                label=str(label),
                alpha=0.7,
            )
        ax.legend(loc='best', title=color_key, bbox_to_anchor=(1.05, 1))
    else:
        ax.scatter(coords[:, 0], coords[:, 1], s=20, alpha=0.7, c='gray')

    ax.set_xlabel('UMAP 1')
    ax.set_ylabel('UMAP 2')
    ax.set_title(title or f'STAGATE Embedding (UMAP)')

    sns.despine(ax=ax)

    if save_path:
        ax.figure.savefig(save_path, dpi=300, bbox_inches='tight')

    return ax


def plot_embedding_pca(
    adata: AnnData,
    embedding_key: str = 'STAGATE',
    color_key: Optional[str] = None,
    components: Tuple[int, int] = (1, 2),
    figsize: Tuple[int, int] = (8, 8),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot PCA of STAGATE embeddings.

    Parameters
    ----------
    adata : AnnData
        Data with embeddings
    embedding_key : str, default='STAGATE'
        Key for embeddings
    color_key : str, optional
        Key for coloring
    components : tuple, default=(1, 2)
        Which PCs to plot
    figsize : tuple, default=(8, 8)
        Figure size
    save_path : str, optional
        Path to save

    Returns
    -------
    matplotlib.figure.Figure
        Figure object
    """
    if embedding_key not in adata.obsm:
        raise ValueError(f"'{embedding_key}' not found")

    from sklearn.decomposition import PCA

    # Compute PCA
    pca = PCA(n_components=max(components))
    pca_result = pca.fit_transform(adata.obsm[embedding_key])

    fig, ax = plt.subplots(figsize=figsize)

    if color_key and color_key in adata.obs:
        labels = adata.obs[color_key]
        unique_labels = sorted(labels.unique())

        colors = plt.get_cmap('tab20')(np.linspace(0, 1, len(unique_labels)))
        color_dict = {label: colors[i] for i, label in enumerate(unique_labels)}

        for label in unique_labels:
            mask = labels == label
            ax.scatter(
                pca_result[mask, components[0]-1],
                pca_result[mask, components[1]-1],
                c=[color_dict[label]],
                s=20,
                label=str(label),
                alpha=0.7,
            )
        ax.legend(loc='best', title=color_key)
    else:
        ax.scatter(
            pca_result[:, components[0]-1],
            pca_result[:, components[1]-1],
            s=20,
            alpha=0.7,
            c='gray',
        )

    ax.set_xlabel(f'PC{components[0]} ({pca.explained_variance_ratio_[components[0]-1]:.1%})')
    ax.set_ylabel(f'PC{components[1]} ({pca.explained_variance_ratio_[components[1]-1]:.1%})')
    ax.set_title('STAGATE Embedding (PCA)')

    sns.despine(ax=ax)

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


# ============================================================================
# Domain Comparison and Statistics
# ============================================================================

def plot_domain_proportions(
    adata: AnnData,
    domain_key: str = 'mclust',
    group_key: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 6),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot domain proportions (optionally by group).

    Parameters
    ----------
    adata : AnnData
        Data with domain labels
    domain_key : str, default='mclust'
        Key for domains
    group_key : str, optional
        Key for grouping (e.g., 'section')
    figsize : tuple, default=(10, 6)
        Figure size
    save_path : str, optional
        Path to save

    Returns
    -------
    matplotlib.figure.Figure
        Figure object

    Examples
    --------
    >>> plot_domain_proportions(adata, 'mclust')
    >>> plot_domain_proportions(adata, 'mclust', 'section')
    """
    if domain_key not in adata.obs:
        raise ValueError(f"'{domain_key}' not found")

    fig, ax = plt.subplots(figsize=figsize)

    if group_key and group_key in adata.obs:
        # Grouped proportions
        df = pd.crosstab(adata.obs[group_key], adata.obs[domain_key], normalize='index')
        df.plot(kind='bar', stacked=True, ax=ax, colormap='tab20')
        ax.set_xlabel(group_key)
        ax.legend(title=domain_key, bbox_to_anchor=(1.05, 1))
    else:
        # Overall proportions
        proportions = adata.obs[domain_key].value_counts().sort_index()
        proportions.plot(kind='bar', ax=ax, color=plt.get_cmap('tab20')(np.linspace(0, 1, len(proportions))))
        ax.set_xlabel('Domain')
        ax.set_ylabel('Count')

    ax.set_title(f'Domain Proportions')
    plt.xticks(rotation=0)

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_confusion_matrix(
    adata: AnnData,
    key1: str,
    key2: str,
    figsize: Tuple[int, int] = (8, 6),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot confusion matrix between two clusterings.

    Parameters
    ----------
    adata : AnnData
        Data with cluster labels
    key1 : str
        First clustering key
    key2 : str
        Second clustering key
    figsize : tuple, default=(8, 6)
        Figure size
    save_path : str, optional
        Path to save

    Returns
    -------
    matplotlib.figure.Figure
        Figure object
    """
    if key1 not in adata.obs or key2 not in adata.obs:
        raise ValueError(f"Keys not found in adata.obs")

    # Create confusion matrix
    confusion = pd.crosstab(adata.obs[key1], adata.obs[key2])

    # Normalize
    confusion_norm = confusion.div(confusion.sum(axis=1), axis=0)

    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(confusion_norm, annot=True, fmt='.2f', cmap='YlOrRd', ax=ax)
    ax.set_xlabel(key2)
    ax.set_ylabel(key1)
    ax.set_title(f'Confusion Matrix: {key1} vs {key2}')

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


# ============================================================================
# Multi-sample Visualization
# ============================================================================

def plot_multi_sample_domains(
    adatas: Dict[str, AnnData],
    domain_key: str = 'mclust',
    spatial_key: str = 'spatial',
    n_cols: int = 2,
    figsize_per_plot: Tuple[int, int] = (8, 8),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot domains for multiple samples side by side.

    Parameters
    ----------
    adatas : Dict[str, AnnData]
        Dictionary mapping sample names to AnnData
    domain_key : str, default='mclust'
        Key for domains
    spatial_key : str, default='spatial'
        Key for coordinates
    n_cols : int, default=2
        Number of columns
    figsize_per_plot : tuple, default=(8, 8)
        Size per subplot
    save_path : str, optional
        Path to save

    Returns
    -------
    matplotlib.figure.Figure
        Figure object

    Examples
    --------
    >>> adatas = {'Slice1': adata1, 'Slice2': adata2}
    >>> plot_multi_sample_domains(adatas, domain_key='mclust')
    """
    n_samples = len(adatas)
    n_rows = (n_samples + n_cols - 1) // n_cols

    figsize = (figsize_per_plot[0] * n_cols, figsize_per_plot[1] * n_rows)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)

    if n_samples == 1:
        axes = np.array([axes])
    else:
        axes = axes.flatten()

    for idx, (name, adata) in enumerate(adatas.items()):
        try:
            plot_domains(
                adata,
                domain_key=domain_key,
                spatial_key=spatial_key,
                ax=axes[idx],
                title=name,
                show_legend=(idx == 0),  # Only show legend for first
            )
        except Exception as e:
            axes[idx].text(0.5, 0.5, f'Error: {e}', ha='center', transform=axes[idx].transAxes)
            axes[idx].axis('off')

    # Hide extra subplots
    for idx in range(n_samples, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_aligned_slices(
    adata: AnnData,
    section_key: str = 'section',
    domain_key: str = 'mclust',
    spatial_key: str = 'spatial',
    figsize: Tuple[int, int] = (15, 5),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot aligned slices with consistent domain colors.

    Parameters
    ----------
    adata : AnnData
        Concatenated data from multiple sections
    section_key : str, default='section'
        Key identifying sections
    domain_key : str, default='mclust'
        Key for domains
    spatial_key : str, default='spatial'
        Key for coordinates
    figsize : tuple, default=(15, 5)
        Figure size
    save_path : str, optional
        Path to save

    Returns
    -------
    matplotlib.figure.Figure
        Figure object
    """
    if section_key not in adata.obs:
        raise ValueError(f"'{section_key}' not found")

    sections = sorted(adata.obs[section_key].unique())
    n_sections = len(sections)

    figsize = (figsize[0] * n_sections, figsize[1])
    fig, axes = plt.subplots(1, n_sections, figsize=figsize)

    if n_sections == 1:
        axes = [axes]

    # Get consistent colors
    all_domains = sorted(adata.obs[domain_key].unique())
    colors = plt.get_cmap('tab20')(np.linspace(0, 1, len(all_domains)))
    color_dict = {d: colors[i] for i, d in enumerate(all_domains)}

    for idx, section in enumerate(sections):
        mask = adata.obs[section_key] == section
        adata_section = adata[mask]
        coords = adata_section.obsm[spatial_key][:, :2]
        labels = adata_section.obs[domain_key]

        for domain in sorted(labels.unique()):
            domain_mask = labels == domain
            axes[idx].scatter(
                coords[domain_mask, 0],
                coords[domain_mask, 1],
                c=[color_dict[domain]],
                s=50,
                label=str(domain),
                alpha=0.9,
            )

        axes[idx].set_aspect('equal')
        axes[idx].set_title(f'Section {section}')
        axes[idx].set_xlabel('Spatial X')
        if idx == 0:
            axes[idx].set_ylabel('Spatial Y')

    # Shared legend
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='center right', title='Domain')

    plt.tight_layout()
    plt.subplots_adjust(right=0.85)

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


# ============================================================================
# Expression Visualization
# ============================================================================

def plot_gene_expression(
    adata: AnnData,
    gene: str,
    layer: Optional[str] = None,
    spatial_key: str = 'spatial',
    cmap: str = 'viridis',
    figsize: Tuple[int, int] = (10, 8),
    title: Optional[str] = None,
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot gene expression on spatial coordinates.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    gene : str
        Gene name
    layer : str, optional
        Layer to use (e.g., 'STAGATE_ReX' for denoised)
    spatial_key : str, default='spatial'
        Key for coordinates
    cmap : str, default='viridis'
        Colormap
    figsize : tuple, default=(10, 8)
        Figure size
    title : str, optional
        Plot title
    save_path : str, optional
        Path to save

    Returns
    -------
    matplotlib.figure.Figure
        Figure object
    """
    if gene not in adata.var_names:
        raise ValueError(f"'{gene}' not found in adata.var_names")

    # Get expression values
    if layer and layer in adata.layers:
        values = adata[:, gene].layers[layer]
        if hasattr(values, 'toarray'):
            values = values.toarray().flatten()
        else:
            values = np.array(values).flatten()
        source = layer
    else:
        values = adata[:, gene].X
        if hasattr(values, 'toarray'):
            values = values.toarray().flatten()
        else:
            values = np.array(values).flatten()
        source = 'X'

    coords = adata.obsm[spatial_key][:, :2]

    fig, ax = plt.subplots(figsize=figsize)

    scatter = ax.scatter(
        coords[:, 0],
        coords[:, 1],
        c=values,
        cmap=cmap,
        s=50,
        alpha=0.9,
    )

    plt.colorbar(scatter, label='Expression', shrink=0.5)

    ax.set_aspect('equal')
    ax.set_xlabel('Spatial X')
    ax.set_ylabel('Spatial Y')
    ax.set_title(title or f'{gene} ({source})')

    sns.despine(ax=ax)

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_denoising_comparison(
    adata: AnnData,
    gene: str,
    spatial_key: str = 'spatial',
    figsize: Tuple[int, int] = (16, 6),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Compare raw vs denoised gene expression.

    Parameters
    ----------
    adata : AnnData
        Data with STAGATE reconstruction
    gene : str
        Gene name
    spatial_key : str, default='spatial'
        Key for coordinates
    figsize : tuple, default=(16, 6)
        Figure size
    save_path : str, optional
        Path to save

    Returns
    -------
    matplotlib.figure.Figure
        Figure object

    Notes
    -----
    Requires STAGATE reconstruction saved in adata.layers['STAGATE_ReX']
    """
    if gene not in adata.var_names:
        raise ValueError(f"'{gene}' not found")

    if 'STAGATE_ReX' not in adata.layers:
        raise ValueError("'STAGATE_ReX' not found. Run train_stagate with save_reconstruction=True")

    coords = adata.obsm[spatial_key][:, :2]

    # Get raw and denoised values
    raw = adata[:, gene].X
    if hasattr(raw, 'toarray'):
        raw = raw.toarray().flatten()
    else:
        raw = np.array(raw).flatten()

    hvg_idx = list(adata[:, adata.var.highly_variable].var_names).index(gene) if gene in adata[:, adata.var.highly_variable].var_names else None
    if hvg_idx is not None:
        denoised = adata[:, adata.var.highly_variable].layers['STAGATE_ReX'][:, hvg_idx]
        if hasattr(denoised, 'toarray'):
            denoised = denoised.toarray().flatten()
        else:
            denoised = np.array(denoised).flatten()
    else:
        denoised = raw  # Fallback

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Raw
    vmax = np.percentile(np.concatenate([raw, denoised]), 99)
    im1 = axes[0].scatter(coords[:, 0], coords[:, 1], c=raw, cmap='viridis', s=50, alpha=0.9, vmax=vmax)
    axes[0].set_title(f'{gene} - Raw')
    axes[0].set_aspect('equal')
    plt.colorbar(im1, ax=axes[0], shrink=0.5)

    # Denoised
    im2 = axes[1].scatter(coords[:, 0], coords[:, 1], c=denoised, cmap='viridis', s=50, alpha=0.9, vmax=vmax)
    axes[1].set_title(f'{gene} - Denoised (STAGATE)')
    axes[1].set_aspect('equal')
    plt.colorbar(im2, ax=axes[1], shrink=0.5)

    for ax in axes:
        ax.set_xlabel('Spatial X')
        ax.set_ylabel('Spatial Y')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


# ============================================================================
# Training Visualization
# ============================================================================

def plot_training_loss(
    losses: List[float],
    figsize: Tuple[int, int] = (8, 5),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot STAGATE training loss curve.

    Parameters
    ----------
    losses : List[float]
        Loss values per epoch
    figsize : tuple, default=(8, 5)
        Figure size
    save_path : str, optional
        Path to save

    Returns
    -------
    matplotlib.figure.Figure
        Figure object
    """
    fig, ax = plt.subplots(figsize=figsize)

    ax.plot(losses, linewidth=1.5)
    ax.set_xlabel('Epoch')
    ax.set_ylabel('MSE Loss')
    ax.set_title('STAGATE Training Loss')
    ax.set_yscale('log')

    sns.despine(ax=ax)

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig
