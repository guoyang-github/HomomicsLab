# Spatial Niche Clustering - Usage Guide

## Overview

This skill clusters spatial transcriptomics spots into tissue microenvironment niches based on cell type proportions from deconvolution. Identifies biologically meaningful regions like tertiary lymphoid structures (TLS), neural niches, tumor-stroma interfaces, and immune infiltrates using unsupervised clustering with optional spatial constraints.

## Prerequisites

### Core Dependencies
```bash
pip install scanpy squidpy pandas numpy scikit-learn leidenalg
```

### Optional Visualization
```bash
pip install seaborn matplotlib
```

### For Differential Abundance Testing
```bash
pip install statsmodels
```

## Quick Start

Tell your AI agent what you want to do:
- "Cluster my spatial spots into niches based on cell type composition"
- "Identify tissue microenvironments like TLS and neural niches"
- "Annotate niches using marker cell types"
- "Compare niche distributions between NI+ and NI- samples"
- "Visualize niche spatial distribution"

## Example Prompts

### Niche Clustering
> "Cluster spots into niches using cell type proportions with spatial constraints"

> "Run KMeans clustering on deconvolution results to find 10 niches"

> "Use Leiden clustering with spatial neighbors to identify tissue zones"

### Niche Annotation
> "Annotate niches as TLS, neural, tumor, or stroma based on marker cell types"

> "Identify immune-enriched niches using T cell and macrophage proportions"

> "Automatically label niches using my custom marker dictionary"

### Niche Comparison
> "Compare niche proportions between treatment and control groups"

> "Test for differential abundance of the neural niche across samples"

> "Which niches are enriched in NI+ compared to NI- regions?"

### Visualization
> "Plot niche distribution on the tissue slide"

> "Create a heatmap showing cell type composition per niche"

> "Visualize niche proportions by experimental group"

## What the Agent Will Do

1. **Prepare proportion data**
   - Extract cell type proportions from deconvolution results (obsm)
   - Validate proportion matrix (values 0-1, rows sum to ~1)
   - Apply PCA dimensionality reduction if needed

2. **Build spatial graph (optional)**
   - Create spatial neighbor graph using Squidpy
   - Adjust neighbor count for platform (Visium: 6, Visium HD: 4)
   - Normalize spatial coordinates

3. **Cluster niches**
   - Apply KMeans (proportion-only) or Leiden (with spatial constraint)
   - Determine optimal cluster count if not specified
   - Assign niche labels to each spot

4. **Calculate niche composition**
   - Aggregate cell type proportions per niche
   - Identify dominant cell types for each niche
   - Compute niche size and distribution

5. **Annotate niches (optional)**
   - Score niches against marker dictionaries
   - Assign labels based on highest scoring cell type combination
   - Flag mixed niches below confidence threshold

6. **Compare groups (optional)**
   - Calculate niche proportions per experimental group
   - Perform chi-square test for distribution differences
   - Apply FDR correction for multiple testing

7. **Visualize results**
   - Spatial niche maps
   - Composition heatmaps
   - Group comparison plots

## Niche Type Marker Examples

### Pancreatic Cancer
```python
pancreas_markers = {
    'TLS': ['B_cell', 'T_cell', 'Plasma_cell'],
    'Neural': ['Schwann_cell', 'Neuron'],
    'Tumor': ['Ductal_cell', 'Cancer_cell'],
    'Stroma': ['Fibroblast', 'Myofibroblast'],
    'Immune_infiltrate': ['T_cell', 'Macrophage', 'NK_cell'],
    'Vascular': ['Endothelial_cell', 'Pericyte'],
    'Acinar': ['Acinar_cell'],
}
```

### General Tumor Microenvironment
```python
tumor_markers = {
    'Tumor_core': ['Cancer_cell', 'Tumor_cell'],
    'Tumor_stroma': ['Fibroblast', 'Cancer_cell'],
    'Immune_hot': ['T_cell', 'B_cell', 'Macrophage'],
    'Immune_cold': ['Fibroblast', 'Endothelial_cell'],
    'TLS': ['B_cell', 'T_cell', 'Follicular_B'],
    'Hypoxic': ['Cancer_cell', 'Fibroblast'],
}
```

### Brain/Neural Tissue
```python
neural_markers = {
    'Neural_cortex': ['Neuron', 'Astrocyte'],
    'White_matter': ['Oligodendrocyte', 'Microglia'],
    'Neurogenic_niche': ['Neural_stem', 'Astrocyte'],
    'Vascular': ['Endothelial_cell', 'Pericyte'],
    'Inflammatory': ['Microglia', 'Macrophage', 'T_cell'],
}
```

## Parameter Selection Guide

### Clustering Method

| Goal | Method | Notes |
|------|--------|-------|
| Pure composition-based | KMeans | Fast, no spatial constraint |
| Spatially-coherent zones | Leiden | Smooth boundaries, contiguous regions |
| Known niche count | KMeans | Set `n_clusters` explicitly |
| Unknown niche count | Leiden | Auto-determines from data |

### Number of Clusters

```python
# For KMeans - common starting points
n_clusters = 8   # Simple tissue (2-3 cell types)
n_clusters = 12  # Complex tissue (5-8 cell types)
n_clusters = 20  # Highly heterogeneous tissue

# Rule of thumb: 1.5x number of cell types
n_clusters = int(1.5 * n_cell_types)
```

### Spatial Neighbors

```python
# Visium (hexagonal grid)
n_neighbors = 6

# Visium HD (square grid)
n_neighbors = 4

# MERFISH/Xenium (irregular)
n_neighbors = 8
```

### Annotation Threshold

```python
# High confidence (fewer unassigned)
threshold = 0.20  # Top 20% composition

# Balanced (default)
threshold = 0.15

# Permissive (more assignments)
threshold = 0.10

# Very permissive
threshold = 0.05
```

## Tips

- **Run deconvolution first** - This skill requires cell type proportions from tools like cell2location or Tangram
- **Start with spatial constraint** - Leiden with spatial neighbors produces more biologically interpretable zones
- **Validate annotations** - Cross-check niche assignments with known histology if available
- **Check niche sizes** - Very small niches (< 1% of spots) may be artifacts
- **Compare methods** - Try both KMeans and Leiden to assess robustness
- **Use domain knowledge** - Custom marker dictionaries improve annotation accuracy
- **Consider biological context** - Expected niches vary by tissue type (tumor vs normal)
- **Group comparison** - Always check if niche distributions differ between conditions
- **Save intermediate results** - Store proportion matrices for reproducibility
- **Visual validation** - Always plot niche maps to check for batch effects or artifacts

## Common Issues

### "No proportions found in adata.obsm"
```python
# Check available keys
print(adata.obsm.keys())

# Common keys from deconvolution
# 'cell_type_proportions', ' proportions', 'q05_cell_abundance_w_sf'
```

### "All spots assigned to one niche"
```python
# Reduce n_clusters or use Leiden
# Check proportion variance across spots
print(adata.obsm['proportions'].std().describe())
```

### "Niche annotations all 'Mixed'"
```python
# Lower the threshold
annotations = annotate_niches_by_markers(comp, markers, threshold=0.08)

# Or check if markers exist in data
print([m for m in markers['TLS'] if m in proportions.columns])
```

### "Disconnected niche regions"
```python
# Increase spatial constraint strength
# Normalize spatial coordinates more aggressively
# Increase n_neighbors for spatial graph
```

## Output Files

| File | Description |
|------|-------------|
| `niche_assignments.csv` | Spot-level niche labels |
| `niche_composition.csv` | Cell type proportions per niche |
| `niche_annotations.csv` | Biological labels for each niche |
| `niche_spatial_map.png` | Spatial distribution of niches |
| `niche_heatmap.png` | Cell type composition heatmap |
| `niche_comparison.csv` | Differential abundance results |

## Related Skills

- **bio-spatial-transcriptomics-deconvolution** - Get cell type proportions
- **bio-spatial-transcriptomics-neighbors** - Build spatial graphs
- **bio-spatial-transcriptomics-visualization** - Advanced visualization
- **bio-spatial-transcriptomics-statistics** - Spatial statistics on niches
