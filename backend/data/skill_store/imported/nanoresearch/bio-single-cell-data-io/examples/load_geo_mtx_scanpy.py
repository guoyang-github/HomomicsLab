"""Example: Load GEO merged MTX + metadata CSV with Scanpy"""

import sys
sys.path.insert(0, '../scripts/python')

from geo_loaders import load_geo_mtx_with_metadata

# GEO pattern: one MTX directory for all cells,
# metadata CSV maps each barcode to its sample
adata = load_geo_mtx_with_metadata(
    mtx_dir="GSE12345/",
    metadata_csv="GSE12345_cell_metadata.csv",
    sample_col="sample"
)

print(f"Loaded: {adata.n_obs} cells x {adata.n_vars} genes")
print(f"Samples: {adata.obs['sample'].value_counts().to_dict()}")

# The metadata CSV can contain additional columns (condition, batch, etc.)
# They are automatically added to adata.obs
print(f"Metadata columns: {list(adata.obs.columns)}")

adata.write_h5ad('geo_loaded.h5ad')
