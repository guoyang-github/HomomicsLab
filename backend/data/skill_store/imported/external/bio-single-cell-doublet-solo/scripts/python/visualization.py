"""
Visualization Functions for SOLO Doublet Detection

This module provides wrapper functions for:
- Histograms of doublet scores
- UMAP/t-SNE plots colored by doublet predictions
- Violin plots comparing doublet scores
- Training history plots

Author: Yang Guo
Date: 2026-04-03
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Optional, List, Tuple, Union
import scanpy as sc

#==============================================================================
# Score Distribution Plots
#==============================================================================

def plot_doublet_score_distribution(
    predictions: pd.DataFrame,
    threshold: float = 0.5,
    bins: int = 50,
    figsize: Tuple[float, float] = (10, 6),
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    **kwargs
):
    """
    Plot histogram of doublet scores.

    Parameters
    ----------
    predictions : pd.DataFrame
        SOLO predictions DataFrame with 'doublet' column
    threshold : float, default=0.5
        Threshold for calling doublets
    bins : int, default=50
        Number of histogram bins
    figsize : Tuple[float, float], default=(10, 6)
        Figure size
    title : Optional[str], default=None
        Plot title
    save_path : Optional[str], default=None
        Path to save figure
    **kwargs
        Additional arguments for matplotlib
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Plot histogram
    ax.hist(predictions['doublet'], bins=bins, alpha=0.7,
            color='steelblue', edgecolor='black', **kwargs)

    # Add threshold line
    ax.axvline(threshold, color='red', linestyle='--', linewidth=2,
               label=f'Threshold = {threshold}')

    # Add statistics
    mean_score = predictions['doublet'].mean()
    ax.axvline(mean_score, color='green', linestyle=':', linewidth=2,
               label=f'Mean = {mean_score:.3f}')

    ax.set_xlabel('Doublet Score', fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title(title or 'Distribution of Doublet Scores')
    ax.legend()

    # Add summary text
    n_doublets = (predictions['doublet'] > threshold).sum()
    doublet_rate = n_doublets / len(predictions) * 100
    ax.text(0.95, 0.95, f'Doublet rate: {doublet_rate:.1f}%\n({n_doublets} / {len(predictions)} cells)',
            transform=ax.transAxes, ha='right', va='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved to {save_path}")

    plt.show()


def plot_doublet_score_boxplot(
    predictions: pd.DataFrame,
    groupby: str,
    figsize: Tuple[float, float] = (10, 6),
    title: Optional[str] = None,
    save_path: Optional[str] = None
):
    """
    Create box plot of doublet scores grouped by category.

    Parameters
    ----------
    predictions : pd.DataFrame
        SOLO predictions
    groupby : str
        Column to group by
    figsize : Tuple[float, float], default=(10, 6)
        Figure size
    title : Optional[str], default=None
        Plot title
    save_path : Optional[str], default=None
        Save path
    """
    fig, ax = plt.subplots(figsize=figsize)

    data = predictions[[groupby, 'doublet']].copy()

    sns.boxplot(data=data, x=groupby, y='doublet', ax=ax)
    ax.axhline(0.5, color='red', linestyle='--', label='Threshold')

    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    ax.set_xlabel(groupby, fontsize=12)
    ax.set_ylabel('Doublet Score', fontsize=12)
    ax.set_title(title or f'Doublet Scores by {groupby}')
    ax.legend()

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()


#==============================================================================
# Embedding Plots
#==============================================================================

def plot_doublets_on_embedding(
    adata: sc.AnnData,
    doublet_key: str = 'solo_prediction',
    score_key: str = 'solo_doublet_score',
    basis: str = 'umap',
    figsize: Tuple[float, float] = (14, 5),
    palette: Optional[dict] = None,
    title: Optional[str] = None,
    save_path: Optional[str] = None
):
    """
    Plot doublet predictions on UMAP/t-SNE embedding.

    Parameters
    ----------
    adata : sc.AnnData
        Data with computed embedding
    doublet_key : str, default='solo_prediction'
        Key in adata.obs with doublet predictions
    score_key : str, default='solo_doublet_score'
        Key in adata.obs with doublet scores
    basis : str, default='umap'
        Embedding to use ('umap', 'tsne', 'pca')
    figsize : Tuple[float, float], default=(14, 5)
        Figure size
    palette : Optional[dict], default=None
        Custom color palette
    title : Optional[str], default=None
        Plot title
    save_path : Optional[str], default=None
        Save path
    """
    if f'X_{basis}' not in adata.obsm:
        raise ValueError(f"Embedding '{basis}' not found. Run sc.tl.umap() first.")

    if palette is None:
        palette = {'singlet': 'blue', 'doublet': 'red'}

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Plot 1: Binary doublet calls
    ax = axes[0]
    sc.pl.embedding(
        adata,
        basis=basis,
        color=doublet_key,
        palette=palette,
        ax=ax,
        show=False,
        legend_loc='right margin'
    )
    ax.set_title('Doublet Prediction')

    # Plot 2: Continuous scores
    ax = axes[1]
    sc.pl.embedding(
        adata,
        basis=basis,
        color=score_key,
        cmap='RdYlBu_r',
        ax=ax,
        show=False,
        vmin=0,
        vmax=1
    )
    ax.set_title('Doublet Score')

    if title:
        fig.suptitle(title, fontsize=14, y=1.02)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()


def plot_doublet_score_on_embedding(
    adata: sc.AnnData,
    score_key: str = 'solo_doublet_score',
    basis: str = 'umap',
    figsize: Tuple[float, float] = (8, 6),
    cmap: str = 'RdYlBu_r',
    title: Optional[str] = None,
    save_path: Optional[str] = None
):
    """
    Plot doublet scores on embedding with colorbar.

    Parameters
    ----------
    adata : sc.AnnData
        Data object
    score_key : str, default='solo_doublet_score'
        Key for doublet scores
    basis : str, default='umap'
        Embedding basis
    figsize : Tuple[float, float], default=(8, 6)
        Figure size
    cmap : str, default='RdYlBu_r'
        Colormap
    title : Optional[str], default=None
        Title
    save_path : Optional[str], default=None
        Save path
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Get coordinates
    coords = adata.obsm[f'X_{basis}']

    # Get scores
    scores = adata.obs[score_key].values

    # Plot
    scatter = ax.scatter(coords[:, 0], coords[:, 1], c=scores, cmap=cmap,
                        s=20, alpha=0.6, edgecolors='none')

    ax.set_xlabel(f'{basis.upper()} 1')
    ax.set_ylabel(f'{basis.upper()} 2')
    ax.set_title(title or 'Doublet Score')

    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Doublet Score')

    # Add threshold line to colorbar
    cbar.ax.axhline(0.5, color='black', linestyle='--', linewidth=2)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()


#==============================================================================
# Training History Plots
#==============================================================================

def plot_training_history(
    model,
    figsize: Tuple[float, float] = (12, 4),
    title: Optional[str] = None,
    save_path: Optional[str] = None
):
    """
    Plot training history (loss curves).

    Parameters
    ----------
    model
        Trained scVI or SOLO model with history attribute
    figsize : Tuple[float, float], default=(12, 4)
        Figure size
    title : Optional[str], default=None
        Title
    save_path : Optional[str], default=None
        Save path
    """
    if not hasattr(model, 'history'):
        raise ValueError("Model does not have history attribute")

    history = model.history
    keys = list(history.keys())

    if len(keys) == 0:
        raise ValueError("History is empty")

    n_plots = len(keys)
    fig, axes = plt.subplots(1, n_plots, figsize=figsize)

    if n_plots == 1:
        axes = [axes]

    for ax, key in zip(axes, keys):
        data = history[key]

        # Handle different history formats
        if hasattr(data, 'values'):
            values = data.values.flatten()
        else:
            values = np.array(data).flatten()

        ax.plot(values, linewidth=2)
        ax.set_xlabel('Epoch', fontsize=10)
        ax.set_ylabel(key, fontsize=10)
        ax.set_title(key)
        ax.grid(True, alpha=0.3)

    if title:
        fig.suptitle(title, fontsize=12)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()


#==============================================================================
# Comparative Plots
#==============================================================================

def compare_doublet_methods(
    adata: sc.AnnData,
    method_keys: List[str],
    basis: str = 'umap',
    figsize: Tuple[float, float] = (16, 4),
    save_path: Optional[str] = None
):
    """
    Compare predictions from multiple doublet detection methods.

    Parameters
    ----------
    adata : sc.AnnData
        Data with predictions from multiple methods
    method_keys : List[str]
        Keys in adata.obs for each method's predictions
    basis : str, default='umap'
        Embedding basis
    figsize : Tuple[float, float], default=(16, 4)
        Figure size
    save_path : Optional[str], default=None
        Save path
    """
    n_methods = len(method_keys)
    fig, axes = plt.subplots(1, n_methods, figsize=figsize)

    if n_methods == 1:
        axes = [axes]

    palette = {'singlet': 'blue', 'doublet': 'red'}

    for ax, key in zip(axes, method_keys):
        sc.pl.embedding(
            adata,
            basis=basis,
            color=key,
            palette=palette,
            ax=ax,
            show=False,
            title=key,
            legend_loc='on data'
        )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()


def plot_agreement_heatmap(
    predictions_df: pd.DataFrame,
    method_columns: List[str],
    figsize: Tuple[float, float] = (8, 6),
    save_path: Optional[str] = None
):
    """
    Plot agreement between multiple doublet detection methods.

    Parameters
    ----------
    predictions_df : pd.DataFrame
        DataFrame with predictions from multiple methods
    method_columns : List[str]
        Column names for each method
    figsize : Tuple[float, float], default=(8, 6)
        Figure size
    save_path : Optional[str], default=None
        Save path
    """
    # Convert to binary (1 = doublet, 0 = singlet)
    binary_preds = predictions_df[method_columns].copy()
    for col in method_columns:
        if binary_preds[col].dtype == object:
            binary_preds[col] = (binary_preds[col] == 'doublet').astype(int)
        else:
            binary_preds[col] = (binary_preds[col] > 0.5).astype(int)

    # Calculate agreement matrix
    agreement = np.zeros((len(method_columns), len(method_columns)))
    for i, method1 in enumerate(method_columns):
        for j, method2 in enumerate(method_columns):
            agreement[i, j] = (binary_preds[method1] == binary_preds[method2]).mean()

    # Plot
    fig, ax = plt.subplots(figsize=figsize)

    sns.heatmap(agreement, annot=True, fmt='.2f', cmap='Blues',
                xticklabels=method_columns, yticklabels=method_columns,
                vmin=0, vmax=1, ax=ax)

    ax.set_title('Agreement Between Doublet Detection Methods')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()


#==============================================================================
# Summary Plots
#==============================================================================

def plot_doublet_summary(
    predictions: pd.DataFrame,
    threshold: float = 0.5,
    figsize: Tuple[float, float] = (14, 10),
    title: Optional[str] = None,
    save_path: Optional[str] = None
):
    """
    Create a comprehensive summary figure with multiple plots.

    Parameters
    ----------
    predictions : pd.DataFrame
        SOLO predictions
    threshold : float, default=0.5
        Doublet threshold
    figsize : Tuple[float, float], default=(14, 10)
        Figure size
    title : Optional[str], default=None
        Title
    save_path : Optional[str], default=None
        Save path
    """
    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(3, 3)

    # 1. Score distribution (large, top)
    ax1 = fig.add_subplot(gs[0, :])
    ax1.hist(predictions['doublet'], bins=50, alpha=0.7, color='steelblue', edgecolor='black')
    ax1.axvline(threshold, color='red', linestyle='--', linewidth=2, label=f'Threshold = {threshold}')
    ax1.set_xlabel('Doublet Score')
    ax1.set_ylabel('Count')
    ax1.set_title('Distribution of Doublet Scores')
    ax1.legend()

    # Calculate statistics
    n_doublets = (predictions['doublet'] > threshold).sum()
    doublet_rate = n_doublets / len(predictions) * 100

    # 2. Pie chart
    ax2 = fig.add_subplot(gs[1, 0])
    labels = ['Singlets', 'Doublets']
    sizes = [len(predictions) - n_doublets, n_doublets]
    colors = ['steelblue', 'coral']
    ax2.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    ax2.set_title('Doublet Rate')

    # 3. Box plot
    ax3 = fig.add_subplot(gs[1, 1])
    singlet_scores = predictions[predictions['doublet'] <= threshold]['doublet']
    doublet_scores = predictions[predictions['doublet'] > threshold]['doublet']
    ax3.boxplot([singlet_scores, doublet_scores], labels=['Singlets', 'Doublets'])
    ax3.set_ylabel('Doublet Score')
    ax3.set_title('Score Distribution by Class')

    # 4. Cumulative distribution
    ax4 = fig.add_subplot(gs[1, 2])
    sorted_scores = np.sort(predictions['doublet'])
    cumulative = np.arange(1, len(sorted_scores) + 1) / len(sorted_scores) * 100
    ax4.plot(sorted_scores, cumulative, linewidth=2)
    ax4.axvline(threshold, color='red', linestyle='--')
    ax4.set_xlabel('Doublet Score')
    ax4.set_ylabel('Cumulative %')
    ax4.set_title('Cumulative Distribution')
    ax4.grid(True, alpha=0.3)

    # 5. Statistics table
    ax5 = fig.add_subplot(gs[2, :])
    ax5.axis('off')

    stats = {
        'Total Cells': len(predictions),
        'Predicted Doublets': int(n_doublets),
        'Doublet Rate (%)': f'{doublet_rate:.2f}',
        'Mean Score': f'{predictions["doublet"].mean():.4f}',
        'Median Score': f'{predictions["doublet"].median():.4f}',
        'Min Score': f'{predictions["doublet"].min():.4f}',
        'Max Score': f'{predictions["doublet"].max():.4f}',
        'Std Score': f'{predictions["doublet"].std():.4f}'
    }

    table_data = [[k, v] for k, v in stats.items()]
    table = ax5.table(cellText=table_data, loc='center', cellLoc='left',
                      colWidths=[0.3, 0.2])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    ax5.set_title('Summary Statistics', pad=20)

    if title:
        fig.suptitle(title, fontsize=14, y=0.98)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()


def plot_batch_comparison(
    batch_results: dict,
    figsize: Tuple[float, float] = (12, 6),
    save_path: Optional[str] = None
):
    """
    Compare doublet detection results across batches.

    Parameters
    ----------
    batch_results : dict
        Dictionary mapping batch names to prediction DataFrames
    figsize : Tuple[float, float], default=(12, 6)
        Figure size
    save_path : Optional[str], default=None
        Save path
    """
    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Plot 1: Doublet rates by batch
    ax = axes[0]
    batches = []
    rates = []
    counts = []

    for batch, preds in batch_results.items():
        if preds is not None:
            n_doublets = (preds['doublet'] > 0.5).sum()
            rate = n_doublets / len(preds) * 100
            batches.append(batch)
            rates.append(rate)
            counts.append(len(preds))

    bars = ax.bar(batches, rates, color='steelblue', alpha=0.7)
    ax.set_xlabel('Batch')
    ax.set_ylabel('Doublet Rate (%)')
    ax.set_title('Doublet Rate by Batch')
    ax.set_ylim(0, max(rates) * 1.2)

    # Add count labels
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'n={count}',
                ha='center', va='bottom', fontsize=9)

    # Plot 2: Score distributions
    ax = axes[1]
    for batch, preds in batch_results.items():
        if preds is not None:
            ax.hist(preds['doublet'], bins=30, alpha=0.5, label=batch, density=True)

    ax.axvline(0.5, color='red', linestyle='--', label='Threshold')
    ax.set_xlabel('Doublet Score')
    ax.set_ylabel('Density')
    ax.set_title('Score Distribution by Batch')
    ax.legend()

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.show()
