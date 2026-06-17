---
name: bio-spatial-transcriptomics-data-io
description: Load spatial transcriptomics data from Visium, Xenium, MERFISH, and other platforms using Seurat (R) and Scanpy/Squidpy (Python). Supports single-sample and multi-sample loading via SampleSheet CSV, including standard Space Ranger outputs and GEO non-standard formats (h5 + spatial.tar.gz). Use when loading Visium, Xenium, MERFISH, or other spatial data.
tool_type: mixed
primary_tool: squidpy
supported_tools: [scanpy, spatialdata, anndata, pandas, Seurat]
keywords: ["spatial", "data-io", "Visium", "Xenium", "MERFISH", "Squidpy", "SpatialData", "Seurat", "R", "samplesheet", "GEO"]
multi_sample:
  supported: true
  input_format: samplesheet.csv
  formats: [visium, visium_h5, xenium, cosmx, merfish, geo_visium, geo_visium_h5]
---

## Version Compatibility

Reference examples tested with: anndata 0.10+, numpy 1.26+, pandas 2.2+, scanpy 1.10+, spatialdata 0.1+, squidpy 1.3+, Seurat 5.0+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

## Data State Markers (通用)

统一使用以下标签标记AnnData状态：

| 标记 | 含义 | 检查方法 |
|------|------|---------|
| **[Raw]** | 原始counts矩阵 | `adata.X.dtype == np.integer` 或 `adata.X.max() > 1000` |
| **[Normalized]** | 归一化+log1p转换 | `adata.X.max() < 100` |
| **[Scaled]** | z-score标准化 | `adata.X.mean() ≈ 0`, `std ≈ 1` |
| **[HVG]** | 子集到高变基因 | `'highly_variable' in adata.var` |
| **[PCA]** | 已计算PCA | `'X_pca' in adata.obsm` |
| **[Clustered]** | 已聚类 | `'leiden' in adata.obs` 或 `'louvain' in adata.obs` |
| **[UMAP]** | 已计算UMAP | `'X_umap' in adata.obsm` |
| **[TSNE]** | 已计算tSNE | `'X_tsne' in adata.obsm` |

---

# Spatial Data I/O

**"Load my Visium spatial data"** → Read spatial transcriptomics outputs (Visium, Xenium, MERFISH, Slide-seq) into AnnData or Seurat objects with spatial coordinates and tissue images.
- Python: `squidpy.read.visium('spaceranger_out/')`, `spatialdata.read_zarr()`
- R: `Seurat::Load10X_Spatial('spaceranger_out/')`

Load and work with spatial transcriptomics data from various platforms.

## Quick Reference: Python ↔ R

### Object Creation Mapping

| Operation | Python (Squidpy/Scanpy) | R (Seurat) | Input | Output State |
|-----------|-------------------------|------------|-------|--------------|
| **Read Visium** | `sc.read_visium()` | `Load10X_Spatial()` | Space Ranger output | [Raw] |
| **Read Visium h5** | `sc.read_visium()` | `Read10X_h5()` + `CreateSeuratObject()` | .h5 file | [Raw] |
| **Read Xenium** | `sq.read.xenium()` | `LoadXenium()` | Xenium output | [Raw] |
| **Read CosMx** | `sdio.cosmx()` | `LoadCosMx()` | CosMx output | [Raw] |
| **Read MERFISH** | `sq.read.vizgen()` | `LoadMERFISH()` | Vizgen output | [Raw] |
| **Read h5ad** | `sc.read_h5ad()` | `SeuratDisk::LoadH5Seurat()` | .h5ad file | [Raw] or later |
| **Save h5ad** | `adata.write_h5ad()` | N/A | - | - |
| **Save RDS** | N/A | `saveRDS()` | .rds file | - |
| **Merge objects** | `ad.concat()` | `merge()` + `JoinLayers()` | Multiple [Raw] | [Raw] (merged) |
| **Get coordinates** | `adata.obsm['spatial']` | `GetTissueCoordinates()` | - | - |
| **Get scale factors** | `adata.uns['spatial']` | `@images[[image]]@scale.factors` | - | - |

---

## Multi-Sample Input via SampleSheet

Use a SampleSheet CSV to declaratively load one or more spatial transcriptomics samples.

### SampleSheet Format (CSV)

```csv
sample_id,file_path,file_format,technology,condition,batch,slice
PA08,data/PA08,visium,Tumor,Batch1,slice1
PA11,data/PA11,visium,Tumor,Batch1,slice1
PA02,data/PA02,visium,Normal,Batch2,slice1
PA12,data/PA12,geo_visium,Normal,Batch2,slice1
```

**Required columns:**

| Column | Description | Validation |
|--------|-------------|------------|
| `sample_id` | Unique sample identifier | Non-empty, unique |
| `file_path` | Path to data file or directory | Must exist |
| `file_format` | Data format code | Must be supported |

**Optional columns:**

| Column | Description | Used by |
|--------|-------------|---------|
| `technology` | Platform (visium, xenium, cosmx, merfish) | Loader selection |
| `batch` | Batch identifier | Downstream integration |
| `condition` | Biological condition/group | Analysis grouping |
| `slice` | Slice/FOV name | Visium/Xenium (default: "slice1"/"fov") |
| `slide` | Slide ID | Visium |
| `note` | Free-text note | Documentation |

**Supported `file_format` values:**

| Format | Path type | Description |
|--------|-----------|-------------|
| `visium` | Directory | Standard Space Ranger output (`spatial/` + `.h5`) |
| `visium_h5` | File | Visium `.h5` file only (no spatial images) |
| `xenium` | Directory | 10X Xenium output |
| `cosmx` | Directory | Nanostring CosMx output |
| `merfish` | Directory | Vizgen MERFISH output |
| `geo_visium` | Directory | GEO Visium: `.h5` + `spatial.tar.gz` (auto-restructured) |
| `geo_visium_h5` | File | GEO Visium `.h5` only (no spatial images) |

### Python

```python
import sys
sys.path.insert(0, 'scripts/python')
from samplesheet import load_from_samplesheet

# Load and merge (default)
adata = load_from_samplesheet('samplesheet.csv', merge=True)
# adata.obs contains: sample_id, condition, batch, technology

# Load as list (for per-sample QC before merging)
adata_list = load_from_samplesheet('samplesheet.csv', merge=False)
```

### R

```r
source('scripts/r/samplesheet.R')

# Load and merge (default)
obj <- load_from_samplesheet('samplesheet.csv', merge = TRUE)
# obj@meta.data contains: sample_id, condition, batch, technology

# Load as list (for per-sample QC before merging)
obj_list <- load_from_samplesheet('samplesheet.csv', merge = FALSE)
```

---

## Python: Squidpy & SpatialData

### Required Imports

```python
import squidpy as sq
import scanpy as sc
import anndata as ad
import spatialdata as sd
import spatialdata_io as sdio
```

### Load 10X Visium Data

**Goal:** Load Visium spatial transcriptomics data from Space Ranger output into an AnnData object.

**Approach:** Use Scanpy's `read_visium` to parse the output directory, which loads expression, spatial coordinates, and tissue images.

> **⚠️ Deprecation note:** `sq.read.visium()` is deprecated in squidpy ≥1.6. Use `sc.read_visium()` (scanpy ≥1.10) instead.

```python
# Load Space Ranger output (standard method)
adata = sc.read_visium('path/to/spaceranger/output/')
print(f'Loaded {adata.n_obs} spots, {adata.n_vars} genes')

# Spatial coordinates are in adata.obsm['spatial']
print(f"Spatial coords shape: {adata.obsm['spatial'].shape}")

# Image is in adata.uns['spatial']
library_id = list(adata.uns['spatial'].keys())[0]
print(f'Library ID: {library_id}')
```

### Load Visium with Scanpy

**Goal:** Load Visium data using Scanpy's built-in reader as an alternative to Squidpy.

**Approach:** Use Scanpy's built-in `read_visium` as an alternative if needed.

```python
# Alternative: same function, explicit call
adata = sc.read_visium('path/to/spaceranger/output/')

# Access tissue image
img = adata.uns['spatial'][library_id]['images']['hires']
scale_factor = adata.uns['spatial'][library_id]['scalefactors']['tissue_hires_scalef']
```

> **⚠️ Parameter naming note:**
> - `sc.read_visium(path=..., count_file=...)` — Scanpy uses `count_file` (singular)
>
> If using the deprecated `sq.read.visium()`, note it used `counts_file` (plural).

### Load 10X Xenium Data

**Goal:** Load single-cell resolution Xenium spatial data.

**Approach:** Use Squidpy's `read.xenium` to parse Xenium output, yielding per-cell expression and coordinates.

```python
# Load Xenium output
adata = sq.read.xenium('path/to/xenium/output/')
print(f'Loaded {adata.n_obs} cells')

# Xenium has single-cell resolution
print(f"Cell coordinates: {adata.obsm['spatial'].shape}")
```

### Load with SpatialData (Recommended for New Projects)

**Goal:** Load spatial data into SpatialData objects for unified multi-modal representation.

**Approach:** Use spatialdata-io readers per platform, which organize expression, shapes, and images into a single object.

```python
import spatialdata_io as sdio

# Load Visium as SpatialData object
sdata = sdio.visium('path/to/spaceranger/output/')
print(sdata)

# Load Xenium
sdata = sdio.xenium('path/to/xenium/output/')

# Access components
table = sdata.tables['table']  # AnnData with expression
shapes = sdata.shapes  # Spatial shapes (spots, cells)
images = sdata.images  # Tissue images
```

### Load MERFISH Data

**Goal:** Load MERFISH (Vizgen MERSCOPE) spatial data.

**Approach:** Use spatialdata-io or Squidpy readers to parse MERSCOPE output with cell-by-gene counts and metadata.

```python
# MERFISH (Vizgen MERSCOPE)
sdata = sdio.merscope('path/to/merscope/output/')

# Or as AnnData
adata = sq.read.vizgen('path/to/vizgen/output/', counts_file='cell_by_gene.csv', meta_file='cell_metadata.csv')
```

### Load Slide-seq Data

```python
# Slide-seq / Slide-seqV2
adata = sq.read.slideseq('beads.csv', coordinates_file='coords.csv')
```

### Load Nanostring CosMx

```python
# CosMx spatial molecular imaging
sdata = sdio.cosmx('path/to/cosmx/output/')
```

### Load Stereo-seq Data

```python
# Stereo-seq (BGI)
sdata = sdio.stereoseq('path/to/stereoseq/output/')
```

### GEO Non-Standard Formats

```python
import sys
sys.path.insert(0, 'scripts/python')
from geo_loaders import load_geo_visium, load_geo_visium_h5

# GEO Visium: h5 + spatial.tar.gz
# Auto-restructures files into standard Space Ranger format
adata = load_geo_visium(data_dir='GSE12345/PA08/', sample_id='PA08')

# GEO Visium H5 only (no spatial images)
adata = load_geo_visium_h5(h5_path='GSE12345/PA08.h5', sample_id='PA08')
```

### Load from H5AD with Spatial Coordinates

```python
# If you have h5ad with spatial already stored
adata = sc.read_h5ad('spatial_data.h5ad')

# Verify spatial data exists
if 'spatial' in adata.obsm:
    print('Has spatial coordinates')
if 'spatial' in adata.uns:
    print('Has image data')
```

### Create Spatial AnnData from Scratch

**Goal:** Construct a spatial AnnData object from raw expression and coordinate arrays.

**Approach:** Build an AnnData with spatial coordinates in `obsm['spatial']` and minimal metadata in `uns['spatial']` for Squidpy compatibility.

```python
import numpy as np
import pandas as pd

# Expression matrix
X = np.random.poisson(5, size=(1000, 500))

# Spatial coordinates
spatial_coords = np.random.rand(1000, 2) * 1000  # x, y in pixels

# Create AnnData
adata = ad.AnnData(X)
adata.obs_names = [f'spot_{i}' for i in range(1000)]
adata.var_names = [f'gene_{i}' for i in range(500)]
adata.obsm['spatial'] = spatial_coords

# Add minimal spatial metadata for Squidpy
adata.uns['spatial'] = {
    'library_id': {
        'scalefactors': {'tissue_hires_scalef': 1.0, 'spot_diameter_fullres': 50},
    }
}
```

### Access Spatial Coordinates

```python
# Get coordinates as numpy array
coords = adata.obsm['spatial']
x_coords = coords[:, 0]
y_coords = coords[:, 1]

# Get coordinates as DataFrame
coord_df = pd.DataFrame(adata.obsm['spatial'], index=adata.obs_names, columns=['x', 'y'])
```

### Access Tissue Images

```python
# Get high-resolution image
library_id = list(adata.uns['spatial'].keys())[0]
hires_img = adata.uns['spatial'][library_id]['images']['hires']
lowres_img = adata.uns['spatial'][library_id]['images']['lowres']

# Scale factors
scalef = adata.uns['spatial'][library_id]['scalefactors']
print(f"Hires scale: {scalef['tissue_hires_scalef']}")
print(f"Spot diameter: {scalef['spot_diameter_fullres']}")
```

### Convert Between Formats

**Goal:** Convert spatial data between SpatialData and AnnData representations.

**Approach:** Extract tables and coordinate arrays from SpatialData, then save as h5ad or zarr.

```python
# SpatialData to AnnData
sdata = sdio.visium('path/to/data/')
adata = sdata.tables['table'].copy()
adata.obsm['spatial'] = np.array(sdata.shapes['spots'][['x', 'y']])

# Save as h5ad
adata.write_h5ad('spatial_converted.h5ad')

# Save SpatialData
sdata.write('spatial_data.zarr')
```

### Load Multiple Samples

**Goal:** Load and merge spatial data from multiple Visium samples into a single AnnData.

**Approach:** Iterate over sample directories, tag each with a sample label, then concatenate with `ad.concat`.

```python
# Load and concatenate multiple Visium samples
samples = ['sample1', 'sample2', 'sample3']
adatas = []

for sample in samples:
    adata = sc.read_visium(f'data/{sample}/')
    adata.obs['sample'] = sample
    adatas.append(adata)

# Concatenate
adata_combined = ad.concat(adatas, label='sample', keys=samples)
print(f'Combined: {adata_combined.n_obs} spots')
```

### Subset by Spatial Region

**Goal:** Extract spots within a rectangular spatial region of interest.

**Approach:** Apply coordinate-based boolean masking on `obsm['spatial']` to filter spots by x/y bounds.

```python
# Select spots in a rectangular region
x_min, x_max = 1000, 2000
y_min, y_max = 1500, 2500

coords = adata.obsm['spatial']
in_region = (coords[:, 0] >= x_min) & (coords[:, 0] <= x_max) & (coords[:, 1] >= y_min) & (coords[:, 1] <= y_max)

adata_region = adata[in_region].copy()
print(f'Selected {adata_region.n_obs} spots')
```

---

## R: Seurat

### Required Libraries

```r
library(Seurat)
library(Matrix)
library(jsonlite)
```

### Load 10X Visium Data

**Goal:** Load Visium spatial transcriptomics data into a Seurat object with images and coordinates.

**Approach:** Use `Load10X_Spatial()` to parse Space Ranger output. Spatial images, coordinates, and scale factors are automatically loaded into the `@images` slot.

```r
# Load Space Ranger output
seurat_obj <- Load10X_Spatial(
  data.dir = 'path/to/spaceranger/output/',
  filename = 'filtered_feature_bc_matrix.h5',
  assay = 'Spatial',
  slice = 'slice1'
)

print(seurat_obj)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `data.dir` | string | Yes | - | Path to Space Ranger output |
| `filename` | string | No | 'filtered_feature_bc_matrix.h5' | Count matrix file name |
| `assay` | string | No | 'Spatial' | Assay name |
| `slice` | string | No | 'slice1' | Image/slice identifier |

| Output | Location | Description |
|--------|----------|-------------|
| Counts | `seurat_obj@assays$Spatial@layers$counts` | Raw counts (v5) |
| Spatial coords | `GetTissueCoordinates(seurat_obj)` | Spot coordinates |
| Images | `seurat_obj@images$slice1` | H&E image + scale factors |
| Scale factors | `seurat_obj@images$slice1@scale.factors` | Pixel conversion factors |

### Extract Spatial Information in R

```r
# Spatial coordinates
coords <- GetTissueCoordinates(seurat_obj)
head(coords)

# Scale factors
sf <- seurat_obj@images$slice1@scale.factors
sf@spot         # spot diameter in full-res pixels
sf@hires        # hires scale factor
sf@lowres       # lowres scale factor

# Load scalefactors_json.json directly
sf_json <- jsonlite::fromJSON('spatial/scalefactors_json.json')
conversion_factor <- 65 / sf_json$spot_diameter_fullres
```

### Load Visium from H5 File Only

```r
# Read h5 file without spatial images
counts <- Read10X_h5('filtered_feature_bc_matrix.h5')
seurat_obj <- CreateSeuratObject(counts = counts, assay = 'Spatial')
```

### Load 10X Xenium Data

**Goal:** Load single-cell resolution Xenium spatial data into a Seurat object.

**Approach:** Use `LoadXenium()` to parse Xenium output. Coordinates are already in micrometers.

```r
seurat_obj <- LoadXenium(
  data.dir = 'path/to/xenium/output/',
  fov = 'fov',
  assay = 'Xenium'
)

# Access single-cell coordinates
coords <- GetTissueCoordinates(seurat_obj)
```

### Load CosMx Data

```r
seurat_obj <- LoadCosMx(
  data.dir = 'path/to/cosmx/output/',
  assay = 'CosMx'
)
```

### Load MERFISH Data

```r
seurat_obj <- LoadMERFISH(
  data.dir = 'path/to/vizgen/output/',
  fov = 'merfish',
  assay = 'MERFISH'
)
```

### GEO Non-Standard Formats

```r
source('scripts/r/geo_loaders.R')

# GEO Visium: h5 + spatial.tar.gz
# Auto-restructures files into standard Space Ranger format
obj <- load_geo_visium(data.dir = 'GSE12345/PA08/', sample_id = 'PA08')

# GEO Visium H5 only (no spatial images)
obj <- load_geo_visium_h5(h5_path = 'GSE12345/PA08.h5', sample_id = 'PA08')
```

### Merge Multiple Spatial Samples in R

**Goal:** Load and merge multiple Visium/Xenium samples into a single Seurat object.

**Approach:** Use `merge()` followed by `JoinLayers()` for Seurat v5 compatibility.

```r
# Load multiple samples
s1 <- Load10X_Spatial('data/sample1/')
s2 <- Load10X_Spatial('data/sample2/')
s3 <- Load10X_Spatial('data/sample3/')

# Merge
merged <- merge(
  x = s1,
  y = c(s2, s3),
  add.cell.ids = c('S1', 'S2', 'S3')
)
merged <- JoinLayers(merged)

# Add sample metadata
merged$sample <- sapply(strsplit(colnames(merged), '_'), `[`, 1)
```

### Subset by Spatial Region in R

```r
# Extract coordinates
coords <- GetTissueCoordinates(seurat_obj)

# Define region of interest
x_min <- 1000; x_max <- 2000
y_min <- 1500; y_max <- 2500

in_region <- coords[, 1] >= x_min & coords[, 1] <= x_max &
             coords[, 2] >= y_min & coords[, 2] <= y_max

seurat_subset <- subset(seurat_obj, cells = rownames(coords)[in_region])
```

### Convert H5AD to Seurat

**Goal:** Convert a Python h5ad file to a Seurat object.

**Approach:** Use `SeuratDisk` as an intermediary via h5Seurat format.

```r
library(SeuratDisk)

# Convert h5ad -> h5seurat -> Seurat
Convert('spatial_data.h5ad', dest = 'h5seurat')
seurat_obj <- LoadH5Seurat('spatial_data.h5seurat')
```

### Save Seurat Spatial Object

```r
# Save as RDS
saveRDS(seurat_obj, file = 'visium_data.rds')

# Load later
seurat_obj <- readRDS('visium_data.rds')
```

---

## Spatial Integration Caveats

**Merging spatial samples requires special handling compared to scRNA-seq:**

1. **Seurat `merge()` does not merge `@images` slots.** After `merge()`, each sample retains its own image in `@images`. Downstream spatial plotting must specify the correct image name.

2. **Coordinates are not batch-corrected.** Batch integration methods like Harmony correct expression embeddings (PCA/UMAP), but spatial coordinates remain in physical pixel/micron space. Do not apply batch correction to `obsm['spatial']` or `GetTissueCoordinates()`.

3. **Scale factors differ per sample.** Each sample has its own `scalefactors_json.json`. After merging, access scale factors via `obj@images[[sample_id]]@scale.factors` (R) or `adata.uns['spatial'][sample_id]['scalefactors']` (Python).

4. **Visium spots vs single-cell resolution.** Visium uses ~55µm spots; Xenium/MERFISH have single-cell resolution. Do not mix these in the same integration without explicit downsampling or spot aggregation.

5. **For Seurat v5:** `merge_spatial_samples()` (called by `load_from_samplesheet(merge=TRUE)`) already performs `JoinLayers()`. Do **not** call `JoinLayers()` again manually.

## Related Skills

- bio-spatial-transcriptomics-preprocessing - QC and normalization after loading
- bio-spatial-transcriptomics-visualization - Plot spatial data
- bio-spatial-transcriptomics-batch-integration - Batch correction for spatial data
- bio-single-cell-data-io - Non-spatial scRNA-seq data loading
