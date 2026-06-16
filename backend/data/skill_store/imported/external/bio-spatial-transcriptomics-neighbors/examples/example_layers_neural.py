"""
Spatial Layer Analysis Example: Perineural Microenvironment
Demonstrates creating layers around neural structures for neural invasion analysis.
"""

import numpy as np
import pandas as pd
import scanpy as sc
import matplotlib.pyplot as plt
import seaborn as sns

# Import spatial layers module
import sys
sys.path.append('../scripts/python')
from spatial_layers import (
    create_spatial_layers,
    analyze_layer_gradients,
    visualize_spatial_layers
)

print("=" * 70)
print("Example: Perineural Microenvironment Analysis")
print("=" * 70)

# Create synthetic data with neural structures
print("\n1. Creating synthetic PDAC data with neural invasion...")

np.random.seed(123)

# Create 500 spots
n_spots = 500

# Coordinates with multiple "nerves" (linear structures)
np.random.seed(42)

# Main tissue grid
x = np.random.uniform(0, 2000, n_spots)
y = np.random.uniform(0, 1500, n_spots)

coords = np.column_stack([x, y])

# Define neural structures (nerve trunks) - linear features
# Nerve 1: diagonal line
nerve1_mask = (
    (np.abs(y - 0.8 * x - 200) < 80) &
    (x > 400) & (x < 1200)
)

# Nerve 2: horizontal line
nerve2_mask = (
    (np.abs(y - 1000) < 60) &
    (x > 800) & (x < 1800)
)

# Combined neural region
neural_mask = nerve1_mask | nerve2_mask

# Define tumor regions
center_x, center_y = 1200, 800
dist_from_tumor = np.sqrt((x - center_x)**2 + (y - center_y)**2)

tumor_mask = dist_from_tumor < 400

# Create cell types with neural invasion signatures
cell_types = [
    'Cancer_cell', 'Cancer_EMT',  # EMT = epithelial-mesenchymal transition
    'Schwann_cell', 'Neuron',
    'Macrophage_NLRP3', 'Macrophage_M2',
    'T_cell_CD8', 'T_cell_CD4',
    'Fibroblast', 'Endothelial'
]

proportions = np.zeros((n_spots, len(cell_types)))

for i in range(n_spots):
    is_neural = neural_mask[i]
    is_tumor = tumor_mask[i]
    is_overlap = is_neural and is_tumor  # Neural invasion zone!

    if is_overlap:
        # Neural invasion zone: High EMT, Schwann, NLRP3
        props = [0.15, 0.35, 0.25, 0.05, 0.10, 0.03, 0.02, 0.02, 0.02, 0.01]
    elif is_neural:
        # Neural region (no tumor): Schwann, Neurons
        props = [0.02, 0.01, 0.40, 0.30, 0.02, 0.05, 0.05, 0.05, 0.05, 0.05]
    elif is_tumor:
        # Tumor (no neural): High cancer, some immune
        props = [0.60, 0.10, 0.01, 0.01, 0.05, 0.08, 0.05, 0.04, 0.04, 0.02]
    else:
        # Stroma: Fibroblasts, immune
        props = [0.05, 0.02, 0.02, 0.01, 0.03, 0.05, 0.15, 0.12, 0.40, 0.15]

    # Add noise
    noise = np.random.normal(0, 0.015, len(props))
    props = np.maximum(props + noise, 0)
    props = props / props.sum()

    proportions[i] = props

# Create AnnData
adata = sc.AnnData(X=proportions)
adata.obs_names = [f'Spot_{i}' for i in range(n_spots)]
adata.var_names = cell_types
adata.obsm['spatial'] = coords

# Add annotations
adata.obs['region'] = np.where(
    neural_mask & tumor_mask, 'Neural_Invasion',
    np.where(neural_mask, 'Neural',
            np.where(tumor_mask, 'Tumor', 'Stroma'))
)

# Add cell type proportions to obs
for i, ct in enumerate(cell_types):
    adata.obs[ct] = proportions[:, i]

# Create binary neural mask for ROI definition
adata.obs['is_neural'] = neural_mask

print(f"Created {n_spots} spots")
print(f"Neural spots: {neural_mask.sum()}")
print(f"Tumor spots: {tumor_mask.sum()}")
print(f"Neural invasion (overlap): {(neural_mask & tumor_mask).sum()}")

# Visualize original data
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Plot anatomical regions
region_colors = {
    'Neural_Invasion': '#d62728',
    'Neural': '#ff7f0e',
    'Tumor': '#9467bd',
    'Stroma': '#2ca02c'
}

for region, color in region_colors.items():
    mask = adata.obs['region'] == region
    if mask.any():
        axes[0].scatter(coords[mask, 0], coords[mask, 1],
                       c=color, label=region, s=30, alpha=0.6)

axes[0].set_xlabel('X (μm)')
axes[0].set_ylabel('Y (μm)')
axes[0].set_title('Anatomical Regions (Neural + Tumor)')
axes[0].legend()
axes[0].set_aspect('equal')

# Plot EMT cancer cells (key marker for neural invasion)
scatter = axes[1].scatter(coords[:, 0], coords[:, 1],
                         c=proportions[:, 1], cmap='Reds', s=30)
axes[1].set_xlabel('X (μm)')
axes[1].set_ylabel('Y (μm)')
axes[1].set_title('EMT Cancer Cells (Neural Invasion Marker)')
plt.colorbar(scatter, ax=axes[1])
axes[1].set_aspect('equal')

plt.tight_layout()
plt.savefig('01_neural_original.png', dpi=150, bbox_inches='tight')
print("\nSaved: 01_neural_original.png")
plt.close()

# ============================================================================
# Step 2: Create Perineural Layers
# ============================================================================

print("\n2. Creating perineural layers...")

# Method 1: Using mask (cell type-based ROI)
print("\nMethod 1: Defining ROI by Schwann cells (mask)")

# Create binary mask for Schwann cell-rich regions
schwann_mask = adata.obs['Schwann_cell'] > 0.15

adata_method1 = create_spatial_layers(
    adata,
    roi_definition=schwann_mask.values,
    roi_type='mask',
    n_layers=4,
    layer_method='distance',
    distance_threshold=80,  # 80μm per layer (finer granularity)
    layer_names=['Neural_core', 'Perineural_0_80', 'Perineural_80_160',
                'Perineural_160_240', 'Distant'],
    buffer_zone=20,  # 20μm buffer
    inplace=False
)

# Method 2: Using coordinates (center-based)
print("\nMethod 2: Using coordinate-based center")

# Find center of neural region
neural_center = coords[neural_mask].mean(axis=0)
print(f"Neural region center: {neural_center}")

adata_method2 = create_spatial_layers(
    adata,
    roi_definition=neural_center.tolist(),
    roi_type='coordinates',
    n_layers=3,
    layer_method='radius',
    distance_threshold=100,
    inplace=False
)

# Continue with Method 1 for detailed analysis
adata = adata_method1

print("\nLayer distribution (Schwann-based):")
print(adata.obs['spatial_layer'].value_counts())

# Visualize layers
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Layer assignment
layer_order = adata.obs['spatial_layer'].cat.categories
layer_colors = plt.cm.viridis(np.linspace(0, 1, len(layer_order)))
layer_color_map = dict(zip(layer_order, layer_colors))

for layer in layer_order:
    mask = adata.obs['spatial_layer'] == layer
    axes[0].scatter(adata.obsm['spatial'][mask, 0],
                   adata.obsm['spatial'][mask, 1],
                   c=[layer_color_map[layer]], label=layer, s=30, alpha=0.6)

axes[0].set_xlabel('X (μm)')
axes[0].set_ylabel('Y (μm)')
axes[0].set_title('Perineural Layers')
axes[0].legend(bbox_to_anchor=(1.05, 1), loc='upper left')
axes[0].set_aspect('equal')

# Distance to neural region
scatter = axes[1].scatter(adata.obsm['spatial'][:, 0],
                         adata.obsm['spatial'][:, 1],
                         c=adata.obs['distance_to_roi'],
                         cmap='plasma', s=30)
axes[1].set_xlabel('X (μm)')
axes[1].set_ylabel('Y (μm)')
axes[1].set_title('Distance to Neural Region (μm)')
plt.colorbar(scatter, ax=axes[1])
axes[1].set_aspect('equal')

plt.tight_layout()
plt.savefig('02_perineural_layers.png', dpi=150, bbox_inches='tight')
print("Saved: 02_perineural_layers.png")
plt.close()

# ============================================================================
# Step 3: Analyze Perineural Gradients
# ============================================================================

print("\n3. Analyzing cell type gradients around neural structures...")

# Analyze all cell types
gradient_results = analyze_layer_gradients(
    adata,
    layer_key='spatial_layer',
    features=cell_types,
    feature_type='obs',
    reference_layer='Neural_core'
)

# Focus on neural invasion markers
ni_markers = ['Cancer_EMT', 'Schwann_cell', 'Macrophage_NLRP3', 'T_cell_CD8']
ni_results = gradient_results[gradient_results['feature'].isin(ni_markers)]

print("\nNeural invasion markers - gradient summary:")
print(ni_results.pivot(index='feature', columns='layer', values='mean_value').round(3))

# Identify gradients
print("\nGradient patterns:")
for marker in ni_markers:
    marker_data = ni_results[ni_results['feature'] == marker]
    trend = marker_data['trend'].iloc[0]
    peak_layer = marker_data.loc[marker_data['mean_value'].idxmax(), 'layer']
    print(f"  {marker}: {trend} (peak in {peak_layer})")

# Visualize
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
axes = axes.flatten()

for idx, marker in enumerate(ni_markers):
    ax = axes[idx]
    marker_data = ni_results[ni_results['feature'] == marker]

    bars = ax.bar(range(len(marker_data)), marker_data['mean_value'],
                  color=plt.cm.Reds(np.linspace(0.3, 0.9, len(marker_data))))
    ax.set_xticks(range(len(marker_data)))
    ax.set_xticklabels(marker_data['layer'], rotation=45, ha='right')
    ax.set_xlabel('Layer')
    ax.set_ylabel('Proportion')
    ax.set_title(f'{marker}\n({marker_data["trend"].iloc[0]})')

    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{height:.3f}', ha='center', va='bottom', fontsize=8)

plt.suptitle('Neural Invasion Markers Across Perineural Layers', fontsize=14, y=1.02)
plt.tight_layout()
plt.savefig('03_neural_markers.png', dpi=150, bbox_inches='tight')
print("\nSaved: 03_neural_markers.png")
plt.close()

# ============================================================================
# Step 4: Neural Invasion Zone Analysis
# ============================================================================

print("\n4. Neural Invasion Zone Characterization...")

# Identify neural invasion spots (EMT + Schwann co-occurrence)
adata.obs['NI_score'] = (
    adata.obs['Cancer_EMT'] * 0.4 +
    adata.obs['Schwann_cell'] * 0.3 +
    adata.obs['Macrophage_NLRP3'] * 0.3
)

# Layer-wise NI score
ni_by_layer = adata.obs.groupby('spatial_layer')['NI_score'].agg(['mean', 'std'])
print("\nNeural Invasion Score by Layer:")
print(ni_by_layer.round(3))

# Statistical test: ANOVA
from scipy import stats
layer_groups = [group['NI_score'].values for name, group in
                adata.obs.groupby('spatial_layer')]
f_stat, p_value = stats.f_oneway(*layer_groups)
print(f"\nANOVA: F={f_stat:.2f}, p={p_value:.2e}")

# Visualization
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Boxplot of NI score by layer
layer_order = adata.obs['spatial_layer'].cat.categories
ni_data = [adata.obs[adata.obs['spatial_layer'] == layer]['NI_score'].values
           for layer in layer_order]

bp = axes[0].boxplot(ni_data, labels=layer_order, patch_artist=True)
for patch in bp['boxes']:
    patch.set_facecolor('lightblue')
axes[0].set_xlabel('Layer')
axes[0].set_ylabel('Neural Invasion Score')
axes[0].set_title('Neural Invasion Score Distribution')
axes[0].tick_params(axis='x', rotation=45)

# Spatial map of NI score
scatter = axes[1].scatter(adata.obsm['spatial'][:, 0],
                         adata.obsm['spatial'][:, 1],
                         c=adata.obs['NI_score'],
                         cmap='YlOrRd', s=30)
axes[1].set_xlabel('X (μm)')
axes[1].set_ylabel('Y (μm)')
axes[1].set_title('Neural Invasion Score (Spatial)')
plt.colorbar(scatter, ax=axes[1], label='NI Score')
axes[1].set_aspect('equal')

plt.tight_layout()
plt.savefig('04_neural_invasion_analysis.png', dpi=150, bbox_inches='tight')
print("Saved: 04_neural_invasion_analysis.png")
plt.close()

# ============================================================================
# Step 5: Summary Statistics
# ============================================================================

print("\n5. Summary Statistics:")
print("=" * 60)

# Layer composition
print("\nCell type composition by perineural layer:")
layer_comp = adata.obs.groupby('spatial_layer')[cell_types].mean()
print(layer_comp.round(3))

# Key findings
print("\nKey Findings:")
print("-" * 60)

# Find cell types enriched in neural core
neural_core_props = layer_comp.loc['Neural_core']
top_neural = neural_core_props.nlargest(3)
print(f"\nCell types enriched in Neural Core:")
for ct, prop in top_neural.items():
    print(f"  - {ct}: {prop:.3f}")

# Find cell types enriched in perineural zone
pn_zone_props = layer_comp.loc['Perineural_0_80']
top_pn = pn_zone_props.nlargest(3)
print(f"\nCell types enriched in Perineural zone (0-80μm):")
for ct, prop in top_pn.items():
    print(f"  - {ct}: {prop:.3f}")

# EMT gradient
emt_gradient = layer_comp['Cancer_EMT']
print(f"\nEMT Cancer Cell Gradient:")
for layer, prop in emt_gradient.items():
    print(f"  - {layer}: {prop:.3f}")

# Distance correlation
print(f"\nCorrelation with distance to neural region:")
distances = adata.obs['distance_to_roi']
for ct in ['Cancer_EMT', 'Schwann_cell', 'Macrophage_NLRP3']:
    corr = np.corrcoef(distances, adata.obs[ct])[0, 1]
    direction = "decreases" if corr < 0 else "increases"
    print(f"  - {ct}: r={corr:.3f} ({direction} with distance)")

print("\n" + "=" * 60)
print("Analysis complete!")
print("=" * 60)
