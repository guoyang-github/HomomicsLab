"""
Utility Functions for scGen
============================

Helper functions for data manipulation, validation, and analysis utilities.
"""

import numpy as np
import pandas as pd
import scanpy as sc
from typing import Optional, Union, List, Dict, Tuple, Any
import warnings


def balancer(
    adata,
    cell_type_key: str
) -> Any:
    """
    Balance cell type populations by upsampling minority classes.

    Makes all cell type populations equal by randomly upsampling
    minority classes to match the majority class.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    cell_type_key : str
        Column in .obs containing cell type labels

    Returns
    -------
    AnnData
        Balanced AnnData with equal cell type populations
    """
    class_names = np.unique(adata.obs[cell_type_key])
    class_pop = {}

    for cls in class_names:
        class_pop[cls] = adata[adata.obs[cell_type_key] == cls].shape[0]

    max_number = np.max(list(class_pop.values()))
    index_all = []

    for cls in class_names:
        class_index = np.array(adata.obs[cell_type_key] == cls)
        index_cls = np.nonzero(class_index)[0]
        # Upsample with replacement if needed
        if len(index_cls) < max_number:
            index_cls_r = np.random.choice(len(index_cls), max_number, replace=True)
            index_cls = index_cls[index_cls_r]
        else:
            index_cls_r = np.random.choice(len(index_cls), max_number, replace=False)
            index_cls = index_cls[index_cls_r]
        index_all.append(index_cls)

    balanced_data = adata[np.concatenate(index_all)].copy()
    return balanced_data


def extractor(
    adata,
    cell_type: str,
    condition_key: str,
    cell_type_key: str,
    ctrl_key: str,
    stim_key: str
) -> List[Any]:
    """
    Extract data subsets for a specific cell type.

    Returns training and test data subsets for leave-one-cell-type-out
    validation or training.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    cell_type : str
        Specific cell type to extract
    condition_key : str
        Column with condition labels
    cell_type_key : str
        Column with cell type labels
    ctrl_key : str
        Control condition label
    stim_key : str
        Stimulated condition label

    Returns
    -------
    list
        [training_data, control_cells, stimulated_cells, all_cell_type_cells]
    """
    cell_with_both_condition = adata[adata.obs[cell_type_key] == cell_type]
    condition_1 = adata[
        (adata.obs[cell_type_key] == cell_type) & (adata.obs[condition_key] == ctrl_key)
    ]
    condition_2 = adata[
        (adata.obs[cell_type_key] == cell_type) & (adata.obs[condition_key] == stim_key)
    ]
    training = adata[
        ~(
            (adata.obs[cell_type_key] == cell_type) &
            (adata.obs[condition_key] == stim_key)
        )
    ]
    return [training, condition_1, condition_2, cell_with_both_condition]


def get_condition_statistics(
    adata,
    condition_key: str,
    cell_type_key: Optional[str] = None
) -> pd.DataFrame:
    """
    Get statistics for each condition (and cell type if specified).

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    condition_key : str
        Column with condition labels
    cell_type_key : str, optional
        Column with cell type labels

    Returns
    -------
    pd.DataFrame
        Statistics DataFrame
    """
    stats = []

    if cell_type_key:
        for ct in adata.obs[cell_type_key].unique():
            ct_data = adata[adata.obs[cell_type_key] == ct]
            for cond in ct_data.obs[condition_key].unique():
                cond_data = ct_data[ct_data.obs[condition_key] == cond]
                stats.append({
                    'cell_type': ct,
                    'condition': cond,
                    'n_cells': len(cond_data),
                    'mean_expression': np.mean(cond_data.X.sum(axis=1)),
                    'median_expression': np.median(cond_data.X.sum(axis=1))
                })
    else:
        for cond in adata.obs[condition_key].unique():
            cond_data = adata[adata.obs[condition_key] == cond]
            stats.append({
                'condition': cond,
                'n_cells': len(cond_data),
                'mean_expression': np.mean(cond_data.X.sum(axis=1)),
                'median_expression': np.median(cond_data.X.sum(axis=1))
            })

    return pd.DataFrame(stats)


def evaluate_prediction_accuracy(
    adata_pred,
    adata_real,
    condition_key: str,
    pred_label: str = "predicted",
    real_label: str = "stimulated",
    top_n_genes: int = 100
) -> Dict[str, float]:
    """
    Evaluate prediction accuracy by comparing predicted vs real stimulated cells.

    Parameters
    ----------
    adata_pred : AnnData
        Predicted stimulated cells
    adata_real : AnnData
        Real stimulated cells
    condition_key : str
        Column with condition labels
    pred_label : str
        Label for predicted cells
    real_label : str
        Label for real cells
    top_n_genes : int
        Number of top variable genes to consider

    Returns
    -------
    dict
        Dictionary with accuracy metrics
    """
    from scipy.stats import pearsonr, spearmanr

    # Get mean expression
    pred_mean = np.array(adata_pred.X.mean(axis=0)).ravel()
    real_mean = np.array(adata_real.X.mean(axis=0)).ravel()

    # Overall correlation
    pearson_all, _ = pearsonr(pred_mean, real_mean)
    spearman_all, _ = spearmanr(pred_mean, real_mean)

    # Correlation for top variable genes
    gene_var = np.var(np.vstack([pred_mean, real_mean]), axis=0)
    top_genes_idx = np.argsort(gene_var)[-top_n_genes:]

    pearson_top, _ = pearsonr(pred_mean[top_genes_idx], real_mean[top_genes_idx])
    spearman_top, _ = spearmanr(pred_mean[top_genes_idx], real_mean[top_genes_idx])

    # R² for all genes
    ss_res = np.sum((real_mean - pred_mean) ** 2)
    ss_tot = np.sum((real_mean - np.mean(real_mean)) ** 2)
    r2_all = 1 - (ss_res / ss_tot)

    # R² for top genes
    ss_res_top = np.sum((real_mean[top_genes_idx] - pred_mean[top_genes_idx]) ** 2)
    ss_tot_top = np.sum((real_mean[top_genes_idx] - np.mean(real_mean[top_genes_idx])) ** 2)
    r2_top = 1 - (ss_res_top / ss_tot_top)

    return {
        'pearson_all': pearson_all,
        'spearman_all': spearman_all,
        'pearson_top_{}'.format(top_n_genes): pearson_top,
        'spearman_top_{}'.format(top_n_genes): spearman_top,
        'r2_all': r2_all,
        'r2_top_{}'.format(top_n_genes): r2_top
    }


def compare_perturbation_vectors(
    delta1: np.ndarray,
    delta2: np.ndarray,
    label1: str = "Vector 1",
    label2: str = "Vector 2"
) -> Dict[str, float]:
    """
    Compare two perturbation vectors.

    Parameters
    ----------
    delta1 : np.ndarray
        First perturbation vector
    delta2 : np.ndarray
        Second perturbation vector
    label1 : str
        Label for first vector
    label2 : str
        Label for second vector

    Returns
    -------
    dict
        Comparison metrics
    """
    from scipy.spatial.distance import cosine
    from scipy.stats import pearsonr, spearmanr

    # Cosine similarity
    cos_sim = 1 - cosine(delta1, delta2)

    # Correlations
    pearson, pearson_p = pearsonr(delta1, delta2)
    spearman, spearman_p = spearmanr(delta1, delta2)

    # Euclidean distance
    euclidean_dist = np.linalg.norm(delta1 - delta2)

    # Magnitude comparison
    mag1 = np.linalg.norm(delta1)
    mag2 = np.linalg.norm(delta2)

    return {
        'cosine_similarity': cos_sim,
        'pearson_r': pearson,
        'pearson_pvalue': pearson_p,
        'spearman_r': spearman,
        'spearman_pvalue': spearman_p,
        'euclidean_distance': euclidean_dist,
        'magnitude_{}'.format(label1.replace(' ', '_')): mag1,
        'magnitude_{}'.format(label2.replace(' ', '_')): mag2
    }


def get_high_confidence_predictions(
    adata_pred,
    adata_real,
    confidence_threshold: float = 0.8
) -> pd.DataFrame:
    """
    Identify high confidence predictions based on correlation.

    Parameters
    ----------
    adata_pred : AnnData
        Predicted cells
    adata_real : AnnData
        Real cells
    confidence_threshold : float
        Minimum correlation for high confidence

    Returns
    -------
    pd.DataFrame
        DataFrame with confidence scores
    """
    from scipy.stats import pearsonr

    results = []

    for i in range(adata_pred.n_obs):
        pred_cell = np.array(adata_pred[i].X).ravel()
        real_cell = np.array(adata_real[i].X).ravel()

        corr, pval = pearsonr(pred_cell, real_cell)

        results.append({
            'cell_idx': i,
            'correlation': corr,
            'pvalue': pval,
            'high_confidence': corr >= confidence_threshold
        })

    return pd.DataFrame(results)


def create_prediction_report(
    model,
    adata,
    predicted_adata,
    delta: np.ndarray,
    ctrl_key: str,
    stim_key: str,
    output_file: Optional[str] = None
) -> str:
    """
    Create a comprehensive prediction report.

    Parameters
    ----------
    model : SCGEN
        Trained model
    adata : AnnData
        Original data
    predicted_adata : AnnData
        Predicted data
    delta : np.ndarray
        Perturbation vector
    ctrl_key : str
        Control key
    stim_key : str
        Stimulated key
    output_file : str, optional
        Path to save report

    Returns
    -------
    str
        Report text
    """
    lines = [
        "=" * 60,
        "scGen Prediction Report",
        "=" * 60,
        "",
        f"Analysis Date: {pd.Timestamp.now()}",
        "",
        "Model Configuration:",
        f"  Hidden layers: {model.module.n_hidden}",
        f"  Latent dimension: {model.module.n_latent}",
        f"  N layers: {model.module.n_layers}",
        "",
        "Data Statistics:",
        f"  Original cells: {adata.n_obs}",
        f"  Predicted cells: {predicted_adata.n_obs}",
        f"  Genes: {adata.n_vars}",
        "",
        "Prediction Parameters:",
        f"  Control key: {ctrl_key}",
        f"  Stimulated key: {stim_key}",
        "",
        "Perturbation Vector:",
        f"  Shape: {delta.shape}",
        f"  Mean: {np.mean(delta):.4f}",
        f"  Std: {np.std(delta):.4f}",
        f"  Min: {np.min(delta):.4f}",
        f"  Max: {np.max(delta):.4f}",
        f"  L2 Norm: {np.linalg.norm(delta):.4f}",
        "",
        "=" * 60
    ]

    report = "\n".join(lines)

    if output_file:
        with open(output_file, 'w') as f:
            f.write(report)
        print(f"Report saved to {output_file}")

    return report


def merge_predictions(
    adata_ctrl,
    adata_real_stim,
    adata_pred_stim,
    condition_key: str = "condition",
    label_ctrl: str = "control",
    label_real: str = "stimulated",
    label_pred: str = "predicted"
) -> Any:
    """
    Merge control, real stimulated, and predicted stimulated cells.

    Parameters
    ----------
    adata_ctrl : AnnData
        Control cells
    adata_real_stim : AnnData
        Real stimulated cells
    adata_pred_stim : AnnData
        Predicted stimulated cells
    condition_key : str
        Column name for condition labels
    label_ctrl : str
        Label for control cells
    label_real : str
        Label for real stimulated cells
    label_pred : str
        Label for predicted cells

    Returns
    -------
    AnnData
        Merged AnnData with condition labels
    """
    # Add condition labels
    adata_ctrl = adata_ctrl.copy()
    adata_real_stim = adata_real_stim.copy()
    adata_pred_stim = adata_pred_stim.copy()

    adata_ctrl.obs[condition_key] = label_ctrl
    adata_real_stim.obs[condition_key] = label_real
    adata_pred_stim.obs[condition_key] = label_pred

    # Concatenate
    merged = sc.concat([adata_ctrl, adata_real_stim, adata_pred_stim])

    return merged


def check_gpu_availability() -> bool:
    """
    Check if GPU is available for training.

    Returns
    -------
    bool
        True if GPU is available
    """
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def get_recommended_hvg_number(
    n_cells: int,
    n_genes: int
) -> int:
    """
    Get recommended number of highly variable genes based on dataset size.

    Parameters
    ----------
    n_cells : int
        Number of cells
    n_genes : int
        Number of genes

    Returns
    -------
    int
        Recommended number of HVGs
    """
    if n_cells < 1000:
        return min(2000, n_genes)
    elif n_cells < 10000:
        return min(5000, n_genes)
    else:
        return min(7000, n_genes)


def subsample_data(
    adata,
    target_cells: int,
    condition_key: Optional[str] = None,
    random_state: int = 42
) -> Any:
    """
    Subsample data to target number of cells.

    Maintains proportional representation of conditions if specified.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    target_cells : int
        Target number of cells
    condition_key : str, optional
        Condition key for stratified sampling
    random_state : int
        Random seed

    Returns
    -------
    AnnData
        Subsampled AnnData
    """
    np.random.seed(random_state)

    if adata.n_obs <= target_cells:
        return adata

    if condition_key:
        # Stratified sampling
        indices = []
        for cond in adata.obs[condition_key].unique():
            cond_data = adata[adata.obs[condition_key] == cond]
            cond_target = int(target_cells * len(cond_data) / len(adata))
            cond_idx = np.random.choice(cond_data.obs_names, cond_target, replace=False)
            indices.extend(cond_idx)
        return adata[indices].copy()
    else:
        # Random sampling
        indices = np.random.choice(adata.obs_names, target_cells, replace=False)
        return adata[indices].copy()
