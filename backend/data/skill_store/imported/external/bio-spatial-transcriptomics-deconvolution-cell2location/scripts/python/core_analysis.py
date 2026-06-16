"""
Cell2location core analysis module.

Author: Yang Guo
Date: 2026-03-31
"""

import warnings
from typing import Optional, List, Dict, Tuple, Union
import pandas as pd
import numpy as np
import scanpy as sc
import anndata as ad
from anndata import AnnData


def prepare_data(
    spatial_adata: AnnData,
    reference_adata: AnnData,
    cell_type_key: str = 'cell_type',
    min_common_genes: int = 100,
    require_int_dtype: bool = True,
) -> Tuple[AnnData, AnnData]:
    """
    Prepare spatial and reference data for cell2location.

    Parameters
    ----------
    spatial_adata : AnnData
        Spatial transcriptomics data with raw counts
    reference_adata : AnnData
        Single-cell reference with cell type annotations
    cell_type_key : str, default='cell_type'
        Column in reference_adata.obs with cell types
    min_common_genes : int, default=100
        Minimum number of common genes required
    require_int_dtype : bool, default=True
        If True, warn and convert non-integer data to integer counts.
        Does not raise an error; use this to ensure cell2location
        receives raw counts even if input was inadvertently normalized.

    Returns
    -------
    Tuple[AnnData, AnnData]
        Prepared spatial and reference data (copies)

    Notes
    -----
    - Always returns copies; original AnnData objects are not modified.
    - If ``.layers['raw']`` or ``.raw`` is present, it is used as the
      expression matrix before subsetting to common genes.

    Examples
    --------
    >>> spatial_prep, ref_prep = prepare_data(
    ...     spatial_adata,
    ...     reference_adata,
    ...     cell_type_key='cell_type'
    ... )
    """
    # Validate inputs
    if cell_type_key not in reference_adata.obs.columns:
        raise ValueError(f"'{cell_type_key}' not found in reference_adata.obs")

    # Work with copies
    spatial = spatial_adata.copy()
    reference = reference_adata.copy()

    # Ensure raw counts in spatial data
    if 'raw' in spatial.layers:
        spatial.X = spatial.layers['raw']
    elif spatial.raw is not None:
        spatial = spatial.raw.to_adata()

    if require_int_dtype and not np.issubdtype(spatial.X.dtype, np.integer):
        warnings.warn("Spatial data should contain raw integer counts. Converting...")
        if hasattr(spatial.X, 'toarray'):
            spatial.X = spatial.X.toarray().astype(int)
        else:
            spatial.X = spatial.X.astype(int)

    # Ensure raw counts in reference
    if 'raw' in reference.layers:
        reference.X = reference.layers['raw']
    elif reference.raw is not None:
        reference = reference.raw.to_adata()

    if require_int_dtype and not np.issubdtype(reference.X.dtype, np.integer):
        warnings.warn("Reference data should contain raw integer counts. Converting...")
        if hasattr(reference.X, 'toarray'):
            reference.X = reference.X.toarray().astype(int)
        else:
            reference.X = reference.X.astype(int)

    # Find common genes
    spatial_genes = set(spatial.var_names)
    ref_genes = set(reference.var_names)
    common_genes = list(spatial_genes & ref_genes)

    if len(common_genes) < min_common_genes:
        raise ValueError(
            f"Only {len(common_genes)} common genes found. "
            f"Need at least {min_common_genes}."
        )

    print(f"Using {len(common_genes)} common genes")

    # Subset to common genes
    spatial = spatial[:, common_genes].copy()
    reference = reference[:, common_genes].copy()

    return spatial, reference


def run_cell2location(
    spatial_adata: AnnData,
    reference_adata: AnnData,
    cell_type_key: str = 'cell_type',
    max_epochs: int = 30000,
    batch_size: Optional[int] = None,
    gpu: bool = True,
    batch_key: Optional[str] = None,
    detection_alpha: float = 200.0,
    N_cells_per_location: Optional[int] = None,
) -> AnnData:
    """
    Run cell2location deconvolution.

    Parameters
    ----------
    spatial_adata : AnnData
        Prepared spatial data with raw counts
    reference_adata : AnnData
        Prepared reference data with cell type annotations
    cell_type_key : str, default='cell_type'
        Column with cell type labels
    max_epochs : int, default=30000
        Maximum training epochs
    batch_size : int, optional
        Batch size. If None, auto-determined as min(2500, n_spots).
    gpu : bool, default=True
        Use GPU if available. Falls back to CPU if CUDA is unavailable.
    batch_key : str, optional
        Column in spatial_adata.obs for batch correction (e.g., "sample").
        If None, no batch correction is applied.
    detection_alpha : float, default=200
        Detection sensitivity prior. Lower values (e.g., 20) account for
        higher within-slide technical variability.
    N_cells_per_location : int, optional
        Expected number of cells per spatial spot. If None, inferred from
        spatial_adata.obs['n_cells'] if present; otherwise defaults to 10.

    Returns
    -------
    AnnData
        Spatial data with deconvolution results in .obsm['q05_cell_abundance_w_sf']
        and other quantiles. This is a **copy** of the input spatial_adata.

    Notes
    -----
    - Operates on copies of both inputs to avoid modifying the originals.
    - If you need to re-run, you can safely pass the same objects again.

    Examples
    --------
    >>> results = run_cell2location(
    ...     spatial_prep,
    ...     ref_prep,
    ...     cell_type_key='cell_type',
    ...     max_epochs=30000
    ... )
    """
    try:
        import cell2location
        from cell2location.models import RegressionModel, Cell2location
        import torch
    except ImportError:
        raise ImportError(
            "cell2location not installed. "
            "Install with: pip install cell2location"
        )

    # Operate on copies to avoid modifying caller's objects
    spatial = spatial_adata.copy()
    reference = reference_adata.copy()

    # Device handled by PyTorch Lightning via accelerator parameter
    if gpu and not torch.cuda.is_available():
        print("GPU not available, using CPU")
        gpu = False

    # Prepare reference (cell type signatures)
    print("Estimating reference signatures...")
    RegressionModel.setup_anndata(
        reference,
        labels_key=cell_type_key,
    )

    ref_model = RegressionModel(reference)
    try:
        # scvi-tools >= 0.20 / cell2location >= 0.1.3
        ref_model.train(max_epochs=250, accelerator='gpu' if gpu else 'cpu')
    except TypeError:
        # Older versions use use_gpu
        ref_model.train(max_epochs=250, use_gpu=gpu)

    # Export cell type signatures
    reference = ref_model.export_posterior(
        reference,
        sample_kwargs={'num_samples': 1000, 'batch_size': 2500}
    )

    # Prepare spatial data
    print("Running cell2location on spatial data...")
    if batch_key is not None:
        Cell2location.setup_anndata(spatial, batch_key=batch_key)
    else:
        Cell2location.setup_anndata(spatial)

    # Determine N_cells_per_location
    if N_cells_per_location is not None:
        n_cells_per_loc = N_cells_per_location
    elif 'n_cells' in spatial.obs.columns:
        n_cells = spatial.obs['n_cells']
        # Validate numeric type
        if not pd.api.types.is_numeric_dtype(n_cells):
            raise ValueError(
                f"spatial.obs['n_cells'] must be numeric, got dtype {n_cells.dtype}. "
                f"Pass N_cells_per_location explicitly to override inference."
            )
        n_cells_per_loc = max(5, int(n_cells.mean()))
    else:
        n_cells_per_loc = 10

    model = Cell2location(
        spatial,
        cell_state_df=reference.varm['means_per_cluster_mu_fg'],
        N_cells_per_location=n_cells_per_loc,
        detection_alpha=detection_alpha,
    )

    try:
        # scvi-tools >= 0.20 / cell2location >= 0.1.3
        model.train(
            max_epochs=max_epochs,
            batch_size=batch_size or min(2500, spatial.n_obs),
            train_size=1,
            accelerator='gpu' if gpu else 'cpu',
        )
    except TypeError:
        # Older versions use use_gpu
        model.train(
            max_epochs=max_epochs,
            batch_size=batch_size or min(2500, spatial.n_obs),
            train_size=1,
            use_gpu=gpu,
        )

    # Export results
    spatial = model.export_posterior(
        spatial,
        sample_kwargs={'num_samples': 1000, 'batch_size': model.adata.n_obs}
    )

    print("Cell2location complete!")
    return spatial


def estimate_cell_type_proportions(
    spatial_adata: AnnData,
    q_threshold: float = 0.05,
    normalize: bool = True,
) -> pd.DataFrame:
    """
    Extract cell type proportions from cell2location results.

    Parameters
    ----------
    spatial_adata : AnnData
        Data after run_cell2location()
    q_threshold : float, default=0.05
        Quantile threshold (q05, q50, q95)
    normalize : bool, default=True
        Normalize to sum to 1 per spot

    Returns
    -------
    pd.DataFrame
        Cell type proportions (spots x cell_types)

    Examples
    --------
    >>> props = estimate_cell_type_proportions(results)
    >>> print(props.head())
    """
    q_str = f"q{int(q_threshold*100):02d}"
    key = f"{q_str}_cell_abundance_w_sf"

    if key not in spatial_adata.obsm:
        raise KeyError(f"'{key}' not found. Run run_cell2location() first.")

    # Copy and rename columns (handle both DataFrame and array inputs)
    obsm_data = spatial_adata.obsm[key]
    if hasattr(obsm_data, 'columns'):
        # It's a DataFrame - copy and rename columns
        props = obsm_data.copy()
        props.columns = [c.replace(f'{q_str}_cell_abundance_w_sf_', '')
                         for c in props.columns]
    else:
        # It's an array - create DataFrame
        raise ValueError(f"Expected DataFrame in obsm['{key}'], got {type(obsm_data)}")

    if normalize:
        props = props.div(props.sum(axis=1), axis=0)
        props = props.fillna(0)

    return props


def extract_proportions(
    spatial_adata: AnnData,
    key: str = 'q05_cell_abundance_w_sf',
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Extract proportions and cell type names.

    Parameters
    ----------
    spatial_adata : AnnData
        Data with cell2location results
    key : str, default='q05_cell_abundance_w_sf'
        Key in .obsm containing proportions

    Returns
    -------
    Tuple[pd.DataFrame, List[str]]
        Proportions DataFrame and cell type names
    """
    if key not in spatial_adata.obsm:
        raise KeyError(f"'{key}' not found in obsm. Run run_cell2location() first.")

    props = spatial_adata.obsm[key].copy()

    # Rename columns in place
    cell_types = [c.replace(f'{key}_', '') for c in props.columns]
    props.columns = cell_types

    return props, cell_types
