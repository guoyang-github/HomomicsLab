"""
Workflow Example: Cell Type Co-localization Analysis

This example demonstrates how to analyze spatial relationships between
different cell types using co-occurrence and join counts statistics.
"""

import sys
sys.path.append('../scripts/python')

import scanpy as sc
import seaborn as sns
import matplotlib.pyplot as plt
from pattern import analyze_spatial_patterns, compute_cooccurrence_probability

# 1. Load spatial data with cell type annotations
adata = sc.read_h5ad('your_spatial_data.h5ad')

# Ensure cell type annotations exist
if 'cell_type' not in adata.obs.columns:
    raise ValueError("Cell type annotations required in adata.obs['cell_type']")

print(f"Cell types: {adata.obs['cell_type'].unique()}")

# 2. Run comprehensive pattern analysis
results = analyze_spatial_patterns(
    adata,
    cluster_key='cell_type',
    n_neighbors=6,
    n_permutations=100
)

# 3. Co-occurrence analysis
cooccur_result = compute_cooccurrence_probability(
    adata,
    cluster_key='cell_type',
    n_neighbors=6,
    n_permutations=100
)

# 4. Visualize co-occurrence z-scores
plt.figure(figsize=(10, 8))
z_scores = cooccur_result['z_scores']
sns.heatmap(z_scores, annot=True, cmap='RdBu_r', center=0, fmt='.2f')
plt.title('Cell Type Co-occurrence Z-scores')
plt.xlabel('Target Cell Type')
plt.ylabel('Source Cell Type')
plt.tight_layout()
plt.savefig('cooccurrence_zscores.png', dpi=300)

# 5. Print significant co-occurrences
significant = cooccur_result['is_significant']
print("\nSignificant co-occurrences (z-score > 1.96 or < -1.96):")
for i, source in enumerate(significant.index):
    for j, target in enumerate(significant.columns):
        if significant.loc[source, target] and source != target:
            z = z_scores.loc[source, target]
            direction = "attracted" if z > 0 else "avoided"
            print(f"  {source} → {target}: {direction} (z={z:.2f})")

# 6. Join Counts results
print("\n\nJoin Counts Results:")
print(results['join_counts'][['category', 'autocorrelation', 'z_score', 'p_value']])

# 7. Neighborhood enrichment
print("\n\nNeighborhood Enrichment (top 5 interactions):")
enrichment = results['neighborhood_enrichment']
significant_enrichment = enrichment[enrichment['p_value'] < 0.05]
print(significant_enrichment.nlargest(5, 'enrichment')[
    ['source', 'target', 'enrichment', 'p_value']
])
