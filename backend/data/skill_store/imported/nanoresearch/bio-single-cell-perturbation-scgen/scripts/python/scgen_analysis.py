"""scGen generative modeling for perturbation analysis."""

import numpy as np
import pandas as pd
import scanpy as sc
import pertpy as pt
from typing import Optional, List


def setup_scgen_data(
    adata: sc.AnnData,
    batch_key: str,
    labels_key: Optional[str] = None,
    n_top_genes: int = 2000
) -> sc.AnnData:
    """
    Prepare AnnData for scGen analysis.

    Args:
        adata: AnnData object
        batch_key: Column with perturbation/condition labels
        labels_key: Column with cell type labels (optional)
        n_top_genes: Number of highly variable genes

    Returns:
        Preprocessed AnnData
    """
    # Preprocess
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes)

    # Setup scGen
    pt.tl.Scgen.setup_anndata(
        adata,
        batch_key=batch_key,
        labels_key=labels_key
    )

    return adata


def train_scgen_model(
    adata: sc.AnnData,
    max_epochs: int = 100,
    batch_size: int = 32,
    early_stopping: bool = True,
    early_stopping_patience: int = 10,
    **kwargs
) -> pt.tl.Scgen:
    """
    Train scGen model.

    Args:
        adata: Prepared AnnData
        max_epochs: Training epochs
        batch_size: Batch size
        early_stopping: Enable early stopping
        early_stopping_patience: Patience for early stopping
        **kwargs: Additional arguments for train()

    Returns:
        Trained scGen model
    """
    print("Initializing scGen model...")
    model = pt.tl.Scgen(adata)

    print("Training model...")
    model.train(
        max_epochs=max_epochs,
        batch_size=batch_size,
        early_stopping=early_stopping,
        early_stopping_patience=early_stopping_patience,
        **kwargs
    )

    print("Training complete!")
    return model


def run_batch_correction(
    model: pt.tl.Scgen,
    adata: Optional[sc.AnnData] = None
) -> sc.AnnData:
    """
    Remove perturbation batch effects using trained scGen model.

    Args:
        model: Trained scGen model
        adata: AnnData to correct (uses training data if None)

    Returns:
        Batch-corrected AnnData
    """
    print("Running batch correction...")
    corrected = model.batch_removal(adata)

    print("Batch correction complete!")
    return corrected


def predict_perturbation_effect(
    model: pt.tl.Scgen,
    ctrl_key: str,
    stim_key: str,
    celltype_to_predict: Optional[str] = None
) -> tuple:
    """
    Predict perturbation effects using scGen.

    Args:
        model: Trained scGen model
        ctrl_key: Control condition label
        stim_key: Stimulated/perturbed condition label
        celltype_to_predict: Specific cell type to predict (optional)

    Returns:
        Tuple of (predicted_adata, delta)
    """
    print(f"Predicting {stim_key} from {ctrl_key}...")

    predicted, delta = model.predict(
        ctrl_key=ctrl_key,
        stim_key=stim_key,
        celltype_to_predict=celltype_to_predict
    )

    print("Prediction complete!")
    return predicted, delta


def extract_perturbation_vector(
    model: pt.tl.Scgen,
    ctrl_key: str,
    stim_key: str
) -> np.ndarray:
    """
    Extract the latent perturbation vector (delta).

    Args:
        model: Trained scGen model
        ctrl_key: Control condition label
        stim_key: Stimulated/perturbed condition label

    Returns:
        Perturbation vector
    """
    _, delta = model.predict(
        ctrl_key=ctrl_key,
        stim_key=stim_key
    )

    return delta


def run_full_scgen_pipeline(
    adata: sc.AnnData,
    batch_key: str,
    labels_key: Optional[str] = None,
    ctrl_key: Optional[str] = None,
    stim_key: Optional[str] = None,
    max_epochs: int = 100
) -> dict:
    """
    Run complete scGen pipeline.

    Args:
        adata: AnnData object
        batch_key: Column with batch/perturbation labels
        labels_key: Column with cell type labels
        ctrl_key: Control label for prediction
        stim_key: Stimulated label for prediction
        max_epochs: Training epochs

    Returns:
        Dictionary with model, corrected data, and predictions
    """
    # Setup
    adata = setup_scgen_data(adata, batch_key, labels_key)

    # Train
    model = train_scgen_model(adata, max_epochs=max_epochs)

    # Batch correction
    corrected = run_batch_correction(model)

    results = {
        'model': model,
        'corrected': corrected
    }

    # Prediction if keys provided
    if ctrl_key and stim_key:
        predicted, delta = predict_perturbation_effect(
            model, ctrl_key, stim_key
        )
        results['predicted'] = predicted
        results['delta'] = delta

    return results
