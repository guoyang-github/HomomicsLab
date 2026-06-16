"""
Core Analysis Functions for scGen
==================================

This module provides wrapper functions for scGen perturbation modeling,
including model training, batch correction, and perturbation prediction.

scGen is a VAE-based generative model for predicting single-cell perturbation responses.
Reference: Lotfollahi et al., Nature Methods 2019
"""

import numpy as np
import pandas as pd
import scanpy as sc
from typing import Optional, Union, List, Dict, Tuple, Any
import warnings


def check_scgen_dependencies() -> bool:
    """
    Check if required dependencies are installed.

    Returns
    -------
    bool
        True if all dependencies are available
    """
    try:
        import scgen
        import torch
        import scvi
        return True
    except ImportError as e:
        raise ImportError(
            f"Missing dependency: {e}. "
            "Install with: pip install scgen scvi-tools torch"
        )


def validate_perturbation_data(
    adata,
    condition_key: str,
    cell_type_key: Optional[str] = None,
    min_cells_per_condition: int = 100
) -> Dict[str, Any]:
    """
    Validate AnnData object for scGen analysis.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    condition_key : str
        Column in .obs containing condition labels (e.g., 'control', 'stimulated')
    cell_type_key : str, optional
        Column in .obs containing cell type labels
    min_cells_per_condition : int
        Minimum number of cells required per condition

    Returns
    -------
    dict
        Validation results with statistics
    """
    if condition_key not in adata.obs.columns:
        raise ValueError(f"Condition key '{condition_key}' not found in adata.obs")

    if cell_type_key and cell_type_key not in adata.obs.columns:
        raise ValueError(f"Cell type key '{cell_type_key}' not found in adata.obs")

    # Check conditions
    conditions = adata.obs[condition_key].unique()
    if len(conditions) < 2:
        raise ValueError(f"Need at least 2 conditions, found {len(conditions)}")

    # Check cell counts per condition
    condition_counts = adata.obs[condition_key].value_counts()
    low_count_conditions = condition_counts[condition_counts < min_cells_per_condition]

    if len(low_count_conditions) > 0:
        warnings.warn(
            f"Conditions with fewer than {min_cells_per_condition} cells: "
            f"{low_count_conditions.to_dict()}. scGen works best with >1000 cells per condition."
        )

    # Check cell types if provided
    cell_type_stats = {}
    if cell_type_key:
        cell_types = adata.obs[cell_type_key].unique()
        for ct in cell_types:
            ct_data = adata[adata.obs[cell_type_key] == ct]
            ct_conditions = ct_data.obs[condition_key].value_counts()
            cell_type_stats[ct] = ct_conditions.to_dict()

    results = {
        'n_cells': adata.n_obs,
        'n_genes': adata.n_vars,
        'n_conditions': len(conditions),
        'conditions': conditions.tolist(),
        'condition_counts': condition_counts.to_dict(),
        'n_cell_types': len(adata.obs[cell_type_key].unique()) if cell_type_key else None,
        'cell_type_condition_counts': cell_type_stats if cell_type_key else None
    }

    print(f"Data validation passed:")
    print(f"  Cells: {results['n_cells']}")
    print(f"  Genes: {results['n_genes']}")
    print(f"  Conditions: {results['n_conditions']} ({', '.join(results['conditions'])})")
    if cell_type_key:
        print(f"  Cell types: {results['n_cell_types']}")

    return results


def preprocess_for_scgen(
    adata,
    n_top_genes: int = 7000,
    flavor: str = "seurat_v3",
    layer: Optional[str] = None,
    copy: bool = False
) -> Any:
    """
    Preprocess data for scGen analysis.

    scGen expects normalized, log-transformed data. We recommend using
    highly variable genes for best performance.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    n_top_genes : int
        Number of highly variable genes to select
    flavor : str
        HVG selection flavor ('seurat_v3', 'cell_ranger', 'seurat')
    layer : str, optional
        Layer to use. If None, uses adata.X
    copy : bool
        If True, return a copy of adata

    Returns
    -------
    AnnData
        Preprocessed AnnData
    """
    if copy:
        adata = adata.copy()

    print("Preprocessing data for scGen...")

    # Check if data needs normalization
    if adata.X.max() > 100:
        print("  Normalizing counts...")
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
    else:
        print("  Data appears normalized, skipping normalization...")

    # Select highly variable genes
    print(f"  Selecting {n_top_genes} highly variable genes...")
    if flavor == "seurat_v3":
        # seurat_v3 requires raw counts
        try:
            sc.pp.highly_variable_genes(
                adata,
                n_top_genes=n_top_genes,
                flavor=flavor
            )
        except ValueError:
            # Fall back to seurat flavor if counts not available
            print("  Falling back to 'seurat' flavor for HVG selection...")
            sc.pp.highly_variable_genes(
                adata,
                n_top_genes=n_top_genes,
                flavor="seurat"
            )
    else:
        sc.pp.highly_variable_genes(
            adata,
            n_top_genes=n_top_genes,
            flavor=flavor
        )

    n_hvg = np.sum(adata.var.highly_variable)
    print(f"  Selected {n_hvg} highly variable genes")

    return adata


def setup_scgen_anndata(
    adata,
    batch_key: str,
    labels_key: Optional[str] = None
) -> Any:
    """
    Setup AnnData for scGen model.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix (should be preprocessed)
    batch_key : str
        Column in .obs containing batch/condition labels
    labels_key : str, optional
        Column in .obs containing cell type labels

    Returns
    -------
    AnnData
        Setup AnnData
    """
    try:
        import scgen
    except ImportError:
        raise ImportError("scgen is required. Install with: pip install scgen")

    print("Setting up AnnData for scGen...")
    print(f"  Batch key: {batch_key}")
    if labels_key:
        print(f"  Labels key: {labels_key}")

    # scGen expects normalized data in adata.X
    scgen.SCGEN.setup_anndata(
        adata,
        batch_key=batch_key,
        labels_key=labels_key
    )

    print("  Setup complete!")
    return adata


def train_scgen_model(
    adata,
    n_hidden: int = 800,
    n_latent: int = 100,
    n_layers: int = 2,
    dropout_rate: float = 0.2,
    max_epochs: int = 100,
    batch_size: int = 32,
    early_stopping: bool = True,
    early_stopping_patience: int = 10,
    random_state: int = 42,
    **trainer_kwargs
) -> Any:
    """
    Train scGen model.

    Parameters
    ----------
    adata : AnnData
        Setup AnnData
    n_hidden : int
        Number of nodes per hidden layer
    n_latent : int
        Dimensionality of the latent space
    n_layers : int
        Number of hidden layers for encoder and decoder
    dropout_rate : float
        Dropout rate for neural networks
    max_epochs : int
        Maximum number of training epochs
    batch_size : int
        Batch size for training
    early_stopping : bool
        Enable early stopping
    early_stopping_patience : int
        Patience for early stopping
    random_state : int
        Random seed for reproducibility
    **trainer_kwargs
        Additional arguments for training

    Returns
    -------
    SCGEN
        Trained scGen model
    """
    try:
        import scgen
        import torch
    except ImportError:
        raise ImportError("scgen is required. Install with: pip install scgen")

    # Set random seed
    if random_state is not None:
        import torch
        torch.manual_seed(random_state)
        np.random.seed(random_state)

    print("Initializing scGen model...")
    print(f"  Hidden layers: {n_hidden} nodes x {n_layers}")
    print(f"  Latent dimension: {n_latent}")
    print(f"  Dropout rate: {dropout_rate}")

    model = scgen.SCGEN(
        adata,
        n_hidden=n_hidden,
        n_latent=n_latent,
        n_layers=n_layers,
        dropout_rate=dropout_rate
    )

    print(f"\nTraining model for up to {max_epochs} epochs...")
    print(f"  Batch size: {batch_size}")
    print(f"  Early stopping: {'enabled' if early_stopping else 'disabled'}")

    model.train(
        max_epochs=max_epochs,
        batch_size=batch_size,
        early_stopping=early_stopping,
        early_stopping_patience=early_stopping_patience,
        **trainer_kwargs
    )

    print("Training complete!")
    return model


def predict_perturbation(
    model,
    ctrl_key: str,
    stim_key: str,
    adata_to_predict: Optional[Any] = None,
    celltype_to_predict: Optional[str] = None,
    restrict_arithmetic_to: Union[str, Dict] = "all"
) -> Tuple[Any, np.ndarray]:
    """
    Predict perturbation effects using trained scGen model.

    This function predicts how cells would look in the stimulated condition
    based on their control state. The prediction is made by computing the
    perturbation vector (delta) in latent space and applying it to the
    control cells.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    ctrl_key : str
        Key for control condition in batch_key column
    stim_key : str
        Key for stimulated condition in batch_key column
    adata_to_predict : AnnData, optional
        Specific AnnData to predict. If None, uses celltype_to_predict
    celltype_to_predict : str, optional
        Specific cell type to predict
    restrict_arithmetic_to : str or dict
        Restrict computation to specific cell types.
        Use "all" for all cell types, or a dict like {"cell_type": ["CD4T", "CD8T"]}

    Returns
    -------
    tuple
        (predicted_adata, delta) where delta is the perturbation vector
    """
    if adata_to_predict is not None and celltype_to_predict is not None:
        raise ValueError("Please provide either adata_to_predict or celltype_to_predict, not both")

    print(f"Predicting perturbation effects...")
    print(f"  Control: {ctrl_key}")
    print(f"  Stimulated: {stim_key}")
    if celltype_to_predict:
        print(f"  Cell type: {celltype_to_predict}")

    predicted_adata, delta = model.predict(
        ctrl_key=ctrl_key,
        stim_key=stim_key,
        adata_to_predict=adata_to_predict,
        celltype_to_predict=celltype_to_predict,
        restrict_arithmetic_to=restrict_arithmetic_to
    )

    print(f"Prediction complete!")
    print(f"  Predicted cells: {predicted_adata.n_obs}")
    print(f"  Delta vector shape: {delta.shape}")

    return predicted_adata, delta


def batch_correction(
    model,
    adata: Optional[Any] = None
) -> Any:
    """
    Remove batch effects using trained scGen model.

    This corrects for technical batch effects while preserving
    biological variation across cell types.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    adata : AnnData, optional
        AnnData to correct. If None, uses the model's training data

    Returns
    -------
    AnnData
        Batch-corrected AnnData with:
        - corrected.X: corrected gene expression
        - corrected.obsm["latent"]: latent representation before correction
        - corrected.obsm["corrected_latent"]: latent representation after correction
    """
    print("Running batch correction...")

    corrected = model.batch_removal(adata)

    print(f"Batch correction complete!")
    print(f"  Cells: {corrected.n_obs}")
    print(f"  Genes: {corrected.n_vars}")

    return corrected


def get_latent_representation(
    model,
    adata: Optional[Any] = None
) -> np.ndarray:
    """
    Get latent space representation of data.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    adata : AnnData, optional
        AnnData to encode. If None, uses training data

    Returns
    Returns
    -------
    np.ndarray
        Latent space coordinates (n_cells x n_latent)
    """
    latent = model.get_latent_representation(adata)
    return latent


def decode_latent(
    model,
    latent: np.ndarray
) -> np.ndarray:
    """
    Decode latent space coordinates back to gene expression.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    latent : np.ndarray
        Latent space coordinates (n_cells x n_latent)

    Returns
    -------
    np.ndarray
        Reconstructed gene expression (n_cells x n_genes)
    """
    # Decode latent coordinates back to gene expression space
    # NOTE: This uses the legacy scgen PyTorch API (scgen>=2.1.0).
    # The scgen package has been migrated to pertpy.tl.Scgen (Jax-based);
    # this skill currently targets the standalone scgen PyTorch version.
    import torch

    with torch.no_grad():
        reconstructed = model.module.generative(
            torch.Tensor(latent)
        )["px"].cpu().numpy()

    return reconstructed


def run_complete_scgen_pipeline(
    adata,
    condition_key: str,
    ctrl_key: str,
    stim_key: str,
    cell_type_key: Optional[str] = None,
    celltype_to_predict: Optional[str] = None,
    n_top_genes: int = 7000,
    n_hidden: int = 800,
    n_latent: int = 100,
    max_epochs: int = 100,
    batch_size: int = 32,
    early_stopping: bool = True,
    early_stopping_patience: int = 10,
    run_batch_correction: bool = True,
    random_state: int = 42
) -> Dict[str, Any]:
    """
    Run complete scGen analysis pipeline.

    This is a convenience function that runs the full scGen workflow:
    1. Preprocess data
    2. Setup AnnData
    3. Train model
    4. Batch correction (optional)
    5. Predict perturbation effects

    Parameters
    ----------
    adata : AnnData
        Raw AnnData object
    condition_key : str
        Column with condition labels
    ctrl_key : str
        Control condition label
    stim_key : str
        Stimulated condition label
    cell_type_key : str, optional
        Column with cell type labels
    celltype_to_predict : str, optional
        Specific cell type to predict
    n_top_genes : int
        Number of highly variable genes
    n_hidden : int
        Hidden layer size
    n_latent : int
        Latent dimension
    max_epochs : int
        Training epochs
    batch_size : int
        Batch size
    early_stopping : bool
        Enable early stopping
    early_stopping_patience : int
        Early stopping patience
    run_batch_correction : bool
        Whether to run batch correction
    random_state : int
        Random seed

    Returns
    -------
    dict
        Dictionary containing:
        - 'model': trained scGen model
        - 'adata': preprocessed AnnData
        - 'corrected': batch-corrected AnnData (if run_batch_correction=True)
        - 'predicted': predicted AnnData
        - 'delta': perturbation vector
    """
    print("=" * 60)
    print("Starting scGen Complete Pipeline")
    print("=" * 60)

    # Step 1: Validate
    print("\n[1/5] Validating data...")
    validate_perturbation_data(adata, condition_key, cell_type_key)

    # Step 2: Preprocess
    print("\n[2/5] Preprocessing data...")
    adata = preprocess_for_scgen(adata, n_top_genes=n_top_genes)

    # Step 3: Setup
    print("\n[3/5] Setting up AnnData...")
    adata = setup_scgen_anndata(adata, batch_key=condition_key, labels_key=cell_type_key)

    # Step 4: Train
    print("\n[4/5] Training model...")
    model = train_scgen_model(
        adata,
        n_hidden=n_hidden,
        n_latent=n_latent,
        max_epochs=max_epochs,
        batch_size=batch_size,
        early_stopping=early_stopping,
        early_stopping_patience=early_stopping_patience,
        random_state=random_state
    )

    results = {
        'model': model,
        'adata': adata
    }

    # Step 5: Batch correction
    if run_batch_correction:
        print("\n[5/5] Running batch correction...")
        corrected = batch_correction(model)
        results['corrected'] = corrected

    # Step 6: Predict
    print("\n[6/6] Predicting perturbation effects...")
    predicted, delta = predict_perturbation(
        model,
        ctrl_key=ctrl_key,
        stim_key=stim_key,
        celltype_to_predict=celltype_to_predict
    )
    results['predicted'] = predicted
    results['delta'] = delta

    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print("=" * 60)

    return results


def extract_perturbation_vector(
    model,
    ctrl_key: str,
    stim_key: str,
    cell_type_key: Optional[str] = None,
    specific_cell_type: Optional[str] = None
) -> np.ndarray:
    """
    Extract the perturbation vector (delta) from latent space.

    The perturbation vector represents the direction and magnitude
    of the perturbation effect in latent space.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    ctrl_key : str
        Control condition label
    stim_key : str
        Stimulated condition label
    cell_type_key : str, optional
        Cell type column (for computing cell type-specific vectors)
    specific_cell_type : str, optional
        Compute vector for specific cell type only

    Returns
    -------
    np.ndarray
        Perturbation vector (delta)
    """
    if specific_cell_type:
        _, delta = model.predict(
            ctrl_key=ctrl_key,
            stim_key=stim_key,
            celltype_to_predict=specific_cell_type
        )
    else:
        _, delta = model.predict(
            ctrl_key=ctrl_key,
            stim_key=stim_key
        )

    return delta


def classify_perturbation_response(
    model,
    adata,
    delta: np.ndarray,
    ctrl_key: str,
    stim_key: str
) -> np.ndarray:
    """
    Classify cells based on their perturbation response.

    Uses the dot product between the perturbation vector and
    cell latent representations to classify cells.

    Parameters
    ----------
    model : SCGEN
        Trained scGen model
    adata : AnnData
        AnnData to classify
    delta : np.ndarray
        Perturbation vector
    ctrl_key : str
        Control label
    stim_key : str
        Stimulated label

    Returns
    -------
    np.ndarray
        Classification scores for each cell
    """
    from .visualization import binary_classifier_scores

    scores = binary_classifier_scores(model, adata, delta, ctrl_key, stim_key)
    return scores
