# Spatial Layers - Usage Guide

Complete guide for creating and analyzing spatial layers around regions of interest.

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Creating Spatial Layers](#creating-spatial-layers)
5. [Analyzing Gradients](#analyzing-gradients)
6. [Visualization](#visualization)
7. [Troubleshooting](#troubleshooting)

---

## Overview

Spatial layer analysis divides tissue into concentric zones centered on a Region of Interest (ROI), enabling quantitative analysis of how cell composition changes with distance.

### Use Cases

| Application | ROI Example | Analysis |
|-------------|-------------|----------|
| Tumor microenvironment | Tumor core | Immune infiltration gradients |
| Neural invasion | Neural structures | Perineural cancer enrichment |
| Vascular niches | Endothelial clusters | Perivascular composition |
| Treatment zones | Post-treatment scar | Remodeling patterns |

---

## Installation

### Python

```bash
pip install squidpy scanpy scikit-learn matplotlib seaborn
```

### R

```r
install.packages(c("ggplot2", "dplyr", "tidyr", "RColorBrewer", "pheatmap"))
```

---

## Quick Start

### Python

```python
from spatial_layers import create_spatial_layers, analyze_layer_gradients

# Create layers
adata = create_spatial_layers(
    adata,
    roi_definition='Tumor_core',
    roi_type='niche',
    n_layers=3,
    distance_threshold=150
)

# Analyze
results = analyze_layer_gradients(adata, layer_key='spatial_layer')
```

### R

```r
source("scripts/r/spatial_layers.R")

# Create layers
seurat_obj <- CreateSpatialLayers(
    seurat_obj,
    roi.definition = "Tumor_core",
    roi.type = "niche",
    n.layers = 3,
    distance.threshold = 150
)

# Analyze
results <- AnalyzeLayerGradients(seurat_obj, layer.key = "spatial_layer")
```

---

## Creating Spatial Layers

### ROI Definition Types

| Type | Input | Use Case |
|------|-------|----------|
| `niche` | Niche name(s) | Pre-defined anatomical regions |
| `cell_type` | Cell type name(s) | Cell type-defined regions |
| `mask` | Boolean array | Custom region selection |
| `coordinates` | [x, y] center | Point-source structures |

### Python Examples

```python
# Method 1: Niche label
adata = create_spatial_layers(
    adata,
    roi_definition='Tumor_core',
    roi_type='niche',
    n_layers=3
)

# Method 2: Cell type mask
mask = adata.obs['Cancer_cell'] > 0.5
adata = create_spatial_layers(
    adata,
    roi_definition=mask,
    roi_type='mask',
    n_layers=4
)

# Method 3: Center coordinates
center = [5000, 3000]  # [x, y]
adata = create_spatial_layers(
    adata,
    roi_definition=center,
    roi_type='coordinates',
    n_layers=3
)
```

### R Examples

```r
# Method 1: Niche label
seurat_obj <- CreateSpatialLayers(
    seurat_obj,
    roi.definition = "Tumor_core",
    roi.type = "niche",
    n.layers = 3
)

# Method 2: Mask
mask <- seurat_obj$Cancer_cell > 0.5
seurat_obj <- CreateSpatialLayers(
    seurat_obj,
    roi.definition = mask,
    roi.type = "mask",
    n.layers = 4
)

# Method 3: Coordinates
center <- c(5000, 3000)  # [x, y]
seurat_obj <- CreateSpatialLayers(
    seurat_obj,
    roi.definition = center,
    roi.type = "coordinates",
    n.layers = 3
)
```

---

## Analyzing Gradients

### Gradient Patterns

| Pattern | Description | Example |
|---------|-------------|---------|
| Decreasing | High near ROI, low far away | Cancer cells in tumor core |
| Increasing | Low near ROI, high far away | Fibroblasts in stroma |
| Peaked | High in middle layers | Immune cells at margin |
| Flat | Uniform across layers | Housekeeping genes |

### Python

```python
from spatial_layers import analyze_layer_gradients

results = analyze_layer_gradients(
    adata,
    layer_key='spatial_layer',
    features=['T_cell', 'Macrophage', 'Fibroblast'],
    feature_type='obs',
    analysis_method='trend',
    reference_layer='Tumor_core'
)

# View results
print(results[['layer', 'feature', 'mean_value', 'trend', 'log2fc']])
```

### R

```r
results <- AnalyzeLayerGradients(
    seurat_obj,
    layer.key = "spatial_layer",
    features = c("T_cell", "Macrophage", "Fibroblast"),
    feature.type = "metadata",
    method = "trend"
)

# View results
head(results)
```

---

## Visualization

### Python

```python
from spatial_layers import visualize_spatial_layers, plot_layer_heatmap

# Spatial layer map
visualize_spatial_layers(
    adata,
    layer_key='spatial_layer',
    show_distance=True
)

# Heatmap
plot_layer_heatmap(
    gradient_results,
    value_col='mean_value',
    normalize=True
)
```

### R

```r
# Plot layers
PlotSpatialLayers(seurat_obj, layer.key = "spatial_layer")

# Composition plot
PlotLayerComposition(
    seurat_obj,
    layer.key = "spatial_layer",
    features = c("T_cell", "Macrophage")
)

# Heatmap
PlotLayerHeatmap(results, value_col = "mean_value")
```

---

## Troubleshooting

### Issue: No spots assigned to ROI

**Cause**: ROI definition too strict

**Solution**:
```python
# Check ROI coverage
print(f"ROI spots: {adata.obs['roi_status'].sum()}")

# Relax threshold if using mask
mask = adata.obs['Cancer_cell'] > 0.1  # Lower threshold
```

### Issue: Uneven layer sizes

**Cause**: Distance threshold too large/small

**Solution**:
```r
# Check distance distribution
hist(seurat_obj$distance_to_roi)

# Adjust threshold
seurat_obj <- CreateSpatialLayers(
    seurat_obj,
    distance.threshold = 100  # Adjust based on distribution
)
```

### Issue: No clear gradient pattern

**Cause**: Feature not ROI-associated

**Solution**: Try different features or check if pattern is truly flat

---

## Complete Example

### Tumor Microenvironment Analysis (R)

```r
library(Seurat)
source("scripts/r/spatial_layers.R")

# Load data
seurat_obj <- Load10X_Spatial("./filtered_feature_bc_matrix/")

# Deconvolution (required for cell type proportions)
# ... run RCTD or similar ...

# Create layers around tumor core
seurat_obj <- CreateSpatialLayers(
    seurat_obj,
    roi.definition = "Tumor_core",
    roi.type = "niche",
    n.layers = 3,
    layer.method = "distance",
    distance.threshold = 150,
    layer.names = c("Tumor_core", "Interface", "Stroma", "Distant")
)

# Analyze immune infiltration
gradient_results <- AnalyzeLayerGradients(
    seurat_obj,
    layer.key = "spatial_layer",
    features = c("T_cell", "CD8_T_cell", "Treg", "Macrophage"),
    feature.type = "metadata"
)

# Visualize
PlotSpatialLayers(seurat_obj, layer.key = "spatial_layer")
PlotLayerComposition(seurat_obj, layer.key = "spatial_layer")
PlotLayerHeatmap(gradient_results)
```
