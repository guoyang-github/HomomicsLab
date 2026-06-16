"""Scanorama batch integration
Reference: scanorama 1.7+, scanpy 1.10+, anndata 0.10+, numpy 1.26+

MNN-based correction for datasets with partial cell-type overlap.
Input: list of AnnData objects (preprocessed separately).
Output: merged AnnData with corrected expression matrix.
"""

import numpy as np
import scanpy as sc
import scanorama


def run_scanorama(adatas, dimred=50):
    """Run Scanorama integration on a list of AnnData objects.

    Args:
        adatas: list of AnnData objects (each preprocessed with log1p)
        dimred: dimensionality of integrated embedding

    Returns:
        corrected_adata: merged AnnData with corrected expression
        integrated: list of corrected matrices
    """
    # Find common genes
    gene_lists = [a.var_names.tolist() for a in adatas]
    common_genes = list(set.intersection(*map(set, gene_lists)))

    # Prepare data matrices (genes x cells)
    datasets = [a[:, common_genes].X.T for a in adatas]

    # Run Scanorama
    # Note: scanorama.correct() expects genes_list as list of lists (one per dataset)
    # return_dimred=False returns 2 values (corrected, genes)
    corrected, genes = scanorama.correct(
        datasets,
        [common_genes] * len(datasets),
        return_dimred=False,
        return_dense=True,
        dimred=dimred
    )

    # Combine into single AnnData
    import anndata as ad
    import pandas as pd

    integrated_data = np.concatenate([c.T for c in corrected], axis=0)
    obs = pd.concat([a.obs for a in adatas])

    corrected_adata = ad.AnnData(
        X=integrated_data,
        obs=obs,
        var=pd.DataFrame(index=genes)
    )

    return corrected_adata


def scanorama_workflow(adatas, dimred=50, resolution=0.5):
    """Complete Scanorama workflow: integrate -> PCA -> cluster.

    Args:
        adatas: list of AnnData objects (raw counts, not preprocessed)
        dimred: dimensionality
        resolution: Leiden resolution

    Returns:
        corrected AnnData with UMAP and clusters
    """
    # Preprocess each separately
    for adata in adatas:
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    # Integrate
    corrected = run_scanorama(adatas, dimred=dimred)

    # Downstream
    sc.pp.pca(corrected, n_comps=50)
    sc.pp.neighbors(corrected)
    sc.tl.umap(corrected)
    sc.tl.leiden(corrected, resolution=resolution, key_added='leiden_scanorama')

    return corrected
