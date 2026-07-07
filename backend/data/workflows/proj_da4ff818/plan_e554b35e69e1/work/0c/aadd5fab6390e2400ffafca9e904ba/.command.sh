#!/bin/bash -ue
python - << 'PYEOF'
import anndata
anndata.settings.allow_write_nullable_strings = True
import scanpy as sc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
adata = sc.read("PA12_sc_normalized.h5ad")
adata = adata[:, adata.var.highly_variable]
sc.tl.pca(adata, n_comps=30)
sc.pp.neighbors(adata, n_neighbors=15)
sc.tl.umap(adata)
sc.tl.leiden(adata, resolution=0.5)
adata.write("PA12_sc_clustered.h5ad")
fig, ax = plt.subplots(figsize=(6, 5))
sc.pl.umap(adata, color='leiden', ax=ax, show=False)
fig.savefig("PA12_sc_umap.png", dpi=150, bbox_inches='tight')
PYEOF
