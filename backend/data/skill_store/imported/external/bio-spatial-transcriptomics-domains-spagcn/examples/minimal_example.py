#!/usr/bin/env python3
"""
SpaGCN Minimal Example

This example demonstrates the basic workflow for spatial domain identification
using SpaGCN on a single Visium sample.

Requirements:
    pip install SpaGCN scanpy anndata numpy pandas matplotlib seaborn

Usage:
    python minimal_example.py
"""

import numpy as np
import pandas as pd
import scanpy as sc
import anndata as ad
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
from visualization import plot_spatial_domains, plot_domain_comparison

print("=" * 70)
print("SpaGCN Minimal Example - Spatial Domain Identification")
print("=" * 70)

# ==============================================================================
# Step 1: Create Simulated Visium Data
# ==============================================================================
print("\nStep 1: Creating simulated Visium data...")

np.random.seed(42)

# Parameters
n_spots = 500
n_genes = 2000

# Create spot coordinates (Visium hexagonal grid pattern)
array_rows = []
array_cols = []
x_pixels = []
y_pixels = []

spot_idx = 0
for row in range(25):
    for col in range(20):
        if spot_idx < n_spots:
            array_rows.append(row)
            array_cols.append(col)
            # Convert to pixel coordinates
            x_pixels.append(col * 100 + (row % 2) * 50)
            y_pixels.append(row * 87)
            spot_idx += 1

# Create expression matrix (simulate spatial patterns)
counts = np.random.poisson(5, size=(n_spots, n_genes))

# Add spatial structure - create 7 domains with different expression
# Domain 0-6 correspond to different tissue layers
domain_labels = []
for i in range(n_spots):
    row = array_rows[i]
    # Create layers based on row position
    domain = min(row // 4, 6)
    domain_labels.append(domain)
    # Add domain-specific expression
    domain_genes_start = domain * (n_genes // 7)
    domain_genes_end = (domain + 1) * (n_genes // 7)
    counts[i, domain_genes_start:domain_genes_end] += np.random.poisson(10, size=len(range(domain_genes_start, domain_genes_end)))

# Create AnnData
spot_names = [f"Spot_{i}" for i in range(n_spots)]
gene_names = [f"Gene_{i}" for i in range(n_genes)]

adata = ad.AnnData(
    X=counts,
    obs=pd.DataFrame({
        'array_row': array_rows[:n_spots],
        'array_col': array_cols[:n_spots],
        'x_pixel': x_pixels[:n_spots],
        'y_pixel': y_pixels[:n_spots],
        'true_domain': domain_labels
    }, index=spot_names),
    var=pd.DataFrame(index=gene_names)
)

print(f"  Created data: {adata.n_obs} spots, {adata.n_vars} genes")
print(f"  True domains: {sorted(set(domain_labels))}")

# ==============================================================================
# Step 2: Preprocess Data
# ==============================================================================
print("\nStep 2: Preprocessing data...")

adata_prep = prepare_data(
    adata,
    min_cells=3,
    min_genes=3,
    n_top_genes=1000
)

# ==============================================================================
# Step 3: Calculate Adjacency Matrix
# ==============================================================================
print("\nStep 3: Calculating adjacency matrix...")

# Without histology
adj = calculate_adjacency_matrix(
    adata_prep,
    x_column="array_col",
    y_column="array_row",
    histology=False
)

print(f"  Adjacency matrix shape: {adj.shape}")
print(f"  Mean distance: {adj.mean():.2f}")

# ==============================================================================
# Step 4: Search for Optimal Parameters
# ==============================================================================
print("\nStep 4: Searching for optimal parameters...")

# Search for l parameter (target p=0.5 means 50% of expression from neighborhood)
l = search_optimal_l(adj, target_p=0.5)
print(f"  Optimal l = {l:.4f}")

# Search for resolution (target 7 clusters)
resolution = search_optimal_resolution(
    adata_prep,
    adj,
    l=l,
    target_clusters=7,
    max_epochs=10  # Use low epochs for speed in parameter search
)
print(f"  Optimal resolution = {resolution:.4f}")

# ==============================================================================
# Step 5: Run SpaGCN
# ==============================================================================
print("\nStep 5: Running SpaGCN...")

# Set seeds for reproducibility
random.seed(100)
torch.manual_seed(100)
np.random.seed(100)

# Run SpaGCN
domains, probabilities = run_spagcn(
    adata_prep,
    adj,
    l=l,
    resolution=resolution,
    max_epochs=200,
    return_probabilities=True
)

# Add to original adata
adata.obs["spagcn_domain"] = domains
adata.obs["spagcn_domain"] = adata.obs["spagcn_domain"].astype('category')

print(f"  Identified {len(set(domains))} domains")
print(f"  Domain distribution: {pd.Series(domains).value_counts().sort_index().to_dict()}")

# ==============================================================================
# Step 6: Domain Refinement (Optional)
# ==============================================================================
print("\nStep 6: Refining domains...")

refined_domains = refine_domains(
    adata,
    domains,
    x_column="array_col",
    y_column="array_row",
    shape="hexagon"
)

adata.obs["refined_domain"] = refined_domains
adata.obs["refined_domain"] = adata.obs["refined_domain"].astype('category')

print(f"  Refinement complete")

# ==============================================================================
# Step 7: Visualization
# ==============================================================================
print("\nStep 7: Creating visualizations...")

# Plot original vs predicted domains
fig = plot_domain_comparison(
    adata,
    domain_columns=["true_domain", "spagcn_domain", "refined_domain"],
    labels=["True Domains", "SpaGCN", "Refined"],
    x_column="x_pixel",
    y_column="y_pixel",
    figsize=(20, 6),
    save_path="spagcn_results.png"
)

print("  Saved visualization to spagcn_results.png")

# ==============================================================================
# Step 8: Evaluate Results
# ==============================================================================
print("\nStep 8: Evaluating results...")

from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

ari = adjusted_rand_score(adata.obs["true_domain"], adata.obs["spagcn_domain"])
nmi = normalized_mutual_info_score(adata.obs["true_domain"], adata.obs["spagcn_domain"])

print(f"  Adjusted Rand Index (ARI): {ari:.3f}")
print(f"  Normalized Mutual Information (NMI): {nmi:.3f}")

# ==============================================================================
# Summary
# ==============================================================================
print("\n" + "=" * 70)
print("Analysis Complete!")
print("=" * 70)

print("\nKey steps demonstrated:")
print("  1. Data preprocessing (normalization, HVG selection)")
print("  2. Adjacency matrix calculation")
print("  3. Parameter optimization (l and resolution)")
print("  4. SpaGCN training and prediction")
print("  5. Domain refinement")
print("  6. Visualization")

print("\nNext steps:")
print("  - Identify spatially variable genes (SVGs)")
print("  - Find meta genes for specific domains")
print("  - Analyze multiple tissue sections")
