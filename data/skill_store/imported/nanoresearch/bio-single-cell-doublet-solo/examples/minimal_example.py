#!/usr/bin/env python
"""
Minimal Example: SOLO Doublet Detection

This example demonstrates the basic workflow for running SOLO
doublet detection on a single-cell RNA-seq dataset.
"""

import scanpy as sc
import sys
sys.path.insert(0, '../scripts/python')

from core_analysis import run_solo_pipeline, filter_doublets
from visualization import plot_doublet_score_distribution, plot_doublets_on_embedding
from utils import validate_adata_for_solo, create_summary_report

# ==============================================================================
# Load and Prepare Data
# ==============================================================================

# Load your data (raw counts required)
adata = sc.read_h5ad("your_raw_counts.h5ad")

# Or use example data
# adata = sc.datasets.pbmc3k()

print(f"Input data: {adata.n_obs} cells, {adata.n_vars} genes")

# Validate data
validate_adata_for_solo(adata, require_raw=True)

# Basic preprocessing (keep raw counts!)
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)

print(f"After filtering: {adata.n_obs} cells, {adata.n_vars} genes")

# ==============================================================================
# Run SOLO Pipeline
# ==============================================================================

# Run complete SOLO pipeline
# This trains scVI, then SOLO, and returns predictions
predictions = run_solo_pipeline(
    adata,
    batch_key=None,              # Set to batch column if multiple batches
    scvi_epochs=400,             # Epochs for scVI training
    solo_epochs=100,             # Epochs for SOLO training
    doublet_ratio=2,             # Ratio of simulated doublets
    doublet_threshold=0.5,       # Threshold for calling doublets
    use_gpu=True,                # Use GPU if available
    random_seed=42,
    inplace=True,                # Add predictions to adata.obs
    verbose=True
)

# View predictions
print("\nPredictions head:")
print(predictions.head())

# ==============================================================================
# Explore Results
# ==============================================================================

# Summary by prediction
print("\nDoublet Detection Statistics:")
n_doublets = (predictions['doublet'] > 0.5).sum()
print(f"  Total cells: {len(predictions)}")
print(f"  Predicted doublets: {n_doublets} ({n_doublets/len(predictions)*100:.1f}%)")
print(f"  Mean doublet score: {predictions['doublet'].mean():.4f}")
print(f"  Median doublet score: {predictions['doublet'].median():.4f}")

# Summary by prediction
print("\nPrediction counts:")
print(adata.obs['solo_prediction'].value_counts())

# ==============================================================================
# Visualization
# ==============================================================================

# Plot doublet score distribution
plot_doublet_score_distribution(
    predictions,
    threshold=0.5,
    title="Doublet Score Distribution",
    save_path="doublet_distribution.pdf"
)

# Compute UMAP for visualization
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes=2000)
sc.pp.scale(adata)
sc.tl.pca(adata, svd_solver='arpack')
sc.pp.neighbors(adata)
sc.tl.umap(adata)

# Plot on UMAP
plot_doublets_on_embedding(
    adata,
    doublet_key='solo_prediction',
    score_key='solo_doublet_score',
    basis='umap',
    title="SOLO Doublet Predictions",
    save_path="doublets_umap.pdf"
)

# ==============================================================================
# Filter Doublets
# ==============================================================================

# Filter out doublets
adata_filtered = filter_doublets(adata, predictions, inplace=False)

print(f"\nBefore filtering: {adata.n_obs} cells")
print(f"After filtering: {adata_filtered.n_obs} cells")
print(f"Removed: {adata.n_obs - adata_filtered.n_obs} doublets")

# Save filtered data
adata_filtered.write_h5ad("filtered_data.h5ad")

# ==============================================================================
# Generate Report
# ==============================================================================

report = create_summary_report(predictions, threshold=0.5, output_path="solo_report.txt")
print(report)

print("\nAnalysis complete!")
