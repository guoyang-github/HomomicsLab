"""Visualization functions for FastCCC cell-cell communication analysis.

This module provides plotting functions for exploring and presenting
FastCCC cell-cell communication results.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Rectangle, Circle
from typing import Optional, Union, List, Dict, Any, Tuple
from anndata import AnnData


def plot_interaction_heatmap(
    pvals: pd.DataFrame,
    interactions_strength: Optional[pd.DataFrame] = None,
    pval_threshold: float = 0.05,
    use_strength: bool = True,
    figsize: Tuple[int, int] = (12, 10),
    cmap: str = 'viridis',
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot heatmap of cell-cell communication interactions.

    Args:
        pvals: DataFrame with p-values (cell_pairs x interactions)
        interactions_strength: Optional DataFrame with interaction strengths
        pval_threshold: P-value threshold for significance
        use_strength: Whether to use strength values instead of -log10(pval)
        figsize: Figure size
        cmap: Colormap
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    if use_strength and interactions_strength is not None:
        # Use interaction strength for significant interactions
        plot_data = interactions_strength.copy()
        plot_data[pvals >= pval_threshold] = 0  # Mask non-significant
        title = 'Interaction Strength (Significant Only)'
        cbar_label = 'Interaction Strength'
    else:
        # Use -log10(p-value)
        plot_data = -np.log10(pvals + 1e-300)
        title = '-log10(p-value)'
        cbar_label = '-log10(p-value)'

    # Sum across interactions for each cell pair
    plot_data_sum = plot_data.sum(axis=1).to_frame('score')

    # Parse cell pairs to create matrix
    cell_types = sorted(set([pair.split('|')[0] for pair in plot_data.index] +
                            [pair.split('|')[1] for pair in plot_data.index]))

    matrix = pd.DataFrame(0, index=cell_types, columns=cell_types)

    for cell_pair, row in plot_data_sum.iterrows():
        source, target = cell_pair.split('|')
        if source in matrix.index and target in matrix.columns:
            matrix.loc[source, target] = row['score']

    # Plot
    fig, ax = plt.subplots(figsize=figsize)

    sns.heatmap(matrix, cmap=cmap, annot=False, fmt='.2f',
                square=True, linewidths=0.5, cbar_kws={'label': cbar_label},
                ax=ax)

    ax.set_title(title, fontsize=14)
    ax.set_xlabel('Target Cell Type', fontsize=12)
    ax.set_ylabel('Source Cell Type', fontsize=12)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_significant_interactions_bar(
    pvals: pd.DataFrame,
    pval_threshold: float = 0.05,
    top_n: int = 20,
    figsize: Tuple[int, int] = (10, 8),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot bar chart of cell pairs with most significant interactions.

    Args:
        pvals: DataFrame with p-values
        pval_threshold: P-value threshold
        top_n: Number of top cell pairs to show
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    # Count significant interactions per cell pair
    sig_counts = (pvals < pval_threshold).sum(axis=1).sort_values(ascending=False)

    # Select top N
    top_pairs = sig_counts.head(top_n)

    # Plot
    fig, ax = plt.subplots(figsize=figsize)

    colors = plt.cm.viridis(np.linspace(0, 1, len(top_pairs)))
    top_pairs.plot(kind='barh', ax=ax, color=colors)

    ax.set_xlabel('Number of Significant Interactions', fontsize=12)
    ax.set_ylabel('Cell Type Pair', fontsize=12)
    ax.set_title(f'Top {top_n} Cell Pairs by Significant Interactions', fontsize=14)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_interaction_network(
    node_df: pd.DataFrame,
    edge_df: pd.DataFrame,
    layout: str = 'spring',
    figsize: Tuple[int, int] = (10, 10),
    node_color: str = 'lightblue',
    edge_color: str = 'gray',
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot cell-cell communication network.

    Args:
        node_df: DataFrame with node information (must have 'id' column)
        edge_df: DataFrame with edge information (must have 'source', 'target', 'weight')
        layout: Network layout ('spring', 'circular', 'random')
        figsize: Figure size
        node_color: Color for nodes
        edge_color: Color for edges
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    try:
        import networkx as nx
    except ImportError:
        raise ImportError("networkx not installed. Install with: pip install networkx")

    # Create graph
    G = nx.DiGraph()

    # Add nodes
    for _, node in node_df.iterrows():
        G.add_node(node['id'], **node.to_dict())

    # Add edges
    for _, edge in edge_df.iterrows():
        G.add_edge(edge['source'], edge['target'], weight=edge.get('weight', 1))

    # Layout
    if layout == 'spring':
        pos = nx.spring_layout(G, k=1, iterations=50)
    elif layout == 'circular':
        pos = nx.circular_layout(G)
    elif layout == 'random':
        pos = nx.random_layout(G)
    else:
        pos = nx.spring_layout(G)

    # Plot
    fig, ax = plt.subplots(figsize=figsize)

    # Draw edges
    edge_weights = [G[u][v].get('weight', 1) for u, v in G.edges()]
    if edge_weights:
        max_weight = max(edge_weights)
        edge_widths = [2 * w / max_weight for w in edge_weights]
    else:
        edge_widths = 1

    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_color,
                           width=edge_widths, alpha=0.6,
                           arrows=True, arrowsize=20,
                           connectionstyle='arc3,rad=0.1')

    # Draw nodes
    node_sizes = []
    for node in G.nodes():
        # Calculate node size based on total connections
        out_weight = sum([G[node][v].get('weight', 1) for v in G.successors(node)])
        in_weight = sum([G[u][node].get('weight', 1) for u in G.predecessors(node)])
        node_sizes.append(300 + (out_weight + in_weight) * 50)

    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_color,
                           node_size=node_sizes, alpha=0.9,
                           edgecolors='black', linewidths=2)

    # Draw labels
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=10, font_weight='bold')

    ax.set_title('Cell-Cell Communication Network', fontsize=14)
    ax.axis('off')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_top_interactions_dot(
    pvals: pd.DataFrame,
    interactions_strength: pd.DataFrame,
    database_file_path: Optional[str] = None,
    top_n: int = 20,
    pval_threshold: float = 0.05,
    figsize: Tuple[int, int] = (12, 10),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot dot plot of top interactions (similar to CellChat bubble plot).

    Args:
        pvals: DataFrame with p-values
        interactions_strength: DataFrame with interaction strengths
        database_file_path: Path to database for ligand/receptor names
        top_n: Number of top interactions to show
        pval_threshold: P-value threshold
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    # Get significant interactions
    sig_mask = pvals < pval_threshold

    # Create results dataframe
    results = []
    for cell_pair in sig_mask.index:
        for interaction in sig_mask.columns:
            if sig_mask.loc[cell_pair, interaction]:
                results.append({
                    'cell_pair': cell_pair,
                    'interaction': interaction,
                    'pvalue': pvals.loc[cell_pair, interaction],
                    'strength': interactions_strength.loc[cell_pair, interaction]
                })

    results_df = pd.DataFrame(results)

    if len(results_df) == 0:
        print("No significant interactions found")
        return None

    # Sort by strength and get top N
    results_df = results_df.nlargest(top_n, 'strength')

    # Parse cell pairs
    results_df['source'] = results_df['cell_pair'].apply(lambda x: x.split('|')[0])
    results_df['target'] = results_df['cell_pair'].apply(lambda x: x.split('|')[1])

    # Create plot
    fig, ax = plt.subplots(figsize=figsize)

    # Create y positions
    y_positions = range(len(results_df))

    # Plot dots
    scatter = ax.scatter(
        results_df['strength'],
        y_positions,
        s=-np.log10(results_df['pvalue']) * 50,  # Size based on significance
        c=results_df['strength'],
        cmap='viridis',
        alpha=0.7,
        edgecolors='black'
    )

    # Add labels
    labels = [f"{row['source']} → {row['target']}: {row['interaction']}"
              for _, row in results_df.iterrows()]
    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels, fontsize=8)

    ax.set_xlabel('Interaction Strength', fontsize=12)
    ax.set_title(f'Top {top_n} Significant Interactions', fontsize=14)

    # Colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Interaction Strength', fontsize=10)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_pvalue_distribution(
    pvals: pd.DataFrame,
    figsize: Tuple[int, int] = (12, 4),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot distribution of p-values.

    Args:
        pvals: DataFrame with p-values
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    fig, axes = plt.subplots(1, 3, figsize=figsize)

    # Flatten p-values
    pval_flat = pvals.values.flatten()

    # Histogram
    axes[0].hist(pval_flat, bins=50, edgecolor='black', alpha=0.7)
    axes[0].axvline(0.05, color='red', linestyle='--', label='p=0.05')
    axes[0].set_xlabel('P-value')
    axes[0].set_ylabel('Frequency')
    axes[0].set_title('P-value Distribution')
    axes[0].legend()

    # Q-Q plot
    from scipy import stats
    stats.probplot(pval_flat, dist="uniform", plot=axes[1])
    axes[1].set_title('Q-Q Plot (Uniform Distribution)')

    # Volcano-like plot
    neg_log_pvals = -np.log10(pval_flat + 1e-300)
    mean_strength = np.random.uniform(0, 1, len(pval_flat))  # Placeholder

    axes[2].scatter(mean_strength, neg_log_pvals, alpha=0.3, s=5)
    axes[2].axhline(-np.log10(0.05), color='red', linestyle='--', label='p=0.05')
    axes[2].set_xlabel('Mean Expression (placeholder)')
    axes[2].set_ylabel('-log10(p-value)')
    axes[2].set_title('Significance Plot')
    axes[2].legend()

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_celltype_communication_chord(
    pvals: pd.DataFrame,
    interactions_strength: pd.DataFrame,
    cell_type_subset: Optional[List[str]] = None,
    pval_threshold: float = 0.05,
    figsize: Tuple[int, int] = (10, 10),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot chord diagram of cell-cell communication.

    Args:
        pvals: DataFrame with p-values
        interactions_strength: DataFrame with interaction strengths
        cell_type_subset: Optional subset of cell types to include
        pval_threshold: P-value threshold
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    try:
        import matplotlib.patches as mpatches
        from matplotlib.patches import FancyBboxPatch
    except ImportError:
        raise ImportError("Required matplotlib components not available")

    # Get significant interactions count per cell pair
    sig_counts = (pvals < pval_threshold).sum(axis=1)

    # Parse cell pairs
    cell_pairs = []
    for cell_pair in sig_counts.index:
        source, target = cell_pair.split('|')
        if cell_type_subset is None or (source in cell_type_subset and target in cell_type_subset):
            cell_pairs.append({
                'source': source,
                'target': target,
                'count': sig_counts[cell_pair]
            })

    pair_df = pd.DataFrame(cell_pairs)

    if len(pair_df) == 0:
        print("No significant interactions found")
        return None

    # Get unique cell types
    cell_types = sorted(set(pair_df['source'].unique()) | set(pair_df['target'].unique()))

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_aspect('equal')
    ax.axis('off')

    # Colors for cell types
    colors = plt.cm.tab20(np.linspace(0, 1, len(cell_types)))
    color_dict = dict(zip(cell_types, colors))

    # Calculate positions on circle
    angles = np.linspace(0, 2*np.pi, len(cell_types), endpoint=False)
    positions = {ct: (np.cos(angle), np.sin(angle)) for ct, angle in zip(cell_types, angles)}

    # Draw nodes
    for ct, (x, y) in positions.items():
        circle = Circle((x, y), 0.08, color=color_dict[ct], ec='black', linewidth=2)
        ax.add_patch(circle)
        ax.text(x*1.2, y*1.2, ct, ha='center', va='center', fontsize=9, fontweight='bold')

    # Draw edges (chords)
    max_count = pair_df['count'].max()
    for _, row in pair_df.iterrows():
        if row['count'] > 0:
            x1, y1 = positions[row['source']]
            x2, y2 = positions[row['target']]

            # Line width based on count
            lw = 1 + 5 * row['count'] / max_count

            # Draw curved line
            ax.annotate('', xy=(x2*0.9, y2*0.9), xytext=(x1*0.9, y1*0.9),
                       arrowprops=dict(arrowstyle='->', color='gray',
                                     lw=lw, alpha=0.5,
                                     connectionstyle='arc3,rad=0.3'))

    ax.set_title('Cell-Cell Communication Network', fontsize=14)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_fastccc_summary(
    pvals: pd.DataFrame,
    interactions_strength: pd.DataFrame,
    output_dir: str = './fastccc_plots',
    prefix: str = '',
    pval_threshold: float = 0.05
) -> Dict[str, str]:
    """Generate a comprehensive set of FastCCC visualization plots.

    Args:
        pvals: DataFrame with p-values
        interactions_strength: DataFrame with interaction strengths
        output_dir: Directory to save plots
        prefix: Prefix for plot filenames
        pval_threshold: P-value threshold for significance

    Returns:
        Dictionary mapping plot names to file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    plots = {}

    # Interaction heatmap
    try:
        fig = plot_interaction_heatmap(
            pvals, interactions_strength,
            pval_threshold=pval_threshold,
            save_path=os.path.join(output_dir, f'{prefix}interaction_heatmap.png')
        )
        plots['interaction_heatmap'] = os.path.join(output_dir, f'{prefix}interaction_heatmap.png')
        plt.close(fig)
    except Exception as e:
        print(f"Error creating heatmap: {e}")

    # Significant interactions bar plot
    try:
        fig = plot_significant_interactions_bar(
            pvals, pval_threshold=pval_threshold,
            save_path=os.path.join(output_dir, f'{prefix}significant_interactions_bar.png')
        )
        plots['significant_bar'] = os.path.join(output_dir, f'{prefix}significant_interactions_bar.png')
        plt.close(fig)
    except Exception as e:
        print(f"Error creating bar plot: {e}")

    # P-value distribution
    try:
        fig = plot_pvalue_distribution(
            pvals,
            save_path=os.path.join(output_dir, f'{prefix}pvalue_distribution.png')
        )
        plots['pvalue_dist'] = os.path.join(output_dir, f'{prefix}pvalue_distribution.png')
        plt.close(fig)
    except Exception as e:
        print(f"Error creating p-value distribution: {e}")

    # Network plot
    try:
        from utils import create_interaction_network_data
        node_df, edge_df = create_interaction_network_data(
            pvals, interactions_strength, pval_threshold=pval_threshold
        )
        fig = plot_interaction_network(
            node_df, edge_df,
            save_path=os.path.join(output_dir, f'{prefix}interaction_network.png')
        )
        plots['network'] = os.path.join(output_dir, f'{prefix}interaction_network.png')
        plt.close(fig)
    except Exception as e:
        print(f"Error creating network plot: {e}")

    return plots


def plot_reference_comparison(
    infer_results: pd.DataFrame,
    comparison_column: str = 'trend_vs_ref',
    figsize: Tuple[int, int] = (10, 6),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot comparison between query and reference.

    Args:
        infer_results: DataFrame with inference results
        comparison_column: Column name for comparison
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    if comparison_column not in infer_results.columns:
        raise ValueError(f"Comparison column '{comparison_column}' not found")

    # Count categories
    counts = infer_results[comparison_column].value_counts()

    # Create plot
    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Pie chart
    colors = {'Both Sig': 'green', 'Up': 'blue', 'Down': 'red', 'Both NS': 'gray'}
    pie_colors = [colors.get(c, 'lightgray') for c in counts.index]

    axes[0].pie(counts.values, labels=counts.index, autopct='%1.1f%%',
                colors=pie_colors, startangle=90)
    axes[0].set_title('Query vs Reference Comparison')

    # Bar chart
    counts.plot(kind='bar', ax=axes[1], color=pie_colors)
    axes[1].set_xlabel('Category')
    axes[1].set_ylabel('Count')
    axes[1].set_title('Interaction Count by Category')
    axes[1].tick_params(axis='x', rotation=45)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


def plot_interaction_strength_vs_significance(
    pvals: pd.DataFrame,
    interactions_strength: pd.DataFrame,
    sample_fraction: float = 0.1,
    figsize: Tuple[int, int] = (10, 6),
    save_path: Optional[str] = None
) -> plt.Figure:
    """Plot interaction strength vs significance.

    Args:
        pvals: DataFrame with p-values
        interactions_strength: DataFrame with interaction strengths
        sample_fraction: Fraction of points to sample for plotting
        figsize: Figure size
        save_path: Optional path to save figure

    Returns:
        Matplotlib figure object
    """
    # Sample data for plotting
    n_total = pvals.shape[0] * pvals.shape[1]
    n_sample = int(n_total * sample_fraction)

    np.random.seed(42)
    sample_idx = np.random.choice(n_total, size=min(n_sample, n_total), replace=False)

    pvals_flat = pvals.values.flatten()[sample_idx]
    strength_flat = interactions_strength.values.flatten()[sample_idx]

    # Create plot
    fig, ax = plt.subplots(figsize=figsize)

    # Color by significance
    colors = np.where(pvals_flat < 0.05, 'red', 'blue')

    ax.scatter(strength_flat, -np.log10(pvals_flat + 1e-300),
               c=colors, alpha=0.3, s=10)

    ax.axhline(-np.log10(0.05), color='red', linestyle='--', label='p=0.05')
    ax.set_xlabel('Interaction Strength')
    ax.set_ylabel('-log10(p-value)')
    ax.set_title('Interaction Strength vs Significance')
    ax.legend()

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig
