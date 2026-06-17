"""Visualization functions for scCODA results.

This module provides plotting functions for visualizing compositional data
and scCODA analysis results.
"""

from typing import List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from anndata import AnnData
from matplotlib import cm
from matplotlib.colors import ListedColormap


def plot_effect_barplot(
    results,
    covariate: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 6),
    save_path: Optional[str] = None,
    show: bool = True,
):
    """Plot barplot of scCODA effect sizes.

    Args:
        results: CAResult object from scCODA analysis.
        covariate: Which covariate to plot (if None, plots all).
        figsize: Figure size (width, height).
        save_path: Path to save figure (optional).
        show: Whether to display the plot.

    Example:
        >>> plot_effect_barplot(results, covariate="condition")
    """
    # Get effect dataframe
    effect_df = results.effect_df.copy()

    # Filter by covariate if specified
    if covariate is not None:
        effect_df = effect_df.loc[effect_df.index.get_level_values("Covariate") == covariate]

    # Reset index for plotting
    effect_df = effect_df.reset_index()

    # Create plot
    fig, ax = plt.subplots(figsize=figsize)

    # Color bars by significance
    colors = ["red" if x != 0 else "gray" for x in effect_df["Final Parameter"]]

    sns.barplot(
        data=effect_df,
        x="Cell Type",
        y="Final Parameter",
        palette=colors,
        ax=ax,
    )

    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax.set_xlabel("Cell Type")
    ax.set_ylabel("Effect Size (log fold change)")
    ax.set_title("scCODA Effect Sizes")
    plt.xticks(rotation=45, ha="right")

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()
    else:
        return fig, ax


def plot_credible_effects(
    results,
    covariate: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 6),
    save_path: Optional[str] = None,
    show: bool = True,
):
    """Plot heatmap of credible effects (significant changes).

    Args:
        results: CAResult object from scCODA analysis.
        covariate: Which covariate to plot (if None, plots all).
        figsize: Figure size (width, height).
        save_path: Path to save figure (optional).
        show: Whether to display the plot.

    Example:
        >>> plot_credible_effects(results)
    """
    # Get credible effects
    credible = results.credible_effects()

    if covariate is not None:
        credible = credible.loc[credible.index.get_level_values("Covariate") == covariate]

    # Convert to matrix format
    credible_df = credible.reset_index().pivot(
        index="Covariate",
        columns="Cell Type",
        values="Final Parameter",
    )

    # Create plot
    fig, ax = plt.subplots(figsize=figsize)

    sns.heatmap(
        credible_df.astype(int),
        cmap="RdYlGn_r",
        cbar_kws={"label": "Credible Effect"},
        ax=ax,
        vmin=0,
        vmax=1,
    )

    ax.set_title("Credible Effects (significant changes)")
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()
    else:
        return fig, ax


def plot_fold_changes(
    results,
    covariate: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 6),
    save_path: Optional[str] = None,
    show: bool = True,
):
    """Plot log2 fold changes for all cell types.

    Args:
        results: CAResult object from scCODA analysis.
        covariate: Which covariate to plot (if None, plots all).
        figsize: Figure size (width, height).
        save_path: Path to save figure (optional).
        show: Whether to display the plot.

    Example:
        >>> plot_fold_changes(results)
    """
    # Get effect dataframe
    effect_df = results.effect_df.copy()

    if covariate is not None:
        effect_df = effect_df.loc[effect_df.index.get_level_values("Covariate") == covariate]

    effect_df = effect_df.reset_index()

    # Create plot
    fig, ax = plt.subplots(figsize=figsize)

    # Color bars by significance
    colors = ["red" if x != 0 else "gray" for x in effect_df["Final Parameter"]]

    sns.barplot(
        data=effect_df,
        x="Cell Type",
        y="log2-fold change",
        palette=colors,
        ax=ax,
    )

    ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax.set_xlabel("Cell Type")
    ax.set_ylabel("Log2 Fold Change")
    ax.set_title("Log2 Fold Changes (vs Reference)")
    plt.xticks(rotation=45, ha="right")

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()
    else:
        return fig, ax


def plot_inclusion_probability(
    results,
    covariate: Optional[str] = None,
    threshold: Optional[float] = None,
    figsize: Tuple[int, int] = (10, 6),
    save_path: Optional[str] = None,
    show: bool = True,
):
    """Plot inclusion probabilities for each cell type.

    Args:
        results: CAResult object from scCODA analysis.
        covariate: Which covariate to plot (if None, plots all).
        threshold: Inclusion probability threshold (if None, uses result threshold).
        figsize: Figure size (width, height).
        save_path: Path to save figure (optional).
        show: Whether to display the plot.

    Example:
        >>> plot_inclusion_probability(results, threshold=0.5)
    """
    # Get threshold from results if not specified
    if threshold is None:
        threshold = results.model_specs.get("threshold_prob", 0.5)

    # Get effect dataframe
    effect_df = results.effect_df.copy()

    if covariate is not None:
        effect_df = effect_df.loc[effect_df.index.get_level_values("Covariate") == covariate]

    effect_df = effect_df.reset_index()

    # Create plot
    fig, ax = plt.subplots(figsize=figsize)

    # Color points by whether they pass threshold
    colors = ["red" if x >= threshold else "gray"
              for x in effect_df["Inclusion probability"]]

    ax.scatter(
        range(len(effect_df)),
        effect_df["Inclusion probability"],
        c=colors,
        s=100,
    )

    ax.axhline(y=threshold, color="blue", linestyle="--", linewidth=1, label=f"Threshold: {threshold:.3f}")
    ax.set_xticks(range(len(effect_df)))
    ax.set_xticklabels(effect_df["Cell Type"], rotation=45, ha="right")
    ax.set_ylabel("Inclusion Probability")
    ax.set_xlabel("Cell Type")
    ax.set_title("Posterior Inclusion Probability")
    ax.legend()
    ax.set_ylim([0, 1])

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()
    else:
        return fig, ax


def plot_composition_summary(
    data: AnnData,
    groupby: Optional[str] = None,
    kind: str = "bar",
    figsize: Tuple[int, int] = (12, 6),
    save_path: Optional[str] = None,
    show: bool = True,
):
    """Plot cell type composition summary.

    Args:
        data: Compositional AnnData object.
        groupby: Column to group by (if None, plots all samples).
        kind: Plot type ("bar", "stacked", "box").
        figsize: Figure size (width, height).
        save_path: Path to save figure (optional).
        show: Whether to display the plot.

    Example:
        >>> plot_composition_summary(data, groupby="condition", kind="stacked")
    """
    if kind == "stacked":
        fig = _plot_stacked_bar(data, groupby, figsize)
    elif kind == "box":
        fig = _plot_boxplot(data, groupby, figsize)
    else:
        fig = _plot_bar(data, groupby, figsize)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()
    else:
        return fig


def _plot_stacked_bar(
    data: AnnData,
    groupby: Optional[str] = None,
    figsize: Tuple[int, int] = (10, 6),
):
    """Create stacked bar plot of compositions."""
    # Calculate relative abundances
    rel_abun = data.X / data.X.sum(axis=1, keepdims=True)

    if groupby is not None:
        # Group by condition
        groups = data.obs[groupby].unique()
        plot_data = []
        for group in groups:
            mask = data.obs[groupby] == group
            mean_comp = rel_abun[mask].mean(axis=0)
            plot_data.append(mean_comp)
        plot_data = np.array(plot_data)
        labels = groups
    else:
        plot_data = rel_abun
        labels = data.obs.index

    # Create plot
    fig, ax = plt.subplots(figsize=figsize)

    n_bars, n_types = plot_data.shape
    x = np.arange(n_bars)
    bottom = np.zeros(n_bars)

    colors = plt.cm.tab20(np.linspace(0, 1, n_types))

    for i in range(n_types):
        ax.bar(x, plot_data[:, i], bottom=bottom, label=data.var.index[i], color=colors[i])
        bottom += plot_data[:, i]

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Proportion")
    ax.set_title("Cell Type Composition")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")

    plt.tight_layout()
    return fig


def _plot_boxplot(
    data: AnnData,
    groupby: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6),
):
    """Create box plot of cell type proportions."""
    # Calculate relative abundances
    rel_abun = data.X / data.X.sum(axis=1, keepdims=True)

    # Create dataframe for plotting
    plot_df = pd.DataFrame(rel_abun, columns=data.var.index, index=data.obs.index)

    if groupby is not None:
        plot_df[groupby] = data.obs[groupby].values
        plot_df = pd.melt(plot_df, id_vars=[groupby], var_name="Cell Type", value_name="Proportion")

        fig, ax = plt.subplots(figsize=figsize)
        sns.boxplot(data=plot_df, x="Cell Type", y="Proportion", hue=groupby, ax=ax)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    else:
        plot_df = pd.melt(plot_df, var_name="Cell Type", value_name="Proportion")

        fig, ax = plt.subplots(figsize=figsize)
        sns.boxplot(data=plot_df, x="Cell Type", y="Proportion", ax=ax)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")

    ax.set_title("Cell Type Proportions")
    plt.tight_layout()
    return fig


def _plot_bar(
    data: AnnData,
    groupby: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6),
):
    """Create bar plot of total counts."""
    fig, ax = plt.subplots(figsize=figsize)

    total_counts = data.X.sum(axis=1)

    if groupby is not None:
        plot_df = pd.DataFrame({
            "Sample": data.obs.index,
            "Total Cells": total_counts,
            groupby: data.obs[groupby],
        })
        sns.barplot(data=plot_df, x="Sample", y="Total Cells", hue=groupby, ax=ax)
    else:
        plot_df = pd.DataFrame({
            "Sample": data.obs.index,
            "Total Cells": total_counts,
        })
        sns.barplot(data=plot_df, x="Sample", y="Total Cells", ax=ax)

    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_title("Total Cells per Sample")
    plt.tight_layout()
    return fig


def plot_results_summary(
    results,
    figsize: Tuple[int, int] = (14, 10),
    save_path: Optional[str] = None,
    show: bool = True,
):
    """Create comprehensive summary plot of scCODA results.

    Creates a multi-panel figure with:
    - Effect sizes
    - Log2 fold changes
    - Inclusion probabilities
    - Credible effects heatmap

    Args:
        results: CAResult object from scCODA analysis.
        figsize: Figure size (width, height).
        save_path: Path to save figure (optional).
        show: Whether to display the plot.

    Example:
        >>> plot_results_summary(results, save_path="results_summary.png")
    """
    fig = plt.figure(figsize=figsize)

    # Create grid
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

    # Panel 1: Effect sizes
    ax1 = fig.add_subplot(gs[0, 0])
    effect_df = results.effect_df.reset_index()
    colors = ["red" if x != 0 else "gray" for x in effect_df["Final Parameter"]]
    sns.barplot(data=effect_df, x="Cell Type", y="Final Parameter", palette=colors, ax=ax1)
    ax1.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax1.set_xticklabels(ax1.get_xticklabels(), rotation=45, ha="right")
    ax1.set_title("Effect Sizes")

    # Panel 2: Log2 fold changes
    ax2 = fig.add_subplot(gs[0, 1])
    sns.barplot(data=effect_df, x="Cell Type", y="log2-fold change", palette=colors, ax=ax2)
    ax2.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax2.set_xticklabels(ax2.get_xticklabels(), rotation=45, ha="right")
    ax2.set_title("Log2 Fold Changes")

    # Panel 3: Inclusion probabilities
    ax3 = fig.add_subplot(gs[1, 0])
    threshold = results.model_specs.get("threshold_prob", 0.5)
    colors = ["red" if x >= threshold else "gray" for x in effect_df["Inclusion probability"]]
    ax3.scatter(range(len(effect_df)), effect_df["Inclusion probability"], c=colors, s=100)
    ax3.axhline(y=threshold, color="blue", linestyle="--", linewidth=1)
    ax3.set_xticks(range(len(effect_df)))
    ax3.set_xticklabels(effect_df["Cell Type"], rotation=45, ha="right")
    ax3.set_ylabel("Inclusion Probability")
    ax3.set_ylim([0, 1])
    ax3.set_title("Posterior Inclusion Probabilities")

    # Panel 4: Credible effects
    ax4 = fig.add_subplot(gs[1, 1])
    credible = results.credible_effects().reset_index().pivot(
        index="Covariate", columns="Cell Type", values="Final Parameter"
    )
    sns.heatmap(credible.astype(int), cmap="RdYlGn_r", ax=ax4, cbar_kws={"label": "Significant"})
    ax4.set_title("Credible Effects")

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")

    if show:
        plt.show()
    else:
        return fig
