#!/usr/bin/env python3
"""
Cell2location batch analysis example.

This example demonstrates processing multiple spatial samples
with a common single-cell reference.
"""

import numpy as np
import pandas as pd
import scanpy as sc
import anndata as ad
from anndata import concat

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

print("=" * 60)
print("Cell2location Batch Analysis Example")
print("=" * 60)

# ==============================================================================
# Step 1: Create Simulated Multi-Sample Data
# ==============================================================================
print("\nStep 1: Creating simulated multi-sample data...")

np.random.seed(42)

# Create reference scRNA-seq data
n_cells = 1000
n_genes = 300

ref_counts = np.random.poisson(5, size=(n_cells, n_genes))
ref_genes = [f"Gene_{i}" for i in range(n_genes)]
ref_cells = [f"Cell_{i}" for i in range(n_cells)]

ref_adata = ad.AnnData(
    X=ref_counts,
    obs=pd.DataFrame({
        'cell_type': np.random.choice(
            ['T_cell', 'B_cell', 'Macrophage', 'Fibroblast', 'Endothelial'],
            n_cells
        ),
        'sample': np.random.choice(['ref1', 'ref2'], n_cells)
    }, index=ref_cells),
    var=pd.DataFrame(index=ref_genes)
)

print(f"  Reference: {ref_adata.n_obs} cells, {ref_adata.n_vars} genes")

# Create multiple spatial samples
samples = ['Sample_A', 'Sample_B', 'Sample_C']
spatial_adatas = []

for sample in samples:
    n_spots = np.random.randint(80, 120)
    counts = np.random.poisson(50, size=(n_spots, n_genes))
    spots = [f"{sample}_Spot_{i}" for i in range(n_spots)]

    adata = ad.AnnData(
        X=counts,
        obs=pd.DataFrame({
            'sample': sample,
            'array_row': np.random.randint(0, 50, n_spots),
            'array_col': np.random.randint(0, 50, n_spots)
        }, index=spots),
        var=pd.DataFrame(index=ref_genes)
    )
    spatial_adatas.append(adata)
    print(f"  {sample}: {n_spots} spots")

# Merge spatial data
merged_spatial = concat(spatial_adatas, label='sample', keys=samples)
print(f"\n  Merged spatial: {merged_spatial.n_obs} spots, {merged_spatial.n_vars} genes")

# ==============================================================================
# Step 2: Estimate Reference Signatures (Once)
# ==============================================================================
print("\nStep 2: Estimating reference cell type signatures...")
print("  Note: Reference signatures only need to be estimated once")

# In practice:
# from cell2location.models import RegressionModel
# RegressionModel.setup_anndata(ref_adata, labels_key='cell_type', batch_key='sample')
# ref_model = RegressionModel(ref_adata)
# ref_model.train(max_epochs=250)
# ref_adata = ref_model.export_posterior(ref_adata, sample_kwargs={'num_samples': 1000})

# Simulate signatures
signatures = pd.DataFrame(
    np.random.lognormal(0, 1, size=(n_genes, 5)),
    index=ref_genes,
    columns=['T_cell', 'B_cell', 'Macrophage', 'Fibroblast', 'Endothelial']
)

print(f"  Signatures shape: {signatures.shape}")
print("  Cell types in reference:", list(signatures.columns))

# ==============================================================================
# Step 3: Process Each Sample
# ==============================================================================
print("\nStep 3: Processing each sample with cell2location...")

results = {}

for sample in samples:
    print(f"\n  Processing {sample}...")

    # Subset to sample
    adata_sample = merged_spatial[merged_spatial.obs['sample'] == sample].copy()

    # In practice:
    # from cell2location.models import Cell2location
    # Cell2location.setup_anndata(adata_sample, batch_key=None)
    # model = Cell2location(adata_sample, cell_state_df=signatures, N_cells_per_location=10)
    # model.train(max_epochs=30000)
    # adata_sample = model.export_posterior(adata_sample, sample_kwargs={'num_samples': 1000})

    # Simulate results
    n_spots_sample = adata_sample.n_obs
    props = np.random.dirichlet(np.ones(5), size=n_spots_sample)
    props_df = pd.DataFrame(
        props,
        index=adata_sample.obs_names,
        columns=signatures.columns
    )

    # Add to obs
    for ct in signatures.columns:
        adata_sample.obs[ct] = props_df[ct].values

    results[sample] = adata_sample
    print(f"    Completed: {n_spots_sample} spots deconvoluted")

# ==============================================================================
# Step 4: Compare Across Samples
# ==============================================================================
print("\n" + "=" * 60)
print("Step 4: Comparing cell type proportions across samples...")
print("=" * 60)

# Aggregate proportions per sample
comparison = pd.DataFrame()
for sample in samples:
    sample_props = results[sample].obs[signatures.columns].mean()
    comparison[sample] = sample_props

print("\n  Mean proportions per sample:")
print(comparison.round(3))

# Find dominant cell types per sample
dominant_per_sample = {}
for sample in samples:
    dominant = results[sample].obs[signatures.columns].idxmax(axis=1)
    dominant_per_sample[sample] = dominant.value_counts()

print("\n  Dominant cell type distribution per sample:")
for sample in samples:
    print(f"    {sample}:")
    print(f"      {dominant_per_sample[sample].to_dict()}")

# ==============================================================================
# Step 5: Identify Sample-Specific Patterns
# ==============================================================================
print("\nStep 5: Identifying sample-specific patterns...")

# Calculate cell type richness (number of cell types with >10% proportion)
richness = {}
for sample in samples:
    props = results[sample].obs[signatures.columns]
    rich = (props > 0.1).sum(axis=1)
    richness[sample] = rich.mean()

print("\n  Mean cell type richness per spot (>10% threshold):")
for sample in samples:
    print(f"    {sample}: {richness[sample]:.2f}")

# Identify spots with high T_cell infiltration
print("\n  Spots with high T_cell proportion (>30%):")
for sample in samples:
    high_tcell = (results[sample].obs['T_cell'] > 0.3).sum()
    total = results[sample].n_obs
    print(f"    {sample}: {high_tcell}/{total} ({100*high_tcell/total:.1f}%)")

# ==============================================================================
# Step 6: Visualization Options
# ==============================================================================
print("\nStep 6: Visualization options...")

print("\n  Sample comparison plots:")
print("    # Box plot of cell type proportions across samples")
print("    import seaborn as sns")
print("    comparison_melted = comparison.reset_index().melt(id_vars='index')")
print("    sns.boxplot(data=comparison_melted, x='variable', y='value')")

print("\n    # Heatmap of proportions")
print("    sns.clustermap(comparison, cmap='viridis', annot=True)")

print("\n  Spatial plots (per sample):")
print("    for sample in samples:")
print("        sq.pl.spatial_scatter(results[sample], color=['T_cell', 'B_cell'])")

# ==============================================================================
# Summary
# ==============================================================================
print("\n" + "=" * 60)
print("Batch Analysis Complete!")
print("=" * 60)

print("\nKey points for batch analysis:")
print("  1. Estimate reference signatures once on combined scRNA-seq")
print("  2. Process each spatial sample separately")
print("  3. Compare proportions across samples")
print("  4. Identify sample-specific patterns")
print("  5. Use consistent parameters across samples")

print("\nBatch processing advantages:")
print("  - Consistent reference across all samples")
print("  - Sample-specific technical effects modeled")
print("  - Enables direct comparison of cell type distributions")
print("  - Identifies batch effects and biological variation")
