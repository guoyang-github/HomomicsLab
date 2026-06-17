"""
Data preprocessing and graph construction for spCLUE.

This module provides functions for preprocessing spatial transcriptomics data
and constructing multi-view graphs (spatial and expression) for contrastive learning.
"""

import scanpy as sc
from sklearn.decomposition import PCA
from scipy.spatial.distance import cdist
import numpy as np
import scipy.sparse as sp


def preprocess(adata, hvgNumber=None):
    """
    Preprocess spatial transcriptomics data.

    Performs filtering, normalization, HVG selection, scaling, and log transformation.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    hvgNumber : int, optional
        Number of highly variable genes to select. If None, uses all genes.

    Returns
    -------
    AnnData
        Preprocessed data
    """
    print("normalized data ---------------->")
    sc.pp.filter_genes(adata, min_counts=1)
    sc.pp.filter_cells(adata, min_counts=1)
    if hvgNumber is not None:
        print(f"========== selecting HVG ============")
        if "count" not in adata.layers:
            raise ValueError(
                "adata.layers['count'] is required for HVG selection with flavor='seurat_v3'. "
                "Please ensure raw counts are stored in adata.layers['count'] before calling preprocess(). "
                "Example: adata.layers['count'] = adata.raw.to_adata().X if adata.raw is not None else adata.X.copy()"
            )
        sc.pp.highly_variable_genes(adata, flavor="seurat_v3", layer="count", n_top_genes=hvgNumber, subset=False)
        adata = adata[:, adata.var["highly_variable"] == True]
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.scale(adata)
    return adata


def prepare_graph(adata, key="spatial", n_neighbors=12, n_comps=50, eps=1e-8, svd_solver="randomized", self_weight=0.3):
    """
    Construct adjacency matrices for spatial or expression graphs.

    Creates KNN graphs from spatial coordinates or PCA-reduced expression profiles,
    then applies symmetric normalization.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    key : str
        Type of graph: 'spatial' (from coordinates) or 'expr' (from expression)
    n_neighbors : int
        Number of neighbors for KNN graph
    n_comps : int
        Number of PCA components for expression graph
    eps : float
        Small constant for numerical stability
    svd_solver : str
        SVD solver for PCA
    self_weight : float
        Weight for self-connections in normalization

    Returns
    -------
    scipy.sparse.coo_matrix
        Normalized adjacency matrix
    """
    n_spots = adata.shape[0]
    assert key in ["spatial", "expr"], "case should be [spatial] or [expr]"
    if key == "spatial":
        print("create adjacent matrix from spatial idx --------------->")
        expr = adata.obsm[key]
        weights = 1. / (cdist(expr, expr, "euclidean") + eps)
    else:
        print("create adjacent matrix from pca expr --------------->")
        expr = PCA(n_components=n_comps, random_state=0, svd_solver=svd_solver).fit_transform(adata.X)
        weights = correlation_graph(expr.T, expr.T)

    print("create knn graph ---->")
    threshold = np.sort(weights)[:, -n_neighbors - 1:-n_neighbors]
    weights[weights < threshold] = 0
    weights = (weights + weights.T) / 2
    weights = weights * (1 - np.eye(n_spots))  # drop the diag

    adjFilter = 0. if key == "spatial" else 0.1
    # convert to bipartite case
    adjBip = np.where(weights > adjFilter, 1, 0)
    print(f"{key} knn graph created ----<")

    return sp.coo_matrix(symm_norm(adjBip, weightDiag=self_weight))


def correlation_graph(A, B):
    """
    Calculate Pearson correlation between columns of A and B.

    Parameters
    ----------
    A : np.ndarray
        Feature matrix, shape: [features, samples_a]
    B : np.ndarray
        Feature matrix, shape: [features, samples_b]

    Returns
    -------
    np.ndarray
        Correlation matrix, shape: [samples_a, samples_b]
    """
    am = A - np.mean(A, axis=0, keepdims=True)
    bm = B - np.mean(B, axis=0, keepdims=True)
    return am.T @ bm / (np.sqrt(np.sum(am**2, axis=0, keepdims=True)).T * np.sqrt(np.sum(bm**2, axis=0, keepdims=True)))


def symm_norm(adj, weightDiag=.3, eps=1e-8):
    """
    Apply symmetric normalization to adjacency matrix.

    Computes D^{-1/2} ((1 - weightDiag) * A + weightDiag * I) D^{-1/2}
    where D is the degree matrix. Uses weighted self-connections.

    Parameters
    ----------
    adj : np.ndarray
        Adjacent matrix with diag = 0
    weightDiag : float
        Weight for self-connections (default 0.3)
    eps : float
        Small constant for numerical stability

    Returns
    -------
    np.ndarray
        Normalized adjacency matrix
    """
    n_spot = adj.shape[0]
    adj_self = (1 - weightDiag) * adj + np.eye(n_spot) * weightDiag
    degrees = 1. / np.sqrt((np.sum(adj_self, axis=1) + eps))
    adj_self *= degrees
    adj_self *= degrees[:, None]
    return adj_self.astype(np.float32)


def calcGAEParams(graph, n_samples):
    """
    Calculate parameters for graph autoencoder loss.

    Parameters
    ----------
    graph : scipy.sparse matrix
        Bipartite graph
    n_samples : int
        Number of samples

    Returns
    -------
    tuple
        (norm_val, pos_weight) for graph autoencoder loss
    """
    non_zero_cnt = graph.sum()
    norm_val = (n_samples * n_samples) / (2 * (n_samples * n_samples - non_zero_cnt))
    pos_weight = (n_samples * n_samples - non_zero_cnt) / non_zero_cnt
    return norm_val, pos_weight


def calcGraphWeight(coor, eps=1e-6):
    """
    Calculate graph weights from coordinates.

    Parameters
    ----------
    coor : np.ndarray
        Coordinate matrix
    eps : float
        Small constant for numerical stability

    Returns
    -------
    np.ndarray
        Distance-based weight matrix
    """
    dist = cdist(coor, coor, "euclidean")
    dist = dist / (np.max(dist) + eps)
    return dist
