"""scVelo RNA Velocity Analysis Example."""

import scanpy as sc
import scvelo as scv
import numpy as np
import pandas as pd

# Create example data with spliced/unspliced layers
np.random.seed(42)
n_cells = 500
n_genes = 1000

adata = sc.AnnData(
    X=np.random.lognormal(3, 1, (n_cells, n_genes)),
    obs=pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)]),
    var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)])
)

# Add spliced and unspliced counts
adata.layers["spliced"] = np.random.lognormal(3, 1, (n_cells, n_genes))
adata.layers["unspliced"] = np.random.lognormal(2, 1, (n_cells, n_genes))

print("scVelo RNA Velocity Analysis Example")
print("=" * 40)

# Step 1: Preprocess
print("\n1. Preprocessing...")
# NOTE: scv.pp.filter_and_normalize was removed in scvelo 0.3+.
# Using equivalent scanpy functions instead.
sc.pp.filter_cells(adata, min_counts=20)
sc.pp.filter_genes(adata, min_counts=20)
sc.pp.highly_variable_genes(adata, n_top_genes=2000, subset=True)
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
scv.pp.moments(adata, n_pcs=30, n_neighbors=30)

# Step 2: Compute velocity
print("\n2. Computing RNA velocity...")
scv.tl.velocity(adata, mode='stochastic')

# Step 3: Compute velocity graph
print("\n3. Computing velocity graph...")
scv.tl.velocity_graph(adata)

# Step 4: Compute velocity embedding
print("\n4. Computing velocity embedding...")
# Note: This requires existing UMAP or other embedding
# Create a simple embedding for demonstration
sc.tl.pca(adata)
sc.pp.neighbors(adata)
sc.tl.umap(adata)

scv.tl.velocity_embedding(adata, basis='umap')

# Step 5: Visualize
print("\n5. Visualizing velocity...")
scv.pl.velocity_embedding_stream(adata, basis='umap', color='velocity_pseudotime')

# Step 6: Velocity pseudotime
print("\n6. Computing velocity pseudotime...")
scv.tl.velocity_pseudotime(adata)
print(f"   Pseudotime range: {adata.obs['velocity_pseudotime'].min():.2f} - {adata.obs['velocity_pseudotime'].max():.2f}")

# Step 7: Identify driver genes
print("\n7. Finding velocity genes...")
scv.tl.velocity_genes(adata)
n_velocity_genes = sum(adata.var['velocity_genes'])
print(f"   Velocity genes: {n_velocity_genes}")

# Step 8: Rank velocity genes
print("\n8. Ranking velocity genes...")
scv.tl.rank_velocity_genes(adata, groupby='leiden' if 'leiden' in adata.obs else None)
print("   Top velocity genes identified")
