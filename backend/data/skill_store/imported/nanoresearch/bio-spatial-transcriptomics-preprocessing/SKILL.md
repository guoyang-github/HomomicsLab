---
name: bio-spatial-transcriptomics-preprocessing
description: Quality control, filtering, normalization, and spatial analysis for spatial transcriptomics (10x Visium) using Seurat (R) and Scanpy/Squidpy (Python). Use for loading Visium data, calculating spatial QC metrics, filtering spots, normalizing counts with SCTransform, dimensionality reduction and clustering, spatial visualization, detecting spatially variable features, and merging multiple slices.
tool_type: mixed
primary_tool: Seurat
supported_tools: [scanpy, squidpy, matplotlib]
keywords: ["spatial-transcriptomics", "visium", "preprocessing", "QC", "normalization", "SCTransform", "spatial-variable-features", "10x-visium"]
---

## Version Compatibility

Reference examples tested with: Seurat 5.x+, SeuratData 0.2.x+, ggplot2 3.5+, scanpy 1.10+, squidpy 1.6+, matplotlib 3.8+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

> **Seurat v5+ spatial note:** In Seurat v5, spatial coordinates are no longer stored
directly in `meta.data` and are instead located in the spatial image structure
(`object[["slice1"]]@boundaries`). The high-level functions below work the same in
v4 and v5, but direct slot access differs.

## Skill Scope Definition

### What This Skill Covers
- Loading 10x Visium Space Ranger output (`Load10X_Spatial`)
- Spatial QC metrics calculation (`nCount_Spatial`, `nFeature_Spatial`, image coverage)
- Filtering spots by UMI/feature counts and tissue boundaries
- Normalization (SCTransform optimized for spatial, LogNormalize)
- Dimensionality reduction (PCA), clustering, and UMAP on spatial data
- Spatial visualization (`SpatialFeaturePlot`, `SpatialDimPlot`)
- Spatially variable feature detection (Moran's I, mark variogram)
- Merging multiple spatial slices and joint analysis

### What This Skill Does NOT Cover
- **Non-standard data format conversion** (GEO h5 + spatial.tar.gz manual reconstruction)
  → Use [bio-spatial-transcriptomics-data-io](../bio-spatial-transcriptomics-data-io/)
- **Single-cell reference integration / label transfer** → Downstream analysis skill
- **Deconvolution (RCTD, SPOTlight, etc.)** → Downstream analysis skill
- **Advanced spatial statistics** (SVG, Trendsceek, SPARK-X) → Dedicated spatial analysis skill

### Workflow Position

```
[data-io] → [ST-preprocessing] → [ST-deconvolution / ST-annotation / ST-spatial-analysis]
  Load    →   QC, Normalize,    →   Label transfer, Cell type
  Spatial     Cluster, Visualize     mapping, SVG analysis
```

### Input/Output State Mapping

| State | From | To | Description |
|-------|------|-----|-------------|
| [Raw] | data-io | - | Raw Visium counts + H&E image |
| [QC] | preprocessing | preprocessing | Calculated nCount_Spatial, nFeature_Spatial |
| [Filtered] | preprocessing | preprocessing | After spot filtering by QC/image |
| [Normalized] | preprocessing | preprocessing | After SCTransform / LogNormalize |
| [Clustered] | preprocessing | preprocessing | PCA + UMAP + clusters assigned |
| [Spatial-Features] | preprocessing | downstream | Spatially variable features detected |
| [Merged] | preprocessing | downstream | Multi-slice integrated |

# Spatial Transcriptomics Preprocessing

**"Preprocess my Visium spatial data"** → Load Visium output, compute spatial QC metrics, filter low-quality spots, normalize with SCTransform, cluster spots, visualize on tissue, and detect spatially variable genes.
- Python: `squidpy.read.visium()` → QC → `sc.pp.normalize_total()` → `sc.pp.log1p()` → PCA → neighbors → leiden → UMAP → `sq.pl.spatial_scatter()`
- R: `Seurat::Load10X_Spatial()` → QC → `SCTransform()` → `RunPCA()` → `FindNeighbors()` → `FindClusters()` → `RunUMAP()` → `SpatialDimPlot()`

## Scanpy / Squidpy (Python)

**Goal:** Preprocess 10x Visium spatial transcriptomics data through QC filtering, normalization, dimensionality reduction, clustering, and spatial visualization.

**Approach:** Load Visium data with Squidpy, calculate spatial QC metrics, filter low-quality spots, normalize and log-transform, identify highly variable genes, scale, run PCA and clustering, and visualize gene expression and clusters on the tissue image.

### Required Imports

```python
import scanpy as sc
import squidpy as sq
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
```

### Load Visium Data

```python
# Load standard Space Ranger output
> **Note:** `sq.read.visium()` was removed in squidpy 1.6+. Use `sc.read_visium()` (scanpy 1.10+) instead.  
> Parameter mapping: `counts_file` (plural) → `count_file` (singular).

```python
adata = sc.read_visium(
    path="spatial/",
    count_file="filtered_feature_bc_matrix.h5",
    library_id="sample1"
)
```

# Key slots populated:
# - adata.X: gene expression matrix
# - adata.obsm['spatial']: spot spatial coordinates (pixel space)
# - adata.uns['spatial']['sample1']['images']['hires']: H&E image
```

### Calculate QC Metrics

```python
# Calculate mitochondrial and spatial QC metrics
adata.var['mt'] = adata.var_names.str.startswith('MT-')
sc.pp.calculate_qc_metrics(
    adata, qc_vars=['mt'], percent_top=None, log1p=False, inplace=True
)

# Key metrics added to adata.obs:
# - n_genes_by_counts: genes detected per spot
# - total_counts: total UMI counts per spot
# - pct_counts_mt: percentage mitochondrial
# - in_tissue: whether spot is within tissue (from Space Ranger)
```

### Visualize QC Metrics

```python
# Violin plots
sc.pl.violin(adata, ['n_genes_by_counts', 'total_counts', 'pct_counts_mt'],
             jitter=0.4, multi_panel=True)

# Spatial QC plots
sq.pl.spatial_scatter(adata, color='total_counts', library_id='sample1',
                      size=1.5, cmap='viridis')
```

### Filter Spots

```python
# Filter spots outside tissue (if not already filtered by Space Ranger)
adata = adata[adata.obs['in_tissue'] == 1].copy()

# Filter by QC metrics
# Note: spatial thresholds are typically more lenient than single-cell
# because spots may contain multiple cells
sc.pp.filter_cells(adata, min_genes=100)
adata = adata[adata.obs['total_counts'] > 200, :].copy()
adata = adata[adata.obs['pct_counts_mt'] < 20, :].copy()

print(f'After filtering: {adata.n_obs} spots, {adata.n_vars} genes')
```

### Store Raw Counts

```python
# Store raw counts before normalization
adata.raw = adata.copy()
# Or use layers
adata.layers['counts'] = adata.X.copy()
```

### Normalization

```python
# Library size normalization + log transform
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
```

### Highly Variable Genes

```python
# Identify highly variable genes
sc.pp.highly_variable_genes(adata, n_top_genes=2000, flavor='seurat')

# Visualize
sc.pl.highly_variable_genes(adata)
print(f'HVGs: {adata.var.highly_variable.sum()}')
```

### Scaling

```python
# Scale to unit variance and zero mean
sc.pp.scale(adata, max_value=10)
```

### Dimensionality Reduction and Clustering

```python
# PCA
sc.pp.pca(adata, n_comps=50, use_highly_variable=True)
sc.pl.pca_variance_ratio(adata, n_pcs=50)

# Neighbors and clustering
sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
sc.tl.leiden(adata, resolution=0.8)

# UMAP
sc.tl.umap(adata)
```

### Spatial Visualization

```python
# Gene expression on tissue
sq.pl.spatial_scatter(adata, color=['leiden', 'total_counts'],
                      library_id='sample1', size=1.5, ncols=2)

# Specific gene expression
sq.pl.spatial_scatter(adata, color='GENE_NAME', library_id='sample1',
                      size=1.5, cmap='viridis')

# Compare with UMAP
sc.pl.umap(adata, color='leiden')
```

### Spatially Variable Features

```python
# Compute spatial autocorrelation with Moran's I
sq.gr.spatial_autocorr(adata, mode='moran', genes=adata.var_names[:100])
# Results stored in adata.uns['moranI']

# Alternatively, compute for selected genes
sq.gr.spatial_autocorr(adata, mode='moran', genes=adata.var_names[adata.var.highly_variable][:50])

# Top spatially variable genes
moran_df = adata.uns['moranI'].copy()
moran_df = moran_df.sort_values('I', ascending=False)
print(moran_df.head(10))

# Visualize top spatially variable genes
top_svgs = moran_df.head(6).index.tolist()
sq.pl.spatial_scatter(adata, color=top_svgs, library_id='sample1',
                      size=1.5, ncols=3, cmap='viridis')
```

### Complete Preprocessing Pipeline

**Goal:** Run end-to-end preprocessing from raw Visium data to analysis-ready spatial object.

**Approach:** Load Visium data, compute QC, filter, normalize, select HVGs, scale, run PCA and clustering, and visualize.

```python
import scanpy as sc
import squidpy as sq

# Load
adata = sc.read_visium(path="spatial/", library_id="sample1")

# QC
adata.var['mt'] = adata.var_names.str.startswith('MT-')
sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], inplace=True)

# Filter
adata = adata[adata.obs['in_tissue'] == 1].copy()
sc.pp.filter_cells(adata, min_genes=100)
adata = adata[adata.obs['total_counts'] > 200, :].copy()

# Store raw
adata.raw = adata.copy()

# Normalize
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# HVGs
sc.pp.highly_variable_genes(adata, n_top_genes=2000)

# Scale
sc.pp.scale(adata, max_value=10)

# PCA + Clustering
sc.pp.pca(adata, use_highly_variable=True)
sc.pp.neighbors(adata, n_pcs=30)
sc.tl.leiden(adata, resolution=0.8)
sc.tl.umap(adata)

# Spatial visualization
sq.pl.spatial_scatter(adata, color=['leiden'], library_id='sample1', size=1.5)
```

---

## Seurat (R)

**Goal:** Preprocess 10x Visium spatial transcriptomics data through QC filtering, normalization, clustering, and spatial visualization using Seurat.

**Approach:** Load Visium data with `Load10X_Spatial`, visualize spatial QC, filter spots, normalize with SCTransform (recommended for spatial), run standard clustering workflow, and detect spatially variable features.

### Required Libraries

```r
library(Seurat)
library(ggplot2)
```

### Load Visium Data

```r
# Load standard Space Ranger output
spatial_obj <- Load10X_Spatial(
    data.dir = "spatial/",
    filename = "filtered_feature_bc_matrix.h5",
    assay = "Spatial",
    slice = "slice1"
)

# Key slots populated:
# - spatial_obj@assays$Spatial: expression matrix
# - spatial_obj@images$slice1: H&E image and spot coordinates
```

### Calculate and Visualize QC Metrics

```r
# Note: Spatial data uses nCount_Spatial and nFeature_Spatial instead of nCount_RNA
# These are added automatically by Load10X_Spatial

# Violin plots of spatial QC
plot1 <- VlnPlot(spatial_obj, features = c("nCount_Spatial", "nFeature_Spatial"),
                 ncol = 2, pt.size = 0)

# Spatial QC plots - show UMI distribution on tissue
plot2 <- SpatialFeaturePlot(spatial_obj, features = "nCount_Spatial")
plot3 <- SpatialFeaturePlot(spatial_obj, features = "nFeature_Spatial")

# Note: variance in molecular counts per spot is often substantial and reflects
# biological differences in cell density across tissue regions, not just technical noise.
```

### Filter Spots

```r
# Filter by spatial QC metrics
# Thresholds are typically more lenient than single-cell due to multi-cell spots
spatial_obj <- subset(
    spatial_obj,
    subset = nCount_Spatial > 200 &
             nFeature_Spatial > 100
)

cat("After filtering:", ncol(spatial_obj), "spots\n")
```

### Normalization (SCTransform - Recommended)

```r
# SCTransform is recommended for spatial data as it better handles the
# biological variance in counts per spot due to varying cell density

# For Seurat v5, set return.only.var.genes = FALSE to retain all genes
# for downstream analysis (e.g., deconvolution)
spatial_obj <- SCTransform(
    spatial_obj,
    assay = "Spatial",
    vars.to.regress = "percent.mt",
    return.only.var.genes = FALSE,
    verbose = FALSE
)
```

### Normalization (Log Normalization - Alternative)

```r
# Standard log normalization (not recommended as primary method for spatial)
spatial_obj <- NormalizeData(spatial_obj, assay = "Spatial",
                              normalization.method = "LogNormalize",
                              scale.factor = 10000)
spatial_obj <- FindVariableFeatures(spatial_obj, selection.method = "vst",
                                     nfeatures = 2000)
```

### Dimensionality Reduction and Clustering

```r
# Run standard single-cell workflow on SCT assay
spatial_obj <- RunPCA(spatial_obj, assay = "SCT")
spatial_obj <- FindNeighbors(spatial_obj, reduction = "pca", dims = 1:30)
spatial_obj <- FindClusters(spatial_obj, resolution = 0.8)
spatial_obj <- RunUMAP(spatial_obj, reduction = "pca", dims = 1:30)
```

### Spatial Visualization

```r
# Clusters on tissue
SpatialDimPlot(spatial_obj, label = TRUE, pt.size.factor = 1.6)

# Gene expression on tissue
SpatialFeaturePlot(spatial_obj, features = c("GENE1", "GENE2"),
                   pt.size.factor = 1.6, alpha = c(0.1, 1))

# UMAP for comparison
DimPlot(spatial_obj, reduction = "umap", label = TRUE)
```

### Highlight Specific Spots

```r
# Highlight spots from specific clusters
SpatialDimPlot(
    spatial_obj,
    cells.highlight = CellsByIdentities(spatial_obj, idents = c(1, 2)),
    facet.highlight = TRUE,
    ncol = 2
)
```

### Spatially Variable Features

```r
# Find features that vary spatially using Moran's I (recommended)
spatial_obj <- FindSpatiallyVariableFeatures(
    spatial_obj,
    assay = "SCT",
    selection.method = "moransi",
    features = VariableFeatures(spatial_obj)[1:1000],
    nfeatures = 50
)

# Alternatively, mark variogram (default, inspired by Trendsceek)
# spatial_obj <- FindSpatiallyVariableFeatures(
#     spatial_obj, assay = "SCT",
#     selection.method = "markvariogram",
#     features = VariableFeatures(spatial_obj)[1:1000]
# )

# View top spatially variable features
top_svgs <- SpatiallyVariableFeatures(spatial_obj, selection.method = "moransi")
head(top_svgs)

# Visualize top SVGs
SpatialFeaturePlot(spatial_obj, features = head(top_svgs, 6),
                   ncol = 3, pt.size.factor = 1.6)
```

### Merging Multiple Slices

```r
# Load multiple slices
slice1 <- Load10X_Spatial(data.dir = "sample1/", slice = "sample1")
slice2 <- Load10X_Spatial(data.dir = "sample2/", slice = "sample2")

# Merge with cell IDs to avoid name conflicts
merged <- merge(slice1, y = slice2,
                add.cell.ids = c("S1", "S2"))

# Set combined variable features for joint analysis
VariableFeatures(merged) <- c(VariableFeatures(slice1),
                               VariableFeatures(slice2))

# Run joint preprocessing
merged <- SCTransform(merged, assay = "Spatial", verbose = FALSE)
merged <- RunPCA(merged)
merged <- FindNeighbors(merged, dims = 1:30)
merged <- FindClusters(merged, resolution = 0.8)
merged <- RunUMAP(merged, dims = 1:30)

# Visualize all slices
SpatialDimPlot(merged)  # automatically facets by slice
```

### Complete Preprocessing Pipeline (SCTransform)

**Goal:** Run end-to-end Seurat spatial preprocessing with SCTransform.

**Approach:** Load Visium data, compute spatial QC, filter, apply SCTransform, run clustering, visualize on tissue, and detect spatially variable features.

```r
library(Seurat)

# Load
spatial_obj <- Load10X_Spatial(
    data.dir = "spatial/",
    filename = "filtered_feature_bc_matrix.h5",
    assay = "Spatial",
    slice = "slice1"
)

# QC and filter
spatial_obj <- subset(
    spatial_obj,
    subset = nCount_Spatial > 200 & nFeature_Spatial > 100
)

# SCTransform normalization
spatial_obj <- SCTransform(
    spatial_obj,
    assay = "Spatial",
    vars.to.regress = "percent.mt",
    return.only.var.genes = FALSE,
    verbose = FALSE
)

# Clustering
spatial_obj <- RunPCA(spatial_obj, assay = "SCT")
spatial_obj <- FindNeighbors(spatial_obj, reduction = "pca", dims = 1:30)
spatial_obj <- FindClusters(spatial_obj, resolution = 0.8)
spatial_obj <- RunUMAP(spatial_obj, reduction = "pca", dims = 1:30)

# Spatial visualization
SpatialDimPlot(spatial_obj, label = TRUE)
SpatialFeaturePlot(spatial_obj, features = "nCount_Spatial")

# Spatially variable features
spatial_obj <- FindSpatiallyVariableFeatures(
    spatial_obj, assay = "SCT",
    selection.method = "moransi",
    features = VariableFeatures(spatial_obj)[1:1000],
    nfeatures = 50
)
```

---

## QC Thresholds Reference

| Metric | Typical Range | Notes |
|--------|---------------|-------|
| min_count (nCount_Spatial) | 100-500 | More lenient than single-cell |
| min_feature (nFeature_Spatial) | 50-200 | Spots contain 0-10 cells |
| max_mt | 10-20% | Tissue-dependent; dying tissue regions may be higher |
| min_cells | 3-10 | Remove rarely detected genes |
| resolution | 0.4-1.2 | Typically lower than single-cell |
| PCA dims | 1:30 | Standard for Visium |

## Method Comparison

| Step | Scanpy/Squidpy | Seurat (SCTransform) |
|------|----------------|----------------------|
| Load | `sc.read_visium()` | `Load10X_Spatial()` |
| QC Metrics | `sc.pp.calculate_qc_metrics()` | Auto-loaded |
| Normalize | `normalize_total` + `log1p` | `SCTransform()` |
| HVGs | `highly_variable_genes` | Included in SCTransform |
| Cluster | `sc.tl.leiden()` | `FindClusters()` |
| Spatial plot | `sq.pl.spatial_scatter()` | `SpatialFeaturePlot()` / `SpatialDimPlot()` |
| SVGs | `sq.gr.spatial_autocorr(mode='moran')` | `FindSpatiallyVariableFeatures(method = "moransi")` |
| Merge | `anndata.concat()` | `merge()` |

## Spatial vs Single-Cell Preprocessing Key Differences

| Aspect | Spatial Transcriptomics | Single-Cell |
|--------|------------------------|-------------|
| QC thresholds | More lenient (multi-cell spots) | Stricter |
| Count variance | Often biological (cell density) | Primarily technical |
| Normalization | SCTransform strongly recommended | SCTransform or LogNorm |
| Clustering resolution | Usually lower (broader regions) | Can be higher |
| Unique analysis | Spatial visualization, SVG detection | Not applicable |
| Spatial coordinates | Required for analysis | Not applicable |

## Related Skills

- bio-spatial-transcriptomics-data-io - Load non-standard spatial data formats
- bio-single-cell-preprocessing - Single-cell QC and normalization (comparable)
- bio-single-cell-clustering - Clustering concepts applicable to spatial
