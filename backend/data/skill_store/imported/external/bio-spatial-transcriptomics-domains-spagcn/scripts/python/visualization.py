"""
Visualization functions for SpaGCN results.

Author: Yang Guo
Date: 2026-04-03
"""

from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scanpy as sc
import seaborn as sns
from anndata import AnnData
from matplotlib.colors import LinearSegmentedColormap


# ==============================================================================
# Domain Visualization
# ==============================================================================

def plot_spatial_domains(
    adata: AnnData,
    domain_column: str = "pred",
    x_column: str = "x_pixel",
    y_column: str = "y_pixel",
    palette: Optional[List[str]] = None,
    size: Optional[float] = None,
    figsize: Tuple[int, int] = (10, 10),
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    dpi: int = 300,
    show: bool = True
) -> plt.Figure:
    """
    Plot spatial domains on tissue coordinates.

    Parameters
    ----------
    adata : AnnData
        Spatial data with domain predictions
    domain_column : str, default="pred"
        Column name containing domain labels
    x_column : str, default="x_pixel"
        Column name for x coordinates
    y_column : str, default="y_pixel"
        Column name for y coordinates
    palette : List[str], optional
        Custom color palette
    size : float, optional
        Spot size (auto-calculated if None)
    figsize : tuple, default=(10, 10)
        Figure size
    title : str, optional
        Plot title
    save_path : str, optional
        Path to save figure
    dpi : int, default=300
        DPI for saved figure
    show : bool, default=True
        Whether to show the plot

    Returns
    -------
    plt.Figure
        Matplotlib figure object

    Examples
    --------
    >>> fig = plot_spatial_domains(adata, domain_column="spagcn_domain")
    >>> fig = plot_spatial_domains(adata, x_column="array_col", y_column="array_row")
    """
    # Auto-calculate size if not provided
    if size is None:
        size = 100000 / adata.n_obs

    # Default color palette
    if palette is None:
        palette = [
            "#F56867", "#FEB915", "#C798EE", "#59BE86", "#7495D3",
            "#D1D1D1", "#6D1A9C", "#15821E", "#3A84E6", "#997273",
            "#787878", "#DB4C6C", "#9E7A7A", "#554236", "#AF5F3C",
            "#93796C", "#F9BD3F", "#DAB370", "#877F6C", "#268785"
        ]

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Plot
    # NOTE: sc.pl.scatter was removed in scanpy 1.10+. Using matplotlib directly.
    domain_vals = adata.obs[domain_column]
    if hasattr(domain_vals, 'cat'):
        codes = domain_vals.cat.codes
        categories = domain_vals.cat.categories
    else:
        codes = pd.Categorical(domain_vals).codes
        categories = pd.Categorical(domain_vals).categories

    # Map domain codes to colors from palette (avoid modifying adata.uns)
    colors = [palette[c % len(palette)] for c in codes]
    ax.scatter(
        adata.obs[y_column],
        adata.obs[x_column],
        c=colors,
        s=size,
        edgecolors='none'
    )
    ax.legend(
        handles=[plt.Line2D([0], [0], marker='o', color='w',
                             markerfacecolor=palette[i % len(palette)], markersize=8, label=str(cat))
                 for i, cat in enumerate(categories)],
        title=domain_column,
        loc='best'
    )

    ax.set_aspect('equal')
    ax.invert_yaxis()

    if title:
        ax.set_title(title)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches='tight')
        print(f"Saved to {save_path}")

    if show:
        plt.show()

    return fig


def plot_domain_comparison(
    adata: AnnData,
    domain_columns: List[str] = ["pred", "refined_pred"],
    labels: List[str] = ["Original", "Refined"],
    x_column: str = "x_pixel",
    y_column: str = "y_pixel",
    figsize: Tuple[int, int] = (20, 10),
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Compare original and refined domain predictions side by side.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    domain_columns : List[str], default=["pred", "refined_pred"]
        Columns to compare
    labels : List[str], default=["Original", "Refined"]
        Labels for each column
    x_column : str, default="x_pixel"
        Column name for x coordinates
    y_column : str, default="y_pixel"
        Column name for y coordinates
    figsize : tuple, default=(20, 10)
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure
    """
    size = 100000 / adata.n_obs

    # Get common color palette
    all_domains = set()
    for col in domain_columns:
        all_domains.update(adata.obs[col].unique())
    all_domains = sorted(list(all_domains))

    palette = plt.cm.tab20(np.linspace(0, 1, len(all_domains)))
    color_map = dict(zip(all_domains, palette))

    fig, axes = plt.subplots(1, len(domain_columns), figsize=figsize)
    if len(domain_columns) == 1:
        axes = [axes]

    for ax, col, label in zip(axes, domain_columns, labels):
        domains = adata.obs[col]
        colors = [color_map[d] for d in domains]

        ax.scatter(
            adata.obs[y_column],
            adata.obs[x_column],
            c=colors,
            s=size,
            alpha=0.8
        )

        ax.set_aspect('equal')
        ax.invert_yaxis()
        ax.set_title(label)

        # Add legend
        handles = [plt.Rectangle((0, 0), 1, 1, color=color_map[d]) for d in sorted(domains.unique())]
        ax.legend(handles, sorted(domains.unique()), bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


# ==============================================================================
# Gene Expression Visualization
# ==============================================================================

def plot_gene_expression(
    adata: AnnData,
    gene: str,
    x_column: str = "x_pixel",
    y_column: str = "y_pixel",
    cmap: str = "viridis",
    size: Optional[float] = None,
    figsize: Tuple[int, int] = (10, 10),
    title: Optional[str] = None,
    use_raw: bool = False,
    save_path: Optional[str] = None,
    dpi: int = 300,
    show: bool = True
) -> plt.Figure:
    """
    Plot gene expression on spatial coordinates.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    gene : str
        Gene name to plot
    x_column : str, default="x_pixel"
        Column name for x coordinates
    y_column : str, default="y_pixel"
        Column name for y coordinates
    cmap : str, default="viridis"
        Colormap
    size : float, optional
        Spot size
    figsize : tuple, default=(10, 10)
        Figure size
    title : str, optional
        Plot title
    use_raw : bool, default=False
        Use raw expression values
    save_path : str, optional
        Path to save figure
    dpi : int, default=300
        DPI for saved figure
    show : bool, default=True
        Whether to show plot

    Returns
    -------
    plt.Figure
        Matplotlib figure

    Examples
    --------
    >>> fig = plot_gene_expression(adata, gene="GFAP")
    """
    if size is None:
        size = 100000 / adata.n_obs

    if gene not in adata.var_names:
        raise ValueError(f"Gene {gene} not found in data")

    # Get expression values
    if use_raw and adata.raw is not None:
        exp = adata.raw[:, gene].X.toarray().flatten() if hasattr(adata.raw[:, gene].X, 'toarray') else adata.raw[:, gene].X.flatten()
    else:
        exp = adata[:, gene].X.toarray().flatten() if hasattr(adata[:, gene].X, 'toarray') else adata[:, gene].X.flatten()

    # Use a local variable instead of modifying adata.obs
    gene_exp = exp

    fig, ax = plt.subplots(figsize=figsize)

    # NOTE: sc.pl.scatter was removed in scanpy 1.10+. Using matplotlib directly.
    scatter = ax.scatter(
        adata.obs[y_column],
        adata.obs[x_column],
        c=gene_exp,
        cmap=cmap,
        s=size,
        edgecolors='none'
    )
    plt.colorbar(scatter, ax=ax, label=gene)

    ax.set_aspect('equal')
    ax.invert_yaxis()

    plot_title = title if title else f"{gene} expression"
    ax.set_title(plot_title)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches='tight')
        print(f"Saved to {save_path}")

    if show:
        plt.show()

    return fig


def plot_multiple_genes(
    adata: AnnData,
    genes: List[str],
    x_column: str = "x_pixel",
    y_column: str = "y_pixel",
    cmap: str = "viridis",
    ncols: int = 3,
    figsize: Optional[Tuple[int, int]] = None,
    use_raw: bool = False,
    save_path: Optional[str] = None,
    dpi: int = 300
) -> plt.Figure:
    """
    Plot multiple genes in a grid.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    genes : List[str]
        List of gene names to plot
    x_column : str, default="x_pixel"
        Column name for x coordinates
    y_column : str, default="y_pixel"
        Column name for y coordinates
    cmap : str, default="viridis"
        Colormap
    ncols : int, default=3
        Number of columns
    figsize : tuple, optional
        Figure size (auto-calculated if None)
    use_raw : bool, default=False
        Use raw expression values
    save_path : str, optional
        Path to save figure
    dpi : int, default=300
        DPI for saved figure

    Returns
    -------
    plt.Figure
        Matplotlib figure
    """
    n_genes = len(genes)
    nrows = (n_genes + ncols - 1) // ncols

    if figsize is None:
        figsize = (5 * ncols, 5 * nrows)

    size = 100000 / adata.n_obs

    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    if nrows == 1 and ncols == 1:
        axes = np.array([axes])
    axes = axes.flatten()

    for idx, gene in enumerate(genes):
        ax = axes[idx]

        if gene not in adata.var_names:
            ax.text(0.5, 0.5, f"{gene} not found", ha='center', va='center', transform=ax.transAxes)
            ax.axis('off')
            continue

        # Get expression
        if use_raw and adata.raw is not None:
            exp = adata.raw[:, gene].X.toarray().flatten() if hasattr(adata.raw[:, gene].X, 'toarray') else adata.raw[:, gene].X.flatten()
        else:
            exp = adata[:, gene].X.toarray().flatten() if hasattr(adata[:, gene].X, 'toarray') else adata[:, gene].X.flatten()

        # Plot
        scatter = ax.scatter(
            adata.obs[y_column],
            adata.obs[x_column],
            c=exp,
            cmap=cmap,
            s=size,
            alpha=0.8
        )

        ax.set_aspect('equal')
        ax.invert_yaxis()
        ax.set_title(gene)
        ax.axis('off')

        plt.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04)

    # Hide unused subplots
    for idx in range(n_genes, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches='tight')

    return fig


# ==============================================================================
# Domain Statistics Visualization
# ==============================================================================

def plot_domain_heatmap(
    adata: AnnData,
    genes: List[str],
    domain_column: str = "pred",
    figsize: Tuple[int, int] = (12, 8),
    cmap: str = "viridis",
    save_path: Optional[str] = None,
    dpi: int = 300
) -> plt.Figure:
    """
    Plot heatmap of gene expression across domains.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    genes : List[str]
        Genes to include
    domain_column : str, default="pred"
        Column with domain labels
    figsize : tuple, default=(12, 8)
        Figure size
    cmap : str, default="viridis"
        Colormap
    save_path : str, optional
        Path to save figure
    dpi : int, default=300
        DPI for saved figure

    Returns
    -------
    plt.Figure
        Matplotlib figure
    """
    # Filter to available genes
    genes = [g for g in genes if g in adata.var_names]

    if len(genes) == 0:
        raise ValueError("None of the specified genes found in data")

    # Calculate mean expression per domain
    domain_means = []
    domains = sorted(adata.obs[domain_column].unique())

    for domain in domains:
        mask = adata.obs[domain_column] == domain
        domain_data = adata[mask, genes]

        if hasattr(domain_data.X, 'toarray'):
            mean_exp = np.array(domain_data.X.mean(axis=0)).flatten()
        else:
            mean_exp = domain_data.X.mean(axis=0)

        domain_means.append(mean_exp)

    # Create DataFrame
    df = pd.DataFrame(domain_means, index=domains, columns=genes)

    # Normalize per gene
    df_norm = (df - df.min(axis=0)) / (df.max(axis=0) - df.min(axis=0) + 1e-10)

    # Plot
    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(df_norm.T, cmap=cmap, ax=ax, cbar_kws={'label': 'Normalized Expression'})
    ax.set_xlabel('Domain')
    ax.set_ylabel('Gene')
    ax.set_title('Gene Expression by Domain')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches='tight')

    return fig


def plot_domain_proportions(
    adata: AnnData,
    domain_column: str = "pred",
    sample_column: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 6),
    save_path: Optional[str] = None,
    dpi: int = 300
) -> plt.Figure:
    """
    Plot domain proportions as bar or stacked bar chart.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    domain_column : str, default="pred"
        Column with domain labels
    sample_column : str, optional
        Column with sample labels (for multi-sample)
    figsize : tuple, default=(10, 6)
        Figure size
    save_path : str, optional
        Path to save figure
    dpi : int, default=300
        DPI for saved figure

    Returns
    -------
    plt.Figure
        Matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    if sample_column is None:
        # Single sample - simple bar chart
        proportions = adata.obs[domain_column].value_counts(normalize=True).sort_index()
        proportions.plot(kind='bar', ax=ax, color='steelblue')
        ax.set_ylabel('Proportion')
        ax.set_title('Domain Proportions')
        ax.set_xlabel('Domain')
    else:
        # Multi-sample - stacked bar chart
        cross_tab = pd.crosstab(adata.obs[sample_column], adata.obs[domain_column], normalize='index')
        cross_tab.plot(kind='bar', stacked=True, ax=ax)
        ax.set_ylabel('Proportion')
        ax.set_title('Domain Proportions by Sample')
        ax.set_xlabel('Sample')
        ax.legend(title='Domain', bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches='tight')

    return fig


# ==============================================================================
# SVG Visualization
# ==============================================================================

def plot_svg_results(
    adata: AnnData,
    svg_results: pd.DataFrame,
    x_column: str = "x_pixel",
    y_column: str = "y_pixel",
    top_n: int = 6,
    cmap: str = "magma",
    figsize: Optional[Tuple[int, int]] = None,
    save_dir: Optional[str] = None,
    dpi: int = 300
) -> List[plt.Figure]:
    """
    Plot spatial expression of top SVGs.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    svg_results : pd.DataFrame
        Results from identify_svgs
    x_column : str, default="x_pixel"
        Column name for x coordinates
    y_column : str, default="y_pixel"
        Column name for y coordinates
    top_n : int, default=6
        Number of top SVGs to plot
    cmap : str, default="magma"
        Colormap
    figsize : tuple, optional
        Figure size
    save_dir : str, optional
        Directory to save individual plots
    dpi : int, default=300
        DPI for saved figures

    Returns
    -------
    List[plt.Figure]
        List of figure objects
    """
    top_genes = svg_results["genes"].head(top_n).tolist()

    if figsize is None:
        figsize = (15, 10)

    figures = []

    # Create combined plot
    fig = plot_multiple_genes(
        adata,
        genes=top_genes,
        x_column=x_column,
        y_column=y_column,
        cmap=cmap,
        ncols=3,
        figsize=figsize
    )
    figures.append(fig)

    # Save individual plots if directory provided
    if save_dir:
        import os
        os.makedirs(save_dir, exist_ok=True)

        for gene in top_genes:
            fig = plot_gene_expression(
                adata,
                gene=gene,
                x_column=x_column,
                y_column=y_column,
                cmap=cmap,
                save_path=os.path.join(save_dir, f"{gene}_svg.png"),
                dpi=dpi,
                show=False
            )
            figures.append(fig)

    return figures


def plot_meta_gene(
    adata: AnnData,
    meta_exp: List[float],
    meta_name: str,
    x_column: str = "x_pixel",
    y_column: str = "y_pixel",
    cmap: Optional[LinearSegmentedColormap] = None,
    figsize: Tuple[int, int] = (10, 10),
    save_path: Optional[str] = None,
    dpi: int = 300,
    show: bool = True
) -> plt.Figure:
    """
    Plot meta gene expression on spatial coordinates.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    meta_exp : List[float]
        Meta gene expression values
    meta_name : str
        Meta gene name (e.g., "GENE1+GENE2-GENE3")
    x_column : str, default="x_pixel"
        Column name for x coordinates
    y_column : str, default="y_pixel"
        Column name for y coordinates
    cmap : LinearSegmentedColormap, optional
        Custom colormap
    figsize : tuple, default=(10, 10)
        Figure size
    save_path : str, optional
        Path to save figure
    dpi : int, default=300
        DPI for saved figure
    show : bool, default=True
        Whether to show plot

    Returns
    -------
    plt.Figure
        Matplotlib figure
    """
    # Custom colormap if not provided
    if cmap is None:
        cmap = LinearSegmentedColormap.from_list(
            'pink_green',
            ['#3AB370', "#EAE7CC", "#FD1593"],
            N=256
        )

    size = 100000 / adata.n_obs

    fig, ax = plt.subplots(figsize=figsize)

    # NOTE: sc.pl.scatter was removed in scanpy 1.10+. Using matplotlib directly.
    scatter = ax.scatter(
        adata.obs[y_column],
        adata.obs[x_column],
        c=meta_exp,
        cmap=cmap,
        s=size,
        edgecolors='none'
    )
    plt.colorbar(scatter, ax=ax, label=meta_name)

    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.set_title(f"Meta Gene: {meta_name}")

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches='tight')
        print(f"Saved to {save_path}")

    if show:
        plt.show()

    return fig


# ==============================================================================
# Multi-Sample Visualization
# ==============================================================================

def plot_multi_sample_domains(
    adatas: List[AnnData],
    sample_names: List[str],
    domain_column: str = "pred",
    x_column: str = "x_pixel",
    y_column: str = "y_pixel",
    ncols: int = 3,
    figsize: Optional[Tuple[int, int]] = None,
    save_path: Optional[str] = None,
    dpi: int = 300
) -> plt.Figure:
    """
    Plot spatial domains for multiple samples.

    Parameters
    ----------
    adatas : List[AnnData]
        List of spatial data objects
    sample_names : List[str]
        Sample names
    domain_column : str, default="pred"
        Column with domain labels
    x_column : str, default="x_pixel"
        Column name for x coordinates
    y_column : str, default="y_pixel"
        Column name for y coordinates
    ncols : int, default=3
        Number of columns
    figsize : tuple, optional
        Figure size
    save_path : str, optional
        Path to save figure
    dpi : int, default=300
        DPI for saved figure

    Returns
    -------
    plt.Figure
        Matplotlib figure
    """
    n_samples = len(adatas)
    nrows = (n_samples + ncols - 1) // ncols

    if figsize is None:
        figsize = (5 * ncols, 5 * nrows)

    # Get common color palette
    all_domains = set()
    for adata in adatas:
        all_domains.update(adata.obs[domain_column].unique())
    all_domains = sorted(list(all_domains))

    palette = plt.cm.tab20(np.linspace(0, 1, len(all_domains)))
    color_map = dict(zip(all_domains, palette))

    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    if n_samples == 1:
        axes = np.array([axes])
    axes = axes.flatten()

    for ax, adata, name in zip(axes, adatas, sample_names):
        domains = adata.obs[domain_column]
        colors = [color_map[d] for d in domains]

        size = 100000 / adata.n_obs

        ax.scatter(
            adata.obs[y_column],
            adata.obs[x_column],
            c=colors,
            s=size,
            alpha=0.8
        )

        ax.set_aspect('equal')
        ax.invert_yaxis()
        ax.set_title(name)
        ax.axis('off')

    # Hide unused subplots
    for idx in range(n_samples, len(axes)):
        axes[idx].axis('off')

    # Add common legend
    handles = [plt.Rectangle((0, 0), 1, 1, color=color_map[d]) for d in all_domains]
    fig.legend(handles, all_domains, loc='center right', title='Domain', bbox_to_anchor=(1.02, 0.5))

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches='tight')

    return fig
