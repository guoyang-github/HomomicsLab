"""Advanced example of FastCCC cell-cell communication analysis.

This example demonstrates advanced features including:
- Reference panel building
- Reference-based CCC inference
- Cauchy combination of multiple methods
- Visualization of results
- Comparison across conditions
"""

import sys
sys.path.append('../scripts/python')

import scanpy as sc
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from core_analysis import (
    run_fastccc,
    run_fastccc_cauchy_combined,
    analyze_celltype_specific_interactions,
    get_top_interactions,
    summarize_interactions_by_cellpair,
    run_fastccc_pipeline
)
from reference_builder import (
    build_reference_panel,
    infer_ccc_with_reference,
    get_reference_info,
    create_celltype_mapping
)
from utils import (
    check_lr_gene_overlap,
    get_database_info,
    filter_interactions,
    get_top_cell_pairs,
    prepare_anndata_for_fastccc,
    export_results_to_cellchat_format
)
from visualization import (
    plot_interaction_heatmap,
    plot_significant_interactions_bar,
    plot_interaction_network,
    plot_top_interactions_dot,
    plot_reference_comparison,
    plot_fastccc_summary
)

# Step 1: Load and prepare data
# -----------------------------
print("Loading data...")

# For this example, create synthetic data with known LR patterns
np.random.seed(42)
n_cells = 500
n_genes = 1000

# Create cell types
cell_types = ['CD4_T', 'CD8_T', 'B_cell', 'Monocyte', 'DC', 'NK']
labels = np.random.choice(cell_types, n_cells)

# Create AnnData
adata = sc.AnnData(
    X=np.random.poisson(2, (n_cells, n_genes)),
    obs=pd.DataFrame({
        'cell_type': labels,
        'condition': np.random.choice(['Control', 'Treatment'], n_cells)
    }, index=[f'cell_{i}' for i in range(n_cells)]),
    var=pd.DataFrame(index=[f'GENE_{i}' for i in range(n_genes)])
)

# Add some known LR genes with differential expression
lr_genes = {
    'CD40': ('B_cell', 'Monocyte'),      # B cell ligand
    'CD40LG': ('CD4_T', 'B_cell'),       # T cell ligand
    'CD28': ('CD4_T', 'DC'),             # T cell receptor
    'CD80': ('DC', 'CD4_T'),             # DC ligand
    'CD86': ('Monocyte', 'CD4_T'),       # Monocyte ligand
    'IL2': ('CD4_T', 'CD8_T'),           # T cell ligand
    'IL2RA': ('CD8_T', 'CD4_T'),         # T cell receptor
    'TNF': ('Monocyte', 'all'),          # Monocyte ligand
    'TNFRSF1A': ('all', 'Monocyte'),     # Multiple receptors
    'CXCL10': ('Monocyte', 'all'),       # Chemokine
    'CXCR3': ('all', 'CD4_T')            # Chemokine receptor
}

for gene, (source, target) in lr_genes.items():
    if gene not in adata.var_names:
        continue
    gene_idx = list(adata.var_names).index(gene)

    # Boost expression in specific cell types
    for i, ct in enumerate(adata.obs['cell_type']):
        if source == 'all' or ct == source:
            adata.X[i, gene_idx] = np.random.poisson(10)

# Ensure sparse matrix
if not hasattr(adata.X, 'toarray'):
    from scipy.sparse import csr_matrix
    adata.X = csr_matrix(adata.X)

print(f"Data shape: {adata.shape}")
print(f"Cell type distribution:")
print(adata.obs['cell_type'].value_counts())

# Step 2: Check database and gene overlap
# ---------------------------------------
print("\n" + "="*50)
print("Step 2: Database Information")
print("="*50)

# database_path = './cellphonedb_data'
# db_info = get_database_info(database_path)
# print(f"\nDatabase: {db_info['database_name']}")
# print(f"  Interactions: {db_info['n_interactions']}")
# print(f"  Ligands: {db_info['n_ligands']}")
# print(f"  Receptors: {db_info['n_receptors']}")

# overlap = check_lr_gene_overlap(adata, database_path)
# print(f"\nGene overlap:")
# print(f"  Data genes: {overlap['n_data_genes']}")
# print(f"  DB genes: {overlap['n_db_genes']}")
# print(f"  Overlap: {overlap['n_overlap']} ({overlap['overlap_fraction']*100:.1f}%)")

# Step 3: Prepare data for FastCCC
# --------------------------------
print("\n" + "="*50)
print("Step 3: Data Preparation")
print("="*50)

adata_prep = prepare_anndata_for_fastccc(
    adata,
    groupby='cell_type',
    min_cells=10
)

print(f"After preparation: {adata_prep.shape}")
print(f"Cell types retained: {adata_prep.obs['cell_type'].nunique()}")

# Step 4: Run FastCCC with Cauchy combination
# -------------------------------------------
print("\n" + "="*50)
print("Step 4: FastCCC Analysis with Cauchy Combination")
print("="*50)

# This would run the actual analysis
# results = run_fastccc_cauchy_combined(
#     adata_prep,
#     database_file_path=database_path,
#     groupby='cell_type',
#     save_path='./fastccc_cauchy_results',
#     single_unit_summary_list=['Mean', 'Median', 'Q3'],
#     complex_aggregation_list=['Minimum', 'Average'],
#     lr_combination_list=['Arithmetic', 'Geometric'],
#     min_percentile=0.1,
#     use_deg=False,
#     verbose=True
# )

# Create mock results for demonstration
print("Creating mock results for demonstration...")
n_interactions = 200
cell_pairs = [f"{s}|{t}" for s in adata_prep.obs['cell_type'].unique()
              for t in adata_prep.obs['cell_type'].unique()]

results = {
    'interactions_strength': pd.DataFrame(
        np.random.gamma(2, 0.5, (len(cell_pairs), n_interactions)),
        index=cell_pairs,
        columns=[f'INT_{i}' for i in range(n_interactions)]
    ),
    'pvals': pd.DataFrame(
        np.random.beta(0.5, 5, (len(cell_pairs), n_interactions)),
        index=cell_pairs,
        columns=[f'INT_{i}' for i in range(n_interactions)]
    ),
    'percents_analysis': pd.DataFrame(
        np.random.random((len(cell_pairs), n_interactions)) > 0.3,
        index=cell_pairs,
        columns=[f'INT_{i}' for i in range(n_interactions)]
    )
}

print(f"Results generated:")
print(f"  Cell pairs: {results['interactions_strength'].shape[0]}")
print(f"  Interactions: {results['interactions_strength'].shape[1]}")

# Step 5: Analyze specific cell type pairs
# ----------------------------------------
print("\n" + "="*50)
print("Step 5: Cell Type Pair Analysis")
print("="*50)

# Analyze T cell -> B cell interactions
source_ct = 'CD4_T'
target_ct = 'B_cell'

pair_results = analyze_celltype_specific_interactions(
    results['pvals'],
    results['interactions_strength'],
    source_celltype=source_ct,
    target_celltype=target_ct,
    pval_threshold=0.05
)

print(f"\nInteractions from {source_ct} to {target_ct}:")
print(f"  Total tested: {len(pair_results)}")
print(f"  Significant: {pair_results['significant'].sum()}")
print("\nTop 5 by strength:")
print(pair_results.head(5)[['strength', 'pvalue', 'significant']])

# Step 6: Get top interactions
# ----------------------------
print("\n" + "="*50)
print("Step 6: Top Interactions")
print("="*50)

top_interactions = get_top_interactions(
    results['interactions_strength'],
    results['pvals'],
    n_top=10,
    by='strength'
)

print("\nTop 10 interactions by strength:")
for _, row in top_interactions.iterrows():
    print(f"  {row['cell_pair']}: {row['interaction']} "
          f"(strength={row['strength']:.3f}, p={row['pvalue']:.4f})")

# Step 7: Summarize by cell pair
# ------------------------------
print("\n" + "="*50)
print("Step 7: Summary by Cell Pair")
print("="*50)

pair_summary = summarize_interactions_by_cellpair(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05
)

print("\nTop cell pairs by significant interactions:")
print(pair_summary.head(10)[['cell_pair', 'n_significant', 'significance_rate']].to_string())

# Step 8: Visualization
# ---------------------
print("\n" + "="*50)
print("Step 8: Generating Visualizations")
print("="*50)

output_dir = './fastccc_plots'
Path(output_dir).mkdir(exist_ok=True)

# Interaction heatmap
print("Creating interaction heatmap...")
fig = plot_interaction_heatmap(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05,
    use_strength=True,
    save_path=f'{output_dir}/interaction_heatmap.png'
)
plt.close()

# Significant interactions bar plot
print("Creating bar plot...")
fig = plot_significant_interactions_bar(
    results['pvals'],
    pval_threshold=0.05,
    top_n=15,
    save_path=f'{output_dir}/significant_interactions.png'
)
plt.close()

# Network plot
print("Creating network plot...")
from utils import create_interaction_network_data
node_df, edge_df = create_interaction_network_data(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05
)
fig = plot_interaction_network(
    node_df, edge_df,
    save_path=f'{output_dir}/interaction_network.png'
)
plt.close()

print(f"\nPlots saved to {output_dir}/")

# Step 9: Reference panel building (optional)
# -------------------------------------------
print("\n" + "="*50)
print("Step 9: Reference Panel Building (Example)")
print("="*50)

# Split data for reference building
reference_data = adata_prep[adata_prep.obs['condition'] == 'Control'].copy()
query_data = adata_prep[adata_prep.obs['condition'] == 'Treatment'].copy()

print(f"Reference data: {reference_data.shape}")
print(f"Query data: {query_data.shape}")

# Build reference panel (would run actual code)
# ref_path = build_reference_panel(
#     reference_data,
#     database_file_path=database_path,
#     reference_name='PBMC_reference',
#     save_path='./reference_panels',
#     groupby='cell_type',
#     min_percentile=0.1
# )

# Step 10: Reference-based inference (optional)
# ---------------------------------------------
print("\n" + "="*50)
print("Step 10: Reference-based Inference (Example)")
print("="*50)

# Run inference (would run actual code)
# infer_results = infer_ccc_with_reference(
#     query_data,
#     database_file_path=database_path,
#     reference_path=ref_path,
#     save_path='./reference_results',
#     groupby='cell_type'
# )

# Create mock inference results
infer_results = pd.DataFrame({
    'sender|receiver': ['CD4_T|B_cell', 'Monocyte|CD4_T', 'DC|CD8_T'],
    'ligand': ['CD40LG', 'IL6', 'IL12A'],
    'receptor': ['CD40', 'IL6R', 'IL12RB1'],
    'comm_score': [0.8, 0.6, 0.7],
    'is_significant': [True, True, False],
    'is_significant_ref': [True, False, True],
    'trend_vs_ref': ['Both Sig', 'Up', 'Down']
})

print(f"Inference results shape: {infer_results.shape}")
print("\nSample results:")
print(infer_results.head())

# Plot reference comparison
print("\nCreating reference comparison plot...")
fig = plot_reference_comparison(
    infer_results,
    save_path=f'{output_dir}/reference_comparison.png'
)
plt.close()

# Step 11: Generate summary report
# --------------------------------
print("\n" + "="*50)
print("Step 11: Summary Report")
print("="*50)

print(f"""
FastCCC Analysis Report
=======================

Dataset:
  - Cells: {adata.n_obs}
  - Genes: {adata.n_vars}
  - Cell types: {', '.join(adata.obs['cell_type'].unique())}
  - Conditions: {', '.join(adata.obs['condition'].unique())}

Analysis Results:
  - Cell pairs analyzed: {results['interactions_strength'].shape[0]}
  - Interactions tested: {results['interactions_strength'].shape[1]}
  - Significant interactions: {(results['pvals'] < 0.05).sum().sum()}

Top Cell Pairs:
  - {pair_summary.iloc[0]['cell_pair']}: {pair_summary.iloc[0]['n_significant']} sig. interactions
  - {pair_summary.iloc[1]['cell_pair']}: {pair_summary.iloc[1]['n_significant']} sig. interactions
  - {pair_summary.iloc[2]['cell_pair']}: {pair_summary.iloc[2]['n_significant']} sig. interactions

Output Files:
  - Plots: {output_dir}/*.png
  - Results: ./fastccc_cauchy_results/

Next Steps:
  1. Explore specific signaling pathways
  2. Perform differential CCC analysis between conditions
  3. Integrate with spatial transcriptomics data
  4. Validate key interactions experimentally
""")

print("\nAnalysis complete!")
