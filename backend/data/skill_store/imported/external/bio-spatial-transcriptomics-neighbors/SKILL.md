---
name: bio-spatial-transcriptomics-neighbors
description: Build spatial neighbor graphs for spatial transcriptomics data. Compute k-nearest neighbors, Delaunay triangulation, and radius-based connectivity for downstream spatial analyses using Squidpy (Python) or custom functions (R). Use when building spatial neighborhood graphs.
tool_type: multi
primary_tool: squidpy
supported_tools: [scanpy, numpy, scikit-learn, scipy, Seurat, FNN, deldir]
languages: [python, r]
keywords: ["spatial", "neighbors", "graph", "Squidpy", "Delaunay", "connectivity", "spatial-network", "KNN", "radius"]
---

## Version Compatibility

Reference examples tested with: matplotlib 3.8+, numpy 1.26+, scanpy 1.10+, scikit-learn 1.4+, scipy 1.12+, squidpy 1.3+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

## Quick Selector

### Method Comparison

| Method | Neighbor Selection | Best For | Key Features |
|--------|-------------------|----------|--------------|
| **KNN** | Fixed count (k) | Regular grids, general use | Exactly k neighbors per spot |
| **Delaunay** | Natural neighbors | Irregular layouts | Adaptive to local density |
| **Radius** | Distance threshold | Variable density | All spots within radius |
| **Grid** | Hexagonal rings | Visium data | Matches Visium grid structure |

### Selection Guide

| Your Situation | Recommended Method | Why |
|----------------|-------------------|-----|
| Visium data | Grid (n_rings=1) | Matches hexagonal grid (6 neighbors) |
| Irregular spots | Delaunay | Natural neighbor selection |
| Variable density | Radius | Consistent spatial scale |
| High-density data | KNN | Fixed neighborhood size |


### Data State Reference

| State | Description | This Skill |
|-------|-------------|------------|
| [Spatial] | Spatial coordinates in `obsm['spatial']` | Required input |
| [Neighbors] | Spatial neighbor graph in `obsp` | Output from all methods |

## Platform-Specific Parameters

### 10x Visium

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 6 | Hexagonal grid has 6 neighbors |
| `radius` | 1 spot | Immediate neighbors only |
| Method | `grid` | Fixed grid structure |

```python
# Visium standard
sq.gr.spatial_neighbors(adata, n_neighs=6, coord_type='grid')
```

### 10x Visium HD

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 8-12 | 2x2 um bins, more neighbors needed |
| `radius` | 2-4 bins | Consider 2-bin radius |
| Method | `radius` | Distance-based |

```python
# Visium HD with 2um bins
sq.gr.spatial_neighbors(adata, radius=8, coord_type='generic')  # 8um = ~4 bins
```

### Stereo-seq

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 4 | Square grid (4 immediate) or 8 (including diagonal) |
| `radius` | 1-2 bins | Depends on bin size (0.5-1 um typical) |
| Method | `grid` or `radius` | Grid for regular arrays |

```python
# Stereo-seq with 0.5um bins
sq.gr.spatial_neighbors(adata, n_neighs=4, coord_type='grid')
```

### Slide-seq / Slide-seqV2

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 5-10 | Near-single-cell resolution |
| `radius` | 10-20 um | Based on cell diameter |
| Method | `radius` | Distance-based |

```python
# Slide-seq
sq.gr.spatial_neighbors(adata, radius=15, coord_type='generic')
```

### MERFISH / seqFISH

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 3-7 | Subcellular resolution |
| `radius` | 5-15 um | Based on expected cell size |
| Method | `radius` or `Delaunay` | Irregular positions |

```python
# MERFISH
sq.gr.spatial_neighbors(adata, radius=10, coord_type='generic')
# Or Delaunay for natural neighbors
sq.gr.spatial_neighbors(adata, delaunay=True, coord_type='generic')
```

### DBiT-seq

| Parameter | Recommended Value | Rationale |
|-----------|------------------|-----------|
| `n_neighbors` | 4-8 | Microfluidic channel dependent |
| `radius` | 1-2 pixels | Depends on pixel size |
| Method | `grid` | Regular grid pattern |

```python
# DBiT-seq
sq.gr.spatial_neighbors(adata, n_neighs=4, coord_type='grid')
```

### Summary Table

| Platform | coord_type | n_neighs | radius | Typical Use |
|----------|------------|----------|--------|-------------|
| Visium | 'grid' | 6 | - | Standard ST |
| Visium HD | 'generic' | 8-12 | 8-16 | High resolution |
| Stereo-seq | 'grid' | 4-8 | - | Subcellular |
| Slide-seq | 'generic' | 5-10 | 10-20 | Single-cell |
| MERFISH | 'generic' | 3-7 | 5-15 | Imaging-based |
| DBiT-seq | 'grid' | 4-8 | - | Microfluidic |

---

**"Build a spatial neighborhood graph"** → Construct spatial connectivity graphs using k-nearest neighbors, Delaunay triangulation, or radius-based methods for downstream spatial statistics.
- Python: `squidpy.gr.spatial_neighbors(adata, coord_type='generic', n_neighs=6)`

Build spatial neighbor graphs for connectivity-based analyses.

## Required Imports

### Python

```python
import squidpy as sq
import scanpy as sc
import numpy as np
```

### R

```r
source("scripts/r/spatial_neighbors.R")
source("scripts/r/visualization.R")
```

## Build K-Nearest Neighbors Graph

**Goal:** Construct a spatial KNN graph connecting each spot to its nearest spatial neighbors.

**Input State:** [Spatial] (coordinates in `obsm['spatial']` or Seurat images slot)
**Output State:** [Neighbors] (spatial graph in `obsp['spatial_connectivities']` or `@misc$spatial_neighbors`)

**Approach:** Use Squidpy's `spatial_neighbors` (Python) or `CreateSpatialNeighbors()` (R) with k-nearest neighbors on coordinate distances.

### Python

```python
# Build spatial KNN graph
sq.gr.spatial_neighbors(adata, n_neighs=6, coord_type='generic')

# Check the graph
print(f"Connectivities shape: {adata.obsp['spatial_connectivities'].shape}")
print(f"Distances shape: {adata.obsp['spatial_distances'].shape}")
```

### R

```r
# Build spatial KNN graph (k=6 for Visium hexagonal grid)
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 6)

# Check the graph
SummarizeSpatialNeighbors(seurat_obj)
# Output: Method: knn, Spots: 2987, Edges: 8961, Mean degree: 6.0
```

## Build Delaunay Triangulation Graph

### Python

```python
# Delaunay triangulation (natural neighbors)
sq.gr.spatial_neighbors(adata, delaunay=True, coord_type='generic')
```

### R

```r
# Delaunay triangulation for irregular spot layouts
seurat_obj <- CreateSpatialNeighborsDelaunay(seurat_obj)
```

## Radius-Based Neighbors

### Python

```python
# Connect all spots within a radius
sq.gr.spatial_neighbors(adata, radius=100, coord_type='generic')
```

### R

```r
# Connect spots within 100 microns
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 100)

# For high-resolution data (Visium HD, Slide-seq)
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 15)
```

## For Visium Data (Grid Structure)

### Python

```python
# For Visium hexagonal grid, use n_rings
sq.gr.spatial_neighbors(adata, n_rings=1, coord_type='grid')  # 6 immediate neighbors
sq.gr.spatial_neighbors(adata, n_rings=2, coord_type='grid')  # Extended neighborhood
```

### R

```r
# Visium immediate neighbors (6 neighbors for hexagonal grid)
seurat_obj <- CreateGridNeighbors(seurat_obj, n_rings = 1)

# Extended neighborhood (18 neighbors with 2 rings)
seurat_obj <- CreateGridNeighbors(seurat_obj, n_rings = 2)
```

## Access Neighbor Information

### Python

```python
# Get connectivities as sparse matrix
conn = adata.obsp['spatial_connectivities']
print(f'Edges in graph: {conn.nnz}')
print(f'Mean neighbors per spot: {conn.nnz / adata.n_obs:.1f}')

# Get distances
dist = adata.obsp['spatial_distances']
nonzero_dist = dist.data[dist.data > 0]
print(f'Mean neighbor distance: {nonzero_dist.mean():.1f}')
```

### R

```r
# Access neighbor graph from Seurat object
conn <- seurat_obj@misc$spatial_neighbors$connectivities
dist <- seurat_obj@misc$spatial_neighbors$distances

# Get statistics
stats <- seurat_obj@misc$spatial_neighbors$stats
print(stats$n_spots)      # Number of spots
print(stats$n_edges)      # Number of edges
print(stats$mean_degree)  # Average neighbors per spot

# Get neighbors for a specific spot
neighbors <- GetSpatialNeighbors(seurat_obj, spot_id = "AAACCCAAGAAACTGA-1")
head(neighbors)
```

## Get Neighbors for a Specific Spot

### Python

```python
from scipy.sparse import csr_matrix

spot_idx = 0
conn = adata.obsp['spatial_connectivities']

# Get neighbor indices
neighbor_indices = conn[spot_idx].nonzero()[1]
print(f'Spot {spot_idx} has {len(neighbor_indices)} neighbors: {neighbor_indices}')

# Get distances to neighbors
dist = adata.obsp['spatial_distances']
neighbor_distances = dist[spot_idx, neighbor_indices].toarray().flatten()
print(f'Distances: {neighbor_distances}')
```

### R

```r
# Get neighbors for a specific spot by ID
spot_id <- colnames(seurat_obj)[1]
neighbors <- GetSpatialNeighbors(seurat_obj, spot_id = spot_id)
print(neighbors)
# Output: data.frame with neighbor IDs and distances

# Access graph directly for custom analysis
conn <- seurat_obj@misc$spatial_neighbors$connectivities
spot_idx <- 1
neighbor_indices <- which(conn[spot_idx, ] > 0)
print(paste("Spot", spot_idx, "has", length(neighbor_indices), "neighbors"))
```

## Build Expression-Based Neighbors

```python
# Standard expression-based neighbors (for comparison)
sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)

# Now adata has both:
# - adata.obsp['spatial_connectivities'] (spatial)
# - adata.obsp['connectivities'] (expression)
```

## Combine Spatial and Expression Neighbors

**Goal:** Create a unified neighbor graph that balances spatial proximity with expression similarity.

**Input State:** [Spatial] + [Normalized] + [PCA]
**Output State:** [Neighbors] (combined graph in `obsp['combined_connectivities']`)

**Approach:** Build separate spatial and expression neighbor graphs, normalize each, then combine with a tunable weight parameter.

```python
# Build both graphs
sq.gr.spatial_neighbors(adata, n_neighs=6, coord_type='generic')
sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)

# Weighted combination (manual)
alpha = 0.5  # Weight for spatial vs expression
spatial_conn = adata.obsp['spatial_connectivities']
expr_conn = adata.obsp['connectivities']

# Normalize and combine
from sklearn.preprocessing import normalize
spatial_norm = normalize(spatial_conn, norm='l1', axis=1)
expr_norm = normalize(expr_conn, norm='l1', axis=1)
combined = alpha * spatial_norm + (1 - alpha) * expr_norm

adata.obsp['combined_connectivities'] = combined
```

## Visualize Neighbor Graph

**Goal:** Display the spatial neighbor graph overlaid on tissue coordinates for visual inspection.

**Input State:** [Neighbors] + [Spatial]
**Output State:** [Neighbors] (visualization only)

**Approach:** Draw edges between connected spots and scatter plot the spot positions.

### Python

```python
import matplotlib.pyplot as plt

# Get coordinates
coords = adata.obsm['spatial']
conn = adata.obsp['spatial_connectivities']

fig, ax = plt.subplots(figsize=(10, 10))

# Draw edges
rows, cols = conn.nonzero()
for i, j in zip(rows, cols):
    if i < j:  # Avoid drawing twice
        ax.plot([coords[i, 0], coords[j, 0]], [coords[i, 1], coords[j, 1]], 'k-', alpha=0.1, linewidth=0.5)

# Draw nodes
ax.scatter(coords[:, 0], coords[:, 1], s=10, c='blue', alpha=0.5)
ax.set_aspect('equal')
plt.title('Spatial neighbor graph')
```

### R

```r
# Plot spatial neighbor graph overlay
p <- PlotSpatialNeighborGraph(seurat_obj, spot_size = 1, edge_alpha = 0.2)
print(p)

# Plot degree distribution
PlotNeighborDegree(seurat_obj, plot_type = "histogram")

# Plot distance distribution
PlotNeighborDistance(seurat_obj)
```

## Compute Graph Statistics

**Goal:** Calculate summary statistics of the spatial neighbor graph (nodes, edges, connectivity).

**Input State:** [Neighbors]
**Output State:** [Neighbors] (metrics computed)

**Approach:** Convert the sparse connectivity matrix to a NetworkX graph (Python) or access stored stats (R).

### Python

```python
import networkx as nx
from scipy.sparse import csr_matrix

conn = adata.obsp['spatial_connectivities']
G = nx.from_scipy_sparse_array(conn)

print(f'Nodes: {G.number_of_nodes()}')
print(f'Edges: {G.number_of_edges()}')
print(f'Average degree: {2 * G.number_of_edges() / G.number_of_nodes():.2f}')
print(f'Connected components: {nx.number_connected_components(G)}')
```

### R

```r
# Print summary statistics
SummarizeSpatialNeighbors(seurat_obj)
# Output:
# Spatial Neighbor Graph Summary
# ==============================
# Method: knn
# KNN k: 6
# Spots: 2987
# Edges: 8961
# Mean degree: 6.00
# Median degree: 6.00

# Access stats programmatically
stats <- seurat_obj@misc$spatial_neighbors$stats
params <- seurat_obj@misc$spatial_neighbors$params
```

## Store Multiple Neighbor Graphs

### Python

```python
# Store different neighborhood sizes
for n_neighs in [4, 6, 10]:
    sq.gr.spatial_neighbors(adata, n_neighs=n_neighs, coord_type='generic')
    adata.obsp[f'spatial_conn_{n_neighs}'] = adata.obsp['spatial_connectivities'].copy()
    adata.obsp[f'spatial_dist_{n_neighs}'] = adata.obsp['spatial_distances'].copy()
```

### R

```r
# Store multiple neighbor graphs with different parameters
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 6, assay = "knn6")
seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 10, assay = "knn10")
seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 100, assay = "radius100")

# Access different graphs
conn_knn6 <- seurat_obj@misc$knn6$connectivities
conn_knn10 <- seurat_obj@misc$knn10$connectivities
conn_radius <- seurat_obj@misc$radius100$connectivities

# Compare statistics
SummarizeSpatialNeighbors(seurat_obj, assay = "knn6")
SummarizeSpatialNeighbors(seurat_obj, assay = "knn10")
SummarizeSpatialNeighbors(seurat_obj, assay = "radius100")
```


## Related Skills

- [bio-spatial-transcriptomics-layers](../bio-spatial-transcriptomics-layers) - Spatial layer analysis around ROIs (e.g., peritumoral zones, perineural regions)
- [bio-spatial-transcriptomics-statistics](../bio-spatial-transcriptomics-statistics) - Statistical analysis using neighbor graphs
- [bio-spatial-transcriptomics-domains](../bio-spatial-transcriptomics-domains) - Spatial domain identification
- [bio-spatial-transcriptomics-niches](../bio-spatial-transcriptomics-niches) - Niche identification and analysis
