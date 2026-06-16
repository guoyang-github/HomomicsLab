"""scVI batch integration with scvi-tools
Reference: scvi-tools 1.1+, anndata 0.10+, scanpy 1.10+

Deep VAE for batch correction. Best for large datasets and complex batch effects.
Input: merged AnnData with raw counts and batch labels.
Output: AnnData with scVI latent space in obsm['X_scVI'].
"""

import scanpy as sc
import scvi


def run_scvi(adata, batch_key='batch', n_latent=30, n_layers=2,
             max_epochs=100, use_gpu=True):
    """Train scVI model and get latent representation.

    Args:
        adata: AnnData with raw counts (uses adata.raw if available)
        batch_key: column in adata.obs defining batches
        n_latent: latent space dimensions
        n_layers: hidden layers
        max_epochs: training epochs
        use_gpu: use GPU if available

    Returns:
        adata with obsm['X_scVI'], trained model
    """
    # Use raw counts
    if adata.raw is not None:
        adata_scvi = sc.AnnData(X=adata.raw.X, obs=adata.obs.copy(), var=adata.raw.var.copy())
    else:
        adata_scvi = adata.copy()

    sc.pp.filter_genes(adata_scvi, min_counts=3)
    sc.pp.highly_variable_genes(adata_scvi, n_top_genes=2000, subset=True)

    scvi.model.SCVI.setup_anndata(adata_scvi, batch_key=batch_key)

    model = scvi.model.SCVI(adata_scvi, n_latent=n_latent, n_layers=n_layers)
    model.train(max_epochs=max_epochs, early_stopping=True, accelerator="gpu" if use_gpu else "cpu")

    adata.obsm['X_scVI'] = model.get_latent_representation()
    return adata, model


def scvi_workflow(adata, batch_key='batch', n_latent=30, max_epochs=100,
                  resolution=0.5, use_gpu=True):
    """Complete scVI workflow: train -> latent -> cluster.

    Args:
        adata: merged AnnData (raw counts)
        batch_key: column in adata.obs defining batches
        n_latent: latent dimensions
        max_epochs: training epochs
        resolution: Leiden resolution
        use_gpu: use GPU

    Returns:
        adata with scVI UMAP and clusters, trained model
    """
    adata, model = run_scvi(
        adata, batch_key=batch_key,
        n_latent=n_latent, max_epochs=max_epochs, use_gpu=use_gpu
    )

    sc.pp.neighbors(adata, use_rep='X_scVI')
    sc.tl.umap(adata)
    sc.tl.leiden(adata, resolution=resolution, key_added='leiden_scvi')

    return adata, model
