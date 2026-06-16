#!/usr/bin/env python3
"""
Minimal Example: GraphST Spatial Domain Identification

This example demonstrates basic GraphST usage for identifying spatial domains
using graph self-supervised learning.

Requirements:
  - GraphST
  - scanpy
  - torch
  - numpy

Reference:
  Long et al. (2023). GraphST: Spatially informed clustering, integration, and
  deconvolution of spatial transcriptomics with graph self-supervised learning.
  Nature Communications.
"""

import warnings
warnings.filterwarnings('ignore')

import numpy as np
import scanpy as sc
import torch
from GraphST.GraphST import GraphST
from GraphST.utils import clustering

print("=" * 60)
print("GraphST Minimal Example")
print("=" * 60)

# ================================================================================
# Step 1: Create Synthetic Data
# ================================================================================

print("\nStep 1: Creating synthetic spatial data...")

np.random.seed(42)

# Create synthetic gene expression data
n_spots = 200
n_genes = 500

# Create spatial coordinates (grid pattern)
x_coords = np.repeat(np.arange(1, 21), 10)
y_coords = np.tile(np.arange(1, 11), 20)

# Create count matrix with spatial patterns
counts = np.random.poisson(lam=2, size=(n_spots, n_genes)).astype(float)

# Add spatial domain patterns
domain_labels = np.zeros(n_spots, dtype=int)
for i in range(n_spots):
    x, y = x_coords[i], y_coords[i]
    if x <= 10 and y <= 5:
        domain_labels[i] = 0
        counts[i, :50] += np.random.poisson(10, 50)  # Domain 0 markers
    elif x > 10 and y <= 5:
        domain_labels[i] = 1
        counts[i, 50:100] += np.random.poisson(10, 50)  # Domain 1 markers
    elif x <= 10 and y > 5:
        domain_labels[i] = 2
        counts[i, 100:150] += np.random.poisson(10, 50)  # Domain 2 markers
    else:
        domain_labels[i] = 3
        counts[i, 150:200] += np.random.poisson(10, 50)  # Domain 3 markers

# Create AnnData object
adata = sc.AnnData(X=counts)
adata.obs_names = [f"Spot_{i}" for i in range(n_spots)]
adata.var_names = [f"Gene_{i}" for i in range(n_genes)]

# Add spatial coordinates
adata.obsm['spatial'] = np.column_stack([x_coords, y_coords])

print(f"  Created AnnData: {adata.n_obs} spots x {adata.n_vars} genes")
print(f"  Spatial coordinates shape: {adata.obsm['spatial'].shape}")
print(f"  Number of ground truth domains: {len(np.unique(domain_labels))}")

# Store ground truth for comparison
adata.obs['ground_truth'] = domain_labels.astype(str)

# ================================================================================
# Step 2: Initialize GraphST Model
# ================================================================================

print("\nStep 2: Initializing GraphST model...")

# Check device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"  Using device: {device}")

# Initialize GraphST
model = GraphST(
    adata=adata,
    device=device,
    learning_rate=0.001,
    epochs=200,  # Reduced for quick demo
    dim_output=64,
    random_seed=42,
    alpha=10,
    beta=1,
    datatype='10X'
)

print("  Model initialized successfully")

# ================================================================================
# Step 3: Train Model
# ================================================================================

print("\nStep 3: Training GraphST model...")
print("  (This may take 1-2 minutes)")

# Train the model
adata = model.train()

print("\n  Training complete!")
print(f"  Embeddings shape: {adata.obsm['emb'].shape}")

# ================================================================================
# Step 4: Clustering
# ================================================================================

print("\nStep 4: Clustering into spatial domains...")

# Use Leiden clustering (doesn't require R)
clustering(
    adata,
    n_clusters=4,
    method='leiden',
    start=0.1,
    end=3.0,
    refinement=False
)

print(f"  Identified {len(adata.obs['domain'].unique())} spatial domains")
print("\n  Domain distribution:")
print(adata.obs['domain'].value_counts().sort_index())

# ================================================================================
# Step 5: Export Results
# ================================================================================

print("\nStep 5: Exporting results...")

import pandas as pd
import os

output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# Export domain assignments
domains_df = adata.obs[['domain']].copy()
domains_df.to_csv(os.path.join(output_dir, "graphst_domains.csv"))
print(f"  Saved: graphst_domains.csv")

# Export embeddings
embeddings_df = pd.DataFrame(
    adata.obsm['emb'],
    index=adata.obs_names
)
embeddings_df.to_csv(os.path.join(output_dir, "graphst_embeddings.csv"))
print(f"  Saved: graphst_embeddings.csv")

# Save AnnData
adata.write_h5ad(os.path.join(output_dir, "graphst_results.h5ad"))
print(f"  Saved: graphst_results.h5ad")

# Export summary
with open(os.path.join(output_dir, "summary.txt"), 'w') as f:
    f.write("GraphST Analysis Summary\n")
    f.write("=" * 40 + "\n\n")
    f.write(f"Spots analyzed: {adata.n_obs}\n")
    f.write(f"Genes: {adata.n_vars}\n")
    f.write(f"Domains identified: {len(adata.obs['domain'].unique())}\n\n")
    f.write("Domain distribution:\n")
    for domain, count in adata.obs['domain'].value_counts().sort_index().items():
        f.write(f"  Domain {domain}: {count} spots\n")

print(f"  Saved: summary.txt")

print("\n" + "=" * 60)
print("Analysis complete!")
print(f"Results saved to: {output_dir}/")
print("=" * 60)

print("\nNext steps:")
print("  1. Review domain assignments in output/graphst_domains.csv")
print("  2. Load results: adata = sc.read_h5ad('output/graphst_results.h5ad')")
print("  3. For real data, use actual Visium or Stereo-seq data")
