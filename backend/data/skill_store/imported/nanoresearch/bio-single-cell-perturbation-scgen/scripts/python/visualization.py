"""
Visualization Functions for scGen
==================================

This module provides visualization functions for scGen perturbation analysis,
including mean/variance regression plots and latent space visualizations.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from typing import Optional, Union, List, Dict, Tuple, Any
import warnings


def plot_regression_mean(
    model,
    adata,
    axis_keys: Dict[str, str],
    labels: Dict[str, str],
    gene_list: Optional[List[str]] = None,
    top_100_genes: Optional[List[str]] = None,
    path_to_save: Optional[str] = None,
    save: bool = True,
    show: bool = False,
    verbose: bool = False,
    legend: bool = True,
    title: Optional[str] = None,
    x_coeff: float = 0.30,
    y_coeff: float = 0.8,
    fontsize: int = 14,
    figsize: Tuple[int, int] = (8, 8),
    **kwargs
) -> Optional[float]:
    """
    Plot mean matching between predicted and real stimulated cells.

    This function plots the mean expression of genes in control vs predicted
    stimulated cells, showing how well the model captures the perturbation effect.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    adata : AnnData
        AnnData with control, predicted, and real stimulated cells
    axis_keys : dict
        Dictionary mapping conditions to keys in adata.obs
        Example: {"x": "control", "y": "predicted", "y1": "stimulated"}
    labels : dict
        Dictionary of axis labels
        Example: {"x": "Control", "y": "Predicted"}
    gene_list : list, optional
        List of specific genes to highlight on the plot
    top_100_genes : list, optional
        List of top differentially expressed genes for separate R² calculation
    path_to_save : str, optional
        Path to save the figure
    save : bool
        Whether to save the figure
    show : bool
        Whether to show the figure
    verbose : bool
        Print R² values
    legend : bool
        Show legend
    title : str, optional
        Plot title
    x_coeff : float
        X position coefficient for R² text
    y_coeff : float
        Y position coefficient for R² text
    fontsize : int
        Font size for plot
    figsize : tuple
        Figure size
    **kwargs
        Additional arguments for plotting

    Returns
    -------
    float or tuple
        R² value for all genes, or (R²_all, R²_top100) if top_100_genes provided
    """
    try:
        from adjustText import adjust_text
    except ImportError:
        warnings.warn("adjustText not installed. Gene labels may overlap.")
        adjust_text = None

    fig, ax = plt.subplots(figsize=figsize)

    # Get condition key from model
    condition_key = model.adata_manager.get_state_registry(
        "batch"
    ).original_key

    # Get data for each condition
    stim = adata[adata.obs[condition_key] == axis_keys["y"]]
    ctrl = adata[adata.obs[condition_key] == axis_keys["x"]]

    # Calculate means
    if top_100_genes is not None:
        if hasattr(top_100_genes, "tolist"):
            top_100_genes = top_100_genes.tolist()
        adata_diff = adata[:, top_100_genes]
        stim_diff = adata_diff[adata_diff.obs[condition_key] == axis_keys["y"]]
        ctrl_diff = adata_diff[adata_diff.obs[condition_key] == axis_keys["x"]]
        x_diff = np.asarray(np.mean(ctrl_diff.X, axis=0)).ravel()
        y_diff = np.asarray(np.mean(stim_diff.X, axis=0)).ravel()
        m, b, r_value_diff, p_value_diff, std_err_diff = stats.linregress(
            x_diff, y_diff
        )
        if verbose:
            print(f"Top 100 DEGs mean R²: {r_value_diff**2:.3f}")

    x = np.asarray(np.mean(ctrl.X, axis=0)).ravel()
    y = np.asarray(np.mean(stim.X, axis=0)).ravel()
    m, b, r_value, p_value, std_err = stats.linregress(x, y)

    if verbose:
        print(f"All genes mean R²: {r_value**2:.3f}")

    # Create plot
    df = pd.DataFrame({axis_keys["x"]: x, axis_keys["y"]: y})
    sns.set_style("whitegrid")
    ax = sns.regplot(x=axis_keys["x"], y=axis_keys["y"], data=df, ax=ax)

    ax.tick_params(labelsize=fontsize)

    if "range" in kwargs:
        start, stop, step = kwargs.get("range")
        ax.set_xticks(np.arange(start, stop, step))
        ax.set_yticks(np.arange(start, stop, step))

    ax.set_xlabel(labels["x"], fontsize=fontsize)
    ax.set_ylabel(labels["y"], fontsize=fontsize)

    # Highlight specific genes
    if gene_list is not None and adjust_text:
        texts = []
        for gene in gene_list:
            if gene in adata.var_names:
                j = adata.var_names.get_loc(gene)
                x_bar = x[j]
                y_bar = y[j]
                texts.append(ax.text(x_bar, y_bar, gene, fontsize=11, color="black"))
                ax.plot(x_bar, y_bar, "o", color="red", markersize=5)

        adjust_text(
            texts,
            x=x,
            y=y,
            arrowprops=dict(arrowstyle="->", color="grey", lw=0.5),
            force_points=(0.0, 0.0),
        )

    if legend:
        ax.legend(loc="center left", bbox_to_anchor=(1, 0.5), fontsize=fontsize)

    if title:
        ax.set_title(title, fontsize=fontsize)

    # Add R² annotation
    ax.text(
        max(x) - max(x) * x_coeff,
        max(y) - y_coeff * max(y),
        r"$\mathrm{R^2_{\mathrm{\mathsf{all\ genes}}}}$= " + f"{r_value ** 2:.2f}",
        fontsize=kwargs.get("textsize", fontsize),
    )

    if top_100_genes is not None:
        ax.text(
            max(x) - max(x) * x_coeff,
            max(y) - (y_coeff + 0.15) * max(y),
            r"$\mathrm{R^2_{\mathrm{\mathsf{top\ 100\ DEGs}}}}$= "
            + f"{r_value_diff ** 2:.2f}",
            fontsize=kwargs.get("textsize", fontsize),
        )

    plt.tight_layout()

    if save and path_to_save:
        plt.savefig(path_to_save, bbox_inches="tight", dpi=150)
        print(f"Saved to {path_to_save}")

    if show:
        plt.show()
    else:
        plt.close()

    if top_100_genes is not None:
        return r_value**2, r_value_diff**2
    else:
        return r_value**2


def plot_regression_variance(
    model,
    adata,
    axis_keys: Dict[str, str],
    labels: Dict[str, str],
    gene_list: Optional[List[str]] = None,
    top_100_genes: Optional[List[str]] = None,
    path_to_save: Optional[str] = None,
    save: bool = True,
    show: bool = False,
    verbose: bool = False,
    legend: bool = True,
    title: Optional[str] = None,
    x_coeff: float = 0.30,
    y_coeff: float = 0.8,
    fontsize: int = 14,
    figsize: Tuple[int, int] = (8, 8),
    **kwargs
) -> Optional[float]:
    """
    Plot variance matching between predicted and real stimulated cells.

    This function plots the variance of genes in control vs predicted
    stimulated cells, showing how well the model captures the variance structure.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    adata : AnnData
        AnnData with control, predicted, and real stimulated cells
    axis_keys : dict
        Dictionary mapping conditions to keys
    labels : dict
        Dictionary of axis labels
    gene_list : list, optional
        List of specific genes to highlight
    top_100_genes : list, optional
        List of top DE genes for separate R² calculation
    path_to_save : str, optional
        Path to save the figure
    save : bool
        Whether to save the figure
    show : bool
        Whether to show the figure
    verbose : bool
        Print R² values
    legend : bool
        Show legend
    title : str, optional
        Plot title
    x_coeff : float
        X position coefficient for text
    y_coeff : float
        Y position coefficient for text
    fontsize : int
        Font size
    figsize : tuple
        Figure size
    **kwargs
        Additional arguments

    Returns
    -------
    float or tuple
        R² value(s)
    """
    import scanpy as sc

    fig, ax = plt.subplots(figsize=figsize)

    condition_key = model.adata_manager.get_state_registry(
        "batch"
    ).original_key

    # Get DEGs if not provided
    if top_100_genes is None:
        sc.tl.rank_genes_groups(
            adata, groupby=condition_key, n_genes=100, method="wilcoxon"
        )
        top_100_genes = adata.uns["rank_genes_groups"]["names"][axis_keys["y"]]

    stim = adata[adata.obs[condition_key] == axis_keys["y"]]
    ctrl = adata[adata.obs[condition_key] == axis_keys["x"]]

    if top_100_genes is not None:
        if hasattr(top_100_genes, "tolist"):
            top_100_genes = top_100_genes.tolist()
        adata_diff = adata[:, top_100_genes]
        stim_diff = adata_diff[adata_diff.obs[condition_key] == axis_keys["y"]]
        ctrl_diff = adata_diff[adata_diff.obs[condition_key] == axis_keys["x"]]
        x_diff = np.asarray(np.var(ctrl_diff.X, axis=0)).ravel()
        y_diff = np.asarray(np.var(stim_diff.X, axis=0)).ravel()
        m, b, r_value_diff, p_value_diff, std_err_diff = stats.linregress(
            x_diff, y_diff
        )
        if verbose:
            print(f"Top 100 DEGs var R²: {r_value_diff**2:.3f}")

    if "y1" in axis_keys.keys():
        real_stim = adata[adata.obs[condition_key] == axis_keys["y1"]]

    x = np.asarray(np.var(ctrl.X, axis=0)).ravel()
    y = np.asarray(np.var(stim.X, axis=0)).ravel()
    m, b, r_value, p_value, std_err = stats.linregress(x, y)

    if verbose:
        print(f"All genes var R²: {r_value**2:.3f}")

    df = pd.DataFrame({axis_keys["x"]: x, axis_keys["y"]: y})
    sns.set_style("whitegrid")
    ax = sns.regplot(x=axis_keys["x"], y=axis_keys["y"], data=df, ax=ax)

    ax.tick_params(labelsize=fontsize)

    if "range" in kwargs:
        start, stop, step = kwargs.get("range")
        ax.set_xticks(np.arange(start, stop, step))
        ax.set_yticks(np.arange(start, stop, step))

    ax.set_xlabel(labels["x"], fontsize=fontsize)
    ax.set_ylabel(labels["y"], fontsize=fontsize)

    # Plot real stimulated if provided
    if "y1" in axis_keys.keys():
        y1 = np.asarray(np.var(real_stim.X, axis=0)).ravel()
        ax.scatter(
            x, y1, marker="*", c="grey", alpha=0.5,
            label=f"{axis_keys['x']}-{axis_keys['y1']}"
        )

    # Highlight genes
    if gene_list is not None:
        for gene in gene_list:
            if gene in adata.var_names:
                j = adata.var_names.get_loc(gene)
                x_bar = x[j]
                y_bar = y[j]
                ax.text(x_bar, y_bar, gene, fontsize=11, color="black")
                ax.plot(x_bar, y_bar, "o", color="red", markersize=5)
                if "y1" in axis_keys.keys():
                    y1_bar = y1[j]
                    ax.text(x_bar, y1_bar, "*", color="black", alpha=0.5)

    if legend:
        ax.legend(loc="center left", bbox_to_anchor=(1, 0.5), fontsize=fontsize)

    if title:
        ax.set_title(title, fontsize=fontsize)

    ax.text(
        max(x) - max(x) * x_coeff,
        max(y) - y_coeff * max(y),
        r"$\mathrm{R^2_{\mathrm{\mathsf{all\ genes}}}}$= " + f"{r_value ** 2:.2f}",
        fontsize=kwargs.get("textsize", fontsize),
    )

    if top_100_genes is not None:
        ax.text(
            max(x) - max(x) * x_coeff,
            max(y) - (y_coeff + 0.15) * max(y),
            r"$\mathrm{R^2_{\mathrm{\mathsf{top\ 100\ DEGs}}}}$= "
            + f"{r_value_diff ** 2:.2f}",
            fontsize=kwargs.get("textsize", fontsize),
        )

    plt.tight_layout()

    if save and path_to_save:
        plt.savefig(path_to_save, bbox_inches="tight", dpi=150)
        print(f"Saved to {path_to_save}")

    if show:
        plt.show()
    else:
        plt.close()

    if top_100_genes is not None:
        return r_value**2, r_value_diff**2
    else:
        return r_value**2


def binary_classifier_scores(
    model,
    adata,
    delta: np.ndarray,
    ctrl_key: str,
    stim_key: str
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate binary classifier scores for cells.

    Computes the dot product between the perturbation vector (delta)
    and the latent representation of each cell.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    adata : AnnData
        AnnData containing control and stimulated cells
    delta : np.ndarray
        Perturbation vector
    ctrl_key : str
        Control condition label
    stim_key : str
        Stimulated condition label

    Returns
    -------
    tuple
        (control_scores, stimulated_scores)
    """
    condition_key = model.adata_manager.get_state_registry(
        "batch"
    ).original_key

    cd = adata[adata.obs[condition_key] == ctrl_key, :]
    stim = adata[adata.obs[condition_key] == stim_key, :]

    latent_cd = model.get_latent_representation(cd)
    latent_stim = model.get_latent_representation(stim)

    dot_cd = np.array([np.dot(delta, vec) for vec in latent_cd])
    dot_stim = np.array([np.dot(delta, vec) for vec in latent_stim])

    return dot_cd, dot_stim


def plot_binary_classifier(
    model,
    adata,
    delta: np.ndarray,
    ctrl_key: str,
    stim_key: str,
    path_to_save: Optional[str] = None,
    save: bool = True,
    show: bool = False,
    fontsize: int = 14,
    figsize: Tuple[int, int] = (8, 6)
) -> None:
    """
    Plot binary classifier distribution.

    Visualizes the separation between control and stimulated cells
    based on their projection onto the perturbation vector.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    adata : AnnData
        AnnData with control and stimulated cells
    delta : np.ndarray
        Perturbation vector
    ctrl_key : str
        Control condition label
    stim_key : str
        Stimulated condition label
    path_to_save : str, optional
        Path to save figure
    save : bool
        Whether to save figure
    show : bool
        Whether to show figure
    fontsize : int
        Font size
    figsize : tuple
        Figure size
    """
    fig, ax = plt.subplots(figsize=figsize)

    dot_cd, dot_stim = binary_classifier_scores(
        model, adata, delta, ctrl_key, stim_key
    )

    ax.hist(dot_cd, label=ctrl_key, bins=50, alpha=0.7, color='blue')
    ax.hist(dot_stim, label=stim_key, bins=50, alpha=0.7, color='red')

    ax.axvline(0, color="k", linestyle="dashed", linewidth=1)
    ax.set_xlabel("Dot Product with Perturbation Vector", fontsize=fontsize)
    ax.set_ylabel("Frequency", fontsize=fontsize)
    ax.set_title("Binary Classifier Distribution", fontsize=fontsize)
    ax.legend(fontsize=fontsize)
    ax.grid(False)

    ax.tick_params(labelsize=fontsize)

    plt.tight_layout()

    if save and path_to_save:
        plt.savefig(path_to_save, bbox_inches="tight", dpi=150)
        print(f"Saved to {path_to_save}")

    if show:
        plt.show()
    else:
        plt.close()


def plot_latent_space(
    model,
    adata,
    color_by: str,
    ctrl_key: Optional[str] = None,
    stim_key: Optional[str] = None,
    path_to_save: Optional[str] = None,
    save: bool = True,
    show: bool = False,
    figsize: Tuple[int, int] = (10, 8),
    **kwargs
) -> None:
    """
    Plot cells in latent space.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    adata : AnnData
        AnnData to plot
    color_by : str
        Column in adata.obs to color by
    ctrl_key : str, optional
        Control key for filtering
    stim_key : str, optional
        Stimulated key for filtering
    path_to_save : str, optional
        Path to save figure
    save : bool
        Whether to save
    show : bool
        Whether to show
    figsize : tuple
        Figure size
    **kwargs
        Additional arguments for scatter plot
    """
    import scanpy as sc

    # Get latent representation
    latent = model.get_latent_representation(adata)

    # Create AnnData from latent space
    adata_latent = sc.AnnData(latent)
    adata_latent.obs = adata.obs.copy()

    # Compute neighbors and UMAP in latent space
    sc.pp.neighbors(adata_latent, n_neighbors=15)
    sc.tl.umap(adata_latent)

    fig, ax = plt.subplots(figsize=figsize)

    sc.pl.umap(
        adata_latent,
        color=color_by,
        ax=ax,
        show=False,
        **kwargs
    )

    plt.tight_layout()

    if save and path_to_save:
        plt.savefig(path_to_save, bbox_inches="tight", dpi=150)
        print(f"Saved to {path_to_save}")

    if show:
        plt.show()
    else:
        plt.close()


def plot_perturbation_vector(
    delta: np.ndarray,
    gene_names: Optional[List[str]] = None,
    top_n: int = 20,
    path_to_save: Optional[str] = None,
    save: bool = True,
    show: bool = False,
    figsize: Tuple[int, int] = (10, 6)
) -> None:
    """
    Plot the perturbation vector components.

    Visualizes the magnitude of each dimension in the perturbation
    vector to understand which latent dimensions are most affected.

    Parameters
    ----------
    delta : np.ndarray
        Perturbation vector
    gene_names : list, optional
        Names for each component (if decoding to gene space)
    top_n : int
        Number of top components to show
    path_to_save : str, optional
        Path to save figure
    save : bool
        Whether to save
    show : bool
        Whether to show
    figsize : tuple
        Figure size
    """
    fig, ax = plt.subplots(figsize=figsize)

    # Get absolute values and sort
    abs_delta = np.abs(delta)
    sorted_idx = np.argsort(abs_delta)[::-1][:top_n]

    x_pos = np.arange(len(sorted_idx))
    values = delta[sorted_idx]

    colors = ['red' if v > 0 else 'blue' for v in values]

    ax.bar(x_pos, values, color=colors, alpha=0.7)
    ax.set_xlabel("Latent Dimension", fontsize=12)
    ax.set_ylabel("Perturbation Magnitude", fontsize=12)
    ax.set_title(f"Top {top_n} Perturbation Vector Components", fontsize=14)
    ax.axhline(0, color='black', linestyle='-', linewidth=0.5)

    plt.tight_layout()

    if save and path_to_save:
        plt.savefig(path_to_save, bbox_inches="tight", dpi=150)
        print(f"Saved to {path_to_save}")

    if show:
        plt.show()
    else:
        plt.close()


def plot_training_history(
    model,
    path_to_save: Optional[str] = None,
    save: bool = True,
    show: bool = False,
    figsize: Tuple[int, int] = (10, 6)
) -> None:
    """
    Plot scGen training history.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    path_to_save : str, optional
        Path to save figure
    save : bool
        Whether to save
    show : bool
        Whether to show
    figsize : tuple
        Figure size
    """
    if not hasattr(model, 'history'):
        warnings.warn("Model has no training history")
        return

    history = model.history

    fig, ax = plt.subplots(figsize=figsize)

    # Plot loss curves
    if 'train_loss_epoch' in history:
        ax.plot(history['train_loss_epoch'], label='Train Loss', linewidth=2)
    if 'validation_loss' in history:
        ax.plot(history['validation_loss'], label='Validation Loss', linewidth=2)

    ax.set_xlabel('Epoch', fontsize=12)
    ax.set_ylabel('Loss', fontsize=12)
    ax.set_title('scGen Training History', fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if save and path_to_save:
        plt.savefig(path_to_save, bbox_inches="tight", dpi=150)
        print(f"Saved to {path_to_save}")

    if show:
        plt.show()
    else:
        plt.close()


def plot_prediction_comparison(
    adata_ctrl,
    adata_stim_real,
    adata_stim_pred,
    genes: List[str],
    path_to_save: Optional[str] = None,
    save: bool = True,
    show: bool = False,
    figsize: Tuple[int, int] = None
) -> None:
    """
    Plot comparison of control, real stimulated, and predicted stimulated cells.

    Creates violin plots for specified genes comparing expression across
    the three conditions.

    Parameters
    ----------
    adata_ctrl : AnnData
        Control cells
    adata_stim_real : AnnData
        Real stimulated cells
    adata_stim_pred : AnnData
        Predicted stimulated cells
    genes : list
        Genes to plot
    path_to_save : str, optional
        Path to save figure
    save : bool
        Whether to save
    show : bool
        Whether to show
    figsize : tuple
        Figure size (auto-calculated if None)
    """
    import seaborn as sns

    n_genes = len(genes)
    if figsize is None:
        figsize = (3 * n_genes, 6)

    fig, axes = plt.subplots(1, n_genes, figsize=figsize, sharey=True)

    if n_genes == 1:
        axes = [axes]

    for idx, gene in enumerate(genes):
        ax = axes[idx]

        # Get expression values
        ctrl_vals = adata_ctrl[:, gene].X.toarray().ravel() if hasattr(adata_ctrl[:, gene].X, 'toarray') else adata_ctrl[:, gene].X.ravel()
        real_vals = adata_stim_real[:, gene].X.toarray().ravel() if hasattr(adata_stim_real[:, gene].X, 'toarray') else adata_stim_real[:, gene].X.ravel()
        pred_vals = adata_stim_pred[:, gene].X.ravel()

        data = pd.DataFrame({
            'Expression': np.concatenate([ctrl_vals, real_vals, pred_vals]),
            'Condition': ['Control'] * len(ctrl_vals) +
                        ['Real Stim'] * len(real_vals) +
                        ['Predicted'] * len(pred_vals)
        })

        sns.violinplot(data=data, x='Condition', y='Expression', ax=ax)
        ax.set_title(gene, fontsize=12)
        ax.tick_params(axis='x', rotation=45)

    plt.tight_layout()

    if save and path_to_save:
        plt.savefig(path_to_save, bbox_inches="tight", dpi=150)
        print(f"Saved to {path_to_save}")

    if show:
        plt.show()
    else:
        plt.close()
