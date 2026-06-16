#!/usr/bin/env python
"""
Minimal Example: LIANA+ Cell-Cell Communication Analysis

Basic workflow for running LIANA+ rank aggregate on single-cell data.
"""

import scanpy as sc
import liana as ln

# Import skill wrappers
import sys
sys.path.insert(0, '../scripts/python')
from core_analysis import run_rank_aggregate, get_top_interactions, export_results
from utils import validate_anndata

# ==============================================================================
# Load Data
# ==============================================================================

adata = sc.read_h5ad("your_annotated_data.h5ad")
# Or: adata = sc.datasets.pbmc3k_processed()

print(f"Data shape: {adata.shape}")
print(f"Cell types: {adata.obs['cell_type'].value_counts()}")

validate_anndata(adata, require_cell_types=True)

# ==============================================================================
# Run LIANA+ Analysis
# ==============================================================================

run_rank_aggregate(
    adata,
    groupby='cell_type',
    resource_name='consensus',
    expr_prop=0.1,
    min_cells=5,
    aggregate_method='rra',
    n_perms=100,
    seed=42,
    key_added='liana_res',
    inplace=True,
    verbose=True
)

liana_res = adata.uns['liana_res']
print(f"\nFound {len(liana_res)} interactions")
print(f"Columns: {list(liana_res.columns)}")

# ==============================================================================
# Explore Results
# ==============================================================================

# Top interactions
top20 = get_top_interactions(liana_res, n=20, by='magnitude_rank')
print("\nTop 20 Interactions:")
print(top20[['source', 'target', 'ligand', 'receptor', 'magnitude_rank', 'specificity_rank']])

# Filter by cell types
b_to_t = get_top_interactions(
    liana_res,
    source_cells=['B_cell'],
    target_cells=['T_cell'],
    n=10
)
print("\nB cell -> T cell interactions:")
print(b_to_t[['ligand', 'receptor', 'magnitude_rank']])

# ==============================================================================
# Visualization (Native liana plotting)
# ==============================================================================

# Dot plot
ln.pl.dotplot(
    adata,
    colour='magnitude_rank',
    size='specificity_rank',
    top_n=30,
    orderby='magnitude_rank',
    orderby_ascending=True
)

# Tile plot
ln.pl.tileplot(
    adata,
    fill='means',
    label='props',
    top_n=20,
    orderby='magnitude_rank',
    orderby_ascending=True
)

# Circle plot
ln.pl.circle_plot(
    adata,
    groupby='cell_type',
    score_key='magnitude_rank',
    inverse_score=True,
    top_n=20
)

# ==============================================================================
# Export Results
# ==============================================================================

export_results(liana_res, 'liana_results.csv', format='csv')
adata.write_h5ad('adata_with_liana.h5ad')

print("\nAnalysis complete!")
