#!/usr/bin/env python3
"""
Advanced Example: GraphST Comprehensive Analysis

This example demonstrates advanced GraphST features including:
- Spatial domain identification with different clustering methods
- Spatial refinement of domain labels
- Multi-section integration
- scRNA-seq transfer (deconvolution)
- Comprehensive visualization

Requirements:
  - GraphST
  - scanpy
  - torch
  - numpy
  - matplotlib
  - seaborn

Reference:
  Long et al. (2023). GraphST: Spatially informed clustering, integration, and
  deconvolution of spatial transcriptomics with graph self-supervised learning.
  Nature Communications.
"""

import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import scanpy as sc
import torch
import matplotlib.pyplot as plt
import seaborn as sns
from GraphST.GraphST import GraphST
from GraphST.utils import (
    clustering, refine_label, search_res,
    project_cell_to_spot
)
import os

print("=" * 70)
print("GraphST Advanced Example")
print("=" * 70)

# Set random seed for reproducibility
np.random.seed(42)
torch.manual_seed(42)

# ================================================================================
# PART 1: Data Preparation
# ================================================================================

print("\n" + "=" * 70)
print("PART 1: Data Preparation")
print("=" * 70)

def create_synthetic_data(n_spots=400, n_genes=1000, n_domains=5, seed=42):
    """Create synthetic spatial data with known patterns."""
    np.random.seed(seed)

    # Create spatial coordinates
    grid_size = int(np.sqrt(n_spots))
    x = np.repeat(np.arange(1, grid_size + 1), grid_size)[:n_spots]
    y = np.tile(np.arange(1, grid_size + 1), grid_size)[:n_spots]

    # Create counts with spatial patterns
    counts = np.random.poisson(lam=2, size=(n_spots, n_genes)).astype(float)

    # Assign domains based on position
    domain_labels = np.zeros(n_spots, dtype=int)
    genes_per_domain = n_genes // n_domains

    for i in range(n_spots):
        # Determine domain based on spatial position
        xi, yi = x[i], y[i]

        # Create concentric-like domains
        center_x, center_y = grid_size / 2, grid_size / 2
        dist = np.sqrt((xi - center_x)**2 + (yi - center_y)**2)
        max_dist = np.sqrt(center_x**2 + center_y**2)
        domain = int((dist / max_dist) * n_domains)
        domain = min(domain, n_domains - 1)

        domain_labels[i] = domain

        # Add domain-specific marker expression
        marker_start = domain * genes_per_domain
        marker_end = marker_start + genes_per_domain
        counts[i, marker_start:marker_end] += np.random.poisson(15, genes_per_domain)

    # Create AnnData
    adata = sc.AnnData(X=counts)
    adata.obs_names = [f"Spot_{i:04d}" for i in range(n_spots)]
    adata.var_names = [f"Gene_{i:04d}" for i in range(n_genes)]
    adata.obsm['spatial'] = np.column_stack([x, y])
    adata.obs['ground_truth'] = [f"Domain_{d}" for d in domain_labels]

    return adata

# Create main dataset
adata = create_synthetic_data(n_spots=400, n_genes=1000, n_domains=5)
print(f"\nCreated AnnData: {adata.n_obs} spots x {adata.n_vars} genes")
print(f"Spatial coordinates shape: {adata.obsm['spatial'].shape}")
print(f"Ground truth domains: {adata.obs['ground_truth'].nunique()}")

# Create output directory
output_dir = "output_advanced"
os.makedirs(output_dir, exist_ok=True)

# ================================================================================
# PART 2: Device Setup
# ================================================================================

print("\n" + "=" * 70)
print("PART 2: Device Setup")
print("=" * 70)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

if device.type == 'cuda':
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Memory allocated: {torch.cuda.memory_allocated(0) / 1024**2:.1f} MB")

# ================================================================================
# PART 3: GraphST Training
# ================================================================================

print("\n" + "=" * 70)
print("PART 3: GraphST Model Training")
print("=" * 70)

# Initialize model
model = GraphST(
    adata=adata,
    device=device,
    learning_rate=0.001,
    epochs=300,  # More epochs for better convergence
    dim_output=64,
    random_seed=42,
    alpha=10,
    beta=1,
    datatype='10X'
)

# Train
print("\nTraining model...")
adata = model.train()

print(f"\nTraining complete!")
print(f"Embeddings shape: {adata.obsm['emb'].shape}")
print(f"Embeddings range: [{adata.obsm['emb'].min():.3f}, {adata.obsm['emb'].max():.3f}]")

# ================================================================================
# PART 4: Clustering Comparison
# ================================================================================

print("\n" + "=" * 70)
print("PART 4: Clustering Method Comparison")
print("=" * 70)

# Try different clustering methods
methods = ['leiden', 'louvain']
n_clusters = 5

for method in methods:
    print(f"\nClustering with {method}...")
    clustering(
        adata,
        n_clusters=n_clusters,
        method=method,
        start=0.1,
        end=3.0,
        increment=0.01,
        refinement=False,
        key='emb'
    )
    # Store result
    adata.obs[f'domain_{method}'] = adata.obs['domain'].copy()
    print(f"  Identified {adata.obs[f'domain_{method}'].nunique()} domains")

# ================================================================================
# PART 5: Spatial Refinement
# ================================================================================

print("\n" + "=" * 70)
print("PART 5: Spatial Refinement")
print("=" * 70)

# Run mclust clustering (if available) or use leiden with refinement
try:
    print("\nClustering with mclust...")
    clustering(
        adata,
        n_clusters=n_clusters,
        method='mclust',
        refinement=False
    )
    adata.obs['domain_mclust'] = adata.obs['domain'].copy()
    print(f"  Mclust domains: {adata.obs['domain_mclust'].nunique()}")

    # Apply spatial refinement
    print("\nApplying spatial refinement...")
    refined_labels = refine_label(adata, radius=30, key='domain_mclust')
    adata.obs['domain_refined'] = refined_labels
    print(f"  Refined domain distribution:")
    print(adata.obs['domain_refined'].value_counts().sort_index())

except Exception as e:
    print(f"  Mclust not available: {e}")
    print("  Using leiden with refinement instead...")
    clustering(
        adata,
        n_clusters=n_clusters,
        method='leiden',
        refinement=True,
        radius=30
    )
    adata.obs['domain_refined'] = adata.obs['domain'].copy()

# ================================================================================
# PART 6: Multi-Section Simulation
# ================================================================================

print("\n" + "=" * 70)
print("PART 6: Multi-Section Integration")
print("=" * 70)

# Create two "slices" for demonstration
print("\nCreating synthetic multi-slice data...")

slice1 = create_synthetic_data(n_spots=200, n_genes=1000, n_domains=5, seed=42)
slice1.obs['batch'] = 'Slice1'

slice2 = create_synthetic_data(n_spots=200, n_genes=1000, n_domains=5, seed=43)
slice2.obs['batch'] = 'Slice2'

# Adjust coordinates for slice2
slice2.obsm['spatial'][:, 0] += 25  # Shift x coordinates

# Concatenate
import anndata as ad
adata_combined = ad.concat([slice1, slice2], label='batch', index_unique='-')
print(f"Combined data: {adata_combined.n_obs} spots from {adata_combined.obs['batch'].nunique()} slices")

# Train on combined data
print("\nTraining GraphST on combined data...")
model_combined = GraphST(
    adata=adata_combined,
    device=device,
    learning_rate=0.001,
    epochs=300,
    dim_output=64,
    random_seed=42,
    datatype='10X'
)

adata_combined = model_combined.train()

# Cluster combined data
clustering(adata_combined, n_clusters=5, method='leiden', refinement=False)
print(f"\nCombined data domains: {adata_combined.obs['domain'].nunique()}")

# ================================================================================
# PART 7: Deconvolution (scRNA-seq Transfer)
# ================================================================================

print("\n" + "=" * 70)
print("PART 7: scRNA-seq Transfer (Deconvolution)")
print("=" * 70)

# Create synthetic scRNA-seq reference
print("\nCreating synthetic scRNA-seq reference...")

n_cells = 500
n_cell_types = 5

cell_type_names = [f"CellType_{i}" for i in range(n_cell_types)]
cell_types = np.random.choice(cell_type_names, n_cells)

# Create expression matrix with cell type markers
counts_sc = np.random.poisson(lam=2, size=(n_cells, 1000)).astype(float)
for i, ct in enumerate(cell_types):
    ct_idx = cell_type_names.index(ct)
    marker_start = ct_idx * 200
    marker_end = marker_start + 200
    counts_sc[i, marker_start:marker_end] += np.random.poisson(20, 200)

adata_sc = sc.AnnData(X=counts_sc)
adata_sc.obs_names = [f"Cell_{i:04d}" for i in range(n_cells)]
adata_sc.var_names = adata.var_names[:1000]  # Use same gene names
adata_sc.obs['cell_type'] = cell_types

print(f"Created scRNA-seq reference: {adata_sc.n_obs} cells x {adata_sc.n_vars} genes")
print(f"Cell types: {adata_sc.obs['cell_type'].nunique()}")

# Prepare subset for deconvolution
adata_subset = adata[:, :1000].copy()

# Run deconvolution
print("\nTraining deconvolution model...")
try:
    model_deconv = GraphST(
        adata=adata_subset,
        adata_sc=adata_sc,
        device=device,
        learning_rate=0.001,
        epochs=200,
        dim_output=64,
        deconvolution=True,
        datatype='10X'
    )

    adata_subset, adata_sc = model_deconv.train_map()

    print("\nDeconvolution complete!")
    print(f"Mapping matrix shape: {adata_subset.obsm['map_matrix'].shape}")

    # Project cell types
    project_cell_to_spot(adata_subset, adata_sc, retain_percent=0.1)

    print("\nProjected cell type proportions:")
    for ct in cell_type_names:
        if ct in adata_subset.obs.columns:
            print(f"  {ct}: {adata_subset.obs[ct].mean():.3f} (mean proportion)")

except Exception as e:
    print(f"Deconvolution skipped: {e}")

# ================================================================================
# PART 8: Export Results
# ================================================================================

print("\n" + "=" * 70)
print("PART 8: Exporting Results")
print("=" * 70)

# Export main results
results_to_export = ['domain', 'domain_leiden', 'domain_louvain']
if 'domain_refined' in adata.obs.columns:
    results_to_export.append('domain_refined')

results_df = adata.obs[results_to_export].copy()
results_df.to_csv(os.path.join(output_dir, "domain_comparison.csv"))
print(f"Saved: domain_comparison.csv")

# Export embeddings
embeddings_df = pd.DataFrame(
    adata.obsm['emb'],
    index=adata.obs_names
)
embeddings_df.to_csv(os.path.join(output_dir, "embeddings.csv"))
print(f"Saved: embeddings.csv")

# Export combined results
combined_df = adata_combined.obs[['domain', 'batch']].copy()
combined_df.to_csv(os.path.join(output_dir, "multi_section_domains.csv"))
print(f"Saved: multi_section_domains.csv")

# Save AnnData objects
adata.write_h5ad(os.path.join(output_dir, "graphst_results.h5ad"))
adata_combined.write_h5ad(os.path.join(output_dir, "multi_section_results.h5ad"))
print(f"Saved: graphst_results.h5ad")
print(f"Saved: multi_section_results.h5ad")

# Export summary report
with open(os.path.join(output_dir, "analysis_report.txt"), 'w') as f:
    f.write("GraphST Advanced Analysis Report\n")
    f.write("=" * 50 + "\n\n")

    f.write("Dataset Summary\n")
    f.write("-" * 50 + "\n")
    f.write(f"Spots analyzed: {adata.n_obs}\n")
    f.write(f"Genes: {adata.n_vars}\n")
    f.write(f"Expected domains: {adata.obs['ground_truth'].nunique()}\n\n")

    f.write("Clustering Results\n")
    f.write("-" * 50 + "\n")
    for method in ['leiden', 'louvain']:
        f.write(f"\n{method.capitalize()}:\n")
        f.write(str(adata.obs[f'domain_{method}'].value_counts().sort_index()))
        f.write("\n")

    if 'domain_refined' in adata.obs.columns:
        f.write("\nRefined:\n")
        f.write(str(adata.obs['domain_refined'].value_counts().sort_index()))
        f.write("\n")

    f.write("\n\nMulti-Section Integration\n")
    f.write("-" * 50 + "\n")
    f.write(f"Total spots: {adata_combined.n_obs}\n")
    f.write(f"Slices: {adata_combined.obs['batch'].nunique()}\n")
    f.write(f"Integrated domains: {adata_combined.obs['domain'].nunique()}\n")

print(f"Saved: analysis_report.txt")

# ================================================================================
# Summary
# ================================================================================

print("\n" + "=" * 70)
print("Analysis Complete!")
print("=" * 70)

print(f"\nOutput files in {output_dir}/:")
print("  - domain_comparison.csv (multiple clustering methods)")
print("  - embeddings.csv (learned representations)")
print("  - multi_section_domains.csv (integrated results)")
print("  - graphst_results.h5ad (main AnnData)")
print("  - multi_section_results.h5ad (integrated AnnData)")
print("  - analysis_report.txt (summary report)")

print("\nNext steps:")
print("  1. Compare clustering methods using domain_comparison.csv")
print("  2. Visualize embeddings with UMAP or t-SNE")
print("  3. Evaluate spatial coherence of identified domains")
print("  4. For real data, use actual Visium or Stereo-seq files")
