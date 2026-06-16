"""BBKNN batch integration with Scanpy
Reference: bbknn 1.6+, scanpy 1.10+, anndata 0.10+

Fast batch-balancing k-nearest neighbors. Preserves local cell-type structure.
Input: merged AnnData with PCA computed.
Output: AnnData with corrected neighbor graph in obsp['connectivities'].
"""

import scanpy as sc
import bbknn


def run_bbknn(adata, batch_key='batch', n_pcs=50, neighbors_within_batch=3):
    """Run BBKNN on PCA embeddings.

    Args:
        adata: AnnData with PCA computed
        batch_key: column in adata.obs defining batches
        n_pcs: PCs to use
        neighbors_within_batch: k per batch

    Returns:
        adata with corrected neighbor graph
    """
    bbknn.bbknn(
        adata,
        batch_key=batch_key,
        n_pcs=n_pcs,
        neighbors_within_batch=neighbors_within_batch
    )
    return adata


def bbknn_workflow(adata, batch_key='batch', n_top_genes=2000,
                   n_pcs=50, resolution=0.5):
    """Complete BBKNN workflow: preprocess -> integrate -> cluster.

    Args:
        adata: merged AnnData (raw counts)
        batch_key: column in adata.obs defining batches
        n_top_genes: number of HVGs
        n_pcs: PCs for PCA
        resolution: Leiden resolution

    Returns:
        adata with BBKNN UMAP and clusters
    """
    # Preprocess
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes, batch_key=batch_key)
    adata.raw = adata
    adata = adata[:, adata.var.highly_variable].copy()
    sc.pp.scale(adata, max_value=10)
    sc.tl.pca(adata, n_comps=n_pcs)

    # Integrate (modifies neighbor graph directly)
    adata = run_bbknn(adata, batch_key=batch_key, n_pcs=n_pcs)

    # Cluster
    sc.tl.umap(adata)
    sc.tl.leiden(adata, resolution=resolution, key_added='leiden_bbknn')

    return adata
