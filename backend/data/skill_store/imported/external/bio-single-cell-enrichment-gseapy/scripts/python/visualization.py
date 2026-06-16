"""
Visualization functions for enrichment analysis results.

Author: Yang Guo
Date: 2026-03-31
"""

from typing import Optional, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import scanpy as sc
from anndata import AnnData


def plot_enrichment(
    results: pd.DataFrame,
    top_n: int = 10,
    pval_cutoff: float = 0.05,
    figsize: Tuple[int, int] = (10, 6),
    title: str = 'Enrichment Results',
    save_path: Optional[str] = None,
    **kwargs
) -> Optional[plt.Figure]:
    """
    Plot ORA/GSEA enrichment results as bar plot.

    Parameters
    ----------
    results : pd.DataFrame
        Enrichment results from gseapy
    top_n : int, default=10
        Number of top pathways to show
    pval_cutoff : float, default=0.05
        Filter pathways by adjusted p-value
    figsize : tuple, default=(10, 6)
        Figure size
    title : str, default='Enrichment Results'
        Plot title
    save_path : str, optional
        Path to save figure
    **kwargs
        Additional arguments for barplot

    Returns
    -------
    plt.Figure
        Matplotlib figure object

    Examples
    --------
    >>> results = run_enrichr(gene_list, gene_sets='KEGG_2021_Human')
    >>> plot_enrichment(results, top_n=15, save_path='enrichment.pdf')
    """
    # Filter significant results
    if 'Adjusted P-value' in results.columns:
        sig_results = results[results['Adjusted P-value'] < pval_cutoff]
    elif 'FDR q-val' in results.columns:
        sig_results = results[results['FDR q-val'] < pval_cutoff]
    else:
        sig_results = results

    if len(sig_results) == 0:
        print("No significant pathways found")
        return None

    # Sort and select top N
    if 'Odds Ratio' in sig_results.columns:
        sig_results = sig_results.sort_values('Odds Ratio', ascending=False)
    elif 'NES' in sig_results.columns:
        sig_results = sig_results.sort_values('NES', ascending=False)

    plot_data = sig_results.head(top_n).copy()

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Determine color by p-value
    if 'Adjusted P-value' in plot_data.columns:
        colors = -np.log10(plot_data['Adjusted P-value'].astype(float))
        color_label = '-log10(Adj P-value)'
    else:
        colors = 'steelblue'
        color_label = None

    # Plot
    y_pos = np.arange(len(plot_data))
    bars = ax.barh(y_pos, plot_data.get('Odds Ratio', plot_data.get('NES', 1)),
                   color=colors if isinstance(colors, str) else plt.cm.RdYlBu_r(
                       plt.Normalize(colors.min(), colors.max())(colors)))

    ax.set_yticks(y_pos)
    ax.set_yticklabels(plot_data['Term'], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel('Odds Ratio' if 'Odds Ratio' in plot_data.columns else 'NES')
    ax.set_title(title)

    # Add colorbar if using p-value colors
    if color_label:
        sm = plt.cm.ScalarMappable(
            cmap='RdYlBu_r',
            norm=plt.Normalize(colors.min(), colors.max())
        )
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax)
        cbar.set_label(color_label)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved to {save_path}")

    return fig


def plot_gsea(
    prerank_result,
    gene_set: str,
    figsize: Tuple[int, int] = (8, 4),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot GSEA enrichment plot for a specific gene set.

    Parameters
    ----------
    prerank_result
        GSEApy Prerank object
    gene_set : str
        Gene set name to plot
    figsize : tuple, default=(8, 4)
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    plt.Figure
        Matplotlib figure

    Examples
    --------
    >>> pre_res = run_prerank(ranked_list, gene_sets='KEGG_2021_Human')
    >>> plot_gsea(pre_res, 'KEGG_APOPTOSIS')
    """
    fig = prerank_result.plot(terms=[gene_set], figsize=figsize)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved to {save_path}")

    return fig


def plot_ssgsea_heatmap(
    adata: AnnData,
    ssgsea_key: str = 'X_ssgsea',
    groupby: Optional[str] = None,
    top_n_pathways: int = 20,
    figsize: Tuple[int, int] = (12, 8),
    save_path: Optional[str] = None,
    **kwargs
):
    """
    Plot heatmap of ssGSEA scores.

    Parameters
    ----------
    adata : AnnData
        Data with ssGSEA scores
    ssgsea_key : str, default='X_ssgsea'
        Key in adata.obsm
    groupby : str, optional
        Column to group by and annotate
    top_n_pathways : int, default=20
        Number of pathways to show (highest variance)
    figsize : tuple, default=(12, 8)
        Figure size
    save_path : str, optional
        Path to save
    **kwargs
        Additional arguments for seaborn.clustermap

    Returns
    -------
    plt.Figure
        Matplotlib figure
    """
    if ssgsea_key not in adata.obsm:
        raise KeyError(f"'{ssgsea_key}' not found in adata.obsm")

    scores = adata.obsm[ssgsea_key]
    pathway_names = adata.uns.get(f'{ssgsea_key}_names', [f'Pathway_{i}' for i in range(scores.shape[1])])

    # Select top pathways by variance
    variances = np.var(scores, axis=0)
    top_indices = np.argsort(variances)[-top_n_pathways:]

    plot_data = pd.DataFrame(
        scores[:, top_indices],
        columns=[pathway_names[i] for i in top_indices],
        index=adata.obs_names
    )

    # Create clustermap
    # Disable column clustering if fewer than 2 pathways (avoids empty distance matrix error)
    clustermap_kwargs = dict(figsize=figsize, cmap='RdBu_r', center=0)
    if len(plot_data.columns) < 2:
        clustermap_kwargs['col_cluster'] = False
    clustermap_kwargs.update(kwargs)

    if groupby and groupby in adata.obs:
        row_colors = adata.obs[groupby].astype('category').cat.codes
        lut = dict(zip(row_colors.unique(), sns.color_palette('tab10', len(row_colors.unique()))))
        row_colors = row_colors.map(lut)

        g = sns.clustermap(
            plot_data,
            row_colors=row_colors,
            **clustermap_kwargs
        )
    else:
        g = sns.clustermap(
            plot_data,
            **clustermap_kwargs
        )

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Saved to {save_path}")

    return g


def plot_pathway_comparison(
    results_df: pd.DataFrame,
    x_col: str = 'group',
    y_col: str = 'mean_score',
    hue_col: str = 'pathway',
    figsize: Tuple[int, int] = (10, 6),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot pathway scores comparison across groups.

    Parameters
    ----------
    results_df : pd.DataFrame
        Results from compare_pathways_across_groups()
    x_col : str, default='group'
        Column for x-axis
    y_col : str, default='mean_score'
        Column for y-values
    hue_col : str, default='pathway'
        Column for grouping/color
    figsize : tuple, default=(10, 6)
        Figure size
    save_path : str, optional
        Path to save

    Returns
    -------
    plt.Figure
        Matplotlib figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    sns.barplot(
        data=results_df,
        x=x_col,
        y=y_col,
        hue=hue_col,
        ax=ax
    )

    ax.set_xlabel('Group')
    ax.set_ylabel('Mean Pathway Score')
    ax.set_title('Pathway Activity Across Groups')
    ax.legend(title='Pathway', bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig
