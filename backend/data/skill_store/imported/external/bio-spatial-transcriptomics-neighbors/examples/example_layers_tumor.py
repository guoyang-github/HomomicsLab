"""
Spatial Layer Analysis Example: Tumor Microenvironment Gradients
Demonstrates creating concentric layers around tumor core for gradient analysis.
"""

import numpy as np
import pandas as pd
import scanpy as sc
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.spatial import distance

# Import spatial layers module
import sys
sys.path.append('../scripts/python')
from spatial_layers import (
    create_spatial_layers,
    analyze_layer_gradients,
    visualize_spatial_layers,
    plot_layer_heatmap
)

print("=" * 70)
print("Example: Tumor Microenvironment Gradients")
print("=" * 70)

# Create synthetic spatial data
print("\n1. Creating synthetic tumor data...")

np.random.seed(42)

# Create 400 spots in a grid
n_spots = 400
grid_size = 20

# Coordinates (simulating Visium spacing ~100μm)
x = np.repeat(np.arange(grid_size), grid_size) * 100
y = np.tile(np.arange(grid_size), grid_size) * 100

coords = np.column_stack([x, y])

# Create cell type proportions with tumor core in center
center_x, center_y = 1000, 1000  # Center of grid

# Calculate distance from center
dist_from_center = np.sqrt((x - center_x)**2 + (y - center_y)**2)

# Define regions based on distance
# 0-300μm: Tumor core
# 300-600μm: Tumor margin
# 600-1000μm: Stroma
# >1000μm: Normal tissue

regions = np.where(
    dist_from_center < 300, 'Tumor_core',
    np.where(dist_from_center < 600, 'Tumor_margin',
            np.where(dist_from_center < 1000, 'Stroma', 'Normal'))
)

# Create deconvolution proportions for 8 cell types
cell_types = [
    'Cancer_cell', 'T_cell', 'Macrophage_M1', 'Macrophage_M2',
    'Fibroblast', 'Endothelial', 'NK_cell', 'DC'
]

proportions = np.zeros((n_spots, len(cell_types)))

for i in range(n_spots):
    d = dist_from_center[i]
    region = regions[i]

    if region == 'Tumor_core':
        # High cancer, low immune
        props = [0.70, 0.05, 0.02, 0.08, 0.08, 0.03, 0.02, 0.02]
    elif region == 'Tumor_margin':
        # Mix of cancer and immune
        props = [0.40, 0.15, 0.05, 0.12, 0.15, 0.05, 0.05, 0.03]
    elif region == 'Stroma':
        # High fibroblast, moderate immune
        props = [0.10, 0.12, 0.03, 0.08, 0.45, 0.10, 0.08, 0.04]
    else:  # Normal
        # Balanced
        props = [0.05, 0.15, 0.05, 0.05, 0.35, 0.15, 0.15, 0.05]

    # Add noise
    noise = np.random.normal(0, 0.02, len(props))
    props = np.maximum(props + noise, 0)
    props = props / props.sum()

    proportions[i] = props

# Create AnnData
adata = sc.AnnData(X=proportions)
adata.obs_names = [f'Spot_{i}' for i in range(n_spots)]
adata.var_names = cell_types
adata.obsm['spatial'] = coords
adata.obs['region'] = regions

# Add cell type proportions to obs for easy access
for i, ct in enumerate(cell_types):
    adata.obs[ct] = proportions[:, i]

print(f"Created {n_spots} spots with {len(cell_types)} cell types")
print(f"Regions: {dict(zip(*np.unique(regions, return_counts=True)))}")

# Visualize original data
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Plot regions
colors = {'Tumor_core': '#e41a1c', 'Tumor_margin': '#ff7f00',
          'Stroma': '#377eb8', 'Normal': '#4daf4a'}
for region, color in colors.items():
    mask = regions == region
    axes[0].scatter(coords[mask, 0], coords[mask, 1],
                   c=color, label=region, s=20, alpha=0.7)
axes[0].set_xlabel('X (μm)')
axes[0].set_ylabel('Y (μm)')
axes[0].set_title('Anatomical Regions')
axes[0].legend()
axes[0].set_aspect('equal')

# Plot cancer cell proportion
scatter = axes[1].scatter(coords[:, 0], coords[:, 1],
                         c=proportions[:, 0], cmap='Reds', s=20)
axes[1].set_xlabel('X (μm)')
axes[1].set_ylabel('Y (μm)')
axes[1].set_title('Cancer Cell Proportion')
plt.colorbar(scatter, ax=axes[1])
axes[1].set_aspect('equal')

plt.tight_layout()
plt.savefig('01_original_data.png', dpi=150, bbox_inches='tight')
print("\nSaved: 01_original_data.png")
plt.close()

# ============================================================================
# Step 2: Create Spatial Layers
# ============================================================================

print("\n2. Creating spatial layers around tumor core...")

# Method 1: Using niche/region label
adata = create_spatial_layers(
    adata,
    roi_definition='Tumor_core',
    roi_type='niche',
    n_layers=3,
    layer_method='distance',
    distance_threshold=150,  # 150μm per layer
    layer_names=['Tumor_core', 'Inner_zone', 'Middle_zone', 'Outer_zone'],
    buffer_zone=0,
    inplace=False
)

print("\nLayer distribution:")
print(adata.obs['spatial_layer'].value_counts())

# Visualize layers
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Layer assignment
layer_colors = {'Tumor_core': '#d62728', 'Inner_zone': '#ff7f0e',
                'Middle_zone': '#2ca02c', 'Outer_zone': '#1f77b4'}

for layer in adata.obs['spatial_layer'].cat.categories:
    mask = adata.obs['spatial_layer'] == layer
    axes[0].scatter(adata.obsm['spatial'][mask, 0],
                   adata.obsm['spatial'][mask, 1],
                   c=layer_colors[layer], label=layer, s=20, alpha=0.7)

axes[0].set_xlabel('X (μm)')
axes[0].set_ylabel('Y (μm)')
axes[0].set_title('Spatial Layers Around Tumor Core')
axes[0].legend()
axes[0].set_aspect('equal')

# Distance to ROI
scatter = axes[1].scatter(adata.obsm['spatial'][:, 0],
                         adata.obsm['spatial'][:, 1],
                         c=adata.obs['distance_to_roi'],
                         cmap='viridis', s=20)
axes[1].set_xlabel('X (μm)')
axes[1].set_ylabel('Y (μm)')
axes[1].set_title('Distance to Tumor Core (μm)')
plt.colorbar(scatter, ax=axes[1])
axes[1].set_aspect('equal')

plt.tight_layout()
plt.savefig('02_spatial_layers.png', dpi=150, bbox_inches='tight')
print("Saved: 02_spatial_layers.png")
plt.close()

# ============================================================================
# Step 3: Analyze Layer Gradients
# ============================================================================

print("\n3. Analyzing cell type gradients across layers...")

# Analyze gradients for all cell types
gradient_results = analyze_layer_gradients(
    adata,
    layer_key='spatial_layer',
    features=cell_types,
    feature_type='obs',
    analysis_method='trend',
    reference_layer='Tumor_core'
)

print("\nGradient analysis results (first 10 rows):")
print(gradient_results.head(10))

# Identify cell types with interesting patterns
print("\nCell type trends:")
trend_summary = gradient_results.groupby('feature')['trend'].first()
print(trend_summary)

# Create heatmap of cell type proportions across layers
pivot_df = gradient_results.pivot(index='feature', columns='layer', values='mean_value')

fig, ax = plt.subplots(figsize=(8, 6))
sns.heatmap(pivot_df, annot=True, fmt='.3f', cmap='YlOrRd', ax=ax)
ax.set_title('Cell Type Proportions Across Layers')
ax.set_xlabel('Layer')
ax.set_ylabel('Cell Type')
plt.tight_layout()
plt.savefig('03_celltype_heatmap.png', dpi=150, bbox_inches='tight')
print("\nSaved: 03_celltype_heatmap.png")
plt.close()

# ============================================================================
# Step 4: Visualize Specific Gradients
# ============================================================================

print("\n4. Visualizing specific cell type gradients...")

# Plot gradients for key cell types
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
axes = axes.flatten()

key_celltypes = ['Cancer_cell', 'T_cell', 'Fibroblast', 'Macrophage_M2']

for idx, ct in enumerate(key_celltypes):
    ct_data = gradient_results[gradient_results['feature'] == ct]

    ax = axes[idx]
    bars = ax.bar(ct_data['layer'], ct_data['mean_value'],
                  color=['#d62728', '#ff7f0e', '#2ca02c', '#1f77b4'])
    ax.set_xlabel('Layer')
    ax.set_ylabel('Proportion')
    ax.set_title(f'{ct} Gradient\n(Trend: {ct_data["trend"].iloc[0]})')
    ax.set_ylim(0, max(ct_data['mean_value']) * 1.2)

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.3f}', ha='center', va='bottom', fontsize=9)

plt.tight_layout()
plt.savefig('04_gradient_bars.png', dpi=150, bbox_inches='tight')
print("Saved: 04_gradient_bars.png")
plt.close()

# ============================================================================
# Step 5: Statistical Summary
# ============================================================================

print("\n5. Statistical Summary:")
print("=" * 50)

# Layer-wise cell type composition
layer_summary = adata.obs.groupby('spatial_layer')[cell_types].mean()
print("\nMean cell type proportions by layer:")
print(layer_summary.round(3))

# Calculate fold changes (compared to tumor core)
print("\nFold changes vs Tumor core:")
fc_df = layer_summary.div(layer_summary.loc['Tumor_core'], axis=1)
print(fc_df.round(2))

# Identify cell types enriched in specific layers
print("\nKey findings:")
for ct in cell_types:
    trend = trend_summary[ct]
    if trend == 'decreasing':
        max_layer = layer_summary[ct].idxmax()
        print(f"  - {ct}: enriched in {max_layer} (tumor-associated)")
    elif trend == 'increasing':
        max_layer = layer_summary[ct].idxmax()
        print(f"  - {ct}: enriched in {max_layer} (stroma-associated)")
    elif trend == 'peaked':
        max_layer = layer_summary[ct].idxmax()
        print(f"  - {ct}: peaked in {max_layer} (interface-enriched)")

# ============================================================================
# Step 6: Compare with Anatomical Regions
# ============================================================================

print("\n6. Comparing layers with anatomical regions...")

# Cross-tabulation
layer_region_crosstab = pd.crosstab(
    adata.obs['spatial_layer'],
    adata.obs['region'],
    normalize='index'
)

print("\nLayer composition by anatomical region (row percentages):")
print((layer_region_crosstab * 100).round(1))

fig, ax = plt.subplots(figsize=(8, 6))
sns.heatmap(layer_region_crosstab * 100, annot=True, fmt='.1f',
            cmap='Blues', ax=ax, cbar_kws={'label': 'Percentage'})
ax.set_title('Layer Composition by Anatomical Region')
ax.set_xlabel('Anatomical Region')
ax.set_ylabel('Spatial Layer')
plt.tight_layout()
plt.savefig('05_layer_region_comparison.png', dpi=150, bbox_inches='tight')
print("\nSaved: 05_layer_region_comparison.png")
plt.close()

print("\n" + "=" * 70)
print("Analysis complete! Generated files:")
print("  - 01_original_data.png")
print("  - 02_spatial_layers.png")
print("  - 03_celltype_heatmap.png")
print("  - 04_gradient_bars.png")
print("  - 05_layer_region_comparison.png")
print("=" * 70)
