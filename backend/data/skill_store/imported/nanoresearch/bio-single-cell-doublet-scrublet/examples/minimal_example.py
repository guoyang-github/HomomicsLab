#!/usr/bin/env python3
"""
Minimal Example: Scrublet Doublet Detection

This example demonstrates the basic workflow for detecting doublets
using Scrublet on single-cell RNA-seq data.

Requirements:
    - scrublet >=0.2.3
    - scanpy >=1.9.0
    - numpy
    - pandas
"""

import scrublet as scr
import scanpy as sc
import numpy as np
import pandas as pd

print("=" * 60)
print("Scrublet Minimal Example")
print("=" * 60)

# ================================================================================
# PART 1: Create Example Data
# ================================================================================

print("\n1. Creating example data...")
np.random.seed(42)

# Create synthetic scRNA-seq data (500 cells, 1000 genes)
n_cells = 500
n_genes = 1000

# Raw count matrix (Poisson-distributed)
counts = np.random.poisson(2, (n_cells, n_genes))

# Create AnnData object
adata = sc.AnnData(
    X=counts,
    obs=pd.DataFrame(index=[f"cell_{i:03d}" for i in range(n_cells)]),
    var=pd.DataFrame(index=[f"GENE_{i:04d}" for i in range(n_genes)])
)

print(f"   Created AnnData: {adata.n_obs} cells x {adata.n_vars} genes")
print(f"   Data type: {type(adata.X)}")

# ================================================================================
# PART 2: Initialize Scrublet
# ================================================================================

print("\n2. Initializing Scrublet...")

# Calculate expected doublet rate (~0.8% per 1000 cells)
expected_rate = n_cells / 1000 * 0.008
print(f"   Expected doublet rate: {expected_rate:.3f} ({expected_rate*100:.1f}%)")

# Initialize Scrublet with raw counts
scrub = scr.Scrublet(
    adata.X,
    expected_doublet_rate=expected_rate,
    sim_doublet_ratio=2.0,  # Simulate 2x doublets per observed cell
    random_state=42
)

print(f"   Scrublet initialized")
print(f"   Simulated doublets: {scrub._sim_doublet_ratio} x {n_cells} = {int(scrub._sim_doublet_ratio * n_cells)}")

# ================================================================================
# PART 3: Run Doublet Detection
# ================================================================================

print("\n3. Running doublet detection...")

# Run the complete doublet detection pipeline
doublet_scores, predicted_doublets = scrub.scrub_doublets(
    min_counts=2,                      # Min counts for gene filtering
    min_cells=3,                       # Min cells for gene filtering
    min_gene_variability_pctl=85,      # Keep top 85% variable genes
    n_prin_comps=30,                   # Number of PCs
    synthetic_doublet_umi_subsampling=1.0,  # No subsampling
    use_approx_neighbors=True,         # Use approximate NN for speed
    verbose=False
)

print(f"   Detection complete!")
print(f"   Scrublet threshold: {scrub.threshold_:.3f}")
print(f"   Predicted doublets: {sum(predicted_doublets)} ({100*sum(predicted_doublets)/len(predicted_doublets):.1f}%)")

# ================================================================================
# PART 4: Add Results to AnnData
# ================================================================================

print("\n4. Adding results to AnnData...")

# Add doublet scores and predictions
adata.obs['doublet_score'] = doublet_scores
adata.obs['predicted_doublet'] = predicted_doublets

# Display results
print("\n   First 10 cells:")
print(adata.obs[['doublet_score', 'predicted_doublet']].head(10))

# Summary statistics
print(f"\n   Doublet score statistics:")
print(f"   - Mean: {np.mean(doublet_scores):.3f}")
print(f"   - Median: {np.median(doublet_scores):.3f}")
print(f"   - Min: {np.min(doublet_scores):.3f}")
print(f"   - Max: {np.max(doublet_scores):.3f}")

# ================================================================================
# PART 5: Filter Doublets
# ================================================================================

print("\n5. Filtering doublets...")

print(f"   Cells before filtering: {adata.n_obs}")

# Filter out predicted doublets
adata_filtered = adata[~adata.obs['predicted_doublet']].copy()

print(f"   Cells after filtering: {adata_filtered.n_obs}")
print(f"   Removed: {adata.n_obs - adata_filtered.n_obs} doublets")

# ================================================================================
# PART 6: Visualization (Optional)
# ================================================================================

print("\n6. Generating histogram...")

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt

    # Plot histogram of doublet scores
    scrub.plot_histogram()
    plt.savefig('doublet_histogram.png', dpi=150, bbox_inches='tight')
    print("   Saved: doublet_histogram.png")
    plt.close()

except ImportError:
    print("   matplotlib not available, skipping visualization")

# ================================================================================
# Summary
# ================================================================================

print("\n" + "=" * 60)
print("Analysis Complete!")
print("=" * 60)

print(f"\nResults Summary:")
print(f"  - Total cells analyzed: {n_cells}")
print(f"  - Predicted doublets: {sum(predicted_doublets)} ({100*sum(predicted_doublets)/len(predicted_doublets):.1f}%)")
print(f"  - Doublet threshold: {scrub.threshold_:.3f}")
print(f"  - Cells retained: {adata_filtered.n_obs}")

print("\nNext steps:")
print("  1. Continue analysis with filtered data: adata_filtered")
print("  2. Adjust threshold if needed: scrub.call_doublets(threshold=0.3)")
print("  3. Visualize on UMAP after standard preprocessing")
