#!/usr/bin/env python3
"""
infercnvpy Basic Analysis Example

Demonstrates complete CNV inference workflow with simulated tumor data.
"""

import numpy as np
import pandas as pd
import scanpy as sc
import sys
from pathlib import Path

# Import analysis module
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

from infercnv_analysis import (
    run_infercnv_pipeline,
    add_gene_positions,
    cluster_by_cnv,
    identify_cnv_regions,
    summarize_cnv_by_chromosome,
    export_cnv_results
)

# ============================================================================
# Step 1: Create Simulated Tumor Data
# ============================================================================

print("=" * 60)
print("Step 1: Create Simulated Tumor Dataset")
print("=" * 60)

np.random.seed(42)
n_cells = 200
n_genes = 500

# Create expression matrix with some CNV signal
counts = np.random.poisson(5, size=(n_cells, n_genes))

# Create gene names with chromosomal positions
genes = []
chromosomes = []
starts = []
ends = []

for i in range(n_genes):
    chr_num = (i // 100) + 1  # 100 genes per chromosome
    if chr_num > 4:  # Only 4 chromosomes for this example
        chr_num = 4
    genes.append(f"GENE_{i}")
    chromosomes.append(f"chr{chr_num}")
    starts.append(i * 10000)
    ends.append((i + 1) * 10000)

# Create cell annotations
cell_types = ['T_cell'] * 40 + ['B_cell'] * 40 + ['Macrophage'] * 20 + ['Tumor'] * 100

# Create AnnData
adata = sc.AnnData(
    X=counts,
    obs=pd.DataFrame({
        'cell_type': cell_types,
    }, index=[f"cell_{i}" for i in range(n_cells)]),
    var=pd.DataFrame({
        'chromosome': chromosomes,
        'start': starts,
        'end': ends
    }, index=genes)
)

print(f"Created dataset: {adata.n_obs} cells, {adata.n_vars} genes")
print(f"Cell types: {adata.obs['cell_type'].value_counts().to_dict()}")

# ============================================================================
# Step 2: Verify Gene Positions
# ============================================================================

print("\n" + "=" * 60)
print("Step 2: Verify Gene Positions")
print("=" * 60)

print("\nGene position annotation:")
print(adata.var.head())

# Check chromosome distribution
print("\nGenes per chromosome:")
print(adata.var['chromosome'].value_counts().sort_index())

# ============================================================================
# Step 3: Run CNV Inference
# ============================================================================

print("\n" + "=" * 60)
print("Step 3: Run CNV Inference")
print("=" * 60)

# Use immune cells as reference
run_infercnv_pipeline(
    adata,
    reference_key="cell_type",
    reference_cat=["T_cell", "B_cell", "Macrophage"],
    window_size=50,
    step=5,
    key_added="cnv",
    verbose=True
)

# Check results
print("\nCNV matrix shape:", adata.obsm["X_cnv"].shape)
print("Chromosome positions:", adata.uns["cnv"]["chr_pos"])

# ============================================================================
# Step 4: Cluster by CNV Profile
# ============================================================================

print("\n" + "=" * 60)
print("Step 4: Cluster by CNV Profile")
print("=" * 60)

cluster_by_cnv(adata, key="cnv", resolution=0.5)

print("\nCNV clusters:")
print(adata.obs["cnv_leiden"].value_counts())

# Compare with original annotations
print("\nComparison of CNV clusters vs cell types:")
comparison = pd.crosstab(adata.obs["cnv_leiden"], adata.obs["cell_type"])
print(comparison)

# ============================================================================
# Step 5: Identify CNV Regions
# ============================================================================

print("\n" + "=" * 60)
print("Step 5: Identify Altered CNV Regions")
print("=" * 60)

cnv_regions = identify_cnv_regions(
    adata,
    key="cnv",
    threshold=0.2,
    min_cells=10
)

if not cnv_regions.empty:
    print("\nSignificant CNV alterations:")
    print(cnv_regions)
else:
    print("\nNo significant alterations found (expected for simulated data)")

# ============================================================================
# Step 6: Summarize by Chromosome
# ============================================================================

print("\n" + "=" * 60)
print("Step 6: Summarize CNV by Chromosome and Cell Type")
print("=" * 60)

chr_summary = summarize_cnv_by_chromosome(
    adata,
    key="cnv",
    groupby="cell_type"
)

print("\nChromosome summary by cell type:")
print(chr_summary)

# ============================================================================
# Step 7: Export Results
# ============================================================================

print("\n" + "=" * 60)
print("Step 7: Export Results")
print("=" * 60)

output_dir = Path("cnv_results")
export_cnv_results(
    adata,
    output_dir=output_dir,
    key="cnv",
    prefix="example"
)

print(f"\nResults exported to: {output_dir.absolute()}")
print("Files created:")
for f in output_dir.iterdir():
    print(f"  - {f.name}")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "=" * 60)
print("Analysis Complete!")
print("=" * 60)

print("\nKey results:")
print(f"  - CNV matrix: {adata.obsm['X_cnv'].shape}")
print(f"  - CNV clusters: {adata.obs['cnv_leiden'].nunique()} clusters")
print(f"  - Output directory: {output_dir.absolute()}")

print("\nNext steps:")
print("  - Visualize with: cnv.pl.chromosome_heatmap(adata, groupby='cell_type')")
print("  - Explore tumor subclones by CNV profile")
print("  - Compare with known cancer alterations")
