"""
Visualization Functions for pertpy
====================================

This module provides visualization functions for perturbation analysis results.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Optional, Union, List, Dict, Tuple, Any


def plot_augur_results(
    adata,
    key: str = "augur_results",
    figsize: Tuple[int, int] = (10, 6),
    save: Optional[str] = None,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot Augur prioritization results.

    Parameters
    ----------
    adata : AnnData
        AnnData with Augur results
    key : str
        Key in .uns with Augur results
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure
    **kwargs
        Additional arguments

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        import pertpy as pt
    except ImportError:
        raise ImportError("pertpy is required")

    if key not in adata.uns:
        raise ValueError(f"Augur results not found in .uns['{key}']")

    fig, ax = plt.subplots(figsize=figsize)

    # pertpy Augur plotting is via instance methods, not pt.pl.augur_scatter
    # This function requires the Augur results dict to be passed separately.
    # If results are not available, plot from adata.uns directly.
    if key in adata.uns and 'summary_metrics' in adata.uns[key]:
        results_df = adata.uns[key]['summary_metrics']
        results_df.plot(kind='scatter', ax=ax, **kwargs)
    else:
        ax.text(0.5, 0.5, 'Augur results not available for plotting',
                ha='center', va='center', transform=ax.transAxes)

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save}")

    return ax


def plot_perturbation_distance_heatmap(
    distance_df: pd.DataFrame,
    cmap: str = "viridis",
    figsize: Tuple[int, int] = (10, 8),
    save: Optional[str] = None,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot heatmap of perturbation distances.

    Parameters
    ----------
    distance_df : pd.DataFrame
        Distance matrix from calculate_perturbation_distances
    cmap : str
        Colormap
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure
    **kwargs
        Additional arguments for seaborn.heatmap

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        import seaborn as sns
    except ImportError:
        raise ImportError("seaborn is required for heatmap plotting")

    fig, ax = plt.subplots(figsize=figsize)

    sns.heatmap(
        distance_df,
        cmap=cmap,
        annot=True,
        fmt=".2f",
        square=True,
        ax=ax,
        **kwargs
    )

    ax.set_title("Perturbation Distance Matrix")

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save}")

    return ax


def plot_mixscape_results(
    adata,
    perturbation_col: str = "perturbation",
    mixscape_col: str = "mixscape_class",
    embedding: str = "X_umap",
    figsize: Tuple[int, int] = (12, 5),
    save: Optional[str] = None,
    **kwargs
) -> Optional[List[plt.Axes]]:
    """
    Plot Mixscape classification results.

    Parameters
    ----------
    adata : AnnData
        AnnData with Mixscape results
    perturbation_col : str
        Column with perturbation labels
    mixscape_col : str
        Column with Mixscape classifications
    embedding : str
        Embedding to use for plotting
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure
    **kwargs
        Additional arguments

    Returns
    -------
    axes : list of matplotlib.axes.Axes or None
    """
    try:
        import pertpy as pt
    except ImportError:
        raise ImportError("pertpy is required")

    if mixscape_col not in adata.obs.columns:
        raise ValueError(f"Mixscape column '{mixscape_col}' not found")

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Plot perturbation labels
    pt.pl.mixscape_plot(adata, color=perturbation_col, embedding=embedding, ax=axes[0], **kwargs)
    axes[0].set_title("Perturbation Labels")

    # Plot Mixscape classification
    pt.pl.mixscape_plot(adata, color=mixscape_col, embedding=embedding, ax=axes[1], **kwargs)
    axes[1].set_title("Mixscape Classification")

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save}")

    return axes


def plot_perturbation_embedding(
    adata,
    perturbation_col: str = "perturbation",
    embedding: str = "X_umap",
    color_by: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 8),
    save: Optional[str] = None,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot perturbations on embedding.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    perturbation_col : str
        Column with perturbation labels
    embedding : str
        Embedding key in .obsm
    color_by : str, optional
        Additional column to color by
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure
    **kwargs
        Additional arguments for scanpy.pl.embedding

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        import scanpy as sc
    except ImportError:
        raise ImportError("scanpy is required")

    if embedding not in adata.obsm:
        raise ValueError(f"Embedding '{embedding}' not found")

    fig, ax = plt.subplots(figsize=figsize)

    # Plot with perturbation colors
    sc.pl.embedding(
        adata,
        basis=embedding.replace("X_", ""),
        color=perturbation_col,
        ax=ax,
        show=False,
        **kwargs
    )

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save}")

    return ax


def plot_de_volcano(
    de_results: pd.DataFrame,
    logfc_col: str = "log2FoldChange",
    pval_col: str = "padj",
    pval_threshold: float = 0.05,
    logfc_threshold: float = 0.5,
    figsize: Tuple[int, int] = (10, 8),
    save: Optional[str] = None,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot volcano plot for differential expression results.

    Parameters
    ----------
    de_results : pd.DataFrame
        DE results DataFrame
    logfc_col : str
        Column with log fold changes
    pval_col : str
        Column with adjusted p-values
    pval_threshold : float
        P-value threshold for significance
    logfc_threshold : float
        LogFC threshold for significance
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure
    **kwargs
        Additional arguments

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Calculate -log10 p-values
    de_results["-log10_padj"] = -np.log10(de_results[pval_col].replace(0, np.nanmin(de_results[pval_col]) * 0.1))

    # Color by significance
    colors = []
    for _, row in de_results.iterrows():
        if row[pval_col] < pval_threshold and abs(row[logfc_col]) > logfc_threshold:
            colors.append("red" if row[logfc_col] > 0 else "blue")
        else:
            colors.append("gray")

    ax.scatter(
        de_results[logfc_col],
        de_results["-log10_padj"],
        c=colors,
        alpha=0.5,
        s=20
    )

    # Add threshold lines
    ax.axhline(-np.log10(pval_threshold), color="black", linestyle="--", alpha=0.5)
    ax.axvline(logfc_threshold, color="black", linestyle="--", alpha=0.5)
    ax.axvline(-logfc_threshold, color="black", linestyle="--", alpha=0.5)

    ax.set_xlabel("Log2 Fold Change")
    ax.set_ylabel("-Log10 Adjusted P-value")
    ax.set_title("Differential Expression Volcano Plot")

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save}")

    return ax


def plot_distance_dendrogram(
    distance_df: pd.DataFrame,
    method: str = "average",
    figsize: Tuple[int, int] = (12, 6),
    save: Optional[str] = None,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot hierarchical clustering dendrogram of perturbations.

    Parameters
    ----------
    distance_df : pd.DataFrame
        Distance matrix
    method : str
        Linkage method
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure
    **kwargs
        Additional arguments

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    try:
        from scipy.cluster.hierarchy import linkage, dendrogram
    except ImportError:
        raise ImportError("scipy is required")

    fig, ax = plt.subplots(figsize=figsize)

    # Convert distance matrix to linkage
    linkage_matrix = linkage(distance_df.values, method=method)

    # Plot dendrogram
    dendrogram(
        linkage_matrix,
        labels=distance_df.index,
        ax=ax,
        **kwargs
    )

    ax.set_xlabel("Perturbation")
    ax.set_ylabel("Distance")
    ax.set_title("Perturbation Clustering Dendrogram")

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save}")

    return ax


def plot_guide_assignment(
    adata,
    guide_rna_column: str = "guide_identity",
    figsize: Tuple[int, int] = (12, 6),
    save: Optional[str] = None,
    **kwargs
) -> Optional[plt.Axes]:
    """
    Plot guide RNA assignment distribution.

    Parameters
    ----------
    adata : AnnData
        AnnData with guide assignments
    guide_rna_column : str
        Column with guide RNA identities
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure
    **kwargs
        Additional arguments

    Returns
    -------
    axes : matplotlib.axes.Axes or None
    """
    if guide_rna_column not in adata.obs.columns:
        raise ValueError(f"Guide RNA column '{guide_rna_column}' not found")

    fig, ax = plt.subplots(figsize=figsize)

    # Count cells per guide
    guide_counts = adata.obs[guide_rna_column].value_counts()

    guide_counts.plot(kind='bar', ax=ax, **kwargs)

    ax.set_xlabel("Guide RNA")
    ax.set_ylabel("Number of Cells")
    ax.set_title("Guide RNA Assignment Distribution")

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save}")

    return ax


def plot_perturbation_summary(
    adata,
    perturbation_col: str = "perturbation",
    embedding: str = "X_umap",
    figsize: Tuple[int, int] = (16, 12),
    save: Optional[str] = None,
    **kwargs
) -> Optional[Any]:
    """
    Create comprehensive perturbation summary plot.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    perturbation_col : str
        Column with perturbation labels
    embedding : str
        Embedding key
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure
    **kwargs
        Additional arguments

    Returns
    -------
    axes : list of matplotlib.axes.Axes or None
    """
    fig = plt.figure(figsize=figsize)

    # Create grid
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # Plot 1: Embedding colored by perturbation
    ax1 = fig.add_subplot(gs[0, :2])
    try:
        import scanpy as sc
        sc.pl.embedding(
            adata,
            basis=embedding.replace("X_", ""),
            color=perturbation_col,
            ax=ax1,
            show=False,
            legend_loc='on data'
        )
    except Exception as e:
        ax1.text(0.5, 0.5, f"Embedding plot failed: {e}", ha='center')

    # Plot 2: Cell counts per perturbation
    ax2 = fig.add_subplot(gs[0, 2])
    perturbation_counts = adata.obs[perturbation_col].value_counts()
    perturbation_counts.plot(kind='bar', ax=ax2)
    ax2.set_title("Cells per Perturbation")
    ax2.set_xlabel("Perturbation")
    ax2.set_ylabel("Cell Count")

    # Plot 3: Expression distribution (if layers exist)
    ax3 = fig.add_subplot(gs[1, :])
    if 'X_pert' in adata.layers:
        pert_data = adata.layers['X_pert']
        ax3.hist(pert_data.flatten(), bins=50, alpha=0.7)
        ax3.set_title("Perturbation Signature Distribution")
        ax3.set_xlabel("Expression Change")
        ax3.set_ylabel("Frequency")
    else:
        ax3.text(0.5, 0.5, "No perturbation signature found", ha='center')

    # Plot 4: Metadata
    ax4 = fig.add_subplot(gs[2, :])
    ax4.axis('off')

    info_text = f"""
    Perturbation Analysis Summary
    =============================
    Total Cells: {adata.n_obs}
    Total Genes: {adata.n_vars}
    Perturbations: {adata.obs[perturbation_col].nunique()}

    Perturbation Counts:
    {perturbation_counts.to_string()}
    """

    ax4.text(0.1, 0.5, info_text, family='monospace', fontsize=10, va='center')

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Figure saved to {save}")

    return fig.axes
