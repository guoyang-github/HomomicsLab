"""Minimal example of FastCCC cell-cell communication analysis.

This example demonstrates the most basic usage of FastCCC on a small dataset.
"""

import sys
sys.path.append('../scripts/python')

import scanpy as sc
import pandas as pd
import numpy as np
from core_analysis import run_fastccc, get_significant_interactions
from utils import check_lr_gene_overlap, summarize_fastccc_results

# Step 1: Create or load test data
# --------------------------------
print("Creating test data...")

np.random.seed(42)
n_cells = 200
n_genes = 500

# Create cell types
cell_types = ['T_cell', 'B_cell', 'Monocyte', 'DC']
labels = np.random.choice(cell_types, n_cells)

# Create AnnData
adata = sc.AnnData(
    X=np.random.poisson(2, (n_cells, n_genes)),
    obs=pd.DataFrame({'cell_type': labels}, index=[f'cell_{i}' for i in range(n_cells)]),
    var=pd.DataFrame(index=[f'GENE_{i}' for i in range(n_genes)])
)

# Add some ligand/receptor genes
lr_genes = ['CD40', 'CD40LG', 'CD28', 'CD80', 'CD86', 'IL2', 'IL2RA', 'TNF', 'TNFRSF1A']
for i, gene in enumerate(lr_genes):
    if i < n_genes:
        adata.var_names = adata.var_names.tolist()
        adata.var_names[i] = gene
        adata.var_names = pd.Index(adata.var_names)

print(f"Data shape: {adata.shape}")
print(f"Cell types: {adata.obs['cell_type'].value_counts()}")

# Step 2: Check gene overlap with database
# ----------------------------------------
print("\nChecking gene overlap...")
# Note: Replace with actual database path
database_path = './cellphonedb_data'

# overlap = check_lr_gene_overlap(adata, database_path)
# print(f"Gene overlap: {overlap['overlap_fraction']*100:.1f}%")

# Step 3: Run FastCCC
# -------------------
print("\nRunning FastCCC analysis...")
# Note: This requires FastCCC to be installed with a valid database

# results = run_fastccc(
#     adata,
#     database_file_path=database_path,
#     groupby='cell_type',
#     save_path='./fastccc_results',
#     single_unit_summary='Mean',
#     complex_aggregation='Minimum',
#     lr_combination='Arithmetic',
#     min_percentile=0.1,
#     verbose=True
# )

# For demonstration, create mock results
print("Creating mock results for demonstration...")
n_interactions = 100
cell_pairs = [f"{s}|{t}" for s in cell_types for t in cell_types]

results = {
    'interactions_strength': pd.DataFrame(
        np.random.gamma(2, 0.5, (len(cell_pairs), n_interactions)),
        index=cell_pairs,
        columns=[f'LIG{i}_REC{i}' for i in range(n_interactions)]
    ),
    'pvals': pd.DataFrame(
        np.random.beta(0.5, 5, (len(cell_pairs), n_interactions)),
        index=cell_pairs,
        columns=[f'LIG{i}_REC{i}' for i in range(n_interactions)]
    ),
    'percents_analysis': pd.DataFrame(
        np.random.random((len(cell_pairs), n_interactions)) > 0.3,
        index=cell_pairs,
        columns=[f'LIG{i}_REC{i}' for i in range(n_interactions)]
    )
}

print(f"FastCCC results generated!")
print(f"  Cell pairs: {results['interactions_strength'].shape[0]}")
print(f"  Interactions: {results['interactions_strength'].shape[1]}")

# Step 4: Summarize results
# -------------------------
print("\nSummarizing results...")
summary = summarize_fastccc_results(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05
)

print(f"Total cell pairs: {summary['n_cell_pairs']}")
print(f"Total interactions: {summary['n_interactions']}")
print(f"Significant interactions: {summary['n_significant']}")
print(f"Significance rate: {summary['significance_rate']*100:.2f}%")

# Step 5: Get top interactions
# ----------------------------
print("\nTop cell pairs by significant interactions:")
sig_by_pair = summary['significant_by_cellpair']
top_pairs = sorted(sig_by_pair.items(), key=lambda x: x[1], reverse=True)[:5]
for pair, count in top_pairs:
    print(f"  {pair}: {count}")

# Step 6: Export results
# ----------------------
# results['pvals'].to_csv('pvals.csv')
# results['interactions_strength'].to_csv('interactions_strength.csv')

print("\nFastCCC analysis complete!")
