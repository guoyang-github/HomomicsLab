#!/bin/bash -ue
python - << 'PYEOF'
import anndata
anndata.settings.allow_write_nullable_strings = True
import scanpy as sc
adata = sc.read("PA12_sc.h5ad")
adata.var['mt'] = adata.var_names.str.startswith('MT-')
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], percent_top=None, log1p=False, inplace=True)
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)
adata = adata[adata.obs.pct_counts_mt < 5.0, :]
adata.write("PA12_sc_qc.h5ad")
PYEOF
