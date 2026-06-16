"""
Utility functions for spCLUE analysis.

Provides clustering algorithms, metrics calculation, batch correction utilities,
and helper functions for data processing.
"""

import math
import itertools
import numpy as np
import time
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from sklearn.metrics import silhouette_score, calinski_harabasz_score
import os
from sklearn.neighbors import NearestNeighbors
from scipy.spatial.distance import cdist
import torch
from torch.backends import cudnn
import pandas as pd
import scipy.sparse as sp
import scanpy as sc
import random


def adjust_learning_rate(optimizer, epoch, lr, total_epochs=500):
    """
    Adjust learning rate using cosine annealing schedule.

    Parameters
    ----------
    optimizer : torch.optim.Optimizer
        PyTorch optimizer
    epoch : int
        Current epoch
    lr : float
        Initial learning rate
    total_epochs : int
        Total number of training epochs for scheduling

    Returns
    -------
    float
        Updated learning rate
    """
    p = {
        'optimizer': 'sgd',
        'optimizer_kwargs': {
            'nesterov': False,
            'weight_decay': 0.0001,
            'momentum': 0.9,
        },
        'scheduler': 'cosine',
        'scheduler_kwargs': {
            'lr_decay_rate': 0.1
        },
    }

    new_lr = None

    if p['scheduler'] == 'cosine':
        eta_min = lr * (p['scheduler_kwargs']['lr_decay_rate']**3)
        new_lr = eta_min + (lr - eta_min) * (1 + math.cos(math.pi * epoch / total_epochs)) / 2

    elif p['scheduler'] == 'step':
        steps = np.sum(epoch > np.array(p['scheduler_kwargs']['lr_decay_epochs']))
        if steps > 0:
            new_lr = lr * (p['scheduler_kwargs']['lr_decay_rate']**steps)

    elif p['scheduler'] == 'constant':
        new_lr = lr

    else:
        raise ValueError('Invalid learning rate schedule {}'.format(p['scheduler']))

    for param_group in optimizer.param_groups:
        param_group['lr'] = new_lr

    return lr


def sparse_mx_to_torch_sparse_tensor(sparse_mx):
    """
    Convert a scipy sparse matrix to a torch sparse tensor.

    Parameters
    ----------
    sparse_mx : scipy.sparse matrix
        Sparse matrix to convert

    Returns
    -------
    torch.sparse_coo_tensor
        PyTorch sparse tensor
    """
    sparse_mx = sparse_mx.tocoo().astype(np.float32)
    indices = torch.from_numpy(
        np.vstack((sparse_mx.row, sparse_mx.col)).astype(np.int64))
    values = torch.from_numpy(sparse_mx.data)
    shape = torch.Size(sparse_mx.shape)
    return torch.sparse_coo_tensor(indices, values, shape)


def batch_refine_label(adata, radius=30, key="label", suffix=None, batch_key="batchID"):
    """
    Refine predicted labels for multi-slice data using spatial smoothing.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    radius : int
        Number of neighbors to consider
    key : str
        Column name in adata.obs containing labels
    suffix : str, optional
        Suffix for new column name
    batch_key : str
        Column name for batch information

    Returns
    -------
    np.ndarray
        Refined labels
    """
    n_neigh = radius
    batch_keys = list(set(adata.obs[batch_key]))
    new_type_all = []
    for bk in batch_keys:
        new_type = []
        adata_tmp = adata[adata.obs[batch_key] == bk]
        old_type = adata_tmp.obs[key].values
        position = adata_tmp.obsm["spatial"]
        distance = cdist(position, position, metric="euclidean")

        n_cell = distance.shape[0]

        for i in range(n_cell):
            vec = distance[i, :]
            index = vec.argsort()
            neigh_type = []
            for j in range(1, n_neigh + 1):
                neigh_type.append(old_type[index[j]])
            max_type = max(neigh_type, key=neigh_type.count)
            new_type.append(max_type)

        suffix_add = "" if suffix is None else "_" + suffix
        new_type_all += [str(i) for i in list(new_type)]
    adata.obs[f"{key}_refined" + suffix_add] = np.array(new_type_all)
    return np.array(new_type_all)


def refine_label(adata, radius=30, key='label', suffix=None):
    """
    Refine predicted labels using spatial smoothing (single slice).

    Assigns each spot the most frequent label among its neighbors.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    radius : int
        Number of neighbors to consider
    key : str
        Column name in adata.obs containing labels
    suffix : str, optional
        Suffix for new column name

    Returns
    -------
    np.ndarray
        Refined labels
    """
    n_neigh = radius
    new_type = []
    old_type = adata.obs[key].values

    position = adata.obsm['spatial']
    distance = cdist(position, position, metric='euclidean')

    n_cell = distance.shape[0]

    for i in range(n_cell):
        vec = distance[i, :]
        index = vec.argsort()
        neigh_type = []
        for j in range(1, n_neigh + 1):
            neigh_type.append(old_type[index[j]])
        max_type = max(neigh_type, key=neigh_type.count)
        new_type.append(max_type)

    suffix_add = "" if suffix is None else "_" + suffix
    new_type = [str(i) for i in list(new_type)]
    adata.obs[f'{key}_refined' + suffix_add] = np.array(new_type)
    return np.array(new_type)


def calculateMetrics(true, pred, embedding):
    """
    Calculate clustering evaluation metrics.

    Parameters
    ----------
    true : np.ndarray
        Ground truth labels
    pred : np.ndarray
        Predicted labels
    embedding : np.ndarray
        Embedding features

    Returns
    -------
    list
        [ARI, NMI, Silhouette, Calinski-Harabasz]
    """
    metric_list = []
    metric_list.append(round(adjusted_rand_score(true, pred), 4))
    metric_list.append(round(normalized_mutual_info_score(true, pred), 4))
    metric_list.append(round(silhouette_score(embedding, pred), 4))
    metric_list.append(round(calinski_harabasz_score(embedding, pred), 4))
    return metric_list


def clustering(adata, n_clusters=12, radius=30, key="embed", refinement=False, suffix=None, cluster_methods=None):
    """
    Perform clustering on spCLUE embeddings.

    Supports mclust, kmeans, leiden, and pred (model predictions) clustering methods.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data with embeddings
    n_clusters : int
        Number of clusters
    radius : int
        Radius for spatial refinement
    key : str
        Key in adata.obsm containing embeddings
    refinement : bool
        Whether to apply spatial refinement
    suffix : str, optional
        Suffix for refined label column
    cluster_methods : str
        Clustering method: 'mclust', 'kmeans', 'leiden', or 'pred'

    Returns
    -------
    AnnData
        Updated AnnData with cluster labels
    """
    embedding = adata.obsm[key]
    if cluster_methods is None:
        cluster_methods = "mclust"
    if cluster_methods == "kmeans":
        kmeans = KMeans(n_clusters=n_clusters, init="k-means++", random_state=2023, n_init=10)
        pred = kmeans.fit_predict(embedding)
        adata.obs["kmeans"] = pred
    elif cluster_methods == "leiden":
        res = searchRes(adata, n_clusters)
        adata.uns["LeidenRes"] = res
        sc.tl.leiden(adata, resolution=res, random_state=2023)
        pred = adata.obs["leiden"].to_numpy(dtype=np.int64)
    elif cluster_methods == "mclust":
        pred = mclust_R(embedding, n_clusters)
        adata.obs["mclust"] = pred
    elif cluster_methods == "pred":
        pred = adata.obs["pred"].to_numpy(dtype=np.int64)
    else:
        raise Exception("please specify correct method !!! \n[ kmeans / leiden / mclust / pred ]")

    if refinement:
        refined_labels = refine_label(adata, radius, key=cluster_methods, suffix=suffix)
    return adata


def mclust_R(data, n_clusters, modelNames="EEE", random_seed=2023):
    """
    Perform clustering using R's mclust package.

    Parameters
    ----------
    data : np.ndarray
        Data to cluster
    n_clusters : int
        Number of clusters
    modelNames : str
        Model type for mclust
    random_seed : int
        Random seed

    Returns
    -------
    np.ndarray
        Cluster assignments
    """
    np.random.seed(random_seed)
    import rpy2.robjects as robjects
    robjects.r.library("mclust")

    import rpy2.robjects.numpy2ri
    rpy2.robjects.numpy2ri.activate()
    r_random_seed = robjects.r['set.seed']
    r_random_seed(random_seed)
    rmclust = robjects.r['Mclust']
    res = rmclust(rpy2.robjects.numpy2ri.numpy2rpy(data), n_clusters, modelNames)
    mclust_res = np.array(res[-2])

    return mclust_res.astype(np.int32) - 1


def fix_seed(seed):
    """
    Set random seeds for reproducibility.

    Parameters
    ----------
    seed : int
        Random seed value
    """
    os.environ['PYTHONHASHSEED'] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    cudnn.deterministic = True
    cudnn.benchmark = False
    os.environ['PYTHONHASHSEED'] = str(seed)
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'


def searchRes(adata, fixed_clus_count, increment=0.01):
    """
    Search for optimal Leiden resolution to achieve target cluster count.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    fixed_clus_count : int
        Target number of clusters
    increment : float
        Resolution increment

    Returns
    -------
    float
        Optimal resolution
    """
    for res in sorted(list(np.arange(0.02, 2.5, increment))):
        sc.tl.leiden(adata, random_state=0, resolution=res)
        count_unique_leiden = len(pd.DataFrame(adata.obs['leiden']).leiden.unique())
        if count_unique_leiden >= fixed_clus_count:
            break
    return res


# ======================== MNN utilities [adapted from scDML] ========================

def nn(ds1, ds2, names1, names2, knn=50, metric_p=2, return_distance=False, metric="cosine", flag="in"):
    """Find nearest neighbors between two datasets."""
    if flag == "in":
        nn_ = NearestNeighbors(n_neighbors=knn, metric=metric)
        nn_.fit(ds2)
        nn_distances, ind = nn_.kneighbors(ds1, return_distance=True)
        if not return_distance:
            match = set()
            for a, b in zip(range(ds1.shape[0]), ind):
                for b_i in b[1:]:
                    match.add((names1[a], names2[b_i]))
            return match
        else:
            match = {}
            for a, b in zip(range(ds1.shape[0]), ind):
                for b_ind, b_i in enumerate(b[1:]):
                    match[(names1[a], names2[b_i])] = nn_distances[a, b_ind + 1]
            return match
    else:
        nn_ = NearestNeighbors(n_neighbors=knn, metric=metric)
        nn_.fit(ds2)
        nn_distances, ind = nn_.kneighbors(ds1, return_distance=True)
        if not return_distance:
            match = set()
            for a, b in zip(range(ds1.shape[0]), ind):
                for b_i in b[0:]:
                    match.add((names1[a], names2[b_i]))
            return match
        else:
            match = {}
            for a, b in zip(range(ds1.shape[0]), ind):
                for b_ind, b_i in enumerate(b):
                    match[(names1[a], names2[b_i])] = nn_distances[a, b_ind]
            return match


def mnn(ds1, ds2, names1, names2, knn=3, save=False, approx=False,
        approx_method="hnswlib", return_distance=False, metric="cosine", flag="in"):
    """Compute mutual nearest neighbors between two datasets."""
    if approx:
        raise NotImplementedError("Approximate MNN not implemented in this version")
    else:
        match1 = nn(ds1, ds2, names1, names2, knn=knn, return_distance=return_distance, metric=metric, flag=flag)
        match2 = nn(ds2, ds1, names2, names1, knn=knn, return_distance=return_distance, metric=metric, flag=flag)

    if flag == "in":
        if not return_distance:
            mutual = match1 | set([(b, a) for a, b in match1])
            return mutual
        else:
            mutual = []
            distances = []
            for a, b in match1.keys():
                mutual.append((a, b))
                mutual.append((b, a))
                distances.append(match1[(a, b)])
                distances.append(match1[(a, b)])
            return mutual, distances
    else:
        if not return_distance:
            mutual = match1 & set([(b, a) for a, b in match2])
            mutual = mutual | set([(b, a) for (a, b) in mutual])
            return mutual
        else:
            mutual = set([(a, b) for a, b in match1.keys()]) & set([(b, a) for a, b in match2.keys()])
            mutual = list(mutual)
            distances = []
            for element_i in mutual:
                distances.append(match1[element_i])
            return mutual, distances


def get_dict_mnn(data_matrix, batch_index, k=5, save=True, approx=False,
                 approx_method="hnswlib", verbose=False, return_distance=False,
                 metric="cosine", flag="in", log=None):
    """
    Calculate KNN or MNN pairs from data matrix.

    Parameters
    ----------
    data_matrix : np.ndarray
        Data matrix [n_samples, n_features]
    batch_index : np.ndarray
        Batch labels for each sample
    k : int
        Number of neighbors
    flag : str
        'in' for KNN within batch, 'inter' for MNN between batches

    Returns
    -------
    tuple
        (rows, cols) indices for sparse matrix
    """
    cell_names = np.array(range(len(data_matrix)))
    batch_unique = np.unique(batch_index)
    cells_batch = []
    for i in batch_unique:
        cells_batch.append(cell_names[batch_index == i])
    mnns = set()
    mnns_distance = []

    if flag == "in":
        num_KNN = 0
        print(f"Calculate KNN pair intra batch...........")
        print(f"number of knn: {k}")
        print(f"metric of distance is: {metric}")
        for comb in list(itertools.combinations(range(len(cells_batch)), 1)):
            i = comb[0]
            j = comb[0]
            print(f"Processing datasets: ({batch_unique[i]}, {batch_unique[j]})")
            target = list(cells_batch[j])
            ref = list(cells_batch[i])
            ds1 = data_matrix[target]
            ds2 = data_matrix[ref]
            names1 = target
            names2 = ref
            match = mnn(ds1, ds2, names1, names2, knn=k, save=save, approx=approx,
                       approx_method=approx_method, return_distance=return_distance, metric=metric, flag=flag)
            mnns = mnns | match
            print(f"There are ({len(match)}) KNN pairs when processing ({batch_unique[i]}, {batch_unique[j]})")
            num_KNN += len(match)
        print(f"Total number of KNN pairs is {num_KNN}.")
        if not return_distance:
            return list(zip(*list(mnns)))
        else:
            return mnns, mnns_distance
    else:
        num_MNN = 0
        print(f"Calculate MNN pair inter batch...........")
        print(f"number of knn: {k}")
        print(f"metric of distance is: {metric}")
        for comb in list(itertools.combinations(range(len(cells_batch)), 2)):
            i = comb[0]
            j = comb[1]
            print(f"Processing datasets: ({batch_unique[i]}, {batch_unique[j]})")
            target = list(cells_batch[j])
            ref = list(cells_batch[i])
            ds1 = data_matrix[target]
            ds2 = data_matrix[ref]
            names1 = target
            names2 = ref
            match = mnn(ds1, ds2, names1, names2, knn=k, save=save, approx=approx,
                       approx_method=approx_method, return_distance=return_distance, metric=metric, flag=flag)
            mnns = mnns | match
            print(f"There are ({len(match)}) MNN pairs when processing ({batch_unique[i]}, {batch_unique[j]})")
            num_MNN += len(match)
        print(f"Total number of MNN pairs is {num_MNN}.")
        if not return_distance:
            return list(zip(*list(mnns)))
        else:
            return mnns, mnns_distance


def convertSet2Coo(graph, n_spots):
    """
    Convert edge list to COO sparse matrix.

    Parameters
    ----------
    graph : list
        List of (rows, cols) tuples
    n_spots : int
        Number of spots

    Returns
    -------
    scipy.sparse.coo_matrix
        Sparse adjacency matrix
    """
    return sp.coo_matrix(([1.] * len(graph[0]), (graph[0], graph[1])), shape=(n_spots, n_spots))
