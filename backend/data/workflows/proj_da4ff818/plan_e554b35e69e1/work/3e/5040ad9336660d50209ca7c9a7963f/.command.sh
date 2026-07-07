#!/bin/bash -ue
python - << 'PYEOF'
import anndata
anndata.settings.allow_write_nullable_strings = True
import scanpy as sc
adata = sc.read("PA12_sc_qc.h5ad")
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes=2000)
adata.write("PA12_sc_normalized.h5ad")
PYEOF
