#!/usr/bin/env python3
"""
Advanced Example: Comprehensive Scrublet Analysis

This example demonstrates advanced Scrublet features including:
- Custom threshold selection
- Visualization on embeddings
- Per-sample processing
- Multiple parameter comparisons
- Accessing detailed results

Requirements:
    - scrublet >=0.2.3
    - scanpy >=1.9.0
    - numpy, pandas, matplotlib
"""

import scrublet as scr
import scanpy as sc
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

print("=" * 70)
print("Scrublet Advanced Example")
print("=" * 70)

np.random.seed(42)

# ================================================================================
# PART 1: Create Example Data with Ground Truth
# ================================================================================

print("\n" + "=" * 70)
print("PART 1: Data Preparation")
print("=" * 70)

def create_synthetic_data(n_cells=1000, n_genes=2000, doublet_rate=0.08, seed=42):
    """Create synthetic data with known doublets."""
    np.random.seed(seed)

    n_doublets = int(n_cells * doublet_rate)
    n_singlets = n_cells - n_doublets

    # Create singlets
    singlet_counts = np.random.poisson(2, (n_singlets, n_genes))

    # Create doublets by combining random pairs
    doublet_counts = []
    for _ in range(n_doublets):
        i, j = np.random.choice(n_singlets, 2, replace=False)
        doublet = singlet_counts[i] + singlet_counts[j]
        doublet_counts.append(doublet)
    doublet_counts = np.array(doublet_counts)

    # Combine
    all_counts = np.vstack([singlet_counts, doublet_counts])

    # Create labels
    is_doublet = np.array([False] * n_singlets + [True] * n_doublets)

    # Shuffle
    shuffle_idx = np.random.permutation(n_cells)
    all_counts = all_counts[shuffle_idx]
    is_doublet = is_doublet[shuffle_idx]

    # Create AnnData
    adata = sc.AnnData(
        X=all_counts,
        obs=pd.DataFrame({
            'cell_type': np.where(is_doublet, 'doublet', 'singlet'),
            'is_doublet': is_doublet
        }, index=[f"cell_{i:04d}" for i in range(n_cells)]),
        var=pd.DataFrame(index=[f"GENE_{i:04d}" for i in range(n_genes)])
    )

    return adata

# Create data
adata = create_synthetic_data(n_cells=1000, n_genes=2000, doublet_rate=0.08)
print(f"\nCreated AnnData: {adata.n_obs} cells x {adata.n_vars} genes")
print(f"Ground truth doublets: {sum(adata.obs['is_doublet'])} ({100*sum(adata.obs['is_doublet'])/adata.n_obs:.1f}%)")

# ================================================================================
# PART 2: Standard Preprocessing for Visualization
# ================================================================================

print("\n" + "=" * 70)
print("PART 2: Preprocessing for Visualization")
print("=" * 70)

# Make a copy for preprocessing (Scrublet uses raw counts internally)
adata_pp = adata.copy()

sc.pp.filter_genes(adata_pp, min_cells=3)
sc.pp.normalize_total(adata_pp, target_sum=1e4)
sc.pp.log1p(adata_pp)
sc.pp.highly_variable_genes(adata_pp, n_top_genes=2000)
sc.pp.pca(adata_pp, n_comps=30)
sc.pp.neighbors(adata_pp)
sc.tl.umap(adata_pp)

print(f"Preprocessing complete")
print(f"  - HVGs: {sum(adata_pp.var.highly_variable)}")
print(f"  - PCs computed: 30")

# ================================================================================
# PART 3: Run Scrublet with Custom Parameters
# ================================================================================

print("\n" + "=" * 70)
print("PART 3: Scrublet Doublet Detection")
print("=" * 70)

# Calculate expected doublet rate
expected_rate = adata.n_obs / 1000 * 0.008
print(f"\nExpected doublet rate: {expected_rate:.3f}")

# Initialize Scrublet
scrub = scr.Scrublet(
    adata.X,
    expected_doublet_rate=expected_rate,
    sim_doublet_ratio=2.0,
    random_state=42
)

# Run with detailed parameters
doublet_scores, predicted_doublets = scrub.scrub_doublets(
    min_counts=2,
    min_cells=3,
    min_gene_variability_pctl=85,
    log_transform=False,
    mean_center=True,
    normalize_variance=True,
    n_prin_comps=30,
    synthetic_doublet_umi_subsampling=1.0,
    use_approx_neighbors=True,
    distance_metric='euclidean',
    get_doublet_neighbor_parents=False,
    verbose=True
)

print(f"\nDetection complete!")
print(f"  - Scrublet threshold: {scrub.threshold_:.3f}")
print(f"  - Predicted doublets: {sum(predicted_doublets)}")

# Add to main AnnData
adata.obs['doublet_score'] = doublet_scores
adata.obs['predicted_doublet'] = predicted_doublets

# ================================================================================
# PART 4: Compare with Ground Truth
# ================================================================================

print("\n" + "=" * 70)
print("PART 4: Performance Evaluation")
print("=" * 70)

# Confusion matrix
tp = sum((adata.obs['predicted_doublet'] == True) & (adata.obs['is_doublet'] == True))
fp = sum((adata.obs['predicted_doublet'] == True) & (adata.obs['is_doublet'] == False))
tn = sum((adata.obs['predicted_doublet'] == False) & (adata.obs['is_doublet'] == False))
fn = sum((adata.obs['predicted_doublet'] == False) & (adata.obs['is_doublet'] == True))

precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

print(f"\nConfusion Matrix:")
print(f"                 Predicted")
print(f"                 Doublet  Singlet")
print(f"Actual Doublet   {tp:6d}   {fn:6d}  (Recall: {recall:.3f})")
print(f"       Singlet   {fp:6d}   {tn:6d}  (Spec: {tn/(tn+fp):.3f})")

print(f"\nMetrics:")
print(f"  - Precision: {precision:.3f}")
print(f"  - Recall: {recall:.3f}")
print(f"  - F1 Score: {f1:.3f}")

# ================================================================================
# PART 5: Manual Threshold Selection
# ================================================================================

print("\n" + "=" * 70)
print("PART 5: Manual Threshold Selection")
print("=" * 70)

# Test multiple thresholds
thresholds = [0.1, 0.2, 0.25, 0.3, 0.4]
threshold_results = []

for thresh in thresholds:
    scrub.call_doublets(threshold=thresh, verbose=False)
    manual_pred = scrub.predicted_doublets_

    tp_t = sum((manual_pred == True) & (adata.obs['is_doublet'] == True))
    fp_t = sum((manual_pred == True) & (adata.obs['is_doublet'] == False))
    fn_t = sum((manual_pred == False) & (adata.obs['is_doublet'] == True))

    precision_t = tp_t / (tp_t + fp_t) if (tp_t + fp_t) > 0 else 0
    recall_t = tp_t / (tp_t + fn_t) if (tp_t + fn_t) > 0 else 0
    f1_t = 2 * precision_t * recall_t / (precision_t + recall_t) if (precision_t + recall_t) > 0 else 0

    threshold_results.append({
        'threshold': thresh,
        'predicted_doublets': sum(manual_pred),
        'precision': precision_t,
        'recall': recall_t,
        'f1': f1_t
    })

print("\nThreshold Comparison:")
print(f"{'Threshold':>10} {'Count':>8} {'Precision':>10} {'Recall':>8} {'F1':>8}")
print("-" * 55)
for r in threshold_results:
    print(f"{r['threshold']:>10.2f} {r['predicted_doublets']:>8d} {r['precision']:>10.3f} {r['recall']:>8.3f} {r['f1']:>8.3f}")

# Use auto threshold for subsequent analysis
scrub.call_doublets(threshold=None, verbose=False)
adata.obs['predicted_doublet'] = scrub.predicted_doublets_

# ================================================================================
# PART 6: Comprehensive Visualization
# ================================================================================

print("\n" + "=" * 70)
print("PART 6: Visualization")
print("=" * 70)

output_dir = "scrublet_output"
import os
os.makedirs(output_dir, exist_ok=True)

# 1. Histogram
print("\n1. Generating histogram...")
fig, axes = plt.subplots(1, 1, figsize=(8, 4))
scrub.plot_histogram()
plt.title('Scrublet Doublet Score Distribution')
plt.tight_layout()
plt.savefig(f'{output_dir}/histogram.png', dpi=150, bbox_inches='tight')
print(f"   Saved: {output_dir}/histogram.png")
plt.close()

# 2. UMAP colored by doublet scores
print("\n2. UMAP colored by doublet score...")
adata_pp.obs['doublet_score'] = doublet_scores
adata_pp.obs['predicted_doublet'] = predicted_doublets

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Doublet score
sc.pl.umap(adata_pp, color='doublet_score', cmap='RdYlBu_r',
           title='Doublet Score', show=False, ax=axes[0])
axes[0].set_xlabel('UMAP1')
axes[0].set_ylabel('UMAP2')

# Predicted doublet
sc.pl.umap(adata_pp, color='predicted_doublet',
           title='Predicted Doublet', show=False, ax=axes[1])
axes[1].set_xlabel('UMAP1')
axes[1].set_ylabel('UMAP2')

plt.tight_layout()
plt.savefig(f'{output_dir}/umap_doublets.png', dpi=150, bbox_inches='tight')
print(f"   Saved: {output_dir}/umap_doublets.png")
plt.close()

# 3. Ground truth comparison
print("\n3. Ground truth comparison...")
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

sc.pl.umap(adata_pp, color='is_doublet', title='Ground Truth Doublets',
           show=False, ax=axes[0])
axes[0].set_xlabel('UMAP1')
axes[0].set_ylabel('UMAP2')

sc.pl.umap(adata_pp, color='predicted_doublet', title='Scrublet Predictions',
           show=False, ax=axes[1])
axes[1].set_xlabel('UMAP1')
axes[1].set_ylabel('UMAP2')

plt.tight_layout()
plt.savefig(f'{output_dir}/umap_comparison.png', dpi=150, bbox_inches='tight')
print(f"   Saved: {output_dir}/umap_comparison.png")
plt.close()

# ================================================================================
# PART 7: Access Additional Attributes
# ================================================================================

print("\n" + "=" * 70)
print("PART 7: Additional Scrublet Attributes")
print("=" * 70)

print(f"\nScrublet Object Attributes:")
print(f"  - doublet_scores_obs_: shape {scrub.doublet_scores_obs_.shape}")
print(f"  - doublet_scores_sim_: shape {scrub.doublet_scores_sim_.shape}")
print(f"  - doublet_parents_: shape {scrub.doublet_parents_.shape}")
print(f"  - z_scores_: mean {np.mean(scrub.z_scores_):.3f}, std {np.std(scrub.z_scores_):.3f}")
print(f"  - threshold_: {scrub.threshold_:.3f}")
print(f"  - detected_doublet_rate_: {scrub.detected_doublet_rate_:.3f}")
print(f"  - overall_doublet_rate_: {scrub.overall_doublet_rate_:.3f}")

# ================================================================================
# PART 8: Export Results
# ================================================================================

print("\n" + "=" * 70)
print("PART 8: Exporting Results")
print("=" * 70)

# Export doublet scores
results_df = pd.DataFrame({
    'cell': adata.obs.index,
    'doublet_score': doublet_scores,
    'predicted_doublet': predicted_doublets,
    'ground_truth': adata.obs['is_doublet'].values
})
results_df.to_csv(f'{output_dir}/doublet_results.csv', index=False)
print(f"   Saved: {output_dir}/doublet_results.csv")

# Export filtered data
adata_filtered = adata[~adata.obs['predicted_doublet']].copy()
adata_filtered.write_h5ad(f'{output_dir}/filtered_data.h5ad')
print(f"   Saved: {output_dir}/filtered_data.h5ad")

# Export summary report
report = f"""
Scrublet Analysis Report
========================

Dataset Summary
---------------
Total cells: {adata.n_obs}
Genes: {adata.n_vars}
Ground truth doublets: {sum(adata.obs['is_doublet'])} ({100*sum(adata.obs['is_doublet'])/adata.n_obs:.1f}%)

Scrublet Parameters
-------------------
Expected doublet rate: {expected_rate:.3f}
Simulated doublet ratio: 2.0
Neighbors: auto
Principal components: 30

Results
-------
Predicted doublets: {sum(predicted_doublets)}
Scrublet threshold: {scrub.threshold_:.3f}
Detected doublet rate: {scrub.detected_doublet_rate_:.3f}
Overall doublet rate: {scrub.overall_doublet_rate_:.3f}

Performance (vs ground truth)
-----------------------------
Precision: {precision:.3f}
Recall: {recall:.3f}
F1 Score: {f1:.3f}

Cells retained after filtering: {adata_filtered.n_obs}
"""

with open(f'{output_dir}/report.txt', 'w') as f:
    f.write(report)
print(f"   Saved: {output_dir}/report.txt")

# ================================================================================
# Summary
# ================================================================================

print("\n" + "=" * 70)
print("Analysis Complete!")
print("=" * 70)

print(f"\nOutput files in {output_dir}/:")
print("  - doublet_results.csv (scores and predictions)")
print("  - filtered_data.h5ad (filtered AnnData)")
print("  - histogram.png (score distribution)")
print("  - umap_doublets.png (visualization)")
print("  - umap_comparison.png (ground truth vs predictions)")
print("  - report.txt (summary)")

print("\nNext steps:")
print("  1. Review histogram.png to verify threshold selection")
print("  2. Compare ground truth vs predictions in umap_comparison.png")
print("  3. Use filtered_data.h5ad for downstream analysis")
print("  4. Adjust threshold if detection rate differs from expected")
