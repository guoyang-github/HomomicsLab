"""Visualization functions for COMPASS metabolic flux analysis.

This module provides plotting functions for exploring and presenting
COMPASS metabolic flux results.
"""

import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Rectangle
from typing import Optional, Union, List, Dict, Any, Tuple
from anndata import AnnData


def plot_reaction_heatmap(
    reaction_scores: pd.DataFrame,
    n_top: int = 50,
    cluster_cells: bool = True,
    cluster_reactions: bool = True,
    figsize: Tuple[int, int] = (12, 10),
    cmap: str = 'viridis',
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot heatmap of reaction scores.

    Args:
        reaction_scores: DataFrame with reaction scores (reactions x cells)
        n_top: Number of top reactions to show
        cluster_cells: Whether to cluster cells
        cluster_reactions: Whether to cluster reactions
        figsize: Figure size
        cmap: Colormap
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    # Select top reactions by variance
    if n_top < reaction_scores.shape[0]:
        var_scores = reaction_scores.var(axis=1).nlargest(n_top)
        plot_data = reaction_scores.loc[var_scores.index]
    else:
        plot_data = reaction_scores

    # Create clustermap
    g = sns.clustermap(
        plot_data,
        cmap=cmap,
        figsize=figsize,
        col_cluster=cluster_cells,
        row_cluster=cluster_reactions,
        xticklabels=False,
        yticklabels=True,
        dendrogram_ratio=0.2,
        cbar_pos=(0.02, 0.8, 0.03, 0.1)
    )

    g.fig.suptitle('COMPASS Reaction Scores', y=1.02, fontsize=14)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return g.fig


def plot_metabolite_scores(
    uptake_scores: pd.DataFrame,
    secretion_scores: Optional[pd.DataFrame] = None,
    n_top: int = 20,
    figsize: Tuple[int, int] = (14, 6),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot top metabolite uptake and secretion scores.

    Args:
        uptake_scores: DataFrame with uptake scores
        secretion_scores: Optional DataFrame with secretion scores
        n_top: Number of top metabolites to show
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    if secretion_scores is not None:
        fig, axes = plt.subplots(1, 2, figsize=figsize)
    else:
        fig, axes = plt.subplots(1, 1, figsize=(figsize[0]//2, figsize[1]))
        axes = [axes]

    # Plot uptake
    uptake_mean = uptake_scores.mean(axis=1).nlargest(n_top)
    axes[0].barh(range(len(uptake_mean)), uptake_mean.values)
    axes[0].set_yticks(range(len(uptake_mean)))
    axes[0].set_yticklabels(uptake_mean.index, fontsize=8)
    axes[0].set_xlabel('Mean Uptake Score')
    axes[0].set_title('Top Metabolite Uptake')
    axes[0].invert_yaxis()

    # Plot secretion
    if secretion_scores is not None:
        secretion_mean = secretion_scores.mean(axis=1).nlargest(n_top)
        axes[1].barh(range(len(secretion_mean)), secretion_mean.values)
        axes[1].set_yticks(range(len(secretion_mean)))
        axes[1].set_yticklabels(secretion_mean.index, fontsize=8)
        axes[1].set_xlabel('Mean Secretion Score')
        axes[1].set_title('Top Metabolite Secretion')
        axes[1].invert_yaxis()

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_reaction_distribution(
    reaction_scores: pd.DataFrame,
    reactions: Optional[List[str]] = None,
    groupby: Optional[pd.Series] = None,
    figsize: Tuple[int, int] = (12, 6),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot distribution of reaction scores.

    Args:
        reaction_scores: DataFrame with reaction scores
        reactions: List of reactions to plot (default: top 10 by variance)
        groupby: Optional grouping for stratified distributions
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    if reactions is None:
        reactions = reaction_scores.var(axis=1).nlargest(10).index.tolist()

    n_reactions = len(reactions)
    n_cols = min(5, n_reactions)
    n_rows = (n_reactions + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
    if n_reactions == 1:
        axes = [axes]
    else:
        axes = axes.flatten() if n_rows > 1 else axes

    for idx, reaction in enumerate(reactions):
        ax = axes[idx] if n_reactions > 1 else axes[0]

        if reaction not in reaction_scores.index:
            continue

        scores = reaction_scores.loc[reaction].dropna()

        if groupby is not None:
            for group in groupby.unique():
                group_scores = scores[groupby == group]
                ax.hist(group_scores, alpha=0.5, label=str(group), bins=20)
            ax.legend()
        else:
            ax.hist(scores, bins=30, alpha=0.7, edgecolor='black')

        ax.set_title(reaction, fontsize=9)
        ax.set_xlabel('Reaction Score')
        ax.set_ylabel('Frequency')

    # Hide unused subplots
    for idx in range(n_reactions, len(axes) if isinstance(axes, np.ndarray) else 1):
        if isinstance(axes, np.ndarray):
            axes[idx].axis('off')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_differential_flux(
    diff_results: pd.DataFrame,
    fdr_threshold: float = 0.05,
    log2fc_threshold: float = 1.0,
    top_n: int = 20,
    figsize: Tuple[int, int] = (10, 8),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot differential flux analysis results.

    Args:
        diff_results: DataFrame from analyze_differential_flux
        fdr_threshold: FDR threshold for significance
        log2fc_threshold: Log2 fold change threshold
        top_n: Number of top significant reactions to label
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    fig, axes = plt.subplots(2, 1, figsize=figsize)

    # Volcano plot
    diff_results['-log10_padj'] = -np.log10(diff_results['padj'] + 1e-300)

    significant = (diff_results['padj'] < fdr_threshold) & \
                  (abs(diff_results['log2FC']) > log2fc_threshold)

    axes[0].scatter(
        diff_results.loc[~significant, 'log2FC'],
        diff_results.loc[~significant, '-log10_padj'],
        alpha=0.5, c='gray', s=20
    )
    axes[0].scatter(
        diff_results.loc[significant, 'log2FC'],
        diff_results.loc[significant, '-log10_padj'],
        alpha=0.7, c='red', s=30
    )

    # Label top significant reactions
    top_sig = diff_results[significant].nsmallest(top_n, 'padj')
    for _, row in top_sig.iterrows():
        axes[0].annotate(
            row['reaction'],
            (row['log2FC'], row['-log10_padj']),
            fontsize=7,
            xytext=(5, 5), textcoords='offset points'
        )

    axes[0].axhline(-np.log10(fdr_threshold), linestyle='--', color='gray', alpha=0.5)
    axes[0].axvline(-log2fc_threshold, linestyle='--', color='gray', alpha=0.5)
    axes[0].axvline(log2fc_threshold, linestyle='--', color='gray', alpha=0.5)
    axes[0].set_xlabel('Log2 Fold Change')
    axes[0].set_ylabel('-Log10 FDR')
    axes[0].set_title('Differential Flux Analysis')

    # Bar plot of top reactions
    top_reactions = diff_results.nsmallest(top_n, 'padj')
    colors = ['red' if padj < fdr_threshold else 'gray' for padj in top_reactions['padj']]

    axes[1].barh(range(len(top_reactions)), top_reactions['log2FC'], color=colors, alpha=0.7)
    axes[1].set_yticks(range(len(top_reactions)))
    axes[1].set_yticklabels(top_reactions['reaction'], fontsize=8)
    axes[1].set_xlabel('Log2 Fold Change')
    axes[1].set_title(f'Top {top_n} Differential Reactions')
    axes[1].invert_yaxis()

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_subsystem_activity(
    reaction_scores: pd.DataFrame,
    subsystems: Dict[str, str],
    groupby: Optional[pd.Series] = None,
    figsize: Tuple[int, int] = (14, 8),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot metabolic subsystem activity.

    Args:
        reaction_scores: DataFrame with reaction scores
        subsystems: Dictionary mapping reactions to subsystems
        groupby: Optional grouping for comparison
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    # Map reactions to subsystems
    reaction_scores_copy = reaction_scores.copy()
    reaction_scores_copy['subsystem'] = reaction_scores_copy.index.map(subsystems)
    reaction_scores_copy = reaction_scores_copy.dropna(subset=['subsystem'])

    # Calculate mean scores per subsystem
    if groupby is not None:
        # Calculate by group
        subsystem_activity = {}
        for group in groupby.unique():
            group_cells = reaction_scores_copy.columns[reaction_scores_copy.columns.isin(
                reaction_scores_copy.columns[groupby == group]
            )]
            group_scores = reaction_scores_copy[group_cells.tolist() + ['subsystem']]
            group_means = group_scores.groupby('subsystem').mean().mean(axis=1)
            subsystem_activity[group] = group_means

        activity_df = pd.DataFrame(subsystem_activity)
    else:
        activity_df = reaction_scores_copy.groupby('subsystem').mean().mean(axis=1).to_frame('Activity')

    # Plot
    fig, ax = plt.subplots(figsize=figsize)

    if groupby is not None:
        activity_df.plot(kind='barh', ax=ax)
        ax.legend(title='Group', bbox_to_anchor=(1.05, 1), loc='upper left')
    else:
        activity_df.sort_values('Activity', ascending=True).plot(kind='barh', ax=ax, legend=False)

    ax.set_xlabel('Mean Reaction Score')
    ax.set_title('Metabolic Subsystem Activity')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_umap_with_metabolism(
    adata: AnnData,
    reaction_scores: pd.DataFrame,
    reactions: List[str],
    color_by: Optional[str] = None,
    figsize: Tuple[int, int] = (16, 4),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot UMAP with metabolic reaction scores overlay.

    Args:
        adata: AnnData with UMAP coordinates in obsm['X_umap']
        reaction_scores: DataFrame with reaction scores
        reactions: List of reactions to visualize
        color_by: Column in adata.obs for cell coloring
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    if 'X_umap' not in adata.obsm:
        raise ValueError("UMAP coordinates not found. Run sc.tl.umap first.")

    n_plots = len(reactions) + (1 if color_by else 0)
    fig, axes = plt.subplots(1, n_plots, figsize=figsize)
    if n_plots == 1:
        axes = [axes]

    plot_idx = 0

    # Plot cell type/color annotation
    if color_by:
        ax = axes[plot_idx]
        sc.pl.umap(adata, color=color_by, ax=ax, show=False)
        ax.set_title(f'Cell Types: {color_by}')
        plot_idx += 1

    # Plot reaction scores
    umap_coords = adata.obsm['X_umap']

    for reaction in reactions:
        if reaction not in reaction_scores.index:
            continue

        ax = axes[plot_idx]
        scores = reaction_scores.loc[reaction, adata.obs_names].values

        scatter = ax.scatter(
            umap_coords[:, 0], umap_coords[:, 1],
            c=scores, cmap='viridis', s=10, alpha=0.6
        )
        ax.set_title(f'{reaction}')
        plt.colorbar(scatter, ax=ax, label='Reaction Score')

        plot_idx += 1

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_sample_comparison(
    reaction_scores: pd.DataFrame,
    groupby: pd.Series,
    top_n: int = 20,
    figsize: Tuple[int, int] = (12, 8),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Compare reaction scores between samples/groups.

    Args:
        reaction_scores: DataFrame with reaction scores
        groupby: Group labels for each cell
        top_n: Number of top varying reactions to show
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    groups = groupby.unique()

    if len(groups) != 2:
        raise ValueError(f"Expected 2 groups, found {len(groups)}")

    # Calculate mean scores per group
    group_means = {}
    for group in groups:
        group_cells = reaction_scores.columns[groupby == group]
        group_means[group] = reaction_scores[group_cells].mean(axis=1)

    mean_df = pd.DataFrame(group_means)

    # Select top varying reactions
    mean_df['diff'] = abs(mean_df[groups[0]] - mean_df[groups[1]])
    top_reactions = mean_df.nlargest(top_n, 'diff')

    # Plot
    fig, ax = plt.subplots(figsize=figsize)

    x = np.arange(len(top_reactions))
    width = 0.35

    ax.bar(x - width/2, top_reactions[groups[0]], width, label=groups[0], alpha=0.8)
    ax.bar(x + width/2, top_reactions[groups[1]], width, label=groups[1], alpha=0.8)

    ax.set_xlabel('Reactions')
    ax.set_ylabel('Mean Reaction Score')
    ax.set_title(f'Top {top_n} Differential Reactions')
    ax.set_xticks(x)
    ax.set_xticklabels(top_reactions.index, rotation=45, ha='right', fontsize=8)
    ax.legend()

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_reaction_correlation(
    reaction_scores: pd.DataFrame,
    reactions: Optional[List[str]] = None,
    n_top: int = 30,
    figsize: Tuple[int, int] = (10, 8),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot correlation matrix of reaction scores.

    Args:
        reaction_scores: DataFrame with reaction scores
        reactions: Specific reactions to include (default: top by variance)
        n_top: Number of top reactions by variance
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    if reactions is None:
        var_scores = reaction_scores.var(axis=1).nlargest(n_top)
        plot_data = reaction_scores.loc[var_scores.index]
    else:
        plot_data = reaction_scores.loc[reaction_scores.index.intersection(reactions)]

    # Calculate correlation
    corr = plot_data.T.corr()

    # Plot
    fig, ax = plt.subplots(figsize=figsize)

    sns.heatmap(
        corr,
        cmap='RdBu_r',
        center=0,
        vmin=-1, vmax=1,
        square=True,
        xticklabels=True,
        yticklabels=True,
        ax=ax
    )

    ax.set_title('Reaction Score Correlations')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_compass_summary(
    reaction_scores: pd.DataFrame,
    uptake_scores: Optional[pd.DataFrame] = None,
    secretion_scores: Optional[pd.DataFrame] = None,
    output_dir: str = './compass_plots',
    prefix: str = ''
) -> Dict[str, str]:
    """Generate a comprehensive set of COMPASS visualization plots.

    Args:
        reaction_scores: DataFrame with reaction scores
        uptake_scores: Optional DataFrame with uptake scores
        secretion_scores: Optional DataFrame with secretion scores
        output_dir: Directory to save plots
        prefix: Prefix for plot filenames

    Returns:
        Dictionary mapping plot names to file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    plots = {}

    # Reaction heatmap
    fig = plot_reaction_heatmap(
        reaction_scores,
        n_top=50,
        save_path=os.path.join(output_dir, f'{prefix}reaction_heatmap.png')
    )
    plots['reaction_heatmap'] = os.path.join(output_dir, f'{prefix}reaction_heatmap.png')
    plt.close(fig)

    # Reaction distributions
    fig = plot_reaction_distribution(
        reaction_scores,
        n_top=10,
        save_path=os.path.join(output_dir, f'{prefix}reaction_distributions.png')
    )
    plots['reaction_distributions'] = os.path.join(output_dir, f'{prefix}reaction_distributions.png')
    plt.close(fig)

    # Metabolite scores
    if uptake_scores is not None:
        fig = plot_metabolite_scores(
            uptake_scores,
            secretion_scores,
            save_path=os.path.join(output_dir, f'{prefix}metabolite_scores.png')
        )
        plots['metabolite_scores'] = os.path.join(output_dir, f'{prefix}metabolite_scores.png')
        plt.close(fig)

    # Reaction correlation
    fig = plot_reaction_correlation(
        reaction_scores,
        n_top=30,
        save_path=os.path.join(output_dir, f'{prefix}reaction_correlation.png')
    )
    plots['reaction_correlation'] = os.path.join(output_dir, f'{prefix}reaction_correlation.png')
    plt.close(fig)

    return plots


def create_interactive_viz(
    reaction_scores: pd.DataFrame,
    adata: AnnData,
    output_file: str = 'compass_viz.html'
) -> str:
    """Create interactive visualization using Plotly.

    Args:
        reaction_scores: DataFrame with reaction scores
        adata: AnnData object (must have UMAP coordinates)
        output_file: Output HTML file

    Returns:
        Path to output file
    """
    try:
        import plotly.express as px
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        raise ImportError("Plotly not installed. Install with: pip install plotly")

    if 'X_umap' not in adata.obsm:
        raise ValueError("UMAP coordinates required. Run sc.tl.umap first.")

    # Create figure with subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('UMAP', 'Reaction Scores', 'Metabolite Uptake', 'Metabolite Secretion'),
        specs=[[{'type': 'scatter'}, {'type': 'heatmap'}],
               [{'type': 'bar'}, {'type': 'bar'}]]
    )

    # Add UMAP (placeholder for cell coloring)
    umap_coords = adata.obsm['X_umap']
    fig.add_trace(
        go.Scatter(
            x=umap_coords[:, 0],
            y=umap_coords[:, 1],
            mode='markers',
            marker=dict(size=3, opacity=0.6)
        ),
        row=1, col=1
    )

    # Add reaction heatmap
    top_reactions = reaction_scores.var(axis=1).nlargest(20)
    heatmap_data = reaction_scores.loc[top_reactions.index]
    fig.add_trace(
        go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale='Viridis'
        ),
        row=1, col=2
    )

    # Update layout
    fig.update_layout(
        height=800,
        title_text="COMPASS Metabolic Analysis Dashboard"
    )

    fig.write_html(output_file)

    return output_file
