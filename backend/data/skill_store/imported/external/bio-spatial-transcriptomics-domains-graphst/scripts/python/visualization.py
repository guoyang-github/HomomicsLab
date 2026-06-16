#!/usr/bin/env python3
"""
Visualization Functions for GraphST Spatial Domain Analysis

Additional plotting functions that complement native GraphST visualizations.
Uses scanpy and matplotlib for spatial transcriptomics visualization.

Author: Yang Guo
Date: 2026-04-07
"""

import numpy as np
import pandas as pd
import scanpy as sc
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Optional, List, Tuple


def plot_domain_comparison(
    adata: sc.AnnData,
    methods: List[str],
    spatial_key: str = 'spatial',
    ncols: int = 3,
    figsize: Tuple[int, int] = None,
    save: Optional[str] = None
) -> plt.Figure:
    """
    Compare spatial domains from different clustering methods.

    Parameters
    ----------
    adata : AnnData
        AnnData with domain assignments
    methods : list
        List of method names (column names in adata.obs)
    spatial_key : str
        Key for spatial coordinates in adata.obsm
    ncols : int
        Number of columns in subplot
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure

    Returns
    -------
    Figure
        Matplotlib figure object
    """
    n_methods = len(methods)
    nrows = (n_methods + ncols - 1) // ncols

    if figsize is None:
        figsize = (4 * ncols, 4 * nrows)

    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    if nrows == 1 and ncols == 1:
        axes = np.array([axes])
    elif nrows == 1:
        axes = axes.reshape(1, -1)
    else:
        axes = axes.flatten()

    spatial = adata.obsm[spatial_key]

    for idx, method in enumerate(methods):
        ax = axes[idx]

        if method not in adata.obs:
            ax.text(0.5, 0.5, f'{method} not found', ha='center', va='center')
            ax.axis('off')
            continue

        domains = adata.obs[method]
        unique_domains = domains.unique()
        colors = plt.cm.tab10(np.linspace(0, 1, len(unique_domains)))

        for i, domain in enumerate(unique_domains):
            mask = domains == domain
            ax.scatter(
                spatial[mask, 0],
                spatial[mask, 1],
                c=[colors[i]],
                label=f'Domain {domain}',
                s=10,
                alpha=0.7
            )

        ax.set_title(f'{method}')
        ax.set_aspect('equal')
        ax.axis('off')

    # Hide unused subplots
    for idx in range(n_methods, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()

    if save:
        fig.savefig(save, dpi=300, bbox_inches='tight')

    return fig


def plot_embedding_umap(
    adata: sc.AnnData,
    color: str = 'domain',
    use_rep: str = 'emb',
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    save: Optional[str] = None
) -> plt.Figure:
    """
    Create UMAP visualization of GraphST embeddings.

    Parameters
    ----------
    adata : AnnData
        AnnData with embeddings
    color : str
        Column in adata.obs to color by
    use_rep : str
        Embedding key in adata.obsm
    n_neighbors : int
        Number of neighbors for UMAP
    min_dist : float
        Minimum distance for UMAP
    save : str, optional
        Path to save figure

    Returns
    -------
    Figure
        Matplotlib figure object
    """
    # Compute neighbors and UMAP if not present
    if 'neighbors' not in adata.uns:
        sc.pp.neighbors(adata, use_rep=use_rep, n_neighbors=n_neighbors)
    if 'X_umap' not in adata.obsm:
        sc.tl.umap(adata, min_dist=min_dist)

    # Plot
    fig, ax = plt.subplots(figsize=(8, 6))
    sc.pl.umap(adata, color=color, ax=ax, show=False)
    ax.set_title(f'UMAP of GraphST Embeddings ({color})')

    if save:
        fig.savefig(save, dpi=300, bbox_inches='tight')

    return fig


def plot_domain_sizes(
    adata: sc.AnnData,
    method: str = 'domain',
    figsize: Tuple[int, int] = (10, 6),
    save: Optional[str] = None
) -> plt.Figure:
    """
    Plot domain size distribution.

    Parameters
    ----------
    adata : AnnData
        AnnData with domain assignments
    method : str
        Column in adata.obs with domain labels
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure

    Returns
    -------
    Figure
        Matplotlib figure object
    """
    if method not in adata.obs:
        raise ValueError(f"{method} not found in adata.obs")

    domain_counts = adata.obs[method].value_counts().sort_index()

    fig, ax = plt.subplots(figsize=figsize)
    domain_counts.plot(kind='bar', ax=ax, color='steelblue')
    ax.set_xlabel('Domain')
    ax.set_ylabel('Number of Spots')
    ax.set_title(f'Domain Size Distribution ({method})')
    ax.tick_params(axis='x', rotation=0)

    plt.tight_layout()

    if save:
        fig.savefig(save, dpi=300, bbox_inches='tight')

    return fig


def plot_spatial_heatmap(
    adata: sc.AnnData,
    features: List[str],
    spatial_key: str = 'spatial',
    ncols: int = 3,
    figsize: Tuple[int, int] = None,
    cmap: str = 'viridis',
    save: Optional[str] = None
) -> plt.Figure:
    """
    Plot spatial heatmap of gene expression or features.

    Parameters
    ----------
    adata : AnnData
        AnnData object
    features : list
        List of gene names or obs columns to plot
    spatial_key : str
        Key for spatial coordinates
    ncols : int
        Number of columns
    figsize : tuple
        Figure size
    cmap : str
        Colormap
    save : str, optional
        Path to save figure

    Returns
    -------
    Figure
        Matplotlib figure object
    """
    n_features = len(features)
    nrows = (n_features + ncols - 1) // ncols

    if figsize is None:
        figsize = (4 * ncols, 4 * nrows)

    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    if nrows == 1:
        axes = axes.reshape(1, -1) if ncols > 1 else [axes]
    else:
        axes = axes.flatten()

    spatial = adata.obsm[spatial_key]

    for idx, feature in enumerate(features):
        ax = axes[idx] if nrows > 1 or ncols > 1 else axes[0]

        # Get values
        if feature in adata.obs.columns:
            values = adata.obs[feature].values
        elif feature in adata.var_names:
            values = adata[:, feature].X.flatten()
            if hasattr(values, 'toarray'):
                values = values.toarray().flatten()
        else:
            ax.text(0.5, 0.5, f'{feature} not found', ha='center', va='center')
            ax.axis('off')
            continue

        # Plot
        scatter = ax.scatter(
            spatial[:, 0],
            spatial[:, 1],
            c=values,
            cmap=cmap,
            s=10,
            alpha=0.7
        )
        ax.set_title(feature)
        ax.set_aspect('equal')
        ax.axis('off')
        plt.colorbar(scatter, ax=ax, fraction=0.046)

    # Hide unused subplots
    for idx in range(n_features, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()

    if save:
        fig.savefig(save, dpi=300, bbox_inches='tight')

    return fig


def plot_embedding_quality(
    adata: sc.AnnData,
    use_rep: str = 'emb',
    figsize: Tuple[int, int] = (12, 4),
    save: Optional[str] = None
) -> plt.Figure:
    """
    Plot embedding quality metrics.

    Parameters
    ----------
    adata : AnnData
        AnnData with embeddings
    use_rep : str
        Embedding key in adata.obsm
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure

    Returns
    -------
    Figure
        Matplotlib figure object
    """
    if use_rep not in adata.obsm:
        raise ValueError(f"{use_rep} not found in adata.obsm")

    emb = adata.obsm[use_rep]

    fig, axes = plt.subplots(1, 3, figsize=figsize)

    # 1. Distribution of embedding values
    ax = axes[0]
    ax.hist(emb.flatten(), bins=50, color='steelblue', edgecolor='black')
    ax.set_xlabel('Embedding Value')
    ax.set_ylabel('Frequency')
    ax.set_title('Embedding Value Distribution')

    # 2. Standard deviation per dimension
    ax = axes[1]
    stds = np.std(emb, axis=0)
    ax.bar(range(len(stds)), stds, color='coral')
    ax.set_xlabel('Dimension')
    ax.set_ylabel('Standard Deviation')
    ax.set_title('Variance per Dimension')

    # 3. Pairwise distance distribution
    ax = axes[2]
    from scipy.spatial.distance import pdist
    distances = pdist(emb[:100])  # Sample for speed
    ax.hist(distances, bins=50, color='lightgreen', edgecolor='black')
    ax.set_xlabel('Pairwise Distance')
    ax.set_ylabel('Frequency')
    ax.set_title('Embedding Distance Distribution')

    plt.tight_layout()

    if save:
        fig.savefig(save, dpi=300, bbox_inches='tight')

    return fig


def plot_multi_section_domains(
    adatas: List[sc.AnnData],
    domain_key: str = 'domain',
    spatial_key: str = 'spatial',
    ncols: int = 2,
    figsize: Tuple[int, int] = None,
    titles: Optional[List[str]] = None,
    save: Optional[str] = None
) -> plt.Figure:
    """
    Plot domains for multiple tissue sections.

    Parameters
    ----------
    adatas : list
        List of AnnData objects
    domain_key : str
        Key for domain assignments
    spatial_key : str
        Key for spatial coordinates
    ncols : int
        Number of columns
    figsize : tuple
        Figure size
    titles : list, optional
        Titles for each section
    save : str, optional
        Path to save figure

    Returns
    -------
    Figure
        Matplotlib figure object
    """
    n_sections = len(adatas)
    nrows = (n_sections + ncols - 1) // ncols

    if figsize is None:
        figsize = (5 * ncols, 5 * nrows)

    if titles is None:
        titles = [f'Section {i+1}' for i in range(n_sections)]

    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    if nrows == 1 and ncols == 1:
        axes = np.array([axes])
    elif nrows == 1:
        axes = axes.reshape(1, -1)
    else:
        axes = axes.flatten()

    for idx, (adata, title) in enumerate(zip(adatas, titles)):
        ax = axes[idx]

        if domain_key not in adata.obs:
            ax.text(0.5, 0.5, f'{domain_key} not found', ha='center', va='center')
            ax.axis('off')
            continue

        spatial = adata.obsm[spatial_key]
        domains = adata.obs[domain_key]
        unique_domains = domains.unique()

        colors = plt.cm.tab10(np.linspace(0, 1, len(unique_domains)))

        for i, domain in enumerate(unique_domains):
            mask = domains == domain
            ax.scatter(
                spatial[mask, 0],
                spatial[mask, 1],
                c=[colors[i]],
                label=f'Domain {domain}',
                s=10,
                alpha=0.7
            )

        ax.set_title(title)
        ax.set_aspect('equal')
        ax.axis('off')

    # Hide unused subplots
    for idx in range(n_sections, len(axes)):
        axes[idx].axis('off')

    # Add legend to first subplot
    if n_sections > 0:
        axes[0].legend(loc='best', markerscale=2)

    plt.tight_layout()

    if save:
        fig.savefig(save, dpi=300, bbox_inches='tight')

    return fig


def create_summary_figure(
    adata: sc.AnnData,
    method: str = 'domain',
    use_rep: str = 'emb',
    figsize: Tuple[int, int] = (16, 12),
    save: Optional[str] = None
) -> plt.Figure:
    """
    Create a comprehensive summary figure.

    Parameters
    ----------
    adata : AnnData
        AnnData with GraphST results
    method : str
        Domain method to display
    use_rep : str
        Embedding key
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure

    Returns
    -------
    Figure
        Matplotlib figure object
    """
    fig = plt.figure(figsize=figsize)

    # Create grid
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # 1. Spatial domains
    ax1 = fig.add_subplot(gs[0, 0])
    spatial = adata.obsm['spatial']
    if method in adata.obs:
        domains = adata.obs[method]
        unique_domains = domains.unique()
        colors = plt.cm.tab10(np.linspace(0, 1, len(unique_domains)))
        for i, domain in enumerate(unique_domains):
            mask = domains == domain
            ax1.scatter(spatial[mask, 0], spatial[mask, 1],
                       c=[colors[i]], label=f'Domain {domain}', s=10)
    ax1.set_title('Spatial Domains')
    ax1.set_aspect('equal')
    ax1.axis('off')

    # 2. Domain sizes
    ax2 = fig.add_subplot(gs[0, 1])
    if method in adata.obs:
        adata.obs[method].value_counts().sort_index().plot(kind='bar', ax=ax2, color='steelblue')
    ax2.set_title('Domain Sizes')
    ax2.set_xlabel('Domain')
    ax2.set_ylabel('Count')

    # 3. UMAP
    ax3 = fig.add_subplot(gs[0, 2])
    if 'X_umap' in adata.obsm:
        sc.pl.umap(adata, color=method, ax=ax3, show=False, legend_loc='on data')
    ax3.set_title('UMAP')

    # 4. Embedding distribution
    ax4 = fig.add_subplot(gs[1, 0])
    if use_rep in adata.obsm:
        ax4.hist(adata.obsm[use_rep].flatten(), bins=50, color='coral', edgecolor='black')
    ax4.set_title('Embedding Distribution')
    ax4.set_xlabel('Value')
    ax4.set_ylabel('Frequency')

    # 5. Spatial coordinate distribution
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.scatter(spatial[:, 0], spatial[:, 1], c='gray', s=1, alpha=0.5)
    ax5.set_title('Spatial Layout')
    ax5.set_aspect('equal')
    ax5.set_xlabel('X')
    ax5.set_ylabel('Y')

    # 6. Domain statistics
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.axis('off')
    if method in adata.obs:
        stats_text = f"""
        Domain Statistics
        ----------------
        Total spots: {adata.n_obs}
        Total domains: {adata.obs[method].nunique()}

        Domain sizes:
        {adata.obs[method].value_counts().sort_index().to_string()}
        """
        ax6.text(0.1, 0.5, stats_text, fontsize=10, family='monospace',
                verticalalignment='center')

    # 7-9. Additional plots can be added here

    if save:
        fig.savefig(save, dpi=300, bbox_inches='tight')

    return fig
