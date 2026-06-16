"""Example: Load multiple samples from a SampleSheet with Scanpy"""

import sys
sys.path.insert(0, '../scripts/python')

from samplesheet import load_from_samplesheet

# Load all samples and merge into a single AnnData
adata = load_from_samplesheet('samplesheet.csv', merge=True)

print(f"Loaded: {adata.n_obs} cells x {adata.n_vars} genes")
print(f"Samples: {adata.obs['sample_id'].value_counts().to_dict()}")

if 'batch' in adata.obs.columns:
    print(f"Batches: {adata.obs['batch'].value_counts().to_dict()}")

# Save merged
adata.write_h5ad('merged.h5ad')

# --- Alternative: load as list for per-sample QC ---
# adata_list = load_from_samplesheet('samplesheet.csv', merge=False)
# for ad in adata_list:
#     print(f"{ad.obs['sample_id'][0]}: {ad.n_obs} cells")
