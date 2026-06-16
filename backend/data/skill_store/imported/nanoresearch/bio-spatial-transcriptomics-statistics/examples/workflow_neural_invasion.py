"""
Workflow Example: Neural Invasion Zone Analysis

This example demonstrates how to analyze cell type distribution
around neural structures using anchor zones and Ro/e analysis.
This is particularly useful for studying neural invasion in
cancers like pancreatic ductal adenocarcinoma (PDAC).
"""

import sys
sys.path.append('../scripts/python')

import scanpy as sc
import seaborn as sns
import matplotlib.pyplot as plt
from zones import analyze_spatial_zones, define_neural_zones, compute_roe
from utils import validate_spatial_data

# 1. Load spatial data
adata = sc.read_h5ad('your_spatial_data.h5ad')

# 2. Validate data
validate_spatial_data(adata)

# 3. Define neural zones
# Assumes 'Neuron' or 'Schwann' cell type exists
if 'cell_type' not in adata.obs.columns:
    raise ValueError("Cell type annotations required")

neural_cell_type = 'Neuron'  # Adjust based on your annotation
if neural_cell_type not in adata.obs['cell_type'].values:
    print(f"Warning: {neural_cell_type} not found. Available types:")
    print(adata.obs['cell_type'].value_counts())

# 4. Create neural zones (concentric layers around neural cells)
neural_zones = define_neural_zones(
    adata,
    neural_cell_type=neural_cell_type,
    cluster_key='cell_type',
    n_layers=5,
    layer_names=['Neural', 'Proximal', 'Intermediate', 'Distal', 'Far']
)

# Add zones to adata
adata.obs['neural_zone'] = neural_zones['zone_label'].values
adata.obs['distance_to_neural'] = neural_zones['distance_to_neural'].values

# 5. Run comprehensive analysis
results = analyze_spatial_zones(
    adata,
    anchor_cell_type=neural_cell_type,
    zone_type='neural',
    cell_type_key='cell_type',
    n_layers=5
)

# 6. Visualize zone composition
composition = results['composition']
print("Cell Type Composition by Zone:")
print(composition)

# Plot composition heatmap
plt.figure(figsize=(10, 6))
sns.heatmap(composition, annot=True, cmap='YlOrRd', fmt='.2f')
plt.title('Cell Type Composition Across Neural Zones')
plt.ylabel('Neural Zone')
plt.xlabel('Cell Type')
plt.tight_layout()
plt.savefig('zone_composition.png', dpi=300)

# 7. Ro/e Analysis
roe = results['roe']
print("\nRo/e Analysis:")
print(roe)

# Plot Ro/e heatmap
plt.figure(figsize=(10, 6))
sns.heatmap(
    roe,
    annot=True,
    cmap='RdYlBu_r',
    center=1,
    vmin=0,
    vmax=3,
    fmt='.2f'
)
plt.title('Ro/e: Cell Type Enrichment in Neural Zones')
plt.ylabel('Cell Type')
plt.xlabel('Neural Zone')
plt.tight_layout()
plt.savefig('roe_heatmap.png', dpi=300)

# 8. Identify enriched/depleted cell types
significant = results['significant_enrichments']
print("\nSignificant Enrichments:")
for cell_type in significant.index:
    enriched_zones = significant.columns[significant.loc[cell_type]].tolist()
    if enriched_zones:
        print(f"  {cell_type}: enriched in {', '.join(enriched_zones)}")

# 9. Plot spatial visualization
sq.pl.spatial_scatter(
    adata,
    color=['cell_type', 'neural_zone', 'distance_to_neural'],
    title=['Cell Types', 'Neural Zones', 'Distance to Neural']
)

print("\nAnalysis complete! Check zone_composition.png and roe_heatmap.png")
