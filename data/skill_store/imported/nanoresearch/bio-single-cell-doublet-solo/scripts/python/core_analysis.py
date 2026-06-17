"""
Core Analysis Functions for SOLO Doublet Detection

This module provides wrapper functions for:
- Training scVI model as prerequisite for SOLO
- Training SOLO for doublet detection
- Predicting doublet probabilities
- Filtering and processing results

Author: Yang Guo
Date: 2026-04-03
"""

import numpy as np
import pandas as pd
import scanpy as sc
from typing import Optional, Union, List, Dict, Tuple
import warnings

#==============================================================================
# scVI Model Training
#==============================================================================

def train_scvi_model(
    adata: sc.AnnData,
    batch_key: Optional[str] = None,
    labels_key: Optional[str] = None,
    layer: Optional[str] = None,
    n_latent: int = 10,
    n_hidden: int = 128,
    n_layers: int = 3,
    max_epochs: int = 400,
    train_size: float = 0.9,
    validation_size: Optional[float] = None,
    batch_size: int = 128,
    use_gpu: bool = True,
    early_stopping: bool = True,
    early_stopping_patience: int = 45,
    check_val_every_n_epoch: int = 1,
    learning_rate: float = 1e-3,
    random_seed: int = 42,
    verbose: bool = True
) -> "scvi.model.SCVI":
    """
    Train scVI model as prerequisite for SOLO.

    SOLO requires a trained scVI model to obtain latent representations
    of cells. This function trains scVI with optimal parameters for
    downstream doublet detection.

    Parameters
    ----------
    adata : sc.AnnData
        Annotated data matrix (raw counts required)
    batch_key : Optional[str], default=None
        Key in adata.obs for batch information
    labels_key : Optional[str], default=None
        Key in adata.obs for cell type labels
    layer : Optional[str], default=None
        Layer to use if not using adata.X
    n_latent : int, default=10
        Dimensionality of the latent space
    n_hidden : int, default=128
        Number of nodes per hidden layer
    n_layers : int, default=3
        Number of hidden layers
    max_epochs : int, default=400
        Maximum number of epochs for training
    train_size : float, default=0.9
        Proportion of data for training
    validation_size : Optional[float], default=None
        Proportion for validation (auto-calculated if None)
    batch_size : int, default=128
        Minibatch size
    use_gpu : bool, default=True
        Use GPU if available
    early_stopping : bool, default=True
        Enable early stopping
    early_stopping_patience : int, default=45
        Patience for early stopping
    check_val_every_n_epoch : int, default=1
        Check validation every N epochs
    learning_rate : float, default=1e-3
        Learning rate
    random_seed : int, default=42
        Random seed for reproducibility
    verbose : bool, default=True
        Print progress

    Returns
    -------
    scvi.model.SCVI
        Trained scVI model

    Examples
    --------
    >>> vae = train_scvi_model(adata, batch_key='batch', max_epochs=400)
    """
    try:
        import scvi
    except ImportError:
        raise ImportError(
            "scvi-tools is required. Install with: pip install scvi-tools"
        )

    # Set random seed for reproducibility
    scvi.settings.seed = random_seed

    if verbose:
        print("Training scVI model for SOLO...")
        print(f"  n_latent: {n_latent}, n_hidden: {n_hidden}, n_layers: {n_layers}")
        print(f"  batch_key: {batch_key}")

    # Guard against double-setup which scvi-tools rejects
    if '_scvi' in adata.uns:
        raise ValueError(
            "AnnData has already been setup for scVI. "
            "Use adata.copy() before calling train_scvi_model(), "
            "or use the existing scVI model."
        )

    # Setup anndata
    scvi.model.SCVI.setup_anndata(
        adata,
        batch_key=batch_key,
        labels_key=labels_key,
        layer=layer
    )

    # Initialize model
    model = scvi.model.SCVI(
        adata,
        n_latent=n_latent,
        n_hidden=n_hidden,
        n_layers=n_layers
    )

    if verbose:
        print(f"  Model initialized with {adata.n_obs} cells, {adata.n_vars} genes")

    # Train model
    model.train(
        max_epochs=max_epochs,
        train_size=train_size,
        validation_size=validation_size,
        batch_size=batch_size,
        early_stopping=early_stopping,
        early_stopping_patience=early_stopping_patience,
        check_val_every_n_epoch=check_val_every_n_epoch,
        lr=learning_rate,
        accelerator="gpu" if use_gpu else "cpu",
        devices="auto"
    )

    if verbose:
        print(f"  Training completed")
        print(f"  Training history keys: {list(model.history.keys())}")

    return model


#==============================================================================
# SOLO Doublet Detection
#==============================================================================

def train_solo_model(
    scvi_model: "scvi.model.SCVI",
    adata: Optional[sc.AnnData] = None,
    restrict_to_batch: Optional[str] = None,
    doublet_ratio: int = 2,
    max_epochs: int = 100,
    train_size: float = 0.9,
    validation_size: Optional[float] = None,
    batch_size: int = 128,
    use_gpu: bool = True,
    early_stopping: bool = True,
    early_stopping_patience: int = 30,
    early_stopping_min_delta: float = 0.0,
    learning_rate: float = 1e-3,
    verbose: bool = True
) -> "scvi.external.SOLO":
    """
    Train SOLO model for doublet detection.

    SOLO is a classifier trained on simulated doublets to distinguish
    singlets from doublets in the latent space.

    Parameters
    ----------
    scvi_model : scvi.model.SCVI
        Pre-trained scVI model
    adata : Optional[sc.AnnData], default=None
        Optional AnnData to use (must be compatible with scvi_model)
    restrict_to_batch : Optional[str], default=None
        Batch category to restrict to (if scVI trained with multiple batches)
    doublet_ratio : int, default=2
        Ratio of simulated doublets to real cells
    max_epochs : int, default=100
        Maximum training epochs
    train_size : float, default=0.9
        Training set proportion
    validation_size : Optional[float], default=None
        Validation set proportion
    batch_size : int, default=128
        Minibatch size
    use_gpu : bool, default=True
        Use GPU if available
    early_stopping : bool, default=True
        Enable early stopping
    early_stopping_patience : int, default=30
        Early stopping patience
    early_stopping_min_delta : float, default=0.0
        Minimum change for early stopping
    learning_rate : float, default=1e-3
        Learning rate
    verbose : bool, default=True
        Print progress

    Returns
    -------
    scvi.external.SOLO
        Trained SOLO model

    Examples
    --------
    >>> vae = train_scvi_model(adata)
    >>> solo = train_solo_model(vae, max_epochs=100)
    """
    try:
        from scvi.external import SOLO
    except ImportError:
        raise ImportError("scvi-tools is required")

    if verbose:
        print("Training SOLO model...")
        print(f"  doublet_ratio: {doublet_ratio}")
        print(f"  restrict_to_batch: {restrict_to_batch}")

    # Create SOLO from scVI model
    solo = SOLO.from_scvi_model(
        scvi_model,
        adata=adata,
        restrict_to_batch=restrict_to_batch,
        doublet_ratio=doublet_ratio
    )

    if verbose:
        print(f"  SOLO model initialized")
        print(f"  Training data: {solo.adata.n_obs} cells (singlets + simulated doublets)")

    # Train SOLO
    solo.train(
        max_epochs=max_epochs,
        train_size=train_size,
        validation_size=validation_size,
        batch_size=batch_size,
        lr=learning_rate,
        accelerator="gpu" if use_gpu else "cpu",
        devices="auto",
        early_stopping=early_stopping,
        early_stopping_patience=early_stopping_patience,
        early_stopping_min_delta=early_stopping_min_delta
    )

    if verbose:
        print(f"  Training completed")
        print(f"  History: {list(solo.history.keys())}")

    return solo


def predict_doublets(
    solo_model: "scvi.external.SOLO",
    soft: bool = True,
    include_simulated_doublets: bool = False,
    return_logits: bool = False
) -> pd.DataFrame:
    """
    Predict doublets using trained SOLO model.

    Parameters
    ----------
    solo_model : scvi.external.SOLO
        Trained SOLO model
    soft : bool, default=True
        Return probabilities (if True) or hard labels (if False)
    include_simulated_doublets : bool, default=False
        Include predictions for simulated doublets
    return_logits : bool, default=False
        Return logits instead of probabilities (only when soft=True)

    Returns
    -------
    pd.DataFrame
        If soft=True: DataFrame with columns 'singlet' and 'doublet' (probabilities).
        If soft=False: DataFrame with column 'prediction' containing string labels
        ('singlet' or 'doublet').

    Examples
    --------
    >>> df = predict_doublets(solo, soft=True)
    >>> df['is_doublet'] = df['doublet'] > 0.5
    """
    predictions = solo_model.predict(
        soft=soft,
        include_simulated_doublets=include_simulated_doublets,
        return_logits=return_logits
    )

    if not soft:
        # SOLO.predict(soft=False) returns a Series of string labels
        predictions = pd.DataFrame({
            'prediction': predictions
        })

    return predictions


def run_solo_pipeline(
    adata: sc.AnnData,
    batch_key: Optional[str] = None,
    scvi_epochs: int = 400,
    solo_epochs: int = 100,
    doublet_ratio: int = 2,
    doublet_threshold: float = 0.5,
    restrict_to_batch: Optional[str] = None,
    use_gpu: bool = True,
    random_seed: int = 42,
    inplace: bool = True,
    verbose: bool = True
) -> Union[pd.DataFrame, Tuple[sc.AnnData, pd.DataFrame]]:
    """
    Complete SOLO pipeline from scVI training to doublet predictions.

    This is the main entry point for SOLO doublet detection, running
    the full workflow: scVI training -> SOLO training -> predictions.

    Parameters
    ----------
    adata : sc.AnnData
        Annotated data matrix with raw counts
    batch_key : Optional[str], default=None
        Key for batch information
    scvi_epochs : int, default=400
        Epochs for scVI training
    solo_epochs : int, default=100
        Epochs for SOLO training
    doublet_ratio : int, default=2
        Ratio of simulated doublets to real cells
    doublet_threshold : float, default=0.5
        Threshold for calling doublets (probability > threshold)
    restrict_to_batch : Optional[str], default=None
        Batch to restrict analysis to
    use_gpu : bool, default=True
        Use GPU
    random_seed : int, default=42
        Random seed
    inplace : bool, default=True
        Add results to adata.obs (if True) or return DataFrame
    verbose : bool, default=True
        Print progress

    Returns
    -------
    Union[pd.DataFrame, Tuple[sc.AnnData, pd.DataFrame]]
        If inplace=True: returns predictions DataFrame
        If inplace=False: returns (adata, predictions)

    Examples
    --------
    >>> # Basic usage
    >>> predictions = run_solo_pipeline(adata)
    >>>
    >>> # With batch correction
    >>> predictions = run_solo_pipeline(adata, batch_key='batch')
    >>>
    >>> # Restrict to one batch
    >>> predictions = run_solo_pipeline(adata, batch_key='batch',
    ...                                   restrict_to_batch='batch_0')
    """
    if not inplace:
        adata = adata.copy()

    # Train scVI
    scvi_model = train_scvi_model(
        adata,
        batch_key=batch_key,
        max_epochs=scvi_epochs,
        use_gpu=use_gpu,
        random_seed=random_seed,
        verbose=verbose
    )

    # Train SOLO
    solo_model = train_solo_model(
        scvi_model,
        restrict_to_batch=restrict_to_batch,
        doublet_ratio=doublet_ratio,
        max_epochs=solo_epochs,
        use_gpu=use_gpu,
        verbose=verbose
    )

    # Predict
    predictions = predict_doublets(solo_model, soft=True)

    # Add hard predictions
    predictions['prediction'] = (predictions['doublet'] > doublet_threshold).astype(int)
    predictions['prediction_label'] = predictions['prediction'].map({0: 'singlet', 1: 'doublet'})

    if verbose:
        n_doublets = (predictions['prediction'] == 1).sum()
        print(f"\nDoublet Detection Results:")
        print(f"  Total cells: {len(predictions)}")
        print(f"  Predicted doublets: {n_doublets} ({n_doublets/len(predictions)*100:.1f}%)")
        print(f"  Predicted singlets: {len(predictions) - n_doublets}")

    if inplace:
        adata.obs['solo_doublet_score'] = predictions['doublet']
        adata.obs['solo_singlet_score'] = predictions['singlet']
        adata.obs['solo_prediction'] = predictions['prediction_label']
        adata.uns['solo_threshold'] = doublet_threshold

    if inplace:
        return predictions
    else:
        return adata, predictions


#==============================================================================
# Batch Processing for Multi-batch Data
#==============================================================================

def run_solo_per_batch(
    adata: sc.AnnData,
    batch_key: str,
    scvi_epochs: int = 400,
    solo_epochs: int = 100,
    doublet_ratio: int = 2,
    doublet_threshold: float = 0.5,
    use_gpu: bool = True,
    random_seed: int = 42,
    verbose: bool = True
) -> Dict[str, pd.DataFrame]:
    """
    Run SOLO separately for each batch in the dataset.

    SOLO should be trained on one lane/batch at a time for optimal
    performance. This function handles multi-batch datasets by training
    a shared scVI model then running SOLO separately per batch.

    Parameters
    ----------
    adata : sc.AnnData
        Annotated data matrix
    batch_key : str
        Key for batch information in adata.obs
    scvi_epochs : int, default=400
        Epochs for scVI training
    solo_epochs : int, default=100
        Epochs for SOLO training per batch
    doublet_ratio : int, default=2
        Ratio of simulated doublets
    doublet_threshold : float, default=0.5
        Threshold for calling doublets
    use_gpu : bool, default=True
        Use GPU
    random_seed : int, default=42
        Random seed
    verbose : bool, default=True
        Print progress

    Returns
    -------
    Dict[str, pd.DataFrame]
        Dictionary mapping batch names to prediction DataFrames

    Examples
    --------
    >>> batch_results = run_solo_per_batch(adata, batch_key='lane')
    >>> all_predictions = pd.concat(batch_results.values())
    """
    # Train scVI on all batches
    scvi_model = train_scvi_model(
        adata,
        batch_key=batch_key,
        max_epochs=scvi_epochs,
        use_gpu=use_gpu,
        random_seed=random_seed,
        verbose=verbose
    )

    # Get unique batches
    batches = adata.obs[batch_key].unique()

    if verbose:
        print(f"\nRunning SOLO for {len(batches)} batches: {list(batches)}")

    # Run SOLO per batch
    results = {}
    for batch in batches:
        if verbose:
            print(f"\n{'='*50}")
            print(f"Processing batch: {batch}")
            print('='*50)

        try:
            solo = train_solo_model(
                scvi_model,
                restrict_to_batch=batch,
                doublet_ratio=doublet_ratio,
                max_epochs=solo_epochs,
                use_gpu=use_gpu,
                verbose=verbose
            )

            predictions = predict_doublets(solo, soft=True)
            predictions['prediction'] = (predictions['doublet'] > doublet_threshold).astype(int)
            predictions['prediction_label'] = predictions['prediction'].map({0: 'singlet', 1: 'doublet'})
            predictions['batch'] = batch

            results[batch] = predictions

        except Exception as e:
            warnings.warn(f"Failed to process batch {batch}: {e}")
            results[batch] = None

    if verbose:
        print(f"\n{'='*50}")
        print("Batch processing complete")
        print('='*50)
        for batch, result in results.items():
            if result is not None:
                n_doublets = (result['prediction'] == 1).sum()
                print(f"  {batch}: {n_doublets} doublets ({n_doublets/len(result)*100:.1f}%)")

    return results


#==============================================================================
# Result Processing
#==============================================================================

def filter_doublets(
    adata: sc.AnnData,
    predictions: pd.DataFrame,
    threshold: Optional[float] = None,
    inplace: bool = False
) -> sc.AnnData:
    """
    Filter out predicted doublets from AnnData.

    Parameters
    ----------
    adata : sc.AnnData
        Original data
    predictions : pd.DataFrame
        SOLO predictions DataFrame
    threshold : Optional[float], default=None
        Threshold for doublet calling (if None, use stored threshold)
    inplace : bool, default=False
        If True, filter in place

    Returns
    -------
    sc.AnnData
        Filtered AnnData with doublets removed
    """
    if not inplace:
        adata = adata.copy()

    if threshold is None:
        threshold = adata.uns.get('solo_threshold', 0.5)

    # Get singlet mask - handle multiple prediction formats
    if 'prediction_label' in predictions.columns:
        singlet_mask = predictions['prediction_label'] == 'singlet'
    elif 'prediction' in predictions.columns:
        if predictions['prediction'].dtype == object:
            # String labels: 'singlet' / 'doublet'
            singlet_mask = predictions['prediction'] == 'singlet'
        else:
            # Numeric labels: 0 = singlet, 1 = doublet
            singlet_mask = predictions['prediction'] == 0
    else:
        singlet_mask = predictions['doublet'] <= threshold

    n_before = adata.n_obs
    n_doublets = (~singlet_mask).sum()

    # Filter
    adata = adata[singlet_mask.values].copy()

    print(f"Filtered {n_doublets} doublets ({n_doublets/n_before*100:.1f}%)")
    print(f"Remaining cells: {adata.n_obs}")

    return adata


def add_predictions_to_adata(
    adata: sc.AnnData,
    predictions: pd.DataFrame,
    doublet_threshold: float = 0.5
):
    """
    Add SOLO predictions to AnnData.obs.

    Parameters
    ----------
    adata : sc.AnnData
        Data object
    predictions : pd.DataFrame
        SOLO predictions
    doublet_threshold : float, default=0.5
        Threshold used for calling doublets
    """
    adata.obs['solo_doublet_score'] = predictions['doublet']
    adata.obs['solo_singlet_score'] = predictions['singlet']

    if 'prediction_label' in predictions.columns:
        adata.obs['solo_prediction'] = predictions['prediction_label']
    elif 'prediction' in predictions.columns:
        adata.obs['solo_prediction'] = predictions['prediction'].map({0: 'singlet', 1: 'doublet'})
    else:
        adata.obs['solo_prediction'] = (predictions['doublet'] > doublet_threshold).map({True: 'doublet', False: 'singlet'})

    adata.uns['solo_threshold'] = doublet_threshold



