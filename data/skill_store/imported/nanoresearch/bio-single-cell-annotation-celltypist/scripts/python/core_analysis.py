"""Core analysis functions for CellTypist automated cell type annotation.

This module provides wrapper functions for the CellTypist package, which performs
automated cell type annotation using pre-trained logistic regression models.

Reference: Domínguez Conde et al., Science 2022
"""

import os
import numpy as np
import pandas as pd
import scanpy as sc
import celltypist
from anndata import AnnData
from typing import Optional, Union, List, Dict, Any
from pathlib import Path


def validate_celltypist_input(
    adata: AnnData,
    check_normalized: bool = True
) -> Dict[str, Any]:
    """Validate input AnnData for CellTypist annotation.

    Args:
        adata: Input AnnData object
        check_normalized: Whether to check for normalized data

    Returns:
        Dictionary with validation results
    """
    results = {'valid': True, 'warnings': [], 'errors': []}

    # Check dimensions
    if adata.n_obs == 0 or adata.n_vars == 0:
        results['errors'].append("Empty AnnData object")
        results['valid'] = False
        return results

    # Check if data is log-normalized
    if check_normalized and adata.n_obs > 0 and adata.n_vars > 0:
        try:
            # Sample up to 1000 cells for efficiency
            sample_size = min(1000, adata.n_obs)
            x_sample = adata.X[:sample_size]
            if hasattr(x_sample, 'toarray'):
                x_sample = x_sample.toarray()
            max_val = float(np.max(x_sample))
            # Heuristic: raw counts are integers; log-normalized values are continuous.
            # This is not perfect but catches the most common case.
            if max_val > 50 and float(max_val).is_integer():
                results['warnings'].append(
                    "Data appears to be raw counts (large integer values). "
                    "CellTypist expects log-normalized data: sc.pp.normalize_total(adata, target_sum=1e4); sc.pp.log1p(adata)"
                )
        except Exception:
            pass  # Skip normalization check if sampling fails

    # Check for gene symbols (not ENSEMBL)
    var_names = adata.var_names[:10]
    ensembl_count = sum(1 for name in var_names if str(name).startswith('ENSG') or str(name).startswith('ENSMUSG'))
    if ensembl_count >= 5:
        results['warnings'].append(
            "Data appears to use ENSEMBL IDs. CellTypist models expect gene symbols (e.g., CD3D, CD19)."
        )

    results['n_cells'] = adata.n_obs
    results['n_genes'] = adata.n_vars

    return results


def get_available_models() -> pd.DataFrame:
    """Get list of available CellTypist models.

    Returns:
        DataFrame with model information
    """
    try:
        models_df = celltypist.models.models_description()
        return models_df
    except Exception as e:
        print(f"Error fetching models: {e}")
        return pd.DataFrame()


def download_celltypist_model(
    model: str = 'Immune_All_Low.pkl',
    force: bool = False
) -> str:
    """Download a CellTypist model.

    Args:
        model: Model name or path
        force: Whether to re-download if already exists

    Returns:
        Path to the downloaded model
    """
    # Check if model already exists locally
    if not force:
        try:
            celltypist.models.Model.load(model)
            print(f"Model '{model}' already available locally")
            return model
        except Exception:
            pass

    # Download model
    print(f"Downloading model: {model}")
    celltypist.models.download_models(model=model, force_update=force)
    return model


def load_celltypist_model(
    model: Union[str, celltypist.models.Model]
) -> celltypist.models.Model:
    """Load a CellTypist model.

    Args:
        model: Model name, path, or Model object

    Returns:
        Loaded Model object
    """
    if isinstance(model, celltypist.models.Model):
        return model

    # Try to load, download if needed
    try:
        return celltypist.models.Model.load(model)
    except FileNotFoundError:
        print(f"Model not found locally, downloading: {model}")
        download_celltypist_model(model)
        return celltypist.models.Model.load(model)


def annotate_cells(
    adata: AnnData,
    model: Union[str, celltypist.models.Model] = 'Immune_All_Low.pkl',
    mode: str = 'best match',
    p_thres: float = 0.5,
    majority_voting: bool = True,
    over_clustering: Optional[Union[str, np.ndarray, pd.Series]] = None,
    use_GPU: bool = False,
    min_prop: float = 0,
    copy: bool = False
) -> celltypist.classifier.AnnotationResult:
    """Run CellTypist cell type annotation.

    This is the main annotation function that predicts cell types using
    pre-trained CellTypist models.

    Args:
        adata: AnnData object with log-normalized data
        model: Pre-trained model name or Model object
        mode: 'best match' (single label) or 'prob match' (multi-label)
        p_thres: Probability threshold for multi-label mode
        majority_voting: Whether to refine predictions via cluster consensus
        over_clustering: Cluster assignments for majority voting. Can be:
            - str: column name in adata.obs
            - array/Series: explicit cluster labels
        use_GPU: Whether to use GPU for over-clustering (Leiden only)
        min_prop: Minimum proportion for subcluster assignment
        copy: Whether to copy AnnData before annotation

    Returns:
        AnnotationResult object with predictions
    """
    if copy:
        adata = adata.copy()

    # Load model if string
    if isinstance(model, str):
        model = load_celltypist_model(model)

    print(f"Running CellTypist annotation with model: {model}")
    print(f"  Mode: {mode}")
    print(f"  Majority voting: {majority_voting}")

    # Run annotation
    predictions = celltypist.annotate(
        adata,
        model=model,
        mode=mode,
        p_thres=p_thres,
        majority_voting=majority_voting,
        over_clustering=over_clustering,
        use_GPU=use_GPU,
        min_prop=min_prop
    )

    print(f"Annotation complete for {predictions.cell_count} cells")

    return predictions


def add_predictions_to_adata(
    predictions: celltypist.classifier.AnnotationResult,
    insert_labels: bool = True,
    insert_conf: bool = True,
    insert_conf_by: str = 'predicted_labels',
    insert_prob: bool = False,
    insert_decision: bool = False,
    prefix: str = 'celltypist_'
) -> AnnData:
    """Add CellTypist predictions to AnnData object.

    Args:
        predictions: AnnotationResult from annotate_cells
        insert_labels: Whether to insert predicted labels
        insert_conf: Whether to insert confidence scores
        insert_conf_by: Which prediction to use for confidence ('predicted_labels' or 'majority_voting')
        insert_prob: Whether to insert probability matrix
        insert_decision: Whether to insert decision matrix
        prefix: Prefix for inserted column names

    Returns:
        AnnData with predictions added
    """
    adata = predictions.to_adata(
        insert_labels=insert_labels,
        insert_conf=insert_conf,
        insert_conf_by=insert_conf_by,
        insert_prob=insert_prob,
        insert_decision=insert_decision,
        prefix=prefix
    )

    # Create convenience column: prefer majority_voting if available
    if insert_labels:
        mv_col = f"{prefix}majority_voting"
        pl_col = f"{prefix}predicted_labels"
        if mv_col in adata.obs.columns:
            adata.obs[f"{prefix}label"] = adata.obs[mv_col]
        elif pl_col in adata.obs.columns:
            adata.obs[f"{prefix}label"] = adata.obs[pl_col]

    return adata


def run_celltypist_annotation(
    adata: AnnData,
    model: Union[str, celltypist.models.Model] = 'Immune_All_Low.pkl',
    majority_voting: bool = True,
    over_clustering: Optional[Union[str, np.ndarray, pd.Series]] = None,
    mode: str = 'best match',
    copy: bool = False,
    prefix: str = 'celltypist_'
) -> AnnData:
    """Complete CellTypist annotation pipeline.

    This function runs the full annotation workflow and adds results to AnnData.

    Args:
        adata: AnnData object with log-normalized data
        model: Pre-trained model name or Model object
        majority_voting: Whether to use cluster consensus
        over_clustering: Cluster assignments for majority voting
        mode: Prediction mode ('best match' or 'prob match')
        copy: Whether to copy AnnData
        prefix: Prefix for output columns

    Returns:
        AnnData with predictions added
    """
    if copy:
        adata = adata.copy()

    # Validate input
    validation = validate_celltypist_input(adata)
    if validation['warnings']:
        for warning in validation['warnings']:
            print(f"⚠️  Warning: {warning}")

    # Run annotation
    predictions = annotate_cells(
        adata,
        model=model,
        majority_voting=majority_voting,
        over_clustering=over_clustering,
        mode=mode
    )

    # Add to AnnData
    adata = add_predictions_to_adata(predictions, prefix=prefix)

    return adata


def filter_by_confidence(
    adata: AnnData,
    conf_col: str = 'celltypist_conf_score',
    label_col: str = 'celltypist_label',
    threshold: float = 0.5,
    unassigned_label: str = 'Unassigned'
) -> AnnData:
    """Filter CellTypist predictions by confidence score.

    Args:
        adata: AnnData with CellTypist predictions
        conf_col: Column with confidence scores
        label_col: Column with predicted labels
        threshold: Minimum confidence threshold
        unassigned_label: Label for low-confidence cells

    Returns:
        AnnData with filtered column added
    """
    if conf_col not in adata.obs.columns:
        for alt in ['conf_score', 'celltypist_conf_score']:
            if alt in adata.obs.columns:
                conf_col = alt
                break
        else:
            raise ValueError(f"Confidence column '{conf_col}' not found in adata.obs. "
                           f"Available: {list(adata.obs.columns)}")

    original_label_col = label_col
    if label_col not in adata.obs.columns:
        for alt in ['celltypist_label', 'majority_voting', 'predicted_labels']:
            if alt in adata.obs.columns:
                label_col = alt
                break
        else:
            raise ValueError(f"Label column '{label_col}' not found in adata.obs. "
                           f"Available: {list(adata.obs.columns)}")

    out_col = f'{original_label_col}_filtered'
    adata.obs[out_col] = np.where(
        adata.obs[conf_col] >= threshold,
        adata.obs[label_col],
        unassigned_label
    )

    n_unassigned = (adata.obs[out_col] == unassigned_label).sum()
    print(f"Filtered {n_unassigned} cells ({n_unassigned/adata.n_obs*100:.1f}%) below confidence threshold {threshold}")

    return adata


def get_model_info(model: Union[str, celltypist.models.Model]) -> Dict[str, Any]:
    """Get information about a CellTypist model.

    Args:
        model: Model name or Model object

    Returns:
        Dictionary with model information
    """
    if isinstance(model, str):
        model = load_celltypist_model(model)

    info = {
        'cell_types': list(model.cell_types),
        'n_cell_types': len(model.cell_types),
        'n_features': len(model.features),
        'features': list(model.features),
        'description': getattr(model, 'description', '')
    }

    return info


def compare_models(
    adata: AnnData,
    models: List[str],
    majority_voting: bool = True
) -> pd.DataFrame:
    """Compare predictions from multiple CellTypist models.

    Args:
        adata: AnnData object
        models: List of model names to compare
        majority_voting: Whether to use majority voting

    Returns:
        DataFrame with comparison results
    """
    results = []

    for model_name in models:
        print(f"Running annotation with: {model_name}")
        predictions = annotate_cells(
            adata,
            model=model_name,
            majority_voting=majority_voting
        )

        # Get summary
        freq = predictions.summary_frequency(
            by='majority_voting' if majority_voting else 'predicted_labels'
        )
        results.append({
            'model': model_name,
            'n_cell_types': len(freq),
            'top_cell_type': freq.index[0] if len(freq) > 0 else None,
            'top_fraction': freq.iloc[0] if len(freq) > 0 else None,
        })

    return pd.DataFrame(results)


def train_celltypist_model(
    adata: AnnData,
    labels: Union[str, np.ndarray, pd.Series],
    genes: Optional[List[str]] = None,
    model_file: Optional[str] = None,
    **kwargs
) -> celltypist.models.Model:
    """Train a custom CellTypist model.

    Args:
        adata: Training data (AnnData or path)
        labels: Cell type labels (column name in adata.obs or array)
        genes: Gene list for training
        model_file: Output path for saving model
        **kwargs: Additional arguments for celltypist.train
            Common kwargs: use_SGD=True, mini_batch=True, balance_cell_type=True,
            max_iter=500, alpha=0.0001, feature_selection=True, top_genes=300

    Returns:
        Trained Model object
    """
    print(f"Training CellTypist model with {adata.n_obs} cells")

    # Train model
    model = celltypist.train(
        adata,
        labels=labels,
        genes=genes,
        **kwargs
    )

    # Save if path provided
    if model_file:
        model.write(model_file)
        print(f"Model saved to: {model_file}")

    return model
