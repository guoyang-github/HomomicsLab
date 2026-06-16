---
name: bio-spatial-transcriptomics-layers
description: Create and analyze spatial layers around regions of interest for gradient analysis. Divide tissue into concentric zones centered on ROIs (e.g., tumor core, neural structures) to analyze microenvironment gradients such as perineural regions, peritumoral infiltration zones, and perivascular niches.
tool_type: multi
primary_tool: spatial-layers
supported_tools: [squidpy, Seurat]
languages: [python, r]
keywords: ["spatial", "layers", "gradient", "roi", "perineural", "peritumoral", "microenvironment", "infiltration", "zones"]
---

## Version Compatibility

- **Python**: >= 3.8, squidpy >= 1.3.0, scanpy >= 1.9.0
- **R**: >= 4.2.0, Seurat >= 4.3.0

## Installation

### Python

```bash
pip install squidpy scanpy scikit-learn
```

### R

```r
install.packages(c("ggplot2", "dplyr", "tidyr", "RColorBrewer"))
```

## Quick Selector

### When to Use Spatial Layers

| Scenario | ROI Definition | Analysis Goal |
|----------|----------------|---------------|
| Tumor microenvironment | Tumor core niche | Immune infiltration gradients |
| Neural invasion | Schwann cells / Neural niche | Perineural cancer cell enrichment |
| Vascular niches | Endothelial cells | Perivascular cell composition |
| Treatment response | Post-treatment scar | Tissue remodeling zones |
| Development | Stem cell niches | Differentiation gradients |

### Layer Methods Comparison

| Method | Description | Best For | Distance Metric |
|--------|-------------|----------|-----------------|
| **distance** | Euclidean distance to ROI boundary | Most applications | Microns (μm) |
| **knn** | Steps in neighbor graph | Single-cell resolution | Graph steps |
| **radius** | Radial expansion from center | Circular ROIs | Microns (μm) |

---

## Concept

**Spatial Layering** creates concentric zones centered on a Region of Interest (ROI), enabling quantitative analysis of how cell composition changes with distance:

```
Layer 0 (ROI):        ████████████████████  Tumor core / Neural structure
                      ░░░░░░░░░░░░░░░░░░░░
Layer 1 (Inner):      ░░░░░░░░░░░░░░░░░░░░  0-100μm: Immediate microenvironment
                      ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
Layer 2 (Middle):     ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  100-200μm: Intermediate zone
                      ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
Layer 3 (Outer):      ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  >200μm: Distant tissue
```

---

## Python Usage

### Create Spatial Layers

```python
import sys
sys.path.append('scripts/python')
from spatial_layers import create_spatial_layers

# Method 1: Using niche/region label
adata = create_spatial_layers(
    adata,
    roi_definition='Tumor_core',     # Niche annotation
    roi_type='niche',
    n_layers=3,
    layer_method='distance',
    distance_threshold=150,          # 150μm per layer
    layer_names=['Tumor_core', 'Inner_zone', 'Middle_zone', 'Outer_zone']
)

# Method 2: Using cell type mask
schwann_mask = adata.obs['Schwann_cell'] > 0.2
adata = create_spatial_layers(
    adata,
    roi_definition=schwann_mask,
    roi_type='mask',
    n_layers=4,
    distance_threshold=80
)

# Method 3: Using center coordinates
center = [adata.obsm['spatial'][:, 0].mean(), 
          adata.obsm['spatial'][:, 1].mean()]
adata = create_spatial_layers(
    adata,
    roi_definition=center,
    roi_type='coordinates',
    layer_method='radius',
    n_layers=3
)
```

### Analyze Layer Gradients

```python
import sys
sys.path.append('scripts/python')
from spatial_layers import analyze_layer_gradients

# Analyze gradients for all cell types
gradient_results = analyze_layer_gradients(
    adata,
    layer_key='spatial_layer',
    features=['T_cell', 'Macrophage', 'Fibroblast'],
    feature_type='obs',
    analysis_method='trend',
    reference_layer='Tumor_core'
)

# Results include:
# - mean_value: Mean proportion in each layer
# - log2fc: Log2 fold change vs reference
# - trend: Pattern ('increasing', 'decreasing', 'peaked', 'valley')
# - pval: Statistical significance
```

### Visualize Layers

```python
import sys
sys.path.append('scripts/python')
from spatial_layers import visualize_spatial_layers, plot_layer_heatmap

# Spatial map with layers
visualize_spatial_layers(
    adata,
    layer_key='spatial_layer',
    show_distance=True,
    save='spatial_layers.png'
)

# Heatmap of cell type proportions across layers
plot_layer_heatmap(
    gradient_results,
    value_col='mean_value',
    normalize=True
)
```

---

## R Usage

### Create Spatial Layers

```r
source("scripts/r/spatial_layers.R")

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

# Using cell type mask
schwann_mask <- seurat_obj$Schwann_cell > 0.2
seurat_obj <- CreateSpatialLayers(
    seurat_obj,
    roi.definition = schwann_mask,
    roi.type = "mask",
    n.layers = 4,
    distance.threshold = 80
)
```

### Analyze Layer Gradients

```r
# Analyze gradients
gradient_results <- AnalyzeLayerGradients(
    seurat_obj,
    layer.key = "spatial_layer",
    features = c("T_cell", "Macrophage", "Cancer_EMT"),
    feature.type = "metadata",
    method = "trend"
)

# Plot composition
PlotLayerComposition(
    seurat_obj,
    layer.key = "spatial_layer",
    features = c("T_cell", "Macrophage", "Fibroblast")
)

# Heatmap visualization
PlotLayerHeatmap(
    gradient_results,
    value_col = "mean_value",
    normalize = TRUE,
    cluster_rows = TRUE,
    cluster_cols = FALSE
)
```

---

## Output Structure

### Python (AnnData)

Added to `adata.obs`:
- `spatial_layer`: Layer assignment (categorical)
- `roi_status`: Whether spot is in ROI (bool)
- `distance_to_roi`: Distance to ROI boundary (μm)

Added to `adata.uns['spatial_layers']`:
- `params`: Analysis parameters
- `layer_stats`: Spot counts and distance statistics per layer

### R (Seurat)

Added to `seurat_obj@meta.data`:
- `spatial_layer`: Layer assignment (factor)
- `roi_status`: Whether spot is in ROI (logical)
- `distance_to_roi`: Distance to ROI boundary (μm)

Added to `seurat_obj@misc$spatial_layers`:
- `params`: List of analysis parameters
- `layer_stats`: List with statistics per layer

---

## Interpretation Guide

| Observation | Interpretation |
|-------------|----------------|
| Cell type decreasing with distance | ROI-associated (e.g., cancer cells in tumor core) |
| Cell type increasing with distance | Distant-associated (e.g., fibroblasts in stroma) |
| Peaked in middle layers | Interface-enriched (e.g., immune cells at tumor margin) |
| Flat across layers | Ubiquitous distribution |

---

## Related Skills

- [bio-spatial-transcriptomics-neighbors](../bio-spatial-transcriptomics-neighbors) - Build spatial neighbor graphs
- [bio-spatial-transcriptomics-niches](../bio-spatial-transcriptomics-niches) - Identify tissue niches before layering
- [bio-spatial-transcriptomics-deconvolution](../bio-spatial-transcriptomics-deconvolution) - Get cell type proportions for layer analysis
- [bio-spatial-transcriptomics-differential-abundance-roe-r](../bio-spatial-transcriptomics-differential-abundance-roe-r) - Alternative gradient analysis

---

## References

1. Palla et al. (2022). Squidpy: a scalable toolkit for spatial omics analysis. *Nature Methods*, 19, 171-178.
2. Satija Lab Seurat: https://satijalab.org/seurat/
