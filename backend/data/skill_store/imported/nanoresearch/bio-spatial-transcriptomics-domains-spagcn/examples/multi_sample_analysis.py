#!/usr/bin/env python3
"""
SpaGCN Multi-Sample Analysis Example

This example demonstrates processing multiple spatial samples
and integrating them for joint domain identification.

Requirements:
    pip install SpaGCN scanpy anndata numpy pandas matplotlib

Usage:
    python multi_sample_analysis.py
"""

import numpy as np
import pandas as pd
import scanpy as sc
import anndata as ad
from anndata import concat
import random
import torch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

from core_analysis import (
    prepare_data,
    calculate_adjacency_matrix,
    search_optimal_l,
    search_optimal_resolution,
    run_spagcn,
    refine_domains
)
from visualization import plot_multi_sample_domains, plot_domain_comparison

print("=" * 70)
print("SpaGCN Multi-Sample Analysis Example")
print("=" * 70)

# ==============================================================================
# Step 1: Create Simulated Multi-Sample Data
# ==============================================================================
print("\nStep 1: Creating simulated multi-sample data...")

np.random.seed(42)

samples = ['Sample_A', 'Sample_B', 'Sample_C']
sample_adatas = []

n_genes = 1000
all_genes = [f"Gene_{i}" for i in range(n_genes)]

for sample_name in samples:
    n_spots = np.random.randint(300, 500)

    # Create coordinates
    array_rows = np.random.randint(0, 30, n_spots)
    array_cols = np.random.randint(0, 25, n_spots)
    x_pixels = array_cols * 100 + (array_rows % 2) * 50
    y_pixels = array_rows * 87

    # Create expression with sample-specific patterns
    counts = np.random.poisson(5, size=(n_spots, n_genes))

    # Add spatial structure
    domain_labels = []
    for i in range(n_spots):
        row = array_rows[i]
        domain = min(row // 6, 4)
        domain_labels.append(domain)
        domain_genes_start = domain * (n_genes // 5)
        domain_genes_end = (domain + 1) * (n_genes // 5)
        counts[i, domain_genes_start:domain_genes_end] += np.random.poisson(8, size=len(range(domain_genes_start, domain_genes_end)))

    # Create AnnData
    spot_names = [f"{sample_name}_Spot_{i}" for i in range(n_spots)]
    adata_sample = ad.AnnData(
        X=counts,
        obs=pd.DataFrame({
            'array_row': array_rows,
            'array_col': array_cols,
            'x_pixel': x_pixels,
            'y_pixel': y_pixels,
            'sample': sample_name,
            'true_domain': domain_labels
        }, index=spot_names),
        var=pd.DataFrame(index=all_genes)
    )
    sample_adatas.append(adata_sample)
    print(f"  {sample_name}: {n_spots} spots")

# ==============================================================================
# Step 2: Process Each Sample Separately
# ==============================================================================
print("\nStep 2: Processing each sample separately...")

individual_results = {}

for adata_sample in sample_adatas:
    sample_name = adata_sample.obs['sample'].iloc[0]
    print(f"\n  Processing {sample_name}...")

    # Preprocess
    adata_prep = prepare_data(adata_sample, min_cells=3, n_top_genes=500)

    # Calculate adjacency
    adj = calculate_adjacency_matrix(
        adata_prep,
        x_column="array_col",
        y_column="array_row",
        histology=False
    )

    # Search parameters
    l = search_optimal_l(adj, target_p=0.5)
    resolution = search_optimal_resolution(adata_prep, adj, l=l, target_clusters=5, max_epochs=10)

    # Run SpaGCN
    random.seed(100)
    torch.manual_seed(100)
    np.random.seed(100)

    domains = run_spagcn(adata_prep, adj, l=l, resolution=resolution, max_epochs=200)

    # Store results
    adata_sample.obs["individual_domain"] = domains
    adata_sample.obs["individual_domain"] = adata_sample.obs["individual_domain"].astype('category')
    individual_results[sample_name] = adata_sample

    print(f"    Domains: {sorted(set(domains))}")

# ==============================================================================
# Step 3: Integrate and Process Jointly
# ==============================================================================
print("\nStep 3: Integrating samples for joint analysis...")

# Concatenate samples
merged_adata = concat(sample_adatas, label='sample', keys=samples, join='inner')
print(f"  Merged data: {merged_adata.n_obs} spots, {merged_adata.n_vars} genes")

# Preprocess merged data
merged_prep = prepare_data(merged_adata, min_cells=3, n_top_genes=500)

# ==============================================================================
# Step 4: Joint Domain Detection
# ==============================================================================
print("\nStep 4: Running joint domain detection...")

# Modify coordinates for integration (offset samples)
x_pixels = []
y_pixels = []
sample_y_offset = 0

for sample in samples:
    mask = merged_prep.obs['sample'] == sample
    sample_adata = merged_prep[mask]
    sample_y_max = sample_adata.obs['y_pixel'].max()

    x_pixels.extend(sample_adata.obs['x_pixel'].tolist())
    y_pixels.extend(sample_adata.obs['y_pixel'].tolist() + sample_y_offset)

    sample_y_offset += sample_y_max + 500

merged_prep.obs['joint_x_pixel'] = x_pixels
merged_prep.obs['joint_y_pixel'] = y_pixels

# Calculate adjacency
adj_joint = calculate_adjacency_matrix(
    merged_prep,
    x_column="joint_x_pixel",
    y_column="joint_y_pixel",
    histology=False
)

# Search parameters
l_joint = search_optimal_l(adj_joint, target_p=0.5)
resolution_joint = search_optimal_resolution(merged_prep, adj_joint, l=l_joint, target_clusters=5, max_epochs=10)

# Run SpaGCN
random.seed(100)
torch.manual_seed(100)
np.random.seed(100)

joint_domains = run_spagcn(merged_prep, adj_joint, l=l_joint, resolution=resolution_joint, max_epochs=200)

merged_adata.obs["joint_domain"] = joint_domains
merged_adata.obs["joint_domain"] = merged_adata.obs["joint_domain"].astype('category')

print(f"  Joint domains: {sorted(set(joint_domains))}")

# ==============================================================================
# Step 5: Compare Individual vs Joint Results
# ==============================================================================
print("\nStep 5: Comparing individual and joint results...")

# Split back to individual samples for visualization
fig, axes = plt.subplots(len(samples), 3, figsize=(18, 6 * len(samples)))
if len(samples) == 1:
    axes = axes.reshape(1, -1)

import matplotlib.pyplot as plt

for idx, sample in enumerate(samples):
    mask = merged_adata.obs['sample'] == sample
    adata_sample = merged_adata[mask].copy()

    # Get original individual results
    orig_sample = individual_results[sample]

    # Plot true domains
    ax = axes[idx, 0]
    domains = adata_sample.obs["true_domain"]
    colors = plt.cm.tab10(np.linspace(0, 1, len(set(domains))))
    color_map = dict(zip(sorted(set(domains)), colors))
    ax.scatter(adata_sample.obs['x_pixel'], adata_sample.obs['y_pixel'],
               c=[color_map[d] for d in domains], s=20, alpha=0.8)
    ax.set_title(f"{sample} - True")
    ax.set_aspect('equal')
    ax.invert_yaxis()

    # Plot individual domains
    ax = axes[idx, 1]
    domains = orig_sample.obs["individual_domain"]
    colors = plt.cm.tab10(np.linspace(0, 1, len(set(domains))))
    color_map = dict(zip(sorted(set(domains)), colors))
    ax.scatter(orig_sample.obs['x_pixel'], orig_sample.obs['y_pixel'],
               c=[color_map[d] for d in domains], s=20, alpha=0.8)
    ax.set_title(f"{sample} - Individual")
    ax.set_aspect('equal')
    ax.invert_yaxis()

    # Plot joint domains
    ax = axes[idx, 2]
    domains = adata_sample.obs["joint_domain"]
    colors = plt.cm.tab10(np.linspace(0, 1, len(set(domains))))
    color_map = dict(zip(sorted(set(domains)), colors))
    ax.scatter(adata_sample.obs['x_pixel'], adata_sample.obs['y_pixel'],
               c=[color_map[d] for d in domains], s=20, alpha=0.8)
    ax.set_title(f"{sample} - Joint")
    ax.set_aspect('equal')
    ax.invert_yaxis()

plt.tight_layout()
plt.savefig("multi_sample_comparison.png", dpi=300, bbox_inches='tight')
print("  Saved comparison to multi_sample_comparison.png")

# ==============================================================================
# Step 6: Domain Statistics
# ==============================================================================
print("\nStep 6: Domain statistics across samples...")

# Domain distribution per sample
domain_stats = pd.crosstab(merged_adata.obs['sample'], merged_adata.obs['joint_domain'])
print("\n  Domain counts per sample:")
print(domain_stats)

# Proportions
print("\n  Domain proportions per sample:")
print(domain_stats.div(domain_stats.sum(axis=1), axis=0).round(3))

# ==============================================================================
# Summary
# ==============================================================================
print("\n" + "=" * 70)
print("Multi-Sample Analysis Complete!")
print("=" * 70)

print("\nKey points for multi-sample analysis:")
print("  1. Process each sample individually for sample-specific patterns")
print("  2. Integrate samples for consistent domain identification")
print("  3. Use joint analysis for cross-sample comparison")
print("  4. Consider batch effects when interpreting results")

print("\nAdvantages of joint analysis:")
print("  - Consistent domain labels across samples")
print("  - Enables direct comparison of domain proportions")
print("  - Identifies common spatial patterns")
print("  - Better for small samples (more data for training)")
