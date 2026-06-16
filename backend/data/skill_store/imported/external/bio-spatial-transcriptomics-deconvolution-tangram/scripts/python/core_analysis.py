"""
Tangram core analysis module for spatial transcriptomics deconvolution.

This module provides wrapper functions for Tangram, a deep learning method
for mapping single-cell RNA-seq data to spatial transcriptomics data.

Author: Yang Guo
Date: 2026-04-03
"""

import warnings
from typing import Optional, List, Dict, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    import torch
import pandas as pd
import numpy as np
import scanpy as sc
from anndata import AnnData
import logging

# Runtime torch import for actual usage (type hints use TYPE_CHECKING block above)
torch = None  # Will be imported at runtime in functions that need it

# Logger for this module (does NOT call basicConfig to avoid overriding user settings)
logger = logging.getLogger(__name__)


def check_tangram_installed():
    """Check if tangram is installed and raise informative error if not."""
    try:
        import tangram as tg
        return tg
    except ImportError:
        raise ImportError(
            "tangram-sc not installed. Install with: pip install tangram-sc\n"
            "Also requires PyTorch: pip install torch"
        )


def prepare_data(
    adata_sc: AnnData,
    adata_sp: AnnData,
    genes: Optional[List[str]] = None,
    gene_to_lowercase: bool = True,
    copy: bool = True,
) -> Tuple[AnnData, AnnData]:
    """
    Pre-process AnnDatas for Tangram mapping.

    This function prepares single-cell and spatial data by:
    - Removing genes with all zero values
    - Finding shared genes between datasets
    - Calculating density priors (uniform and RNA count-based)
    - Computing spatial neighborhood parameters

    Parameters
    ----------
    adata_sc : AnnData
        Single-cell data (cell-by-gene)
    adata_sp : AnnData
        Spatial transcriptomics data (spot-by-gene)
    genes : List[str], optional
        List of genes to use for mapping. If None, uses all shared genes.
    gene_to_lowercase : bool, default=True
        Convert gene names to lowercase for matching
    copy : bool, default=True
        Return copies of input AnnDatas

    Returns
    -------
    Tuple[AnnData, AnnData]
        Prepared single-cell and spatial AnnDatas with:
        - uns['training_genes']: genes used for training
        - uns['overlap_genes']: all shared genes
        - obs['uniform_density']: uniform density prior (spatial)
        - obs['rna_count_based_density']: RNA count-based density (spatial)

    Examples
    --------
    >>> adata_sc_prep, adata_sp_prep = prepare_data(
    ...     adata_sc, adata_sp, genes=marker_genes
    ... )
    >>> print(f"Training genes: {len(adata_sc_prep.uns['training_genes'])}")
    """
    tg = check_tangram_installed()

    if copy:
        adata_sc = adata_sc.copy()
        adata_sp = adata_sp.copy()

    # Run Tangram preprocessing
    tg.pp_adatas(
        adata_sc=adata_sc,
        adata_sp=adata_sp,
        genes=genes,
        gene_to_lowercase=gene_to_lowercase,
    )

    logger.info(f"Prepared data with {len(adata_sc.uns['training_genes'])} training genes")

    return adata_sc, adata_sp


def map_cells_to_space(
    adata_sc: AnnData,
    adata_sp: AnnData,
    mode: str = 'cells',
    cluster_label: Optional[str] = None,
    cv_train_genes: Optional[List[str]] = None,
    device: Union[str, 'torch.device'] = 'cpu',
    learning_rate: float = 0.1,
    num_epochs: int = 1000,
    scale: bool = True,
    density_prior: Union[str, np.ndarray, None] = 'rna_count_based',
    random_state: Optional[int] = None,
    verbose: bool = True,
    # Regularization parameters
    lambda_d: float = 0,
    lambda_g1: float = 1,
    lambda_g2: float = 0,
    lambda_r: float = 0,
    # Constrained mode parameters
    lambda_count: float = 1,
    lambda_f_reg: float = 1,
    target_count: Optional[int] = None,
) -> AnnData:
    """
    Map single-cell data to spatial coordinates using Tangram.

    This is the main training function that learns a mapping matrix between
    single cells and spatial spots using gradient descent optimization.

    Parameters
    ----------
    adata_sc : AnnData
        Single-cell data (must run prepare_data first)
    adata_sp : AnnData
        Spatial data (must run prepare_data first)
    mode : str, default='cells'
        Mapping mode:
        - 'cells': Map individual cells (higher resolution, slower)
        - 'clusters': Map cell type averages (faster, uses cluster_label)
        - 'constrained': Map with cell count constraints (requires target_count)
    cluster_label : str, optional
        Column in adata_sc.obs for cluster aggregation. Required for 'clusters' mode.
    cv_train_genes : List[str], optional
        Genes to use for training (for cross-validation). If None, uses all training_genes.
    device : str or torch.device, default='cpu'
        Device for training ('cpu', 'cuda:0', etc.)
    learning_rate : float, default=0.1
        Learning rate for optimizer
    num_epochs : int, default=1000
        Number of training epochs
    scale : bool, default=True
        For clusters mode: weight by cluster size
    density_prior : str, ndarray, or None, default='rna_count_based'
        Density prior for spots: 'rna_count_based', 'uniform', custom array, or None
    random_state : int, optional
        Random seed for reproducibility
    verbose : bool, default=True
        Print training progress
    lambda_d : float, default=0
        Strength of density regularizer. Automatically set to 1 if density_prior is provided.
    lambda_g1 : float, default=1
        Strength of gene-voxel cosine similarity term (main loss)
    lambda_g2 : float, default=0
        Strength of voxel-gene cosine similarity term
    lambda_r : float, default=0
        Strength of entropy regularizer (promotes peaked probabilities)
    lambda_count : float, default=1
        For constrained mode: regularizer for count term
    lambda_f_reg : float, default=1
        For constrained mode: regularizer for filter (promotes Boolean values)
    target_count : int, optional
        For constrained mode: expected number of cells per spot

    Returns
    -------
    AnnData
        Cell-by-spot mapping matrix with:
        - X: mapping probabilities (cells x spots)
        - obs: cell metadata from adata_sc
        - var: spot metadata from adata_sp
        - uns['train_genes_df']: training gene scores
        - uns['training_history']: loss history

    Examples
    --------
    >>> # Clusters mode (faster)
    >>> adata_map = map_cells_to_space(
    ...     adata_sc, adata_sp,
    ...     mode='clusters',
    ...     cluster_label='cell_type',
    ...     num_epochs=1000,
    ...     device='cuda:0'
    ... )
    >>>
    >>> # Cells mode (higher resolution)
    >>> adata_map = map_cells_to_space(
    ...     adata_sc, adata_sp,
    ...     mode='cells',
    ...     num_epochs=1000,
    ...     lambda_g1=1,
    ...     lambda_r=0.5,
    ... )
    """
    # Validate inputs first (before importing heavy dependencies)
    if mode not in ['cells', 'clusters', 'constrained']:
        raise ValueError(f"mode must be 'cells', 'clusters', or 'constrained', got '{mode}'")

    if mode == 'clusters' and cluster_label is None:
        raise ValueError("cluster_label must be provided for 'clusters' mode")

    if mode == 'constrained' and target_count is None:
        raise ValueError("target_count must be provided for 'constrained' mode")

    import torch
    tg = check_tangram_installed()

    # Run mapping
    adata_map = tg.map_cells_to_space(
        adata_sc=adata_sc,
        adata_sp=adata_sp,
        mode=mode,
        cluster_label=cluster_label,
        cv_train_genes=cv_train_genes,
        device=device,
        learning_rate=learning_rate,
        num_epochs=num_epochs,
        scale=scale,
        density_prior=density_prior,
        random_state=random_state,
        verbose=verbose,
        lambda_d=lambda_d,
        lambda_g1=lambda_g1,
        lambda_g2=lambda_g2,
        lambda_r=lambda_r,
        lambda_count=lambda_count,
        lambda_f_reg=lambda_f_reg,
        target_count=target_count,
    )

    return adata_map


def project_genes(
    adata_map: AnnData,
    adata_sc: AnnData,
    cluster_label: Optional[str] = None,
    scale: bool = True,
) -> AnnData:
    """
    Transfer gene expression from single-cell data to spatial coordinates.

    Projects gene expression using the mapping matrix learned by map_cells_to_space.

    Parameters
    ----------
    adata_map : AnnData
        Mapping result from map_cells_to_space (cell-by-spot)
    adata_sc : AnnData
        Single-cell data with genes to project
    cluster_label : str, optional
        Must match cluster_label used in map_cells_to_space
    scale : bool, default=True
        Must match scale parameter used in map_cells_to_space

    Returns
    -------
    AnnData
        Spot-by-gene AnnData with projected gene expression:
        - X: projected expression (spots x genes)
        - obs: spot metadata from adata_map.var
        - var: gene metadata from adata_sc.var
        - var['is_training']: indicates training genes

    Examples
    --------
    >>> adata_ge = project_genes(adata_map, adata_sc)
    >>> # Compare projected vs measured expression
    >>> df_compare = compare_spatial_geneexp(adata_ge, adata_sp, adata_sc)
    """
    tg = check_tangram_installed()

    adata_ge = tg.project_genes(
        adata_map=adata_map,
        adata_sc=adata_sc,
        cluster_label=cluster_label,
        scale=scale,
    )

    return adata_ge


def project_cell_annotations(
    adata_map: AnnData,
    adata_sp: AnnData,
    annotation: str = 'cell_type',
    threshold: float = 0.5,
) -> None:
    """
    Transfer cell annotations to spatial data.

    Computes cell type proportions per spot using the mapping matrix.

    Parameters
    ----------
    adata_map : AnnData
        Mapping result from map_cells_to_space
    adata_sp : AnnData
        Spatial data to annotate (modified in-place)
    annotation : str, default='cell_type'
        Column in adata_map.obs containing annotations
    threshold : float, default=0.5
        For constrained mode: minimum F_out value to include cell

    Returns
    -------
    None
        Updates adata_sp.obsm['tangram_ct_pred'] with cell type proportions

    Examples
    --------
    >>> project_cell_annotations(adata_map, adata_sp, annotation='cell_type')
    >>> print(adata_sp.obsm['tangram_ct_pred'].head())
    """
    tg = check_tangram_installed()

    tg.project_cell_annotations(
        adata_map=adata_map,
        adata_sp=adata_sp,
        annotation=annotation,
        threshold=threshold,
    )


def compare_spatial_geneexp(
    adata_ge: AnnData,
    adata_sp: AnnData,
    adata_sc: Optional[AnnData] = None,
    genes: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Compare projected gene expression with measured spatial data.

    Computes cosine similarity between projected and measured expression.

    Parameters
    ----------
    adata_ge : AnnData
        Projected gene expression from project_genes
    adata_sp : AnnData
        Measured spatial data
    adata_sc : AnnData, optional
        Single-cell data for sparsity comparison
    genes : List[str], optional
        Genes to compare. If None, uses all training genes.

    Returns
    -------
    pd.DataFrame
        Comparison results with columns:
        - 'score': cosine similarity (0-1)
        - 'is_training': whether gene was used for training
        - 'sparsity_sp': sparsity in spatial data
        - 'sparsity_sc': sparsity in single-cell data (if adata_sc provided)
        - 'sparsity_diff': difference in sparsity

    Examples
    --------
    >>> df_compare = compare_spatial_geneexp(adata_ge, adata_sp, adata_sc)
    >>> print(f"Mean test score: {df_compare['score'].mean():.3f}")
    """
    tg = check_tangram_installed()

    df = tg.compare_spatial_geneexp(
        adata_ge=adata_ge,
        adata_sp=adata_sp,
        adata_sc=adata_sc,
        genes=genes,
    )

    return df


def cross_val(
    adata_sc: AnnData,
    adata_sp: AnnData,
    cluster_label: Optional[str] = None,
    mode: str = 'clusters',
    scale: bool = True,
    lambda_d: float = 0,
    lambda_g1: float = 1,
    lambda_g2: float = 0,
    lambda_r: float = 0,
    lambda_count: float = 1,
    lambda_f_reg: float = 1,
    target_count: Optional[int] = None,
    num_epochs: int = 1000,
    device: Union[str, 'torch.device'] = 'cuda:0',
    learning_rate: float = 0.1,
    density_prior: Union[str, np.ndarray, None] = None,
    random_state: Optional[int] = None,
    cv_mode: str = 'loo',
    return_gene_pred: bool = False,
    verbose: bool = False,
) -> Union[Dict, Tuple[Dict, AnnData, pd.DataFrame]]:
    """
    Perform cross-validation to assess gene prediction accuracy.

    Iteratively holds out genes and measures prediction accuracy.

    Parameters
    ----------
    adata_sc : AnnData
        Single-cell data
    adata_sp : AnnData
        Spatial data
    cluster_label : str, optional
        For clusters mode
    mode : str, default='clusters'
        Mapping mode ('cells', 'clusters', 'constrained')
    scale : bool, default=True
        Weight by cluster size
    lambda_d, lambda_g1, lambda_g2, lambda_r : float
        Regularization parameters (see map_cells_to_space)
    lambda_count, lambda_f_reg : float
        Constrained mode parameters
    target_count : int, optional
        For constrained mode
    num_epochs : int, default=1000
        Training epochs per fold
    device : str or torch.device, default='cuda:0'
        Computation device
    learning_rate : float, default=0.1
        Learning rate
    density_prior : str, ndarray, or None
        Density prior
    random_state : int, optional
        Random seed
    cv_mode : str, default='loo'
        Cross-validation mode: 'loo' (leave-one-out) or '10fold'
    return_gene_pred : bool, default=False
        Return predicted expression for test genes
    verbose : bool, default=False
        Print progress

    Returns
    -------
    Dict or tuple
        cv_dict with 'avg_test_score' and 'avg_train_score'
        If return_gene_pred=True: also returns adata_ge_cv and test_gene_df

    Examples
    --------
    >>> cv_dict = cross_val(adata_sc, adata_sp, mode='clusters', cluster_label='cell_type')
    >>> print(f"CV test score: {cv_dict['avg_test_score']:.3f}")
    >>>
    >>> # With gene predictions
    >>> cv_dict, adata_ge_cv, df_test = cross_val(
    ...     adata_sc, adata_sp, return_gene_pred=True, cv_mode='loo'
    ... )
    """
    tg = check_tangram_installed()

    result = tg.cross_val(
        adata_sc=adata_sc,
        adata_sp=adata_sp,
        cluster_label=cluster_label,
        mode=mode,
        scale=scale,
        lambda_d=lambda_d,
        lambda_g1=lambda_g1,
        lambda_g2=lambda_g2,
        lambda_r=lambda_r,
        lambda_count=lambda_count,
        lambda_f_reg=lambda_f_reg,
        target_count=target_count,
        num_epochs=num_epochs,
        device=device,
        learning_rate=learning_rate,
        density_prior=density_prior,
        random_state=random_state,
        cv_mode=cv_mode,
        return_gene_pred=return_gene_pred,
        verbose=verbose,
    )

    return result


def eval_metric(
    df_all_genes: pd.DataFrame,
    test_genes: Optional[List[str]] = None,
) -> Tuple[Dict, Tuple]:
    """
    Compute evaluation metrics on test genes.

    Parameters
    ----------
    df_all_genes : pd.DataFrame
        Output from compare_spatial_geneexp
    test_genes : List[str], optional
        Genes to evaluate. If None, uses non-training genes.

    Returns
    -------
    Tuple[Dict, Tuple]
        - metric_dict with: 'avg_test_score', 'avg_train_score', 'sp_sparsity_score', 'auc_score'
        - auc_coordinates for plotting

    Examples
    --------
    >>> metrics, auc_coords = eval_metric(df_compare)
    >>> print(f"AUC score: {metrics['auc_score']:.3f}")
    """
    tg = check_tangram_installed()

    metric_dict, auc_coordinates = tg.eval_metric(
        df_all_genes=df_all_genes,
        test_genes=test_genes,
    )

    return metric_dict, auc_coordinates


def count_cell_annotations(
    adata_map: AnnData,
    adata_sc: AnnData,
    adata_sp: AnnData,
    annotation: str = 'cell_type',
    threshold: float = 0.5,
) -> None:
    """
    Count cells per spot for each annotation (deconvolution).

    Requires constrained mode mapping with segmentation information.

    Parameters
    ----------
    adata_map : AnnData
        Mapping result from constrained mode
    adata_sc : AnnData
        Single-cell data
    adata_sp : AnnData
        Spatial data with image_features from squidpy
    annotation : str, default='cell_type'
        Cell annotation column
    threshold : float, default=0.5
        Minimum F_out value to include cell

    Returns
    -------
    None
        Updates adata_sp.obsm['tangram_ct_count'] with cell counts per spot

    Examples
    --------
    >>> # Requires segmentation data in adata_sp.obsm['image_features']
    >>> count_cell_annotations(adata_map, adata_sc, adata_sp, annotation='cell_type')
    """
    tg = check_tangram_installed()

    tg.count_cell_annotations(
        adata_map=adata_map,
        adata_sc=adata_sc,
        adata_sp=adata_sp,
        annotation=annotation,
        threshold=threshold,
    )


def create_segment_cell_df(adata_sp: AnnData) -> None:
    """
    Create segmentation cell dataframe for deconvolution.

    Prepares segmentation data from squidpy image features.

    Parameters
    ----------
    adata_sp : AnnData
        Spatial data with image_features from squidpy.im.calculate_image_features

    Returns
    -------
    None
        Updates adata_sp with:
        - uns['tangram_cell_segmentation']: cell segmentation dataframe
        - obsm['tangram_spot_centroids']: spot centroids

    Examples
    --------
    >>> import squidpy as sq
    >>> sq.im.calculate_image_features(adata_sp, ...)
    >>> create_segment_cell_df(adata_sp)
    """
    tg = check_tangram_installed()

    tg.create_segment_cell_df(adata_sp)


def deconvolve_cell_annotations(
    adata_sp: AnnData,
    filter_cell_annotation: Optional[List[str]] = None,
) -> AnnData:
    """
    Assign cell annotations to each segmented cell.

    Creates an AnnData with individual cell assignments.

    Parameters
    ----------
    adata_sp : AnnData
        Spatial data with tangram_ct_count and segmentation
    filter_cell_annotation : List[str], optional
        Cell types to include. If None, uses all.

    Returns
    -------
    AnnData
        Cell-level assignments with obs['cluster'] as annotation

    Examples
    --------
    >>> adata_cells = deconvolve_cell_annotations(adata_sp)
    >>> sq.pl.spatial_scatter(adata_cells, color='cluster')
    """
    tg = check_tangram_installed()

    adata_segment = tg.deconvolve_cell_annotations(
        adata_sp=adata_sp,
        filter_cell_annotation=filter_cell_annotation,
    )

    return adata_segment


def extract_deconvolution_results(
    adata_sp: AnnData,
    annotation_key: str = 'tangram_ct_pred',
    normalize: bool = True,
) -> pd.DataFrame:
    """
    Extract cell type proportions from Tangram projections.

    Parameters
    ----------
    adata_sp : AnnData
        Spatial data with Tangram projections
    annotation_key : str, default='tangram_ct_pred'
        Key in adata_sp.obsm with projected annotations
    normalize : bool, default=True
        Normalize proportions to sum to 1 per spot

    Returns
    -------
    pd.DataFrame
        Cell type proportions per spot (spots x cell_types)

    Examples
    --------
    >>> props = extract_deconvolution_results(adata_sp)
    >>> print(props.head())
    """
    if annotation_key not in adata_sp.obsm:
        raise KeyError(
            f"'{annotation_key}' not found in adata_sp.obsm. "
            "Run project_cell_annotations() first."
        )

    props = pd.DataFrame(
        adata_sp.obsm[annotation_key].values,
        index=adata_sp.obs_names,
        columns=adata_sp.obsm[annotation_key].columns
    )

    if normalize:
        props = props.div(props.sum(axis=1), axis=0)
        props = props.fillna(0)

    return props


def get_training_scores(adata_map: AnnData) -> pd.DataFrame:
    """
    Get training scores for training genes.

    Parameters
    ----------
    adata_map : AnnData
        Mapping result from map_cells_to_space

    Returns
    -------
    pd.DataFrame
        Training scores with columns:
        - 'train_score': cosine similarity
        - 'sparsity_sc': single-cell sparsity
        - 'sparsity_sp': spatial sparsity
        - 'sparsity_diff': sparsity difference

    Examples
    --------
    >>> df_scores = get_training_scores(adata_map)
    >>> print(df_scores.sort_values('train_score', ascending=False).head())
    """
    if 'train_genes_df' not in adata_map.uns:
        raise KeyError("'train_genes_df' not found. Run map_cells_to_space() first.")

    return adata_map.uns['train_genes_df']


def annotate_gene_sparsity(adata: AnnData) -> None:
    """
    Annotate gene sparsity in AnnData.

    Adds 'sparsity' column to adata.var (1 - % non-zero observations).

    Parameters
    ----------
    adata : AnnData
        Data to annotate (modified in-place)

    Returns
    -------
    None
    """
    tg = check_tangram_installed()

    tg.annotate_gene_sparsity(adata)


def check_mapping_quality(
    adata_map: AnnData,
    min_score: float = 0.5,
) -> dict:
    """
    Check mapping quality from training gene scores.

    Parameters
    ----------
    adata_map : AnnData
        Mapping result from map_cells_to_space
    min_score : float, default=0.5
        Minimum average training score threshold for warning

    Returns
    -------
    dict
        Quality report with keys:
        - 'avg_score': mean training score across genes
        - 'median_score': median training score
        - 'min_score': minimum training score
        - 'max_score': maximum training score
        - 'passes_threshold': bool, whether avg_score >= min_score
        - 'n_training_genes': number of genes used for training

    Examples
    --------
    >>> report = check_mapping_quality(adata_map, min_score=0.7)
    >>> print(f"Average score: {report['avg_score']:.3f}")
    >>> if not report['passes_threshold']:
    ...     print("Warning: low mapping quality")
    """
    df_scores = get_training_scores(adata_map)
    avg_score = df_scores['train_score'].mean()
    median_score = df_scores['train_score'].median()
    min_s = df_scores['train_score'].min()
    max_s = df_scores['train_score'].max()

    passes = avg_score >= min_score
    if not passes:
        warnings.warn(
            f"Average training score ({avg_score:.3f}) is below threshold ({min_score}). "
            f"Consider using marker genes, checking gene overlap, or increasing num_epochs."
        )

    return {
        'avg_score': avg_score,
        'median_score': median_score,
        'min_score': min_s,
        'max_score': max_s,
        'passes_threshold': passes,
        'n_training_genes': len(df_scores),
    }


def export_results(
    adata_map: AnnData,
    adata_sp: AnnData,
    output_dir: str,
    annotation_key: Optional[str] = None,
    prefix: str = 'tangram',
) -> None:
    """
    Export Tangram mapping results to files.

    Parameters
    ----------
    adata_map : AnnData
        Mapping result
    adata_sp : AnnData
        Spatial data with projections
    output_dir : str
        Directory for output files
    annotation_key : str, optional
        If provided, export cell type proportions
    prefix : str, default='tangram'
        Prefix for output files

    Returns
    -------
    None

    Examples
    --------
    >>> export_results(adata_map, adata_sp, './output', annotation_key='cell_type')
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Export mapping matrix (handle sparse matrices)
    mapping_matrix = adata_map.X
    if sparse.issparse(mapping_matrix):
        mapping_matrix = mapping_matrix.toarray()
    mapping_df = pd.DataFrame(
        mapping_matrix,
        index=adata_map.obs_names,
        columns=adata_map.var_names
    )
    mapping_df.to_csv(os.path.join(output_dir, f'{prefix}_mapping_matrix.csv'))

    # Export training scores
    if 'train_genes_df' in adata_map.uns:
        adata_map.uns['train_genes_df'].to_csv(
            os.path.join(output_dir, f'{prefix}_training_scores.csv')
        )

    # Export cell type proportions
    if annotation_key and 'tangram_ct_pred' in adata_sp.obsm:
        adata_sp.obsm['tangram_ct_pred'].to_csv(
            os.path.join(output_dir, f'{prefix}_celltype_proportions.csv')
        )

    # Export training history
    if 'training_history' in adata_map.uns:
        hist = adata_map.uns['training_history']
        try:
            if isinstance(hist, dict):
                hist_df = pd.DataFrame(hist)
            elif isinstance(hist, list):
                hist_df = pd.DataFrame(hist)
            else:
                hist_df = pd.DataFrame(hist)
            hist_df.to_csv(
                os.path.join(output_dir, f'{prefix}_training_history.csv'),
                index=False
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not export training_history: {e}")

    logger.info(f"Results exported to {output_dir}")
