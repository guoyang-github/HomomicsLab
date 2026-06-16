"""
Basic STAGATE Spatial Domain Analysis Example

This example demonstrates the complete workflow for spatial domain
identification using STAGATE's graph attention autoencoder.

Steps:
1. Load and prepare Visium spatial data
2. Build spatial neighbor network
3. Train STAGATE model
4. Cluster domains using mclust or Leiden
5. Visualize results
6. Multi-slice integration (optional)

Author: Yang Guo
Date: 2026-04-03
"""

import numpy as np
import pandas as pd
import scanpy as sc
import matplotlib.pyplot as plt

# Import STAGATE wrapper functions
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

from core_analysis import (
    prepare_data,
    build_spatial_network,
    build_3d_spatial_network,
    plot_network_stats,
    train_stagate,
    mclust_clustering,
    leiden_clustering,
    create_batch_data,
    export_results,
    compute_domain_enrichment,
)

from visualization import (
    plot_domains,
    plot_domains_comparison,
    plot_embedding_umap,
    plot_domain_proportions,
    plot_gene_expression,
    plot_denoising_comparison,
    plot_multi_sample_domains,
    plot_aligned_slices,
)


# ============================================================================
# PART 1: Load Sample Data
# ============================================================================

print("=" * 70)
print("PART 1: Loading Spatial Data")
print("=" * 70)

# Option 1: Use Visium sample data from scanpy
try:
    adata = sc.datasets.visium(
        filename='V1_Mouse_Brain_Sagittal_Posterior'
    )
    adata.var_names_make_unique()
    print(f"Loaded Visium mouse brain data: {adata.n_obs} spots x {adata.n_vars} genes")
except:
    # Create synthetic data for demonstration
    print("Creating synthetic spatial data for demonstration...")
    n_spots = 500
    n_genes = 1000

    counts = np.random.poisson(5, (n_spots, n_genes))
    adata = sc.AnnData(X=counts)
    adata.var_names = [f'GENE_{i}' for i in range(n_genes)]
    adata.obs_names = [f'SPOT_{i}' for i in range(n_spots)]

    # Create grid coordinates
    grid_size = int(np.ceil(np.sqrt(n_spots)))
    x = np.repeat(np.arange(grid_size), grid_size)[:n_spots]
    y = np.tile(np.arange(grid_size), grid_size)[:n_spots]
    adata.obsm['spatial'] = np.column_stack([x * 100, y * 100])

    # Add some structure
    adata.obs['region'] = pd.Categorical(
        np.where(x < grid_size/2, 'Region1', 'Region2')
    )

    print(f"Created synthetic data: {adata.n_obs} spots x {adata.n_vars} genes")

# Check spatial coordinates
print(f"\nSpatial coordinates shape: {adata.obsm['spatial'].shape}")
print(f"Coordinate range:")
print(f"  X: [{adata.obsm['spatial'][:,0].min():.1f}, {adata.obsm['spatial'][:,0].max():.1f}]")
print(f"  Y: [{adata.obsm['spatial'][:,1].min():.1f}, {adata.obsm['spatial'][:,1].max():.1f}]")


# ============================================================================
# PART 2: Data Preparation
# ============================================================================

print("\n" + "=" * 70)
print("PART 2: Data Preparation")
print("=" * 70)

# Prepare data
adata = prepare_data(
    adata,
    min_counts=100,
    n_top_genes=3000,
    normalize=True,
    log1p=True,
)

print(f"\nFinal data: {adata.n_obs} spots x {adata.n_vars} genes")
print(f"HVGs: {adata.var.highly_variable.sum()}")


# ============================================================================
# PART 3: Build Spatial Network
# ============================================================================

print("\n" + "=" * 70)
print("PART 3: Building Spatial Network")
print("=" * 70)

# Method 1: Radius-based neighbors (recommended for Visium)
build_spatial_network(
    adata,
    rad_cutoff=150,  # ~3 spot diameters for Visium
    model='Radius',
    spatial_key='spatial',
    verbose=True,
)

# Visualize network statistics
print("\n--- Network Statistics ---")
plot_network_stats(adata)
plt.savefig('network_stats.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved: network_stats.png")

# Method 2: KNN-based neighbors (alternative)
# build_spatial_network(adata, k_cutoff=10, model='KNN')


# ============================================================================
# PART 4: Train STAGATE Model
# ============================================================================

print("\n" + "=" * 70)
print("PART 4: Training STAGATE Model")
print("=" * 70)

# Train STAGATE
adata = train_stagate(
    adata,
    hidden_dims=[512, 30],  # [hidden_dim, embedding_dim]
    n_epochs=500,           # Reduce for faster training
    lr=0.001,
    key_added='STAGATE',
    gradient_clipping=5.0,
    weight_decay=0.0001,
    random_seed=0,
    save_loss=True,
    save_reconstruction=True,  # For denoising
    device=None,              # Auto-detect GPU/CPU
)

print(f"\nSTAGATE embeddings shape: {adata.obsm['STAGATE'].shape}")


# ============================================================================
# PART 5: Cluster Domains
# ============================================================================

print("\n" + "=" * 70)
print("PART 5: Clustering Domains")
print("=" * 70)

# Method 1: mclust clustering (requires R and rpy2)
try:
    adata = mclust_clustering(
        adata,
        n_clusters=7,
        used_obsm='STAGATE',
        model_names='EEE',
        random_seed=2020,
        key_added='mclust',
    )
except Exception as e:
    print(f"mclust failed (requires R): {e}")
    print("Using Leiden clustering instead...")
    adata = leiden_clustering(
        adata,
        resolution=0.5,
        used_obsm='STAGATE',
        key_added='mclust',
    )

# Method 2: Leiden clustering
adata = leiden_clustering(
    adata,
    resolution=0.5,
    used_obsm='STAGATE',
    key_added='stagate_leiden',
    n_neighbors=15,
)

print("\nDomain counts:")
print(adata.obs['mclust'].value_counts().sort_index())


# ============================================================================
# PART 6: Visualize Results
# ============================================================================

print("\n" + "=" * 70)
print("PART 6: Visualization")
print("=" * 70)

# 1. Plot spatial domains
print("\n--- Plotting Spatial Domains ---")
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

plot_domains(adata, domain_key='mclust', ax=axes[0], title='STAGATE Domains (mclust)')
plot_domains(adata, domain_key='stagate_leiden', ax=axes[1], title='STAGATE Domains (Leiden)')

plt.tight_layout()
plt.savefig('stagate_domains.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved: stagate_domains.png")

# 2. Plot UMAP of embeddings
print("\n--- Plotting UMAP ---")
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

plot_embedding_umap(adata, embedding_key='STAGATE', color_key='mclust', ax=axes[0])
plot_embedding_umap(adata, embedding_key='STAGATE', color_key='stagate_leiden', ax=axes[1])

plt.tight_layout()
plt.savefig('stagate_umap.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved: stagate_umap.png")

# 3. Compare clustering methods
print("\n--- Comparing Clustering Methods ---")
fig = plot_domains_comparison(
    adata,
    domain_keys=['mclust', 'stagate_leiden'],
    n_cols=2,
    figsize_per_plot=(8, 7),
)
plt.savefig('stagate_comparison.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved: stagate_comparison.png")

# 4. Domain proportions
print("\n--- Domain Proportions ---")
fig = plot_domain_proportions(adata, domain_key='mclust')
plt.savefig('stagate_proportions.png', dpi=150, bbox_inches='tight')
plt.close()
print("Saved: stagate_proportions.png")


# ============================================================================
# PART 7: Gene Expression Visualization (Optional)
# ============================================================================

print("\n" + "=" * 70)
print("PART 7: Gene Expression Visualization")
print("=" * 70)

# Plot a highly variable gene
hvg_genes = adata.var_names[adata.var.highly_variable][:5]
print(f"\nPlotting top HVGs: {list(hvg_genes)}")

for gene in hvg_genes[:3]:
    try:
        fig = plot_gene_expression(
            adata,
            gene=gene,
            layer=None,  # Use raw expression
            cmap='viridis',
        )
        plt.savefig(f'expression_{gene}.png', dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Saved: expression_{gene}.png")
    except Exception as e:
        print(f"Could not plot {gene}: {e}")

# Compare raw vs denoised (if reconstruction saved)
if 'STAGATE_ReX' in adata.layers:
    print("\n--- Denoising Comparison ---")
    try:
        gene = hvg_genes[0]
        fig = plot_denoising_comparison(adata, gene=gene)
        plt.savefig(f'denoising_{gene}.png', dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Saved: denoising_{gene}.png")
    except Exception as e:
        print(f"Could not plot denoising: {e}")


# ============================================================================
# PART 8: Export Results
# ============================================================================

print("\n" + "=" * 70)
print("PART 8: Exporting Results")
print("=" * 70)

export_results(
    adata,
    output_dir='./stagate_results',
    domain_key='mclust',
    embedding_key='STAGATE',
)

print("\n" + "=" * 70)
print("Analysis Complete!")
print("=" * 70)
print("\nGenerated files:")
print("  - network_stats.png: Spatial network statistics")
print("  - stagate_domains.png: Spatial domain maps")
print("  - stagate_umap.png: UMAP visualization")
print("  - stagate_comparison.png: Clustering comparison")
print("  - stagate_proportions.png: Domain proportions")
print("  - expression_*.png: Gene expression maps")
print("  - stagate_results/: Exported data files")
print("\nNext steps:")
print("  1. Adjust n_clusters or resolution based on results")
print("  2. Try 3D analysis if you have multiple sections")
print("  3. Use batch processing for large datasets")
print("=" * 70)
