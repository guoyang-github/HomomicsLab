"""
Core analysis functions for SpaGCN spatial domain identification.

This module provides functions for:
- Data preprocessing and preparation
- Adjacency matrix calculation (with/without histology)
- Optimal parameter search (l and resolution)
- SpaGCN model training and prediction
- Domain refinement
- Spatially variable gene (SVG) identification
- Meta gene discovery

Author: Yang Guo
Date: 2026-04-03
"""

import random
from typing import List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import scanpy as sc
import torch
from anndata import AnnData
from scipy.sparse import issparse


# ==============================================================================
# Data Preparation
# ==============================================================================

def prepare_data(
    adata: AnnData,
    min_counts: int = 100,
    min_genes: int = 3,
    min_cells: int = 3,
    max_counts: Optional[int] = None,
    max_genes: Optional[int] = None,
    filter_mitochondrial: bool = True,
    filter_ribosomal: bool = False,
    normalize: bool = True,
    log_transform: bool = True,
    hvg_selection: bool = True,
    n_top_genes: int = 3000,
) -> AnnData:
    """
    Prepare spatial transcriptomics data for SpaGCN analysis.

    SpaGCN requires normalized and log-transformed data. Highly variable
    gene selection is recommended to reduce noise and computational cost.

    Parameters
    ----------
    adata : AnnData
        Raw spatial transcriptomics data
    min_counts : int, default=100
        Minimum total counts per spot
    min_genes : int, default=3
        Minimum genes expressed per spot
    min_cells : int, default=3
        Minimum cells expressing a gene
    max_counts : int, optional
        Maximum total counts per spot
    max_genes : int, optional
        Maximum genes expressed per spot
    filter_mitochondrial : bool, default=True
        Remove mitochondrial genes (MT-*)
    filter_ribosomal : bool, default=False
        Remove ribosomal genes (RPL*, RPS*)
    normalize : bool, default=True
        Normalize per cell
    log_transform : bool, default=True
        Log1p transform
    hvg_selection : bool, default=True
        Select highly variable genes
    n_top_genes : int, default=3000
        Number of HVGs to select

    Returns
    -------
    AnnData
        Preprocessed data ready for SpaGCN

    Examples
    --------
    >>> adata = prepare_data(adata_raw, n_top_genes=3000)
    >>> adata = prepare_data(adata_raw, hvg_selection=False)
    """
    adata = adata.copy()

    # Filter cells
    if min_counts is not None or min_genes is not None or max_counts is not None or max_genes is not None:
        sc.pp.filter_cells(adata, min_counts=min_counts)
        if min_genes:
            sc.pp.filter_cells(adata, min_genes=min_genes)
        if max_counts:
            sc.pp.filter_cells(adata, max_counts=max_counts)
        if max_genes:
            sc.pp.filter_cells(adata, max_genes=max_genes)

    # Filter genes
    if min_cells:
        sc.pp.filter_genes(adata, min_cells=min_cells)

    # Filter special genes
    if filter_mitochondrial:
        adata = adata[:, ~adata.var_names.str.startswith('MT-')]
    if filter_ribosomal:
        adata = adata[:, ~(adata.var_names.str.startswith('RPL') | adata.var_names.str.startswith('RPS'))]

    # Store raw counts
    adata.raw = adata.copy()

    # Normalization and log transform
    if normalize:
        sc.pp.normalize_total(adata, target_sum=1e4)
    if log_transform:
        sc.pp.log1p(adata)

    # HVG selection
    if hvg_selection:
        sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes, flavor='seurat')
        adata = adata[:, adata.var.highly_variable].copy()

    print(f"After preprocessing: {adata.n_obs} spots, {adata.n_vars} genes")
    return adata


def calculate_adjacency_matrix(
    adata: AnnData,
    x_column: str = "array_col",
    y_column: str = "array_row",
    x_pixel_column: Optional[str] = None,
    y_pixel_column: Optional[str] = None,
    histology: bool = False,
    image: Optional[np.ndarray] = None,
    beta: int = 49,
    alpha: float = 1.0,
    platform: str = "visium"
) -> np.ndarray:
    """
    Calculate adjacency matrix for spatial data.

    This function creates a distance-based adjacency matrix that can optionally
    incorporate histology image information. The adjacency matrix is used by
    SpaGCN to define the spatial graph structure.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    x_column : str, default="array_col"
        Column name for x coordinates (array coordinates)
    y_column : str, default="array_row"
        Column name for y coordinates (array coordinates)
    x_pixel_column : str, optional
        Column name for x pixel coordinates (for histology)
    y_pixel_column : str, optional
        Column name for y pixel coordinates (for histology)
    histology : bool, default=False
        Whether to include histology information
    image : np.ndarray, optional
        Histology image (H&E). Required if histology=True.
        Image should be in format (height, width, channels)
    beta : int, default=49
        Area around each spot to extract color information.
        Only used when histology=True.
    alpha : float, default=1.0
        Weight for histology in adjacency calculation.
        Higher values give more weight to histology.
    platform : str, default="visium"
        Spatial platform type ("visium", "st", "slideseq")

    Returns
    -------
    np.ndarray
        Adjacency matrix (distance matrix) of shape (n_spots, n_spots)

    Examples
    --------
    >>> # Without histology
    >>> adj = calculate_adjacency_matrix(adata, histology=False)

    >>> # With histology
    >>> adj = calculate_adjacency_matrix(
    ...     adata,
    ...     x_pixel_column="x_pixel",
    ...     y_pixel_column="y_pixel",
    ...     histology=True,
    ...     image=he_image,
    ...     beta=49,
    ...     alpha=1.0
    ... )
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    x = adata.obs[x_column].tolist()
    y = adata.obs[y_column].tolist()

    if histology:
        if image is None:
            raise ValueError("Image is required when histology=True")
        if x_pixel_column is None or y_pixel_column is None:
            raise ValueError(
                "x_pixel_column and y_pixel_column are required for histology"
            )
        x_pixel = adata.obs[x_pixel_column].tolist()
        y_pixel = adata.obs[y_pixel_column].tolist()

        adj = spg.calculate_adj_matrix(
            x=x,
            y=y,
            x_pixel=x_pixel,
            y_pixel=y_pixel,
            image=image,
            beta=beta,
            alpha=alpha,
            histology=True
        )
    else:
        adj = spg.calculate_adj_matrix(
            x=x,
            y=y,
            histology=False
        )

    return adj


# ==============================================================================
# Parameter Search
# ==============================================================================

def search_optimal_l(
    adj: np.ndarray,
    target_p: float = 0.5,
    start: float = 0.01,
    end: float = 1000,
    tol: float = 0.01,
    max_run: int = 100
) -> float:
    """
    Search for optimal l parameter given target p.

    The l parameter controls the distance decay in the adjacency matrix.
    p represents the percentage of total expression contributed by neighborhoods.

    Parameters
    ----------
    adj : np.ndarray
        Adjacency matrix from calculate_adjacency_matrix
    target_p : float, default=0.5
        Target percentage (0-1 or >1 if you want unbounded search)
    start : float, default=0.01
        Starting value for l search
    end : float, default=1000
        Ending value for l search
    tol : float, default=0.01
        Tolerance for convergence
    max_run : int, default=100
        Maximum iterations

    Returns
    -------
    float
        Optimal l value

    Examples
    --------
    >>> l = search_optimal_l(adj, target_p=0.5)
    >>> l = search_optimal_l(adj, target_p=0.3, start=0.1, end=100)
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    l = spg.search_l(
        p=target_p,
        adj=adj,
        start=start,
        end=end,
        tol=tol,
        max_run=max_run
    )

    if l is None:
        print(f"Warning: Could not find l in range [{start}, {end}]")
        print(f"Trying extended range...")
        l = spg.search_l(
            p=target_p,
            adj=adj,
            start=start/10,
            end=end*10,
            tol=tol,
            max_run=max_run
        )

    return l


def search_optimal_resolution(
    adata: AnnData,
    adj: np.ndarray,
    l: float,
    target_clusters: int,
    start: float = 0.4,
    step: float = 0.1,
    tol: float = 5e-3,
    lr: float = 0.05,
    max_epochs: int = 10,
    r_seed: int = 100,
    t_seed: int = 100,
    n_seed: int = 100,
    max_run: int = 10
) -> float:
    """
    Search for optimal resolution to achieve target number of clusters.

    Uses binary search to find the Louvain resolution that produces
    approximately the target number of clusters.

    Parameters
    ----------
    adata : AnnData
        Preprocessed spatial data
    adj : np.ndarray
        Adjacency matrix
    l : float
        Spatial weight parameter from search_optimal_l
    target_clusters : int
        Desired number of spatial domains
    start : float, default=0.4
        Starting resolution
    step : float, default=0.1
        Step size for resolution search
    tol : float, default=5e-3
        Convergence tolerance
    lr : float, default=0.05
        Learning rate for training
    max_epochs : int, default=10
        Epochs for each test run (can be low for search)
    r_seed : int, default=100
        Random seed
    t_seed : int, default=100
        Torch seed
    n_seed : int, default=100
        NumPy seed
    max_run : int, default=10
        Maximum iterations

    Returns
    -------
    float
        Optimal resolution

    Examples
    --------
    >>> res = search_optimal_resolution(adata, adj, l=0.8, target_clusters=7)
    >>> res = search_optimal_resolution(adata, adj, l=0.8, target_clusters=10, max_epochs=20)
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    res = spg.search_res(
        adata=adata,
        adj=adj,
        l=l,
        target_num=target_clusters,
        start=start,
        step=step,
        tol=tol,
        lr=lr,
        max_epochs=max_epochs,
        r_seed=r_seed,
        t_seed=t_seed,
        n_seed=n_seed,
        max_run=max_run
    )

    return res


# ==============================================================================
# SpaGCN Model
# ==============================================================================

def run_spagcn(
    adata: AnnData,
    adj: np.ndarray,
    l: float,
    resolution: float = 0.4,
    num_pcs: int = 50,
    lr: float = 0.005,
    max_epochs: int = 2000,
    weight_decay: float = 0,
    opt: str = "admin",
    init_spa: bool = True,
    init: str = "louvain",
    n_neighbors: int = 10,
    n_clusters: Optional[int] = None,
    tol: float = 1e-3,
    r_seed: int = 100,
    t_seed: int = 100,
    n_seed: int = 100,
    return_probabilities: bool = False
) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
    """
    Run SpaGCN to identify spatial domains.

    This is the main function for training SpaGCN and predicting spatial domains.

    Parameters
    ----------
    adata : AnnData
        Preprocessed spatial data
    adj : np.ndarray
        Adjacency matrix
    l : float
        Spatial weight parameter
    resolution : float, default=0.4
        Louvain resolution (use search_optimal_resolution if target clusters known)
    num_pcs : int, default=50
        Number of principal components
    lr : float, default=0.005
        Learning rate
    max_epochs : int, default=2000
        Maximum training epochs
    weight_decay : float, default=0
        Weight decay for optimizer
    opt : str, default="admin"
        Optimizer ("admin" or "adam")
    init_spa : bool, default=True
        Initialize with spatial information
    init : str, default="louvain"
        Initialization method ("louvain" or "kmeans")
    n_neighbors : int, default=10
        Number of neighbors for Louvain
    n_clusters : int, optional
        Number of clusters (for kmeans initialization)
    tol : float, default=1e-3
        Convergence tolerance
    r_seed : int, default=100
        Random seed
    t_seed : int, default=100
        Torch seed
    n_seed : int, default=100
        NumPy seed
    return_probabilities : bool, default=False
        Whether to return cluster probabilities

    Returns
    -------
    np.ndarray or tuple
        Domain predictions (and probabilities if requested)

    Examples
    --------
    >>> # Basic usage
    >>> l = search_optimal_l(adj)
    >>> domains = run_spagcn(adata, adj, l=l)

    >>> # With target clusters
    >>> res = search_optimal_resolution(adata, adj, l=l, target_clusters=7)
    >>> domains, prob = run_spagcn(adata, adj, l=l, resolution=res, return_probabilities=True)
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    # Set seeds
    random.seed(r_seed)
    torch.manual_seed(t_seed)
    np.random.seed(n_seed)

    # Initialize and train
    clf = spg.SpaGCN()
    clf.set_l(l)

    clf.train(
        adata=adata,
        adj=adj,
        num_pcs=num_pcs,
        lr=lr,
        max_epochs=max_epochs,
        weight_decay=weight_decay,
        init_spa=init_spa,
        init=init,
        n_neighbors=n_neighbors,
        n_clusters=n_clusters,
        res=resolution,
        tol=tol,
        opt=opt
    )

    # Predict
    y_pred, prob = clf.predict()

    if return_probabilities:
        return y_pred, prob
    return y_pred


def refine_domains(
    adata: AnnData,
    predictions: np.ndarray,
    x_column: str = "array_col",
    y_column: str = "array_row",
    shape: str = "hexagon"
) -> List:
    """
    Refine domain predictions using spatial smoothing.

    Post-processing step that assigns each spot to the most common
    domain among its neighbors, reducing noisy predictions.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    predictions : np.ndarray
        Domain predictions from run_spagcn
    x_column : str, default="array_col"
        Column name for x coordinates
    y_column : str, default="array_row"
        Column name for y coordinates
    shape : str, default="hexagon"
        Spot shape: "hexagon" for Visium, "square" for ST

    Returns
    -------
    List
        Refined domain predictions

    Examples
    --------
    >>> refined = refine_domains(adata, predictions, shape="hexagon")
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    x = adata.obs[x_column].tolist()
    y = adata.obs[y_column].tolist()

    # Calculate 2D adjacency
    adj_2d = spg.calculate_adj_matrix(x=x, y=y, histology=False)

    # Refine predictions
    refined = spg.refine(
        sample_id=adata.obs.index.tolist(),
        pred=predictions.tolist(),
        dis=adj_2d,
        shape=shape
    )

    return refined


# ==============================================================================
# Spatially Variable Genes (SVGs)
# ==============================================================================

def identify_svgs(
    adata: AnnData,
    target_domain: Union[int, str],
    domain_column: str = "pred",
    x_column: str = "array_col",
    y_column: str = "array_row",
    min_in_group_fraction: float = 0.8,
    min_in_out_group_ratio: float = 1.0,
    min_fold_change: float = 1.5,
    num_min_neighbors: int = 10,
    num_max_neighbors: int = 14,
    max_neighbor_ratio: float = 0.5
) -> pd.DataFrame:
    """
    Identify spatially variable genes (SVGs) for a target domain.

    SVGs are genes that are specifically expressed in a spatial domain
    compared to neighboring domains.

    Parameters
    ----------
    adata : AnnData
        Spatial data with domain predictions in .obs
    target_domain : int or str
        Target spatial domain to find SVGs for
    domain_column : str, default="pred"
        Column name containing domain predictions
    x_column : str, default="array_col"
        Column name for x coordinates
    y_column : str, default="array_row"
        Column name for y coordinates
    min_in_group_fraction : float, default=0.8
        Minimum fraction of cells in target domain expressing the gene
    min_in_out_group_ratio : float, default=1.0
        Minimum ratio of in-group to out-group expression fraction
    min_fold_change : float, default=1.5
        Minimum fold change between in-group and out-group
    num_min_neighbors : int, default=10
        Minimum number of neighbors to consider
    num_max_neighbors : int, default=14
        Maximum number of neighbors to consider
    max_neighbor_ratio : float, default=0.5
        Ratio for determining neighboring domains

    Returns
    -------
    pd.DataFrame
        DataFrame with SVG information:
        - genes: Gene names
        - in_group_fraction: Fraction expressing in target
        - out_group_fraction: Fraction expressing out of target
        - in_out_group_ratio: Ratio of fractions
        - fold_change: Expression fold change
        - pvals_adj: Adjusted p-values

    Examples
    --------
    >>> svgs = identify_svgs(adata, target_domain=0)
    >>> svgs = identify_svgs(adata, target_domain="Layer1", domain_column="domain")
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    # Get coordinates
    x = adata.obs[x_column].tolist()
    y = adata.obs[y_column].tolist()

    # Calculate 2D adjacency for radius search
    adj_2d = spg.calculate_adj_matrix(x=x, y=y, histology=False)

    # Search for optimal radius
    start = np.quantile(adj_2d[adj_2d != 0], q=0.001)
    end = np.quantile(adj_2d[adj_2d != 0], q=0.1)

    r = spg.search_radius(
        target_cluster=target_domain,
        cell_id=adata.obs.index.tolist(),
        x=x,
        y=y,
        pred=adata.obs[domain_column].tolist(),
        start=start,
        end=end,
        num_min=num_min_neighbors,
        num_max=num_max_neighbors,
        max_run=100
    )

    if r is None:
        raise RuntimeError(
            f"Could not find optimal radius for domain {target_domain}. "
            "Try adjusting num_min_neighbors/num_max_neighbors or check domain size."
        )

    # Find neighboring domains
    nbr_domains = spg.find_neighbor_clusters(
        target_cluster=target_domain,
        cell_id=adata.obs.index.tolist(),
        x=x,
        y=y,
        pred=adata.obs[domain_column].tolist(),
        radius=r,
        ratio=max_neighbor_ratio
    )

    # Limit to top 3 neighbors
    nbr_domains = nbr_domains[:3]

    # Rank genes
    de_genes_info = spg.rank_genes_groups(
        input_adata=adata,
        target_cluster=target_domain,
        nbr_list=nbr_domains,
        label_col=domain_column,
        adj_nbr=True,
        log=True
    )

    # Filter
    filtered = de_genes_info[
        (de_genes_info["pvals_adj"] < 0.05) &
        (de_genes_info["in_out_group_ratio"] > min_in_out_group_ratio) &
        (de_genes_info["in_group_fraction"] > min_in_group_fraction) &
        (de_genes_info["fold_change"] > min_fold_change)
    ].copy()

    # Sort and annotate
    filtered = filtered.sort_values(by="in_group_fraction", ascending=False)
    filtered["target_domain"] = target_domain
    filtered["neighbors"] = str(nbr_domains)

    print(f"SVGs for domain {target_domain}: {filtered['genes'].tolist()[:10]}")

    return filtered


# ==============================================================================
# Meta Gene Discovery
# ==============================================================================

def find_meta_gene(
    adata: AnnData,
    target_domain: Union[int, str],
    start_gene: str,
    domain_column: str = "pred",
    mean_diff: float = 0,
    early_stop: bool = True,
    max_iter: int = 5,
    use_raw: bool = False
) -> Tuple[str, List]:
    """
    Find meta gene by combining multiple genes through iterative refinement.

    A meta gene is a weighted combination of genes that best represents
    a spatial domain. It is constructed by iteratively adding genes that
    are enriched in the target domain and subtracting genes that are depleted.

    Parameters
    ----------
    adata : AnnData
        Spatial data with domain predictions
    target_domain : int or str
        Target domain to find meta gene for
    start_gene : str
        Starting gene (seed gene)
    domain_column : str, default="pred"
        Column name containing domain predictions
    mean_diff : float, default=0
        Minimum mean difference for continuing
    early_stop : bool, default=True
        Whether to use early stopping
    max_iter : int, default=5
        Maximum iterations
    use_raw : bool, default=False
        Use raw expression values

    Returns
    -------
    tuple
        (meta_gene_name, meta_gene_expression)
        meta_gene_name is a string like "GENE1+GENE2-GENE3"
        meta_gene_expression is a list of expression values

    Examples
    --------
    >>> meta_name, meta_exp = find_meta_gene(adata, target_domain=0, start_gene="GFAP")
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    meta_name, meta_exp = spg.find_meta_gene(
        input_adata=adata,
        pred=adata.obs[domain_column].tolist(),
        target_domain=target_domain,
        start_gene=start_gene,
        mean_diff=mean_diff,
        early_stop=early_stop,
        max_iter=max_iter,
        use_raw=use_raw
    )

    return meta_name, meta_exp


# ==============================================================================
# Multi-Sample Analysis
# ==============================================================================

def run_spagcn_multi_sample(
    adata_list: List[AnnData],
    adj_list: List[np.ndarray],
    l_list: List[float],
    resolution: float = 0.4,
    num_pcs: int = 50,
    lr: float = 0.005,
    max_epochs: int = 2000,
    weight_decay: float = 0,
    opt: str = "admin",
    init_spa: bool = True,
    init: str = "louvain",
    n_neighbors: int = 10,
    n_clusters: Optional[int] = None,
    tol: float = 1e-3,
    r_seed: int = 100,
    t_seed: int = 100,
    n_seed: int = 100,
    return_probabilities: bool = False
) -> dict:
    """
    Run SpaGCN on multiple tissue sections jointly.

    Uses multiSpaGCN to integrate multiple adjacent tissue sections
    and identify consistent spatial domains across samples.

    Parameters
    ----------
    adata_list : List[AnnData]
        List of preprocessed AnnData objects (one per sample)
    adj_list : List[np.ndarray]
        List of adjacency matrices (one per sample)
    l_list : List[float]
        List of spatial weight parameters (one per sample)
    resolution : float, default=0.4
        Louvain resolution for joint clustering
    num_pcs : int, default=50
        Number of principal components
    lr : float, default=0.005
        Learning rate
    max_epochs : int, default=2000
        Maximum training epochs
    weight_decay : float, default=0
        Weight decay for optimizer
    opt : str, default="admin"
        Optimizer ("admin" or "adam")
    init_spa : bool, default=True
        Initialize with spatial information
    init : str, default="louvain"
        Initialization method ("louvain" or "kmeans")
    n_neighbors : int, default=10
        Number of neighbors for Louvain initialization
    n_clusters : int, optional
        Number of clusters for kmeans initialization
    tol : float, default=1e-3
        Convergence tolerance
    r_seed : int, default=100
        Random seed
    t_seed : int, default=100
        Torch seed
    n_seed : int, default=100
        NumPy seed
    return_probabilities : bool, default=False
        Whether to return cluster probabilities

    Returns
    -------
    dict
        Dictionary with keys:
        - "domains": np.ndarray of domain predictions
        - "probabilities": np.ndarray of probabilities (if requested)
        - "adata": Combined AnnData with all samples

    Examples
    --------
    >>> results = run_spagcn_multi_sample(
    ...     adata_list=[adata1, adata2],
    ...     adj_list=[adj1, adj2],
    ...     l_list=[l1, l2],
    ...     resolution=0.2
    ... )
    >>> domains = results["domains"]
    >>> adata_combined = results["adata"]
    """
    try:
        import SpaGCN as spg
    except ImportError:
        raise ImportError(
            "SpaGCN is required. Install with: pip install SpaGCN"
        )

    # Set seeds
    random.seed(r_seed)
    torch.manual_seed(t_seed)
    np.random.seed(n_seed)

    # Initialize and train
    clf = spg.multiSpaGCN()

    clf.train(
        adata_list=adata_list,
        adj_list=adj_list,
        l_list=l_list,
        num_pcs=num_pcs,
        lr=lr,
        max_epochs=max_epochs,
        weight_decay=weight_decay,
        init_spa=init_spa,
        init=init,
        n_neighbors=n_neighbors,
        n_clusters=n_clusters,
        res=resolution,
        tol=tol,
        opt=opt
    )

    # Predict
    y_pred, prob = clf.predict()

    result = {
        "domains": y_pred,
        "adata": clf.adata_all
    }

    if return_probabilities:
        result["probabilities"] = prob

    return result
