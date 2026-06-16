"""
Visualization functions for BRIE2 splicing analysis results.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from anndata import AnnData
from typing import List, Optional, Tuple, Union, Dict, Any


def plot_psi_distribution(
    adata: AnnData,
    events: Optional[List[str]] = None,
    n_events: int = 6,
    figsize: Tuple[int, int] = (15, 10),
    save: Optional[str] = None,
) -> plt.Figure:
    """
    Plot PSI distribution for selected events.

    Parameters
    ----------
    adata : AnnData
        BRIE quantified data
    events : list, optional
        Specific events to plot (default: random sample)
    n_events : int, default=6
        Number of events to plot if events not specified
    figsize : tuple, default=(15, 10)
        Figure size
    save : str, optional
        Path to save figure

    Returns
    -------
    matplotlib Figure
    """
    if events is None:
        # Select random events
        n_events = min(n_events, adata.n_vars)
        events = np.random.choice(adata.var_names, n_events, replace=False)
    else:
        n_events = len(events)

    n_cols = 3
    n_rows = (n_events + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
    axes = axes.flatten() if n_events > 1 else [axes]

    for idx, event in enumerate(events):
        ax = axes[idx]
        psi = adata[:, event].X.flatten()
        psi = psi[~np.isnan(psi)]

        sns.histplot(psi, bins=50, kde=True, ax=ax, color="steelblue")
        ax.set_xlabel("PSI (Percent Spliced In)")
        ax.set_ylabel("Number of Cells")
        ax.set_title(f"{event}\nn={len(psi)}, mean={np.mean(psi):.2f}")
        ax.set_xlim(0, 1)

    # Hide unused subplots
    for idx in range(n_events, len(axes)):
        axes[idx].set_visible(False)

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches="tight")

    return fig


def plot_psi_heatmap(
    adata: AnnData,
    events: Optional[List[str]] = None,
    n_events: int = 50,
    groupby: Optional[str] = None,
    cmap: str = "viridis",
    figsize: Tuple[int, int] = (12, 10),
    save: Optional[str] = None,
) -> plt.Figure:
    """
    Plot heatmap of PSI values.

    Parameters
    ----------
    adata : AnnData
        BRIE quantified data
    events : list, optional
        Events to include
    n_events : int, default=50
        Number of events if not specified
    groupby : str, optional
        Column in adata.obs for grouping/coloring cells
    cmap : str, default='viridis'
        Colormap
    figsize : tuple, default=(12, 10)
        Figure size
    save : str, optional
        Path to save figure

    Returns
    -------
    matplotlib Figure
    """
    if events is None:
        # Select events with highest variance
        psi = adata.X if hasattr(adata.X, "shape") else adata.layers.get("psi", adata.X)
        variances = np.nanvar(psi, axis=0)
        top_idx = np.argsort(variances)[-n_events:]
        events = adata.var_names[top_idx]
    else:
        n_events = len(events)

    # Get PSI matrix
    psi_matrix = adata[:, events].X

    # Create colorbar for groups if specified
    row_colors = None
    color_map = None
    unique_groups = None
    if groupby is not None and groupby in adata.obs.columns:
        groups = adata.obs[groupby]
        unique_groups = groups.unique()
        palette = sns.color_palette("husl", len(unique_groups))
        color_map = dict(zip(unique_groups, palette))
        # Convert to numpy array for seaborn compatibility
        row_colors = groups.map(color_map).values

    # Plot heatmap (use clustermap if row_colors needed, else heatmap)
    if row_colors is not None:
        g = sns.clustermap(
            psi_matrix,
            xticklabels=events,
            yticklabels=False,
            cmap=cmap,
            vmin=0,
            vmax=1,
            row_colors=row_colors,
            cbar_kws={"label": "PSI"},
            figsize=figsize,
        )
        fig = g.fig
        ax = g.ax_heatmap

        # Add legend for groups
        handles = [plt.Rectangle((0, 0), 1, 1, color=color_map[g]) for g in unique_groups]
        ax.legend(handles, unique_groups, title=groupby, loc="upper left", bbox_to_anchor=(1.15, 1))
    else:
        fig, ax = plt.subplots(figsize=figsize)

        sns.heatmap(
            psi_matrix,
            xticklabels=events,
            yticklabels=False,
            cmap=cmap,
            vmin=0,
            vmax=1,
            cbar_kws={"label": "PSI"},
            ax=ax,
        )

        ax.set_xlabel("Splicing Events")
        ax.set_ylabel("Cells")
        ax.set_title("PSI Heatmap")

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches="tight")

    return fig


def plot_volcano(
    df: pd.DataFrame,
    x_col: str = "delta_psi",
    y_col: str = "pvalue",
    q_col: str = "qvalue",
    q_threshold: float = 0.05,
    effect_threshold: float = 0.1,
    figsize: Tuple[int, int] = (10, 8),
    save: Optional[str] = None,
) -> plt.Figure:
    """
    Create volcano plot for differential splicing results.

    Parameters
    ----------
    df : DataFrame
        Results from compare_cell_groups or BRIE LRT
    x_col : str, default='delta_psi'
        Column for x-axis (effect size)
    y_col : str, default='pvalue'
        Column for y-axis (p-values)
    q_col : str, default='qvalue'
        Column for q-values (FDR)
    q_threshold : float, default=0.05
        Significance threshold
    effect_threshold : float, default=0.1
        Effect size threshold
    figsize : tuple, default=(10, 8)
        Figure size
    save : str, optional
        Path to save figure

    Returns
    -------
    matplotlib Figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Prepare data
    x = df[x_col].values
    y = -np.log10(df[y_col].replace(0, 1e-300))  # Avoid log(0)

    # Determine colors
    colors = []
    for i in range(len(df)):
        is_significant = df[q_col].iloc[i] < q_threshold if q_col in df.columns else False
        is_large_effect = abs(x[i]) > effect_threshold

        if is_significant and is_large_effect:
            colors.append("red")
        elif is_significant:
            colors.append("orange")
        elif is_large_effect:
            colors.append("blue")
        else:
            colors.append("gray")

    # Scatter plot
    ax.scatter(x, y, c=colors, alpha=0.6, s=50)

    # Add thresholds
    ax.axhline(-np.log10(0.05), color="red", linestyle="--", alpha=0.5, label="p=0.05")
    if q_threshold != 0.05 and q_col in df.columns:
        ax.axhline(-np.log10(q_threshold), color="orange", linestyle="--", alpha=0.5, label=f"q={q_threshold}")

    ax.axvline(-effect_threshold, color="blue", linestyle="--", alpha=0.5)
    ax.axvline(effect_threshold, color="blue", linestyle="--", alpha=0.5, label=f"|ΔPSI|={effect_threshold}")

    # Labels
    ax.set_xlabel(x_col.replace("_", " ").title())
    ax.set_ylabel(f"-log10({y_col})")
    ax.set_title("Differential Splicing Volcano Plot")
    ax.legend(loc="upper right")

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches="tight")

    return fig


def plot_psi_trajectory(
    adata: AnnData,
    events: List[str],
    pseudotime_key: str = "pseudotime",
    smooth: bool = True,
    figsize: Tuple[int, int] = (12, 4),
    save: Optional[str] = None,
) -> plt.Figure:
    """
    Plot PSI values along a trajectory (e.g., pseudotime).

    Parameters
    ----------
    adata : AnnData
        BRIE quantified data
    events : list
        Events to plot
    pseudotime_key : str, default='pseudotime'
        Column in adata.obs with trajectory values
    smooth : bool, default=True
        Add smoothed trend line
    figsize : tuple, default=(12, 4)
        Figure size
    save : str, optional
        Path to save figure

    Returns
    -------
    matplotlib Figure
    """
    if pseudotime_key not in adata.obs.columns:
        raise ValueError(f"'{pseudotime_key}' not found in adata.obs")

    n_events = len(events)
    n_cols = min(3, n_events)
    n_rows = (n_events + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
    axes = axes.flatten() if n_events > 1 else [axes]

    pseudotime = adata.obs[pseudotime_key].values

    for idx, event in enumerate(events):
        ax = axes[idx]
        psi = adata[:, event].X.flatten()

        # Remove NaN
        mask = ~np.isnan(psi)
        pt, psi_clean = pseudotime[mask], psi[mask]

        # Scatter
        ax.scatter(pt, psi_clean, alpha=0.3, s=10, color="gray")

        # Smooth trend
        if smooth and len(pt) > 10:
            from scipy.interpolate import UnivariateSpline

            sort_idx = np.argsort(pt)
            try:
                spline = UnivariateSpline(pt[sort_idx], psi_clean[sort_idx], s=len(pt))
                ax.plot(pt[sort_idx], spline(pt[sort_idx]), "r-", linewidth=2, label="Trend")
            except:
                pass

        ax.set_xlabel(pseudotime_key.title())
        ax.set_ylabel("PSI")
        ax.set_title(event)
        ax.set_ylim(0, 1)

    # Hide unused subplots
    for idx in range(n_events, len(axes)):
        axes[idx].set_visible(False)

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches="tight")

    return fig


def plot_splicing_summary(
    adata: AnnData,
    groupby: str,
    events: Optional[List[str]] = None,
    n_events: int = 10,
    figsize: Tuple[int, int] = (12, 8),
    save: Optional[str] = None,
) -> plt.Figure:
    """
    Create comprehensive splicing summary plot.

    Parameters
    ----------
    adata : AnnData
        BRIE quantified data
    groupby : str
        Column in adata.obs for grouping
    events : list, optional
        Specific events to plot
    n_events : int, default=10
        Number of top variable events
    figsize : tuple, default=(12, 8)
        Figure size
    save : str, optional
        Path to save figure

    Returns
    -------
    matplotlib Figure
    """
    if events is None:
        # Select most variable events
        psi = adata.X if hasattr(adata.X, "shape") else adata.layers.get("psi", adata.X)
        variances = np.nanvar(psi, axis=0)
        top_idx = np.argsort(variances)[-n_events:]
        events = adata.var_names[top_idx]
    else:
        n_events = len(events)

    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1])

    # 1. Boxplot by group
    ax1 = fig.add_subplot(gs[0, :])
    psi_df = pd.DataFrame(
        adata[:, events].X,
        columns=events,
        index=adata.obs_names,
    )
    psi_df[groupby] = adata.obs[groupby].values

    psi_melted = psi_df.melt(id_vars=[groupby], var_name="Event", value_name="PSI")

    sns.boxplot(data=psi_melted, x="Event", y="PSI", hue=groupby, ax=ax1)
    ax1.set_xticklabels(ax1.get_xticklabels(), rotation=45, ha="right")
    ax1.set_title("PSI Distribution by Group")

    # 2. Mean PSI heatmap
    ax2 = fig.add_subplot(gs[1, 0])
    mean_psi = psi_df.groupby(groupby)[events].mean()
    sns.heatmap(mean_psi, annot=True, fmt=".2f", cmap="RdYlBu_r", vmin=0, vmax=1, ax=ax2)
    ax2.set_title("Mean PSI by Group")

    # 3. PSI variance
    ax3 = fig.add_subplot(gs[1, 1])
    var_psi = psi_df.groupby(groupby)[events].var()
    sns.heatmap(var_psi, annot=True, fmt=".3f", cmap="YlOrRd", ax=ax3)
    ax3.set_title("PSI Variance by Group")

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches="tight")

    return fig
