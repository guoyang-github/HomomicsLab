#!/usr/bin/env python
"""
Advanced Example: LIANA+ Cell-Cell Communication Analysis

Demonstrates:
- Multi-method comparison
- Spatial CCC analysis (bivariate, inflow, MISTy)
- Cross-condition comparison
- Native liana visualization
"""

import scanpy as sc
import pandas as pd
import liana as ln

import sys
sys.path.insert(0, '../scripts/python')
from core_analysis import (
    run_rank_aggregate, run_individual_method,
    get_top_interactions, summarize_by_cell_pair, export_results
)
from utils import validate_anndata, filter_cell_types, get_interaction_matrix

# ==============================================================================
# Example 1: Method Comparison
# ==============================================================================

print("=" * 60)
print("Example 1: Comparing Multiple CCC Methods")
print("=" * 60)

adata = sc.read_h5ad("your_data.h5ad")
validate_anndata(adata, groupby='cell_type')

# Run individual methods
methods = ['cellphonedb', 'cellchat', 'connectome', 'natmi']
for method in methods:
    run_individual_method(
        adata,
        method=method,
        groupby='cell_type',
        resource_name='consensus',
        expr_prop=0.1,
        key_added=f'liana_{method}',
        verbose=True
    )

# Find common interactions across all methods
interaction_sets = [
    set(adata.uns[f'liana_{m}']['interaction_key'])
    for m in methods
]
common = set.intersection(*interaction_sets)
print(f"\nCommon interactions across all methods: {len(common)}")

# Run rank aggregate for consensus
run_rank_aggregate(
    adata,
    groupby='cell_type',
    resource_name='consensus',
    aggregate_method='rra',
    key_added='liana_consensus',
    verbose=True
)

# ==============================================================================
# Example 2: Resource Selection
# ==============================================================================

print("\n" + "=" * 60)
print("Example 2: Working with LR Resources")
print("=" * 60)

ln.rs.show_resources()

# Check coverage
resource = ln.rs.select_resource('consensus')
genes_in_data = set(adata.var_names)
resource_genes = set(resource['ligand']) | set(resource['receptor'])
coverage = len(resource_genes & genes_in_data) / len(resource_genes)
print(f"Resource coverage: {coverage:.1%}")

# ==============================================================================
# Example 3: Spatial CCC — Bivariate (Visium)
# ==============================================================================

print("\n" + "=" * 60)
print("Example 3: Spatial Bivariate Analysis (Visium)")
print("=" * 60)

spatial_adata = sc.read_h5ad("your_visium_data.h5ad")
validate_anndata(spatial_adata, groupby='cell_type')

# Ensure spatial coordinates exist
assert 'spatial' in spatial_adata.obsm, "spatial coordinates missing"

# Step 1: Compute spatial neighbors (prerequisite)
import squidpy as sq
sq.gr.spatial_neighbors(spatial_adata, coord_type="grid", n_neighs=6)

# Step 2: Run bivariate analysis (returns new AnnData)
lrdata = ln.method.bivariate(
    spatial_adata,
    local_name='morans',
    global_name=['morans', 'lee'],
    resource_name='consensus',
    connectivity_key='spatial_connectivities',
    n_perms=100,
    use_raw=False
)

# Step 3: Compute global specificity
ln.mt.compute_global_specificity(
    lrdata,
    groupby='cell_type',
    use_raw=False,
    uns_key='global_interactions'
)

global_res = lrdata.uns['global_interactions']

# ==============================================================================
# Example 4: Spatial CCC — Inflow (Xenium/CosMx)
# ==============================================================================

print("\n" + "=" * 60)
print("Example 4: Spatial Inflow Analysis (Single-Cell Resolution)")
print("=" * "*60")

sc_adata = sc.read_h5ad("your_xenium_data.h5ad")
validate_anndata(sc_adata, groupby='cell_type')

# Step 1: Compute spatial neighbors
ln.ut.spatial_neighbors(sc_adata, bandwidth=50, spatial_key='spatial')

# Step 2: Load resource and run inflow
resource = ln.rs.select_resource('consensus')
lrdata = ln.mt.inflow(
    sc_adata,
    groupby='cell_type',
    resource=resource,
    use_raw=False
)

# Step 3: Compute global specificity
ln.mt.compute_global_specificity(
    lrdata,
    groupby='cell_type',
    use_raw=False,
    uns_key='global_interactions'
)

# Visualize
ln.pl.dotplot(
    lrdata,
    colour='lr_mean',
    size='pval',
    uns_key='global_interactions',
    inverse_size=True
)

# ==============================================================================
# Example 5: MISTy Multi-View Spatial Analysis
# ==============================================================================

print("\n" + "=" * 60)
print("Example 5: MISTy Multi-View Analysis")
print("=" * 60)

misty = ln.method.lrMistyData(
    spatial_adata,
    resource_name='consensus',
    spatial_key='spatial',
    bandwidth=100,
    kernel='misty_rbf'
)
misty = misty.fit(n_neighbors=10)
misty.plot_target_metrics()
misty.plot_interactions()
misty.plot_contribution()

# ==============================================================================
# Example 6: Cross-Condition Comparison
# ==============================================================================

print("\n" + "=" * 60)
print("Example 6: Comparing Conditions")
print("=" * 60)

# Approach 1: Run per-condition and compare
conditions = {}
for cond in ['control', 'disease']:
    adata_cond = adata[adata.obs['condition'] == cond].copy()
    run_rank_aggregate(adata_cond, groupby='cell_type', inplace=True)
    conditions[cond] = adata_cond.uns['liana_res']

# Find condition-specific interactions
common = set(conditions['control']['interaction_key']).intersection(
    set(conditions['disease']['interaction_key'])
)
disease_specific = set(conditions['disease']['interaction_key']) - common
print(f"Disease-specific interactions: {len(disease_specific)}")

# Approach 2: by_sample within single dataset
ln.mt.rank_aggregate.by_sample(
    adata,
    groupby='cell_type',
    sample_key='sample_id',
    resource_name='consensus',
    inplace=True,
    key_added='liana_by_sample'
)

# Multi-sample dot plot
ln.pl.dotplot_by_sample(
    adata,
    sample_key='sample_id',
    colour='magnitude_rank',
    size='specificity_rank'
)

# ==============================================================================
# Example 7: Summarize and Export
# ==============================================================================

print("\n" + "=" * 60)
print("Example 7: Summary and Export")
print("=" * 60)

liana_res = adata.uns['liana_consensus']

# Summary by cell pair
pair_summary = summarize_by_cell_pair(liana_res, agg_func='count')
print("\nInteractions by cell pair:")
print(pair_summary)

# Convert to matrix
matrix = get_interaction_matrix(liana_res, value_col='magnitude_rank')
print(f"\nInteraction matrix shape: {matrix.shape}")

# Export
export_results(liana_res, 'liana_results.csv', format='csv')
export_results(liana_res, 'liana_results.tsv', format='tsv')
adata.write_h5ad('adata_with_liana.h5ad')

print("\nAdvanced analysis complete!")
