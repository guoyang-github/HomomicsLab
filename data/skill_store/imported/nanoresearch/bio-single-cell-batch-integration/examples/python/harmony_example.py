"""Example: Harmony integration with Scanpy
Reference: scanpy 1.10+, harmonypy 0.0.10+

Demonstrates loading multiple h5ad files and running Harmony integration.
"""

import scanpy as sc
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'python'))

from harmony import harmony_workflow

# Load multiple samples and merge
adatas = []
for sample in ['sample1.h5ad', 'sample2.h5ad', 'sample3.h5ad']:
    adata = sc.read_h5ad(sample)
    adata.obs['batch'] = sample.replace('.h5ad', '')
    adatas.append(adata)

adata = sc.concat(adatas, label='batch')

# Run Harmony integration
adata = harmony_workflow(adata, batch_key='batch', resolution=0.5)

# Differential expression on harmony clusters
sc.tl.rank_genes_groups(adata, groupby='leiden_harmony', method='wilcoxon',
                        use_raw=True)

# Save
adata.write('harmony_integrated.h5ad')
print('Integration complete. Clusters:', adata.obs['leiden_harmony'].nunique())
