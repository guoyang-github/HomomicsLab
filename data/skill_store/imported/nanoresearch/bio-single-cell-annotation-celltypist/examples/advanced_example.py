"""Advanced Example: CellTypist Comprehensive Analysis
======================================================

Advanced workflow demonstrating:
- Model selection and comparison
- Majority voting with custom over-clustering
- Confidence filtering and visualization
- Multi-sample analysis

Reference: Domínguez Conde et al., Science 2022
"""

import os
import sys
import numpy as np
import pandas as pd
import scanpy as sc
import celltypist

# Import wrapper functions
sys.path.append('../scripts/python')
from core_analysis import (
    validate_celltypist_input,
    annotate_cells,
    add_predictions_to_adata,
    run_celltypist_annotation,
    filter_by_confidence,
    compare_models,
)
from visualization import (
    plot_confidence_distribution,
    plot_celltype_proportions,
    plot_prediction_heatmap,
    plot_annotation_summary
)
from utils import (
    prepare_data_for_celltypist,
    recommend_model,
    summarize_annotations,
    export_annotations,
    check_gene_overlap,
    create_annotation_report
)

print("=" * 60)
print("CellTypist Advanced Example")
print("=" * 60)

# -----------------------------------------------------------------------------
# Step 1: Create comprehensive test data
# -----------------------------------------------------------------------------
print("\n[Step 1] Creating test data with multiple samples...")

np.random.seed(42)
n_cells = 2000
n_genes = 3000

adata = sc.AnnData(
    X=np.random.lognormal(3, 1, (n_cells, n_genes)),
    obs=pd.DataFrame({
        'sample': np.random.choice(['Sample_A', 'Sample_B', 'Sample_C', 'Sample_D'], n_cells),
        'condition': np.random.choice(['Control', 'Treatment'], n_cells),
        'batch': np.random.choice(['Batch1', 'Batch2'], n_cells)
    }, index=[f"cell_{i}" for i in range(n_cells)]),
    var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)])
)

# Normalize
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# Compute PCA and clustering for majority voting
sc.pp.highly_variable_genes(adata, n_top_genes=2000)
sc.pp.pca(adata, use_highly_variable=True)
sc.pp.neighbors(adata)
sc.tl.leiden(adata, resolution=0.5)

print(f"Created data: {adata.n_obs} cells x {adata.n_vars} genes")
print(f"Samples: {adata.obs['sample'].unique().tolist()}")
print(f"Clusters: {adata.obs['leiden'].nunique()} Leiden clusters")

# -----------------------------------------------------------------------------
# Step 2: Model selection
# -----------------------------------------------------------------------------
print("\n[Step 2] Model selection...")

recommended = recommend_model(tissue='immune', species='human', resolution='low')
print(f"Recommended model: {recommended}")

# -----------------------------------------------------------------------------
# Step 3: Check gene overlap with model (will auto-download if needed)
# -----------------------------------------------------------------------------
print("\n[Step 3] Checking gene overlap with model...")

# NOTE: With random gene names, overlap will be 0%. In practice, use real data.
try:
    overlap_stats = check_gene_overlap(adata, recommended)
    print(f"  Overlap: {overlap_stats['overlap_fraction']*100:.1f}%")
except Exception as e:
    print(f"  (Expected low overlap with random genes: {e})")

# -----------------------------------------------------------------------------
# Step 4: Run annotation with different settings (mock for demo)
# -----------------------------------------------------------------------------
print("\n[Step 4] Simulating annotation results...")

# In practice:
#   predictions = celltypist.annotate(adata, model=recommended,
#                                     majority_voting=True, over_clustering='leiden')
#   adata = predictions.to_adata(prefix='celltypist_')

# Mock predictions for demonstration
adata.obs['celltypist_predicted_labels'] = np.random.choice(
    ['CD4 T cell', 'CD8 T cell', 'B cell', 'Monocyte', 'NK cell', 'DC'],
    adata.n_obs
)
adata.obs['celltypist_majority_voting'] = np.random.choice(
    ['CD4 T cell', 'CD8 T cell', 'B cell', 'Monocyte', 'NK cell', 'DC'],
    adata.n_obs
)
adata.obs['celltypist_conf_score'] = np.random.beta(8, 1.5, adata.n_obs)
adata.obs['celltypist_label'] = adata.obs['celltypist_majority_voting']

print("  Annotation complete (mock data)")

# -----------------------------------------------------------------------------
# Step 5: Confidence filtering
# -----------------------------------------------------------------------------
print("\n[Step 5] Filtering by confidence...")

adata = filter_by_confidence(adata, threshold=0.5)
n_unassigned = (adata.obs['celltypist_label_filtered'] == 'Unassigned').sum()
print(f"  {n_unassigned} cells marked as Unassigned")

# -----------------------------------------------------------------------------
# Step 6: Summarize and compare across samples
# -----------------------------------------------------------------------------
print("\n[Step 6] Summarizing annotations...")

summary = summarize_annotations(adata)
print("\nCell Type Summary:")
print(summary.to_string())

print("\nCell type proportions by condition:")
props = adata.obs.groupby('condition')['celltypist_label'].value_counts(normalize=True)
print(props)

# -----------------------------------------------------------------------------
# Step 7: Visualization
# -----------------------------------------------------------------------------
print("\n[Step 7] Creating visualizations...")

output_dir = './celltypist_plots'
os.makedirs(output_dir, exist_ok=True)

# Summary plot
print("  Creating summary plot...")
plot_annotation_summary(adata, output_dir=output_dir)

# Confidence distribution
print("  Creating confidence distribution plot...")
plot_confidence_distribution(
    adata,
    save=f'{output_dir}/confidence_distribution.pdf'
)

# Cell type proportions by condition
print("  Creating cell type proportion plot...")
plot_celltype_proportions(
    adata,
    groupby='condition',
    save=f'{output_dir}/celltype_proportions.pdf'
)

# Prediction heatmap (predictions vs clusters)
print("  Creating prediction heatmap...")
plot_prediction_heatmap(
    adata,
    cluster_col='leiden',
    save=f'{output_dir}/prediction_heatmap.pdf'
)

# -----------------------------------------------------------------------------
# Step 8: Export results
# -----------------------------------------------------------------------------
print("\n[Step 8] Exporting results...")

export_annotations(adata, output_file='advanced_annotation_results.csv')

report = create_annotation_report(
    adata,
    model_name='Immune_All_Low.pkl',
    output_file='advanced_annotation_report.txt'
)

adata.write('annotated_data.h5ad')
print("  Saved: annotated_data.h5ad")

# -----------------------------------------------------------------------------
# Step 9: Model comparison example
# -----------------------------------------------------------------------------
print("\n[Step 9] Model comparison...")

print("""
To compare multiple models:

    models = ['Immune_All_Low.pkl', 'Immune_All_High.pkl']
    results_df = compare_models(adata, models, majority_voting=True)
    print(results_df)

This annotates the data with each model and reports cell type counts.
""")

print("\n" + "=" * 60)
print("Advanced example complete!")
print("=" * 60)
