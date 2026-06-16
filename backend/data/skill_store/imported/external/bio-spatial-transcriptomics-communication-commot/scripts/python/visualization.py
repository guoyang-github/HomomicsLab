"""
Visualization functions for COMMOT spatial communication analysis.

Provides spatial visualization, network plots, and directional vector fields
for cell-cell communication results.

All wrappers use database_name to locate COMMOT results, following the native
key pattern: 'commot-{database_name}-...'

Author: Yang Guo
Date: 2026-04-03
Version: 1.2.0
"""

from typing import Optional, List, Dict, Tuple, Union
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy import sparse
import scanpy as sc
from anndata import AnnData
import seaborn as sns


# ============================================================================
# Spatial Communication Visualization
# ============================================================================

def plot_communication_strength(
    adata: AnnData,
    lr_pair: str,
    database_name: str = 'cellchat',
    summary: str = 'receiver',
    cmap: str = 'coolwarm',
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 8),
    show_colorbar: bool = True,
    spot_size: float = 1.0,
    save_path: Optional[str] = None,
    ax: Optional[mpl.axes.Axes] = None,
) -> mpl.axes.Axes:
    """
    Plot communication strength on spatial coordinates.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    lr_pair : str
        Ligand-receptor pair (format: 'LIGAND-RECEPTOR')
    database_name : str, default='cellchat'
        Database name used in run_commot()
    summary : str, default='receiver'
        'sender' or 'receiver' strength to plot
    cmap : str, default='coolwarm'
        Colormap for strength values
    title : str, optional
        Plot title
    figsize : tuple, default=(10, 8)
        Figure size
    show_colorbar : bool, default=True
        Whether to show colorbar
    spot_size : float, default=1.0
        Size of spots
    save_path : str, optional
        Path to save figure
    ax : matplotlib.axes.Axes, optional
        Existing axes to plot on

    Returns
    -------
    matplotlib.axes.Axes
        Axes object

    Examples
    --------
    >>> plot_communication_strength(adata, 'TGFB1-TGFBR1_TGFBR2', database_name='cellchat')
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    # Get summary key using correct COMMOT key pattern
    summary_key = f'commot-{database_name}-sum-{summary}'
    if summary_key not in adata.obsm:
        raise KeyError(f"'{summary_key}' not found. Run COMMOT first.")

    # Extract values for this LR pair
    col_name = f"{summary[0]}-{lr_pair}"  # 'r-' or 's-' prefix
    if col_name not in adata.obsm[summary_key].columns:
        available = adata.obsm[summary_key].columns.tolist()
        raise ValueError(
            f"'{lr_pair}' not found in results. "
            f"Available: {available[:10]}..."
        )

    values = adata.obsm[summary_key][col_name].values

    # Plot on spatial coordinates
    if 'spatial' not in adata.obsm:
        raise ValueError("'spatial' not found in adata.obsm")
    coords = adata.obsm['spatial']

    scatter = ax.scatter(
        coords[:, 0],
        coords[:, 1],
        c=values,
        cmap=cmap,
        s=spot_size * 100,
        alpha=0.8,
        edgecolors='none',
    )

    if show_colorbar:
        cbar = plt.colorbar(scatter, ax=ax, shrink=0.5)
        cbar.set_label(f'{summary.capitalize()} Strength')

    ax.set_aspect('equal')
    ax.set_xlabel('Spatial X')
    ax.set_ylabel('Spatial Y')
    ax.set_title(title or f'{lr_pair} ({summary})')

    # Remove spines
    sns.despine(ax=ax)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return ax


def plot_communication_direction(
    adata: AnnData,
    database_name: str,
    pathway_name: Optional[str] = None,
    lr_pair: Optional[Tuple[str, str]] = None,
    plot_method: str = 'grid',
    cmap: str = 'viridis',
    scale: float = 1.0,
    grid_density: float = 0.5,
    stream_density: float = 1.0,
    background: str = 'summary',
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 10),
    save_path: Optional[str] = None,
    ax: Optional[mpl.axes.Axes] = None,
    **kwargs
) -> mpl.axes.Axes:
    """
    Plot communication direction vectors.

    Visualizes the directional flow of cell-cell communication using
    vector fields, streamlines, or grid plots.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    database_name : str
        Database name used in run_commot()
    pathway_name : str, optional
        Signaling pathway to plot. Alternative to lr_pair.
    lr_pair : tuple[str, str], optional
        Specific LR pair as (ligand, receptor). Alternative to pathway_name.
    plot_method : str, default='grid'
        Plot type: 'cell', 'grid', or 'stream'
    cmap : str, default='viridis'
        Colormap
    scale : float, default=1.0
        Vector scale factor
    grid_density : float, default=0.5
        Grid density for grid/stream plots
    stream_density : float, default=1.0
        Streamline density
    background : str, default='summary'
        Background type: 'summary', 'image', or 'cluster'
    title : str, optional
        Plot title
    figsize : tuple, default=(12, 10)
        Figure size
    save_path : str, optional
        Path to save figure
    ax : matplotlib.axes.Axes, optional
        Existing axes
    **kwargs
        Additional arguments passed to native plot_cell_communication()

    Returns
    -------
    matplotlib.axes.Axes
        Axes object

    Examples
    --------
    >>> plot_communication_direction(adata, database_name='cellchat', pathway_name='TGFb', plot_method='stream')
    >>> plot_communication_direction(adata, database_name='cellchat', lr_pair=('TGFB1', 'TGFBR1_TGFBR2'))
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError("commot not installed")

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    # Check if direction has been computed (check both sender and receiver)
    what = pathway_name or (f"{lr_pair[0]}-{lr_pair[1]}" if lr_pair else None)
    if what is not None:
        vf_key_sender = f'commot_sender_vf-{database_name}-{what}'
        vf_key_receiver = f'commot_receiver_vf-{database_name}-{what}'
        if vf_key_sender not in adata.obsm and vf_key_receiver not in adata.obsm:
            print("Computing communication direction...")
            ct.tl.communication_direction(
                adata,
                database_name=database_name,
                pathway_name=pathway_name,
                lr_pair=lr_pair,
            )

    # Use COMMOT's native plotting function.
    # Note: scale/grid_density/stream_density are not in the documented native API,
    # so we only pass them through **kwargs to avoid TypeError on older versions.
    plot_kwargs = dict(kwargs)
    if scale != 1.0:
        plot_kwargs.setdefault('scale', scale)
    if grid_density != 0.5:
        plot_kwargs.setdefault('grid_density', grid_density)
    if stream_density != 1.0:
        plot_kwargs.setdefault('stream_density', stream_density)

    ax = ct.pl.plot_cell_communication(
        adata,
        database_name=database_name,
        pathway_name=pathway_name,
        lr_pair=lr_pair,
        plot_method=plot_method,
        cmap=cmap,
        background=background,
        ax=ax,
        **plot_kwargs,
    )

    if title:
        ax.set_title(title)
    else:
        what = pathway_name or (f"{lr_pair[0]}-{lr_pair[1]}" if lr_pair else "all")
        ax.set_title(f'Communication Direction: {what}')

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return ax


def plot_lr_expression(
    adata: AnnData,
    ligand: str,
    receptor: str,
    cmap: str = 'viridis',
    figsize: Tuple[int, int] = (16, 6),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Plot ligand and receptor expression side by side on spatial coordinates.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    ligand : str
        Ligand gene name
    receptor : str
        Receptor gene name (first subunit if heteromeric)
    cmap : str, default='viridis'
        Colormap
    figsize : tuple, default=(16, 6)
        Figure size
    save_path : str, optional
        Path to save figure

    Returns
    -------
    matplotlib.figure.Figure
        Figure object

    Examples
    --------
    >>> plot_lr_expression(adata, 'TGFB1', 'TGFBR1')
    """
    if 'spatial' not in adata.obsm:
        raise ValueError("'spatial' not found in adata.obsm")

    coords = adata.obsm['spatial']
    fig, axes = plt.subplots(1, 2, figsize=figsize)

    def _get_expr(gene):
        """Extract expression values, handling both dense and sparse matrices."""
        x = adata[:, gene].X
        if sparse.issparse(x):
            return x.toarray().flatten()
        return np.array(x).flatten()

    # Plot ligand
    if ligand in adata.var_names:
        expr = _get_expr(ligand)
        scatter = axes[0].scatter(
            coords[:, 0], coords[:, 1],
            c=expr, cmap=cmap, s=20, alpha=0.8, edgecolors='none'
        )
        plt.colorbar(scatter, ax=axes[0], shrink=0.6)
        axes[0].set_title(f'Ligand: {ligand}')
        axes[0].set_aspect('equal')
        axes[0].set_xlabel('Spatial X')
        axes[0].set_ylabel('Spatial Y')
    else:
        axes[0].text(0.5, 0.5, f'{ligand} not found', ha='center', va='center', transform=axes[0].transAxes)
        axes[0].axis('off')

    # Plot receptor (support heteromeric by checking subunits)
    receptor_found = receptor in adata.var_names
    if not receptor_found and '_' in receptor:
        # User provided full heteromeric name (e.g., TGFBR1_TGFBR2)
        pass  # already checked exact match above
    elif not receptor_found:
        # Try to find a heteromeric complex containing this receptor as first subunit
        candidates = [v for v in adata.var_names if v.startswith(receptor + '_')]
        if candidates:
            receptor = candidates[0]
            receptor_found = True

    if receptor_found:
        expr = _get_expr(receptor)
        scatter = axes[1].scatter(
            coords[:, 0], coords[:, 1],
            c=expr, cmap=cmap, s=20, alpha=0.8, edgecolors='none'
        )
        plt.colorbar(scatter, ax=axes[1], shrink=0.6)
        axes[1].set_title(f'Receptor: {receptor}')
        axes[1].set_aspect('equal')
        axes[1].set_xlabel('Spatial X')
        axes[1].set_ylabel('Spatial Y')
    else:
        axes[1].text(0.5, 0.5, f'{receptor} not found', ha='center', va='center', transform=axes[1].transAxes)
        axes[1].axis('off')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


# ============================================================================
# Cluster Communication Visualization
# ============================================================================

def _get_cluster_uns_names(
    adata: AnnData,
    database_name: str,
    cluster_key: str,
    pathway_name: Optional[str] = None,
    lr_pair: Optional[Tuple[str, str]] = None,
) -> List[str]:
    """Construct uns_names for cluster communication plotting."""
    prefix = f'commot_cluster-{cluster_key}-{database_name}'

    # Try exact match first
    if lr_pair is not None:
        exact = f'{prefix}-{lr_pair[0]}-{lr_pair[1]}'
        if exact in adata.uns:
            return [exact]
    elif pathway_name is not None:
        exact = f'{prefix}-{pathway_name}'
        if exact in adata.uns:
            return [exact]

    # Auto-discover matching keys
    matching = [k for k in adata.uns.keys() if k.startswith(prefix)]
    if matching:
        return matching

    raise KeyError(
        f"No cluster communication results found for '{prefix}'. "
        f"Run cluster_communication() first."
    )


def plot_cluster_communication_network(
    adata: AnnData,
    database_name: str,
    cluster_key: str = 'cluster',
    pathway_name: Optional[str] = None,
    lr_pair: Optional[Tuple[str, str]] = None,
    cmap: str = 'Reds',
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 10),
    save_path: Optional[str] = None,
    ax: Optional[mpl.axes.Axes] = None,
    **kwargs
) -> mpl.axes.Axes:
    """
    Plot cluster communication as network diagram.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    database_name : str
        Database name used in run_commot()
    cluster_key : str, default='cluster'
        Key for cluster annotations (mapped to native 'clustering')
    pathway_name : str, optional
        Specific pathway. If None, uses all available.
    lr_pair : tuple[str, str], optional
        Specific LR pair as (ligand, receptor).
    cmap : str, default='Reds'
        Colormap for edge weights
    title : str, optional
        Plot title
    figsize : tuple, default=(10, 10)
        Figure size
    save_path : str, optional
        Path to save
    ax : matplotlib.axes.Axes, optional
        Existing axes
    **kwargs
        Additional arguments passed to native plot_cluster_communication_network()

    Returns
    -------
    matplotlib.axes.Axes
        Axes object

    Examples
    --------
    >>> plot_cluster_communication_network(adata, database_name='cellchat', cluster_key='cell_type')
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError("commot not installed")

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    # Ensure cluster communication is computed
    uns_names = _get_cluster_uns_names(
        adata, database_name, cluster_key, pathway_name, lr_pair
    )

    # Plot network using native API.
    # ax is not in the documented native params; try with ax and fallback.
    try:
        ax = ct.pl.plot_cluster_communication_network(
            adata,
            uns_names=uns_names,
            clustering=cluster_key,
            ax=ax,
            **kwargs,
        )
    except TypeError:
        ax = ct.pl.plot_cluster_communication_network(
            adata,
            uns_names=uns_names,
            clustering=cluster_key,
            **kwargs,
        )

    if title:
        ax.set_title(title)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return ax


def plot_cluster_communication_dotplot(
    adata: AnnData,
    database_name: str,
    cluster_key: str = 'cluster',
    pathway_name: Optional[str] = None,
    cmap: str = 'YlOrRd',
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 10),
    save_path: Optional[str] = None,
    ax: Optional[mpl.axes.Axes] = None,
    **kwargs
) -> mpl.axes.Axes:
    """
    Plot cluster communication as dot plot.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    database_name : str
        Database name used in run_commot()
    cluster_key : str, default='cluster'
        Key for cluster annotations (mapped to native 'clustering')
    pathway_name : str, optional
        Specific pathway to plot
    cmap : str, default='YlOrRd'
        Colormap
    title : str, optional
        Plot title
    figsize : tuple, default=(12, 10)
        Figure size
    save_path : str, optional
        Path to save
    ax : matplotlib.axes.Axes, optional
        Existing axes
    **kwargs
        Additional arguments passed to native plot_cluster_communication_dotplot()

    Returns
    -------
    matplotlib.axes.Axes
        Axes object

    Examples
    --------
    >>> plot_cluster_communication_dotplot(adata, database_name='cellchat', cluster_key='cell_type')
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError("commot not installed")

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    # Plot dotplot using native API.
    # cmap and ax are not in the documented native params; try with them and fallback.
    try:
        ax = ct.pl.plot_cluster_communication_dotplot(
            adata,
            database_name=database_name,
            pathway_name=pathway_name,
            clustering=cluster_key,
            cmap=cmap,
            ax=ax,
            **kwargs,
        )
    except TypeError:
        ax = ct.pl.plot_cluster_communication_dotplot(
            adata,
            database_name=database_name,
            pathway_name=pathway_name,
            clustering=cluster_key,
            **kwargs,
        )

    if title:
        ax.set_title(title)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return ax


def plot_cluster_communication_chord(
    adata: AnnData,
    database_name: str,
    cluster_key: str = 'cluster',
    pathway_name: Optional[str] = None,
    lr_pair: Optional[Tuple[str, str]] = None,
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 10),
    save_path: Optional[str] = None,
) -> None:
    """
    Plot cluster communication as chord diagram.

    Uses COMMOT's R-based chord diagram plotting.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    database_name : str
        Database name used in run_commot()
    cluster_key : str, default='cluster'
        Key for cluster annotations
    pathway_name : str, optional
        Specific pathway
    lr_pair : tuple[str, str], optional
        Specific LR pair as (ligand, receptor)
    title : str, optional
        Plot title
    figsize : tuple, default=(10, 10)
        Figure size
    save_path : str, optional
        Path to save

    Examples
    --------
    >>> plot_cluster_communication_chord(adata, database_name='cellchat', cluster_key='cell_type')

    Notes
    -----
    Requires R and circlize package installed.
    """
    try:
        import commot as ct
    except ImportError:
        raise ImportError("commot not installed")

    # Ensure cluster communication is computed
    _get_cluster_uns_names(adata, database_name, cluster_key, pathway_name, lr_pair)

    # Plot chord diagram using native API.
    # Save before calling native plot if possible, since native may create its own figure.
    fig_before = plt.gcf()
    ct.pl.plot_cluster_communication_chord(
        adata,
        database_name=database_name,
        pathway_name=pathway_name,
        lr_pair=lr_pair,
        clustering=cluster_key,
    )

    if save_path:
        # Save the currently active figure (native plot may have switched it)
        plt.gcf().savefig(save_path, dpi=300, bbox_inches='tight')


# ============================================================================
# Summary and Comparison Visualization
# ============================================================================

def plot_communication_heatmap(
    adata: AnnData,
    lr_pairs: Optional[List[str]] = None,
    database_name: str = 'cellchat',
    summary: str = 'receiver',
    cmap: str = 'YlOrRd',
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 8),
    save_path: Optional[str] = None,
    ax: Optional[mpl.axes.Axes] = None,
    seed: int = 42,
) -> mpl.axes.Axes:
    """
    Plot heatmap of communication strengths.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    lr_pairs : List[str], optional
        LR pairs to include. If None, uses top 20 pairs.
    database_name : str, default='cellchat'
        Database name used in run_commot()
    summary : str, default='receiver'
        'sender' or 'receiver'
    cmap : str, default='YlOrRd'
        Colormap
    title : str, optional
        Plot title
    figsize : tuple, default=(12, 8)
        Figure size
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
    >>> plot_communication_heatmap(adata, lr_pairs=['TGFB1-TGFBR1_TGFBR2', 'IL2-IL2RA'])
    """
    summary_key = f'commot-{database_name}-sum-{summary}'
    if summary_key not in adata.obsm:
        raise KeyError(f"'{summary_key}' not found. Run COMMOT first.")

    df = adata.obsm[summary_key]

    # Select LR pairs
    if lr_pairs is None:
        # Use all columns, limit to top 20 by total
        cols = df.columns.tolist()
        totals = [(c, df[c].sum()) for c in cols]
        totals = sorted(totals, key=lambda x: x[1], reverse=True)[:20]
        lr_pairs = [c for c, _ in totals]
    else:
        # Convert to column names
        cols = [f"{summary[0]}-{pair}" for pair in lr_pairs]
        lr_pairs = [c for c in cols if c in df.columns]

    if len(lr_pairs) == 0:
        raise ValueError("No valid LR pairs found")

    # Subset and sample if needed
    data = df[lr_pairs].values

    # Sample cells if too many (deterministic with seed)
    max_cells = 500
    if data.shape[0] > max_cells:
        rng = np.random.default_rng(seed)
        idx = rng.choice(data.shape[0], max_cells, replace=False)
        data = data[idx]

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    # Plot heatmap
    sns.heatmap(
        data,
        cmap=cmap,
        xticklabels=[c.replace(f'{summary[0]}-', '') for c in lr_pairs],
        yticklabels=False,
        ax=ax,
        cbar_kws={'label': f'{summary.capitalize()} Strength'},
    )

    ax.set_xlabel('Ligand-Receptor Pair')
    ax.set_ylabel('Spots/Cells')
    ax.set_title(title or f'Communication {summary.capitalize()} Heatmap')

    plt.xticks(rotation=45, ha='right')

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return ax


def plot_top_lr_pairs(
    adata: AnnData,
    n: int = 15,
    database_name: str = 'cellchat',
    summary: str = 'total',
    figsize: Tuple[int, int] = (10, 8),
    save_path: Optional[str] = None,
    ax: Optional[mpl.axes.Axes] = None,
) -> mpl.axes.Axes:
    """
    Bar plot of top LR pairs by total communication strength.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    n : int, default=15
        Number of top pairs to show
    database_name : str, default='cellchat'
        Database name used in run_commot()
    summary : str, default='total'
        'sender', 'receiver', or 'total'
    figsize : tuple, default=(10, 8)
        Figure size
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
    >>> plot_top_lr_pairs(adata, n=20, database_name='cellchat')
    """
    # Get summary data
    sender_key = f'commot-{database_name}-sum-sender'
    receiver_key = f'commot-{database_name}-sum-receiver'

    df_sender = adata.obsm.get(sender_key, pd.DataFrame())
    df_receiver = adata.obsm.get(receiver_key, pd.DataFrame())

    if df_sender.empty and df_receiver.empty:
        raise ValueError("No COMMOT summary data found")

    # Calculate totals
    totals = []
    pairs = []

    all_pairs = set()
    if not df_sender.empty:
        all_pairs.update([c.replace('s-', '') for c in df_sender.columns])
    if not df_receiver.empty:
        all_pairs.update([c.replace('r-', '') for c in df_receiver.columns])

    for pair in all_pairs:
        total = 0
        if not df_sender.empty and f's-{pair}' in df_sender.columns:
            total += df_sender[f's-{pair}'].sum()
        if not df_receiver.empty and f'r-{pair}' in df_receiver.columns:
            total += df_receiver[f'r-{pair}'].sum()

        totals.append(total)
        pairs.append(pair)

    # Create DataFrame and sort
    df = pd.DataFrame({'lr_pair': pairs, 'total': totals})
    df = df.sort_values('total', ascending=False).head(n)

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    # Plot
    colors = plt.cm.YlOrRd(np.linspace(0.3, 0.9, len(df)))
    bars = ax.barh(range(len(df)), df['total'].values, color=colors)

    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df['lr_pair'].values)
    ax.invert_yaxis()
    ax.set_xlabel('Total Communication Strength')
    ax.set_title(f'Top {n} LR Pairs')

    # Add value labels
    for i, (bar, val) in enumerate(zip(bars, df['total'].values)):
        ax.text(val, i, f' {val:.1f}', va='center', fontsize=8)

    sns.despine(ax=ax)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return ax


def plot_communication_summary_by_cluster(
    adata: AnnData,
    cluster_key: str,
    lr_pair: str,
    database_name: str = 'cellchat',
    figsize: Tuple[int, int] = (12, 5),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Box plot of communication strength by cluster.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    cluster_key : str
        Key for cluster annotations
    lr_pair : str
        LR pair to plot
    database_name : str, default='cellchat'
        Database name used in run_commot()
    figsize : tuple, default=(12, 5)
        Figure size
    save_path : str, optional
        Path to save

    Returns
    -------
    matplotlib.figure.Figure
        Figure object

    Examples
    --------
    >>> plot_communication_summary_by_cluster(adata, 'cell_type', 'TGFB1-TGFBR1_TGFBR2')
    """
    if cluster_key not in adata.obs:
        raise ValueError(f"'{cluster_key}' not found in adata.obs")

    # Get data
    sender_key = f'commot-{database_name}-sum-sender'
    receiver_key = f'commot-{database_name}-sum-receiver'

    df_sender = adata.obsm.get(sender_key, pd.DataFrame())
    df_receiver = adata.obsm.get(receiver_key, pd.DataFrame())

    col_s = f's-{lr_pair}'
    col_r = f'r-{lr_pair}'

    data_list = []

    if col_s in df_sender.columns:
        for cluster in adata.obs[cluster_key].unique():
            mask = adata.obs[cluster_key] == cluster
            values = df_sender.loc[mask.values, col_s].values
            for v in values:
                data_list.append({'cluster': cluster, 'type': 'Sender', 'strength': v})

    if col_r in df_receiver.columns:
        for cluster in adata.obs[cluster_key].unique():
            mask = adata.obs[cluster_key] == cluster
            values = df_receiver.loc[mask.values, col_r].values
            for v in values:
                data_list.append({'cluster': cluster, 'type': 'Receiver', 'strength': v})

    if len(data_list) == 0:
        raise ValueError(f"No data found for {lr_pair}")

    df_plot = pd.DataFrame(data_list)

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=figsize)

    for idx, comm_type in enumerate(['Sender', 'Receiver']):
        df_subset = df_plot[df_plot['type'] == comm_type]
        if len(df_subset) > 0:
            sns.boxplot(data=df_subset, x='cluster', y='strength', ax=axes[idx])
            axes[idx].set_title(f'{comm_type}: {lr_pair}')
            axes[idx].tick_params(axis='x', rotation=45)

    plt.suptitle(f'Communication Strength by Cluster: {lr_pair}', y=1.02)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


# ============================================================================
# Multi-sample Comparison
# ============================================================================

def plot_communication_comparison(
    adatas: Dict[str, AnnData],
    lr_pair: str,
    database_name: str = 'cellchat',
    summary: str = 'receiver',
    figsize: Tuple[int, int] = (14, 6),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """
    Compare communication strength across multiple samples/conditions.

    Parameters
    ----------
    adatas : Dict[str, AnnData]
        Dictionary mapping sample names to AnnData objects
    lr_pair : str
        LR pair to compare
    database_name : str, default='cellchat'
        Database name used in run_commot()
    summary : str, default='receiver'
        'sender' or 'receiver'
    figsize : tuple, default=(14, 6)
        Figure size
    save_path : str, optional
        Path to save

    Returns
    -------
    matplotlib.figure.Figure
        Figure object

    Examples
    --------
    >>> adatas = {'Control': adata_ctrl, 'Treatment': adata_treat}
    >>> plot_communication_comparison(adatas, 'TGFB1-TGFBR1_TGFBR2')
    """
    n_samples = len(adatas)
    fig, axes = plt.subplots(1, n_samples, figsize=figsize)

    if n_samples == 1:
        axes = [axes]

    col_name = f"{summary[0]}-{lr_pair}"

    for idx, (name, adata) in enumerate(adatas.items()):
        summary_key = f'commot-{database_name}-sum-{summary}'

        if summary_key not in adata.obsm:
            axes[idx].text(0.5, 0.5, 'No data', ha='center', transform=axes[idx].transAxes)
            continue

        if col_name not in adata.obsm[summary_key].columns:
            axes[idx].text(0.5, 0.5, f'{lr_pair} not found', ha='center', transform=axes[idx].transAxes)
            continue

        if 'spatial' not in adata.obsm:
            axes[idx].text(0.5, 0.5, 'No spatial coords', ha='center', transform=axes[idx].transAxes)
            continue

        values = adata.obsm[summary_key][col_name].values
        coords = adata.obsm['spatial']

        scatter = axes[idx].scatter(
            coords[:, 0],
            coords[:, 1],
            c=values,
            cmap='coolwarm',
            s=50,
            alpha=0.8,
        )

        axes[idx].set_aspect('equal')
        axes[idx].set_title(f'{name}')
        axes[idx].set_xlabel('Spatial X')
        axes[idx].set_ylabel('Spatial Y')

        plt.colorbar(scatter, ax=axes[idx], shrink=0.5)

    plt.suptitle(f'{lr_pair} ({summary})', y=1.02)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig


# ============================================================================
# Utility Functions
# ============================================================================

def create_figure_grid(
    n_plots: int,
    n_cols: int = 3,
    figsize_per_plot: Tuple[int, int] = (6, 5),
) -> Tuple[plt.Figure, np.ndarray]:
    """
    Create a grid of subplots for multiple visualizations.

    Parameters
    ----------
    n_plots : int
        Number of plots
    n_cols : int, default=3
        Number of columns
    figsize_per_plot : tuple, default=(6, 5)
        Size of each subplot

    Returns
    -------
    Tuple[plt.Figure, np.ndarray]
        Figure and array of axes

    Examples
    --------
    >>> fig, axes = create_figure_grid(6, n_cols=3)
    """
    n_rows = (n_plots + n_cols - 1) // n_cols

    figsize = (figsize_per_plot[0] * n_cols, figsize_per_plot[1] * n_rows)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)

    if n_plots == 1:
        axes = np.array([axes])
    else:
        axes = axes.flatten()

    # Hide extra subplots
    for idx in range(n_plots, len(axes)):
        axes[idx].axis('off')

    return fig, axes[:n_plots]


def plot_multiple_lr_pairs(
    adata: AnnData,
    lr_pairs: List[str],
    plot_func = plot_communication_strength,
    n_cols: int = 3,
    figsize_per_plot: Tuple[int, int] = (6, 5),
    save_path: Optional[str] = None,
    **kwargs,
) -> plt.Figure:
    """
    Plot multiple LR pairs in a grid.

    Parameters
    ----------
    adata : AnnData
        Data with COMMOT results
    lr_pairs : List[str]
        List of LR pairs to plot
    plot_func : callable, default=plot_communication_strength
        Function to use for plotting
    n_cols : int, default=3
        Number of columns
    figsize_per_plot : tuple, default=(6, 5)
        Size of each subplot
    save_path : str, optional
        Path to save
    **kwargs
        Additional arguments passed to plot_func

    Returns
    -------
    matplotlib.figure.Figure
        Figure object

    Examples
    --------
    >>> plot_multiple_lr_pairs(adata, ['TGFB1-TGFBR1_TGFBR2', 'IL2-IL2RA'])
    """
    fig, axes = create_figure_grid(len(lr_pairs), n_cols, figsize_per_plot)

    for idx, lr_pair in enumerate(lr_pairs):
        try:
            plot_func(adata, lr_pair, ax=axes[idx], **kwargs)
            axes[idx].set_title(lr_pair)
        except Exception as e:
            axes[idx].text(0.5, 0.5, f'Error: {str(e)[:30]}',
                          ha='center', transform=axes[idx].transAxes)
            axes[idx].axis('off')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return fig
