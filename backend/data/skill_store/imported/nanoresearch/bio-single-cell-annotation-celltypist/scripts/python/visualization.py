"""Visualization functions for CellTypist annotation results.

This module provides plotting functions for visualizing CellTypist predictions,
confidence scores, and model comparisons.
"""

import numpy as np
import pandas as pd
import scanpy as sc
import matplotlib.pyplot as plt
import seaborn as sns
from anndata import AnnData
from typing import Optional, Union, List, Tuple
import celltypist


def _resolve_col(adata: AnnData, col: str, alternatives: List[str]) -> str:
    """Resolve a column name using fallbacks."""
    if col in adata.obs.columns:
        return col
    for alt in alternatives:
        if alt in adata.obs.columns:
            return alt
    raise KeyError(f"Column '{col}' (or alternatives {alternatives}) not found in adata.obs")


def plot_celltypist_dotplot(
    predictions: celltypist.classifier.AnnotationResult,
    use_as_reference: str = 'leiden',
    use_as_prediction: str = 'majority_voting',
    cmap: str = 'RdBu_r',
    title: str = 'CellTypist Annotation',
    figsize: Optional[Tuple[int, int]] = None,
    save: Optional[str] = None
) -> None:
    """Create dot plot comparing CellTypist predictions to reference labels.

    Args:
        predictions: AnnotationResult from CellTypist
        use_as_reference: Column in adata.obs to use as reference (e.g., 'leiden')
        use_as_prediction: Prediction column ('majority_voting' or 'predicted_labels')
        cmap: Colormap for probability scores
        title: Plot title
        figsize: Figure size
        save: Path to save figure
    """
    try:
        celltypist.plot.dotplot(
            predictions,
            use_as_reference=use_as_reference,
            use_as_prediction=use_as_prediction,
            cmap=cmap,
            title=title,
            figsize=figsize,
            save=save
        )
    except AttributeError as e:
        print(f"Error creating dotplot: {e}")
        if not hasattr(predictions, 'adata'):
            print("  Hint: predictions object must contain an 'adata' attribute. "
                  "Ensure predictions were generated from an AnnData input, not a file path.")
    except Exception as e:
        print(f"Error creating dotplot: {e}")


def plot_confidence_distribution(
    adata: AnnData,
    conf_col: str = 'celltypist_conf_score',
    label_col: str = 'celltypist_label',
    figsize: Tuple[int, int] = (10, 6),
    save: Optional[str] = None
) -> None:
    """Plot distribution of confidence scores.

    Args:
        adata: AnnData with CellTypist predictions
        conf_col: Column with confidence scores
        label_col: Column with predicted labels
        figsize: Figure size
        save: Path to save figure
    """
    conf_col = _resolve_col(adata, conf_col, ['conf_score', 'celltypist_conf_score'])
    label_col = _resolve_col(adata, label_col, ['celltypist_label', 'majority_voting', 'predicted_labels'])

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Overall distribution
    axes[0].hist(adata.obs[conf_col], bins=50, color='steelblue', edgecolor='white')
    axes[0].axvline(0.5, color='red', linestyle='--', label='Threshold (0.5)')
    axes[0].set_xlabel('Confidence Score')
    axes[0].set_ylabel('Count')
    axes[0].set_title('Confidence Score Distribution')
    axes[0].legend()

    # By cell type (top 10)
    cell_counts = adata.obs[label_col].value_counts().head(10).index
    subset = adata[adata.obs[label_col].isin(cell_counts)]

    sns.boxplot(data=subset.obs, x=label_col, y=conf_col, ax=axes[1])
    axes[1].axhline(0.5, color='red', linestyle='--')
    axes[1].set_xticklabels(axes[1].get_xticklabels(), rotation=45, ha='right')
    axes[1].set_xlabel('Cell Type')
    axes[1].set_ylabel('Confidence Score')
    axes[1].set_title('Confidence by Cell Type (Top 10)')

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Saved: {save}")

    plt.show()


def plot_celltype_proportions(
    adata: AnnData,
    label_col: str = 'celltypist_label',
    groupby: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6),
    save: Optional[str] = None
) -> None:
    """Plot cell type proportions.

    Args:
        adata: AnnData with CellTypist predictions
        label_col: Column with predicted labels
        groupby: Optional grouping variable
        figsize: Figure size
        save: Path to save figure
    """
    label_col = _resolve_col(adata, label_col, ['celltypist_label', 'majority_voting', 'predicted_labels'])

    if groupby is None:
        # Simple bar plot
        proportions = adata.obs[label_col].value_counts(normalize=True)

        fig, ax = plt.subplots(figsize=figsize)
        proportions.plot(kind='bar', ax=ax, color='steelblue')
        ax.set_xlabel('Cell Type')
        ax.set_ylabel('Proportion')
        ax.set_title('Cell Type Proportions')
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    else:
        # Grouped bar plot
        props = adata.obs.groupby([groupby, label_col]).size().unstack(fill_value=0)
        props = props.div(props.sum(axis=1), axis=0)

        fig, ax = plt.subplots(figsize=figsize)
        props.plot(kind='bar', stacked=True, ax=ax, colormap='tab20')
        ax.set_xlabel(groupby)
        ax.set_ylabel('Proportion')
        ax.set_title(f'Cell Type Proportions by {groupby}')
        ax.legend(title='Cell Type', bbox_to_anchor=(1.05, 1), loc='upper left')
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Saved: {save}")

    plt.show()


def plot_umap_with_predictions(
    adata: AnnData,
    label_col: str = 'celltypist_label',
    conf_col: str = 'celltypist_conf_score',
    use_raw: bool = False,
    legend_loc: str = 'on data',
    figsize: Tuple[int, int] = (16, 6),
    save: Optional[str] = None
) -> None:
    """Plot UMAP with CellTypist predictions and confidence scores.

    Args:
        adata: AnnData with UMAP and CellTypist predictions
        label_col: Column with predicted labels
        conf_col: Column with confidence scores
        use_raw: Whether to use raw data for plotting
        legend_loc: Legend location ('on data' or 'right margin')
        figsize: Figure size
        save: Path to save figure
    """
    label_col = _resolve_col(adata, label_col, ['celltypist_label', 'majority_voting', 'predicted_labels'])
    conf_col = _resolve_col(adata, conf_col, ['conf_score', 'celltypist_conf_score'])

    if 'X_umap' not in adata.obsm:
        print("UMAP not found in adata.obsm['X_umap']. Running UMAP first...")
        if 'X_pca' not in adata.obsm:
            if 'highly_variable' not in adata.var.columns:
                sc.pp.highly_variable_genes(adata, n_top_genes=2000)
            sc.pp.pca(adata, use_highly_variable=True)
        if 'neighbors' not in adata.uns:
            sc.pp.neighbors(adata)
        sc.tl.umap(adata)

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Predicted labels
    sc.pl.umap(adata, color=label_col, ax=axes[0], show=False,
               legend_loc=legend_loc, title='CellTypist Predictions')

    # Confidence scores
    sc.pl.umap(adata, color=conf_col, ax=axes[1], show=False,
               title='Confidence Scores', cmap='viridis')

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Saved: {save}")

    plt.show()


def plot_prediction_heatmap(
    adata: AnnData,
    label_col: str = 'celltypist_label',
    cluster_col: str = 'leiden',
    cmap: str = 'Blues',
    figsize: Tuple[int, int] = (12, 10),
    save: Optional[str] = None
) -> None:
    """Plot heatmap of predicted labels vs clusters.

    Args:
        adata: AnnData with predictions and cluster labels
        label_col: Column with predicted labels
        cluster_col: Column with cluster assignments
        cmap: Colormap
        figsize: Figure size
        save: Path to save figure
    """
    label_col = _resolve_col(adata, label_col, ['celltypist_label', 'majority_voting', 'predicted_labels'])

    if cluster_col not in adata.obs.columns:
        raise ValueError(f"Cluster column '{cluster_col}' not found in adata.obs")

    # Create confusion matrix
    confusion = pd.crosstab(adata.obs[cluster_col], adata.obs[label_col])

    # Normalize by cluster
    confusion_norm = confusion.div(confusion.sum(axis=1), axis=0)

    # Plot
    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(confusion_norm, cmap=cmap, annot=False, ax=ax, cbar_kws={'label': 'Proportion'})
    ax.set_xlabel('CellTypist Prediction')
    ax.set_ylabel(f'{cluster_col} Cluster')
    ax.set_title('Cell Type Predictions by Cluster')

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Saved: {save}")

    plt.show()


def plot_model_comparison(
    results_df: pd.DataFrame,
    figsize: Tuple[int, int] = (10, 6),
    save: Optional[str] = None
) -> None:
    """Plot comparison of multiple CellTypist models.

    Args:
        results_df: DataFrame from compare_models
        figsize: Figure size
        save: Path to save figure
    """
    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Number of cell types detected
    axes[0].bar(results_df['model'], results_df['n_cell_types'], color='steelblue')
    axes[0].set_xlabel('Model')
    axes[0].set_ylabel('Number of Cell Types')
    axes[0].set_title('Cell Types Detected by Model')
    axes[0].set_xticklabels(results_df['model'], rotation=45, ha='right')

    # Agreement between models (if multiple models)
    if len(results_df) > 1:
        axes[1].text(0.5, 0.5, f"Models compared: {len(results_df)}",
                    ha='center', va='center', fontsize=12)
        axes[1].set_title('Model Comparison')
        axes[1].axis('off')

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Saved: {save}")

    plt.show()


def plot_top_celltypes(
    adata: AnnData,
    label_col: str = 'celltypist_label',
    top_n: int = 10,
    figsize: Tuple[int, int] = (10, 6),
    save: Optional[str] = None
) -> None:
    """Plot top N most frequent cell types.

    Args:
        adata: AnnData with CellTypist predictions
        label_col: Column with predicted labels
        top_n: Number of top cell types to show
        figsize: Figure size
        save: Path to save figure
    """
    label_col = _resolve_col(adata, label_col, ['celltypist_label', 'majority_voting', 'predicted_labels'])

    cell_counts = adata.obs[label_col].value_counts().head(top_n)

    fig, ax = plt.subplots(figsize=figsize)
    cell_counts.plot(kind='barh', ax=ax, color='steelblue')
    ax.set_xlabel('Count')
    ax.set_ylabel('Cell Type')
    ax.set_title(f'Top {top_n} Cell Types')

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches='tight')
        print(f"Saved: {save}")

    plt.show()


def plot_annotation_summary(
    adata: AnnData,
    label_col: str = 'celltypist_label',
    conf_col: str = 'celltypist_conf_score',
    output_dir: Optional[str] = None
) -> None:
    """Create a comprehensive summary plot of CellTypist annotations.

    Args:
        adata: AnnData with CellTypist predictions
        label_col: Column with predicted labels
        conf_col: Column with confidence scores
        output_dir: Directory to save plots
    """
    fig = plt.figure(figsize=(16, 12))

    label_col = _resolve_col(adata, label_col, ['celltypist_label', 'majority_voting', 'predicted_labels'])
    conf_col = _resolve_col(adata, conf_col, ['conf_score', 'celltypist_conf_score'])

    # 1. Cell type counts
    ax1 = plt.subplot(2, 3, 1)
    cell_counts = adata.obs[label_col].value_counts()
    cell_counts.plot(kind='bar', ax=ax1, color='steelblue')
    ax1.set_title('Cell Type Counts')
    ax1.set_xticklabels(ax1.get_xticklabels(), rotation=45, ha='right')

    # 2. Confidence distribution
    ax2 = plt.subplot(2, 3, 2)
    ax2.hist(adata.obs[conf_col], bins=50, color='steelblue', edgecolor='white')
    ax2.axvline(0.5, color='red', linestyle='--', label='Threshold')
    ax2.set_title('Confidence Distribution')
    ax2.set_xlabel('Confidence Score')
    ax2.legend()

    # 3. Top cell types
    ax3 = plt.subplot(2, 3, 3)
    top10 = cell_counts.head(10)
    top10.plot(kind='barh', ax=ax3, color='steelblue')
    ax3.set_title('Top 10 Cell Types')

    # 4. Confidence by cell type (top 5)
    ax4 = plt.subplot(2, 3, 4)
    top5_types = cell_counts.head(5).index
    subset = adata[adata.obs[label_col].isin(top5_types)]
    sns.boxplot(data=subset.obs, x=label_col, y=conf_col, ax=ax4)
    ax4.set_xticklabels(ax4.get_xticklabels(), rotation=45, ha='right')
    ax4.set_title('Confidence by Cell Type (Top 5)')

    # 5. Confidence categories
    ax5 = plt.subplot(2, 3, 5)
    conf_categories = pd.cut(adata.obs[conf_col], bins=[0, 0.3, 0.5, 0.7, 1.0],
                            labels=['Low (<0.3)', 'Medium (0.3-0.5)', 'High (0.5-0.7)', 'Very High (>0.7)'])
    conf_categories.value_counts().plot(kind='bar', ax=ax5, color='steelblue')
    ax5.set_title('Confidence Categories')
    ax5.set_xticklabels(ax5.get_xticklabels(), rotation=45, ha='right')

    # 6. Summary statistics
    ax6 = plt.subplot(2, 3, 6)
    ax6.axis('off')
    stats_text = f"""
Annotation Summary
=================
Total cells: {adata.n_obs}
Cell types: {len(cell_counts)}
Mean confidence: {adata.obs[conf_col].mean():.3f}
Median confidence: {adata.obs[conf_col].median():.3f}
High confidence (>0.5): {(adata.obs[conf_col] > 0.5).sum()} ({(adata.obs[conf_col] > 0.5).mean()*100:.1f}%)
"""
    ax6.text(0.1, 0.5, stats_text, fontsize=10, verticalalignment='center',
             family='monospace')

    plt.tight_layout()

    if output_dir:
        import os
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, 'celltypist_summary.png')
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved: {save_path}")

    plt.show()
