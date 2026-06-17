# Spatial Neighbor Graphs - Usage Guide

Complete guide for building and using spatial neighbor graphs in spatial transcriptomics analysis.

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Methods Overview](#methods-overview)
5. [Python Usage](#python-usage)
6. [R Usage](#r-usage)
7. [Platform-Specific Recommendations](#platform-specific-recommendations)
8. [Output Structure](#output-structure)
9. [Visualization](#visualization)
10. [Troubleshooting](#troubleshooting)

---

## Overview

Spatial neighbor graphs define which spots/cells are considered neighbors for downstream spatial analyses. This skill provides:

- **K-Nearest Neighbors (KNN)**: Fixed number of neighbors per spot
- **Radius-based**: All spots within a distance threshold
- **Delaunay Triangulation**: Natural neighbor relationships
- **Grid-based**: Visium-specific hexagonal grid matching

### When to Use Each Method

| Method | Best For | Key Feature |
|--------|----------|-------------|
| **KNN** | Regular layouts, fixed neighborhood size | Exactly k neighbors per spot |
| **Radius** | Variable density, consistent spatial scale | Distance-based connectivity |
| **Delaunay** | Irregular layouts, natural tessellation | Adaptive to local structure |
| **Grid** | Visium data | Matches hexagonal grid (6 neighbors) |

---

## Installation

### Python

```bash
pip install squidpy scanpy
```

### R

```r
install.packages(c("FNN", "deldir", "Matrix", "ggplot2", "patchwork"))
```

---

## Quick Start

### Python

```python
import squidpy as sq

# For Visium (6 neighbors for hexagonal grid)
sq.gr.spatial_neighbors(adata, n_rings=1, coord_type='grid')  # 6 immediate neighbors

# For high-resolution data (radius-based)
sq.gr.spatial_neighbors(adata, radius=50, coord_type='generic')
```

### R

```r
source("scripts/r/spatial_neighbors.R")

# For Visium (6 neighbors)
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 6)

# For high-resolution data (radius-based)
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 50)
```

---

## Methods Overview

### Method Comparison

| Method | Neighbor Selection | Typical Use | Complexity |
|--------|-------------------|-------------|------------|
| KNN | Fixed count (k) | Regular grids | O(n log n) |
| Radius | Distance threshold | Variable density | O(n²) |
| Delaunay | Natural neighbors | Irregular layouts | O(n log n) |
| Grid | Hexagonal rings | Visium-specific | O(n) |

### Selection Guide

| Your Situation | Recommended Method | Parameters |
|----------------|-------------------|------------|
| 10x Visium | Grid | `n_rings=1` (6 neighbors) |
| Irregular spots | Delaunay | Adaptive |
| Variable density | Radius | 100-200 μm typical |
| High-density data | KNN | 5-15 neighbors |

---

## Python Usage

### Build K-Nearest Neighbors Graph

```python
import squidpy as sq

# Build spatial KNN graph
sq.gr.spatial_neighbors(adata, n_neighs=6, coord_type='generic')

# Check the graph
print(f"Connectivities shape: {adata.obsp['spatial_connectivities'].shape}")
print(f"Distances shape: {adata.obsp['spatial_distances'].shape}")
```

**Parameters:**
- `n_neighs`: Number of nearest neighbors (default: 6)
- `coord_type`: 'generic' for arbitrary coordinates, 'grid' for regular grids
- `radius`: Alternative to n_neighs, connect all spots within radius
- `delaunay`: Use Delaunay triangulation instead of KNN

### Radius-Based Neighbors

```python
# Connect all spots within 100 pixels/microns
sq.gr.spatial_neighbors(adata, radius=100, coord_type='generic')
```

### Delaunay Triangulation

```python
# Delaunay triangulation for natural neighbors
sq.gr.spatial_neighbors(adata, delaunay=True, coord_type='generic')
```

### For Visium Data (Grid Structure)

```python
# For Visium hexagonal grid, use n_rings
sq.gr.spatial_neighbors(adata, n_rings=1, coord_type='grid')  # 6 immediate neighbors
sq.gr.spatial_neighbors(adata, n_rings=2, coord_type='grid')  # Extended neighborhood
```

### Access Neighbor Information

```python
from scipy.sparse import csr_matrix

# Get connectivities as sparse matrix
conn = adata.obsp['spatial_connectivities']
print(f'Edges in graph: {conn.nnz}')
print(f'Mean neighbors per spot: {conn.nnz / adata.n_obs:.1f}')

# Get distances
dist = adata.obsp['spatial_distances']
nonzero_dist = dist.data[dist.data > 0]
print(f'Mean neighbor distance: {nonzero_dist.mean():.1f}')

# Get neighbors for a specific spot
spot_idx = 0
neighbor_indices = conn[spot_idx].nonzero()[1]
print(f'Spot {spot_idx} has {len(neighbor_indices)} neighbors: {neighbor_indices}')
```

---

## R Usage

### Load Functions

```r
source("scripts/r/spatial_neighbors.R")
source("scripts/r/visualization.R")
```

### Build KNN Graph

```r
# Standard Visium (6 neighbors for hexagonal grid)
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 6)

# High-resolution data with more neighbors
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 10)

# Custom coordinates
seurat_obj <- CreateSpatialNeighbors(
  seurat_obj,
  n_neighbors = 6,
  coords = c("x_coord", "y_coord")
)
```

**Parameters:**
- `n_neighbors`: Number of nearest neighbors (default: 6)
- `coords`: Columns containing spatial coordinates (default: c("imagerow", "imagecol"))
- `assay`: Name for storing neighbor graph in @misc (default: "spatial_neighbors")
- `verbose`: Print progress messages (default: TRUE)

### Radius-Based Neighbors

```r
# Connect spots within 100 microns
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 100)

# For Visium HD with 2um bins
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 8)
```

### Delaunay Triangulation

```r
# Delaunay triangulation for irregular spot layout
seurat_obj <- CreateSpatialNeighborsDelaunay(seurat_obj)
```

### Grid Neighbors (Visium-specific)

```r
# Visium immediate neighbors (6 neighbors)
seurat_obj <- CreateGridNeighbors(seurat_obj, n_rings = 1)

# Extended neighborhood (18 neighbors)
seurat_obj <- CreateGridNeighbors(seurat_obj, n_rings = 2)
```

### Access Neighbor Information

```r
# View graph summary
SummarizeSpatialNeighbors(seurat_obj)

# Get neighbors for a specific spot
neighbors <- GetSpatialNeighbors(seurat_obj, spot_id = "AAACCCAAGAAACTGA-1")
print(neighbors)

# Access graph directly
conn <- seurat_obj@misc$spatial_neighbors$connectivities
dist <- seurat_obj@misc$spatial_neighbors$distances

# Get graph statistics
stats <- seurat_obj@misc$spatial_neighbors$stats
print(stats$mean_degree)
```

### Visualize Neighbor Graph

```r
# Plot the graph
p <- PlotSpatialNeighborGraph(seurat_obj)
print(p)

# Plot degree distribution
PlotNeighborDegree(seurat_obj, plot_type = "histogram")

# Plot distance distribution
PlotNeighborDistance(seurat_obj)
```

---

## Platform-Specific Recommendations

### 10x Visium

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 6 | Hexagonal grid has 6 neighbors |
| `radius` | 1 spot | Immediate neighbors only |
| Method | Grid | Fixed grid structure |

**Python:**
```python
sq.gr.spatial_neighbors(adata, n_neighs=6, coord_type='grid')
```

**R:**
```r
seurat_obj <- CreateGridNeighbors(seurat_obj, n_rings = 1)
# or
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 6)
```

### 10x Visium HD

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 8-12 | 2x2 μm bins, more neighbors needed |
| `radius` | 8-16 μm | ~4-8 bins |
| Method | Radius | Distance-based |

**Python:**
```python
sq.gr.spatial_neighbors(adata, radius=8, coord_type='generic')
```

**R:**
```r
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 8)
```

### Stereo-seq

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 4 | Square grid (4 immediate) or 8 (including diagonal) |
| `radius` | 1-2 bins | Depends on bin size (0.5-1 μm typical) |
| Method | Grid | Regular arrays |

**Python:**
```python
sq.gr.spatial_neighbors(adata, n_neighs=4, coord_type='grid')
```

**R:**
```r
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 4)
```

### Slide-seq / Slide-seqV2

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 5-10 | Near-single-cell resolution |
| `radius` | 10-20 μm | Based on cell diameter |
| Method | Radius | Distance-based |

**Python:**
```python
sq.gr.spatial_neighbors(adata, radius=15, coord_type='generic')
```

**R:**
```r
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 15)
```

### MERFISH / seqFISH

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 3-7 | Subcellular resolution |
| `radius` | 5-15 μm | Based on expected cell size |
| Method | Radius or Delaunay | Irregular positions |

**Python:**
```python
# Radius-based
sq.gr.spatial_neighbors(adata, radius=10, coord_type='generic')
# Or Delaunay for natural neighbors
sq.gr.spatial_neighbors(adata, delaunay=True, coord_type='generic')
```

**R:**
```r
# Radius-based
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 10)
# Or Delaunay
seurat_obj <- CreateSpatialNeighborsDelaunay(seurat_obj)
```

### DBiT-seq

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 4-8 | Microfluidic channel dependent |
| `radius` | 1-2 pixels | Depends on pixel size |
| Method | Grid | Regular grid pattern |

**Python:**
```python
sq.gr.spatial_neighbors(adata, n_neighs=4, coord_type='grid')
```

**R:**
```r
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 4)
```

---

## Output Structure

### Python (AnnData)

After running `sq.gr.spatial_neighbors()`, the following are added to `adata`:

```python
# Sparse connectivity matrix (n_obs × n_obs)
adata.obsp['spatial_connectivities']
# - Binary matrix (0/1) indicating neighbor relationships
# - Symmetric: if A is neighbor of B, B is neighbor of A

# Sparse distance matrix (n_obs × n_obs)
adata.obsp['spatial_distances']
# - Contains actual distances between connected spots
# - Distance units match coordinate units (microns or pixels)

# Graph parameters
adata.uns['spatial_neighbors']
# - 'connectivities_key': Key in obsp
# - 'distances_key': Key in obsp
# - 'params': Parameters used to build graph
```

### R (Seurat)

After running `CreateSpatialNeighbors()`, the following are added to `@misc`:

```r
# Access the neighbor graph
seurat_obj@misc$spatial_neighbors

# Structure:
# $connectivities: Sparse connectivity matrix (n_spots × n_spots)
# $distances: Sparse distance matrix (n_spots × n_spots)
# $params: List of parameters used
#   - method: "knn", "radius", or "delaunay"
#   - n_neighbors: Number of neighbors (KNN only)
#   - radius: Distance threshold (radius only)
#   - coords: Coordinate columns used
# $stats: Graph statistics
#   - n_spots: Number of spots
#   - n_edges: Number of edges
#   - mean_degree: Mean neighbors per spot
#   - median_degree: Median neighbors per spot
```

**Accessing specific elements:**

```r
# Connectivity matrix
conn <- seurat_obj@misc$spatial_neighbors$connectivities

# Distance matrix
dist <- seurat_obj@misc$spatial_neighbors$distances

# Parameters
params <- seurat_obj@misc$spatial_neighbors$params
print(params$method)  # "knn"
print(params$n_neighbors)  # 6

# Statistics
stats <- seurat_obj@misc$spatial_neighbors$stats
print(stats$mean_degree)  # Average neighbors per spot
```

---

## Visualization

### Python

```python
import squidpy as sq

# Plot spatial graph with connectivity
sq.pl.spatial_scatter(
    adata,
    connectivity_key="spatial_connectivities",
    edges_color="black",
    edges_width=0.2,
    shape=None
)
```

### R

```r
source("scripts/r/visualization.R")

# Plot the spatial neighbor graph
p <- PlotSpatialNeighborGraph(
  seurat_obj,
  spot_size = 1,
  edge_alpha = 0.2,
  title = "Spatial Neighbor Graph (KNN-6)"
)
print(p)

# Plot degree distribution
PlotNeighborDegree(seurat_obj, plot_type = "histogram")

# Plot distance distribution
PlotNeighborDistance(seurat_obj)

# Compare two methods
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 6, assay = "knn")
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 50, assay = "radius")

CompareNeighborGraphs(seurat_obj, assay1 = "knn", assay2 = "radius")
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. No coordinates found

**Error:**
```
Coordinates not found. Expected columns: imagerow, imagecol
```

**Solution:**
```r
# Check available columns in metadata
colnames(seurat_obj@meta.data)

# For Visium, try getting from images slot
img_name <- names(seurat_obj@images)[1]
coords <- seurat_obj@images[[img_name]]@coordinates

# Or specify custom coordinate columns
seurat_obj <- CreateSpatialNeighbors(
  seurat_obj,
  coords = c("row", "col")  # Your coordinate columns
)
```

#### 2. No matching cell IDs

**Error:**
```
No matching cell IDs between coordinates and Seurat object
```

**Solution:**
```r
# Check that rownames of coordinates match colnames of Seurat
head(rownames(coord_matrix))
head(colnames(seurat_obj))

# Ensure they match
rownames(coord_matrix) <- colnames(seurat_obj)
```

#### 3. All spots isolated (radius too small)

**Warning:**
```
No neighbors found with given radius. Try increasing radius.
```

**Solution:**
```r
# Check typical spot spacing
coord_matrix <- GetSpatialCoordinates(seurat_obj)
knn_result <- FNN::get.knn(coord_matrix, k = 1)
median_spacing <- median(knn_result$nn.dist)
print(paste("Median spot spacing:", median_spacing))

# Use radius > median spacing
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = median_spacing * 2)
```

#### 4. Memory issues with large datasets

**Problem:** Large distance matrix causes memory error.

**Solution:**
```r
# Use KNN instead of radius (more memory efficient)
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 6)

# Or use smaller radius
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 50)

# For very large datasets, subset first
seurat_subset <- subset(seurat_obj, cells = sample(Cells(seurat_obj), 10000))
```

#### 5. FNN package not found (R)

**Error:**
```
FNN package required. Install with: install.packages('FNN')
```

**Solution:**
```r
install.packages("FNN")
# Also install other dependencies
install.packages(c("deldir", "Matrix", "ggplot2", "patchwork"))
```

#### 6. Squidpy import error (Python)

**Error:**
```
ImportError: No module named 'squidpy'
```

**Solution:**
```bash
pip install squidpy scanpy
```

#### 7. Coordinate scale issues

**Problem:** Neighbor distances seem wrong (too large or too small).

**Solution:**
```python
# Check coordinate scale
print(adata.obsm['spatial'][:5])

# Check if coordinates are in pixels or microns
# If needed, convert scale
adata.obsm['spatial'] = adata.obsm['spatial'] * scale_factor  # Convert pixels to microns
```

---

## Complete Examples

### Example 1: Visium Analysis Pipeline (Python)

```python
import scanpy as sc
import squidpy as sq

# Load Visium data
adata = sc.read_visium("./filtered_feature_bc_matrix/")

# Preprocess
sc.pp.filter_genes(adata, min_cells=3)
sc.pp.normalize_total(adata)
sc.pp.log1p(adata)

# Build neighbor graph (6 neighbors for hexagonal grid)
sq.gr.spatial_neighbors(adata, n_neighs=6, coord_type='grid')

# Spatial statistics
sq.gr.spatial_autocorr(adata, mode="moranI")

# Leiden clustering on spatial graph
sc.pp.pca(adata)
sc.pp.neighbors(adata, use_rep='X_pca')
sc.tl.leiden(adata)

# Plot
sq.pl.spatial_scatter(adata, color="leiden")
```

### Example 2: Slide-seq Analysis Pipeline (R)

```r
library(Seurat)
source("scripts/r/spatial_neighbors.R")
source("scripts/r/visualization.R")

# Load Slide-seq data
seurat_obj <- LoadSlideSeq("./slideseq_data/")

# Build radius-based neighbor graph (15 μm radius)
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 15)

# Visualize
PlotSpatialNeighborGraph(seurat_obj, title = "Slide-seq Neighbor Graph")

# Use graph for downstream analysis (e.g., spatial DE)
# ...
```

### Example 3: Comparing Methods (R)

```r
# Build graphs with different methods
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 6, assay = "knn6")
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 10, assay = "knn10")
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 100, assay = "radius100")

# Compare statistics
cat("KNN-6:\n")
print(seurat_obj@misc$knn6$stats)

cat("\nKNN-10:\n")
print(seurat_obj@misc$knn10$stats)

cat("\nRadius-100:\n")
print(seurat_obj@misc$radius100$stats)

# Visualize comparison
CompareNeighborGraphs(seurat_obj, assay1 = "knn6", assay2 = "radius100")
```

---

## Related Skills

- [bio-spatial-transcriptomics-statistics](../bio-spatial-transcriptomics-statistics) - Use neighbor graph for spatial statistics
- [bio-spatial-transcriptomics-domains](../bio-spatial-transcriptomics-domains) - Identify domains using spatial graph
- [bio-spatial-transcriptomics-niches](../bio-spatial-transcriptomics-niches) - Identify tissue niches
- [bio-spatial-transcriptomics-layers](../bio-spatial-transcriptomics-layers) - Spatial layer analysis (formerly in this skill)

---

## References

1. Palla et al. (2022). Squidpy: a scalable toolkit for spatial omics analysis. *Nature Methods*, 19, 171-178.
2. Cable et al. (2022). Robust decomposition of cell type mixtures in spatial transcriptomics. *Nature Methods*, 19, 711-718.
3. Satija Lab Seurat: https://satijalab.org/seurat/
