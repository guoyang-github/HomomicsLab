"""Harmony batch integration with Scanpy
Reference: anndata 0.10+, scanpy 1.10+, harmonypy 0.0.10+

Run Harmony iterative correction on PCA embeddings.
Input: merged AnnData with PCA computed and batch labels in obs.
Output: AnnData with harmony embeddings in obsm['X_pca_harmony'].
"""

import scanpy as sc
import harmonypy as hm


def run_harmony_scanpy(adata, batch_key='batch', n_pcs_use=30):
    """Run Harmony integration on PCA embeddings.

    Args:
        adata: AnnData with PCA computed (obsm['X_pca'])
        batch_key: column in adata.obs defining batches
        n_pcs_use: number of PCs to use for Harmony

    Returns:
        adata with obsm['X_pca_harmony'] added
    """
    ho = hm.run_harmony(
        adata.obsm['X_pca'],
        adata.obs,
        batch_key,
        max_iter_harmony=10
    )
    adata.obsm['X_pca_harmony'] = ho.Z_corr.T
    return adata


def harmony_workflow(adata, batch_key='batch', n_top_genes=2000,
                     n_pcs=50, resolution=0.5):
    """Complete Harmony workflow: preprocess -> integrate -> cluster.

    Args:
        adata: merged AnnData (raw counts in .X)
        batch_key: column in adata.obs defining batches
        n_top_genes: number of HVGs
        n_pcs: PCs for PCA
        resolution: Leiden resolution

    Returns:
        adata with harmony UMAP and clusters
    """
    # Preprocess
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes, batch_key=batch_key)
    adata.raw = adata
    adata = adata[:, adata.var.highly_variable].copy()
    sc.pp.scale(adata, max_value=10)
    sc.tl.pca(adata, n_comps=n_pcs)

    # Integrate
    adata = run_harmony_scanpy(adata, batch_key=batch_key, n_pcs_use=min(30, n_pcs))

    # Cluster on harmony
    sc.pp.neighbors(adata, use_rep='X_pca_harmony')
    sc.tl.umap(adata)
    sc.tl.leiden(adata, resolution=resolution, key_added='leiden_harmony')

    return adata
