"""Minimal example of COMPASS metabolic flux analysis.

This example demonstrates the most basic usage of COMPASS on a small
dataset. For larger datasets, consider using microclustering.
"""

import sys
sys.path.append('../scripts/python')

import scanpy as sc
import pandas as pd
from core_analysis import run_compass, add_compass_results_to_adata
from utils import create_test_data

# Step 1: Create or load test data
# --------------------------------
print("Creating test data...")
adata = create_test_data(n_cells=50, n_genes=500, n_cell_types=3)
print(f"Data shape: {adata.shape}")
print(f"Cell types: {adata.obs['cell_type'].value_counts()}")

# Step 2: Run COMPASS
# -------------------
print("\nRunning COMPASS analysis...")
# Note: This requires COMPASS to be installed with CPLEX
# For actual use, set output_dir to a valid path

compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=2,
    lambda_param=0.0,  # No penalty sharing for this small dataset
    calc_metabolites=True,
    verbose=True
)

# Step 3: Access results
# ----------------------
print("\nCOMPASS Results:")
if 'reaction_scores' in compass_results:
    print(f"  Reaction scores shape: {compass_results['reaction_scores'].shape}")
    print(f"  Top 5 reactions by mean score:")
    top_rxns = compass_results['reaction_scores'].mean(axis=1).nlargest(5)
    for rxn, score in top_rxns.items():
        print(f"    {rxn}: {score:.3f}")

if 'uptake_scores' in compass_results:
    print(f"\n  Uptake scores shape: {compass_results['uptake_scores'].shape}")

# Step 4: Add results to AnnData
# ------------------------------
adata = add_compass_results_to_adata(adata, compass_results)

print("\nCOMPASS results added to AnnData!")
print(f"New obsm keys: {list(adata.obsm.keys())}")

# Optional: Save results
# ----------------------
# adata.write('compass_results.h5ad')
# compass_results['reaction_scores'].to_csv('reaction_scores.csv')
