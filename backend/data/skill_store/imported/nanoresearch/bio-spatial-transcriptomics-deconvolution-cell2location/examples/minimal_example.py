#!/usr/bin/env python3
"""
Minimal cell2location deconvolution example.

This example demonstrates the basic workflow for spatial deconvolution
using cell2location with a single-cell reference.
"""

import numpy as np
import pandas as pd
import scanpy as sc
import anndata as ad

# Import from skill
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

from core_analysis import prepare_data, run_cell2location, estimate_cell_type_proportions
from visualization import plot_proportions_spatial, plot_cell_type_maps

print("=" * 60)
print("Cell2location Minimal Example")
print("=" * 60)

# ==============================================================================
# Step 1: Create Simulated Data
# ==============================================================================
print("\nStep 1: Creating simulated data...")

np.random.seed(42)

# Create reference scRNA-seq data
n_cells = 500
n_genes = 200

ref_counts = np.random.poisson(5, size=(n_cells, n_genes))
ref_genes = [f"Gene_{i}" for i in range(n_genes)]
ref_cells = [f"Cell_{i}" for i in range(n_cells)]

ref_adata = ad.AnnData(
    X=ref_counts,
    obs=pd.DataFrame({
        'cell_type': np.random.choice(['T_cell', 'B_cell', 'Macrophage', 'Fibroblast'], n_cells)
    }, index=ref_cells),
    var=pd.DataFrame(index=ref_genes)
)

print(f"  Reference: {ref_adata.n_obs} cells, {ref_adata.n_vars} genes")
print(f"  Cell types: {ref_adata.obs['cell_type'].value_counts().to_dict()}")

# Create spatial data
n_spots = 100

spatial_counts = np.random.poisson(50, size=(n_spots, n_genes))
spatial_genes = ref_genes  # Same genes
spatial_spots = [f"Spot_{i}" for i in range(n_spots)]

spatial_adata = ad.AnnData(
    X=spatial_counts,
    obs=pd.DataFrame(index=spatial_spots),
    var=pd.DataFrame(index=spatial_genes)
)

print(f"  Spatial: {spatial_adata.n_obs} spots, {spatial_adata.n_vars} genes")

# ==============================================================================
# Step 2: Prepare Data
# ==============================================================================
print("\nStep 2: Preparing data...")

spatial_prep, ref_prep = prepare_data(
    spatial_adata=spatial_adata,
    reference_adata=ref_adata,
    cell_type_key='cell_type',
    min_common_genes=50
)

print(f"  Prepared spatial: {spatial_prep.n_obs} spots, {spatial_prep.n_vars} genes")
print(f"  Prepared reference: {ref_prep.n_obs} cells, {ref_prep.n_vars} genes")

# ==============================================================================
# Step 3: Run Cell2location (Simplified)
# ==============================================================================
print("\nStep 3: Running cell2location...")
print("  Note: In practice, use run_cell2location() with proper parameters")
print("  This example shows the workflow structure")

# In practice, you would run:
# results = run_cell2location(
#     spatial_prep,
#     ref_prep,
#     cell_type_key='cell_type',
#     max_epochs=30000,
#     gpu=True
# )

# For this example, simulate results
print("\n  Simulating cell2location results...")
cell_types = ref_prep.obs['cell_type'].unique()
n_cell_types = len(cell_types)

# Simulate proportions (summing to 1 per spot)
props = np.random.dirichlet(np.ones(n_cell_types), size=n_spots)
props_df = pd.DataFrame(
    props,
    index=spatial_prep.obs_names,
    columns=cell_types
)

print(f"  Estimated proportions shape: {props_df.shape}")
print(f"  Cell types: {list(cell_types)}")

# ==============================================================================
# Step 4: Analyze Results
# ==============================================================================
print("\nStep 4: Analyzing results...")

# Add proportions to spatial data
for ct in cell_types:
    spatial_prep.obs[ct] = props_df[ct].values

print("\n  Mean proportions per cell type:")
print(props_df.mean().sort_values(ascending=False))

# Find dominant cell type per spot
dominant = props_df.idxmax(axis=1)
spatial_prep.obs['dominant_cell_type'] = dominant

print("\n  Dominant cell type distribution:")
print(dominant.value_counts())

# ==============================================================================
# Step 5: Visualization (Conceptual)
# ==============================================================================
print("\nStep 5: Visualization options...")

print("\n  To visualize proportions on spatial coordinates:")
print("    sq.pl.spatial_scatter(adata, color=['T_cell', 'B_cell', 'Macrophage'])")

print("\n  To plot proportions as stacked bar:")
print("    props_df.plot(kind='bar', stacked=True, figsize=(10, 4))")

print("\n  To create proportion heatmap:")
print("    import seaborn as sns")
print("    sns.clustermap(props_df.T, cmap='viridis')")

# ==============================================================================
# Summary
# ==============================================================================
print("\n" + "=" * 60)
print("Example Complete!")
print("=" * 60)

print("\nKey steps for cell2location analysis:")
print("  1. Prepare annotated scRNA-seq reference")
print("  2. Load spatial transcriptomics data")
print("  3. Run prepare_data() to harmonize genes")
print("  4. Run run_cell2location() for deconvolution")
print("  5. Extract proportions with estimate_cell_type_proportions()")
print("  6. Visualize with spatial plots and heatmaps")

print("\nFor real analysis, use:")
print("  results = run_cell2location(spatial_prep, ref_prep, cell_type_key='cell_type')")
