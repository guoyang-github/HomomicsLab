"""
Workflow Example: Spatial Autocorrelation Analysis with Moran's I

This example demonstrates how to use Moran's I to analyze spatial patterns
in gene expression data.
"""

import sys
sys.path.append('../scripts/python')

import scanpy as sc
import matplotlib.pyplot as plt
from core_stats import compute_morans_i, compute_lisa, run_autocorrelation_analysis

# 1. Load spatial transcriptomics data
# Replace with your actual data path
adata = sc.read_h5ad('your_spatial_data.h5ad')

# 2. Verify spatial data is available
if 'spatial' not in adata.obsm:
    raise ValueError("No spatial coordinates found in adata.obsm['spatial']")

print(f"Data shape: {adata.shape}")
print(f"Spatial coordinates shape: {adata.obsm['spatial'].shape}")

# 3. Compute Moran's I for specific genes of interest
genes_of_interest = ['GeneA', 'GeneB', 'GeneC']
results = compute_morans_i(adata, genes=genes_of_interest, k=6)

print("\nMoran's I Results:")
print(results)

# 4. Identify significantly clustered genes
significant = results[results['p_value'] < 0.05]
print(f"\nSignificantly clustered genes: {len(significant)}")
print(significant[['gene', 'I', 'p_value']])

# 5. Run comprehensive analysis
full_results = run_autocorrelation_analysis(
    adata,
    genes=None,  # Use highly variable genes
    k=6,
    compute_local=True
)

# 6. Get top clustered genes
top_genes = full_results['top_clustered'][:10]
print(f"\nTop 10 clustered genes: {top_genes}")

# 7. Visualize LISA results for the top gene
top_gene = top_genes[0]
lisa_results = full_results['lisa'][top_gene]
adata.obs['lisa_cluster'] = lisa_results['cluster'].values

# Plot spatial distribution
sq.pl.spatial_scatter(adata, color=[top_gene, 'lisa_cluster'], title=[f'{top_gene} Expression', 'LISA Clusters'])

plt.savefig('moran_analysis_results.png', dpi=300)
print("\nResults saved to moran_analysis_results.png")
