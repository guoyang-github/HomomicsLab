---
name: bio-single-cell-data-io
description: Read, write, and create single-cell data objects using Seurat (R) and Scanpy (Python). Supports single-sample and multi-sample loading via SampleSheet CSV, including standard 10X, GEO MTX, GEO H5, and merged-matrix formats. Use for loading, saving, converting, or merging single-cell data.
tool_type: mixed
primary_tool: Seurat
supported_tools: [scanpy, anndata, pandas, numpy]
keywords: ["single-cell", "data-io", "10X", "Seurat", "Scanpy", "h5ad", "AnnData", "file-conversion", "samplesheet", "GEO"]
multi_sample:
  supported: true
  input_format: samplesheet.csv
  formats: [10x_mtx, 10x_h5, geo_mtx, geo_mtx_merged, geo_h5, h5ad, rds]
---

## Version Compatibility

Reference examples tested with: Cell Ranger 8.0+, anndata 0.10+, numpy 1.26+, pandas 2.2+, scanpy 1.10+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

### Seurat v4 vs v5 Notes

**This skill assumes Seurat v5 by default.** Key differences relevant to data I/O:

| Feature | v4 | v5 |
|---------|-----|-----|
| Counts access | `GetAssayData(obj, slot = "counts")` | `LayerData(obj, layer = "counts")` or `obj[["RNA"]]$counts` |
| Assay data | Slots (`counts`, `data`, `scale.data`) | Layers (`counts`, `data`, `scale.data`) |
| Merge multiple | Creates single matrix | Auto-creates split layers |
| Default assay | `DefaultAssay(obj)` returns assay name | Same, but assay structure changed |

**If your pipeline requires v4 compatibility:**
- Use `GetAssayData()` instead of `LayerData()`
- After `merge()`, call `JoinLayers()` is **not** needed in v4 (v5 only)
- `as.SingleCellExperiment()` may need `SeuratObject` compatibility updates

Detect your version: `packageVersion("Seurat")`

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

# Single-Cell Data I/O

Read, write, and create single-cell data objects for analysis.

## Quick Reference: Scanpy ↔ Seurat

### Object Creation Mapping

| Operation | Scanpy (Python) | Seurat (R) | Input | Output State |
|-----------|----------------|------------|-------|--------------|
| **Read 10X MTX** | `sc.read_10x_mtx()` | `Read10X()` + `CreateSeuratObject()` | 10X output folder | [Raw] |
| **Read 10X h5** | `sc.read_10x_h5()` | `Read10X_h5()` + `CreateSeuratObject()` | .h5 file | [Raw] |
| **Read h5ad** | `sc.read_h5ad()` | N/A (use SeuratDisk) | .h5ad file | [Raw] or later |
| **Read RDS** | N/A | `readRDS()` | .rds file | [Raw] or later |
| **Create from matrix** | `ad.AnnData()` | `CreateSeuratObject()` | Counts matrix | [Raw] |
| **Save h5ad** | `adata.write_h5ad()` | N/A | - | - |
| **Save RDS** | N/A | `saveRDS()` | - | - |
| **Merge objects** | `ad.concat()` | `merge()` | Multiple [Raw] | [Raw] (merged) |

### Data State Notes

- **After loading:** State depends on source. 10X Cell Ranger output is always [Raw] (counts)
- **After conversion:** State preserved during format conversion
- **Before saving:** Ensure correct format for target tool

### AnnData vs Seurat Object Structure

| Component | AnnData (Python) | Seurat (R) |
|-----------|------------------|------------|
| Expression matrix | `adata.X` | `LayerData(seurat_obj, layer='counts')` or `seurat_obj[['RNA']]$counts` |
| Cell metadata | `adata.obs` | `seurat_obj@meta.data` |
| Gene metadata | `adata.var` | `seurat_obj@assays$RNA@meta.features` (v5) |
| Embeddings | `adata.obsm` | `seurat_obj@reductions` |
| Layers | `adata.layers` | `seurat_obj@assays$RNA@layers` (v5) |
| Unstructured data | `adata.uns` | `seurat_obj@misc` |

---

## Multi-Sample Input via SampleSheet

Use a SampleSheet CSV to declaratively load one or more samples. This is the **recommended entry point** for multi-sample workflows.

### SampleSheet Format (CSV)

```csv
sample_id,file_path,file_format,condition,batch,technology
PA08,data/PA08/filtered_feature_bc_matrix,10x_mtx,High_NI,Batch1,10x_v3
PA11,data/PA11/filtered_feature_bc_matrix,10x_mtx,High_NI,Batch1,10x_v3
PA02,data/PA02/filtered_feature_bc_matrix,10x_mtx,High_NI,Batch2,10x_v3
PA12,data/PA12/filtered_feature_bc_matrix,10x_mtx,Low_NI,Batch2,10x_v3
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
| `batch` | Batch identifier | `batch-integration` (recommended for multi-sample) |
| `condition` | Biological condition/group | Differential analysis |
| `technology` | Sequencing platform | Documentation |
| `sex` | Sex | Covariate |
| `age` | Age | Covariate |
| `note` | Free-text note | Documentation |

**Supported `file_format` values:**

| Format | Path type | Description |
|--------|-----------|-------------|
| `10x_mtx` | Directory | Standard Cell Ranger `filtered_feature_bc_matrix/` |
| `10x_h5` | File | Single `.h5` file (Cell Ranger output) |
| `geo_mtx` | Directory | GEO-style MTX (auto-detects `features.tsv.gz` vs `genes.tsv.gz`) |
| `geo_mtx_merged` | Directory | GEO merged MTX + separate metadata CSV |
| `geo_h5` | File | GEO `.h5` file |
| `h5ad` | File | Scanpy `.h5ad` (Python only) |
| `rds` | File | Seurat `.rds` (R only) |

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

### Downstream Integration

When `merge = TRUE`, the returned object is ready for `batch-integration`:

```r
# R / Seurat v5
source('scripts/r/samplesheet.R')
obj <- load_from_samplesheet('samplesheet.csv', merge = TRUE)

source('../bio-single-cell-batch-integration/scripts/r/seurat-v5/integrate.R')
obj <- integrate_v5_standard(obj = obj, method = 'harmony')
```

```python
# Python / Scanpy
from samplesheet import load_from_samplesheet
adata = load_from_samplesheet('samplesheet.csv', merge=True)

# sc.external.pp.harmony_integrate(adata, key='batch')
```

---

## Scanpy (Python)

**Goal:** Load, create, and save single-cell data objects using Scanpy and AnnData.

**Approach:** Read 10X Genomics output, CSV, or Loom formats into AnnData objects, manipulate metadata and layers, and write to h5ad format.

**Input State:** None (file-based operation)
**Output State:** [Raw] Raw counts matrix

**"Load my 10X data"** → Read Cell Ranger output directory or h5 file into an AnnData object with expression matrix, cell barcodes, and gene annotations.

### Required Imports

```python
import scanpy as sc
import anndata as ad
import pandas as pd
import numpy as np
```

### Reading 10X Genomics Data

```python
# Read 10X cellranger output (filtered_feature_bc_matrix directory)
adata = sc.read_10x_mtx('filtered_feature_bc_matrix/', var_names='gene_symbols', cache=True)
print(f'Loaded {adata.n_obs} cells x {adata.n_vars} genes')

# Read 10X h5 file directly
adata = sc.read_10x_h5('filtered_feature_bc_matrix.h5')
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | Yes | - | Path to 10X output directory |
| `var_names` | string | No | 'gene_symbols' | Use 'gene_symbols' or 'gene_ids' |
| `make_unique` | bool | No | True | Make gene names unique |
| `gex_only` | bool | No | True | Keep gene expression features only (exclude antibody/CRISPR) |
| `prefix` | string | No | None | Prefix to prepend to gene names |
| `cache` | bool | No | False | Cache read data to disk |
| `cache_compression` | str/None | No | None | Compression for cache file |


| Output | Location | Description |
|--------|----------|-------------|
| Counts | `adata.X` | Raw counts matrix (cells x genes) |
| Cell IDs | `adata.obs_names` | Cell barcodes |
| Gene IDs | `adata.var_names` | Gene symbols or IDs |
| Gene metadata | `adata.var` | 'gene_ids' or 'feature_types' |

### AnnData Object Structure

```python
# AnnData stores:
# - adata.X: expression matrix (cells x genes)
# - adata.obs: cell metadata (DataFrame)
# - adata.var: gene metadata (DataFrame)
# - adata.uns: unstructured annotations (dict)
# - adata.obsm: cell embeddings (PCA, UMAP)
# - adata.varm: gene embeddings
# - adata.obsp: cell-cell graphs
# - adata.layers: alternative matrices (raw counts, normalized)

print(f'Shape: {adata.shape}')
print(f'Cell metadata: {adata.obs.columns.tolist()}')
print(f'Gene metadata: {adata.var.columns.tolist()}')
```

### Creating AnnData from Matrix

```python
import anndata as ad
import numpy as np
import pandas as pd

counts = np.random.poisson(1, size=(100, 500))  # 100 cells x 500 genes
cell_ids = [f'cell_{i}' for i in range(100)]
gene_ids = [f'gene_{i}' for i in range(500)]

adata = ad.AnnData(
    X=counts,
    obs=pd.DataFrame(index=cell_ids),
    var=pd.DataFrame(index=gene_ids)
)
```

### Reading/Writing h5ad Files

```python
# h5ad is the native AnnData format
adata = sc.read_h5ad('data.h5ad')

# Write to h5ad
adata.write_h5ad('output.h5ad')

# Write compressed
adata.write_h5ad('output.h5ad', compression='gzip')
```

### Reading Other Formats

```python
# CSV/TSV (genes as columns, cells as rows)
adata = sc.read_csv('counts.csv')

# Loom format
adata = sc.read_loom('data.loom')

# Text file (tab-separated)
adata = sc.read_text('counts.txt')
```

### GEO Non-Standard Formats

```python
import sys
sys.path.insert(0, 'scripts/python')
from geo_loaders import load_geo_mtx_with_metadata, load_geo_h5

# GEO: merged MTX + separate metadata CSV
# Pattern: all cells in one MTX, metadata CSV maps barcodes to samples
adata = load_geo_mtx_with_metadata(
    mtx_dir='GSE12345/',
    metadata_csv='GSE12345_cell_metadata.csv',
    sample_col='sample'
)

# GEO: H5 file
adata = load_geo_h5('GSE12345.h5', sample_id='PA08')
```

### Adding Metadata

```python
# Add cell metadata
adata.obs['sample'] = 'sample_1'
adata.obs['batch'] = ['batch_1'] * 50 + ['batch_2'] * 50

# Add gene metadata
adata.var['gene_type'] = 'protein_coding'

# Add unstructured data
adata.uns['experiment'] = 'PBMC_3k'
```

### Subsetting AnnData

```python
# Subset by cells
adata_subset = adata[adata.obs['batch'] == 'batch_1'].copy()

# Subset by genes
adata_subset = adata[:, adata.var['highly_variable']].copy()

# Boolean indexing
adata_subset = adata[adata.obs['n_genes'] > 200, :].copy()
```

### Storing Raw Counts

```python
# Store raw counts before normalization
adata.raw = adata.copy()

# Access raw counts later
raw_counts = adata.raw.X

# Or use layers
adata.layers['counts'] = adata.X.copy()
```

---

## Seurat (R)

**Goal:** Load, create, and save single-cell data objects using Seurat.

**Approach:** Read 10X Genomics output into Seurat objects, manipulate metadata, merge samples, and serialize with RDS or h5Seurat formats.

**Input State:** None (file-based operation)
**Output State:** [Raw] Raw counts matrix

### Required Libraries

```r
library(Seurat)
library(Matrix)
```

### Reading 10X Genomics Data

```r
# Read 10X cellranger output
counts <- Read10X(data.dir = 'filtered_feature_bc_matrix/')

# Create Seurat object
seurat_obj <- CreateSeuratObject(counts = counts, project = 'PBMC', min.cells = 3, min.features = 200)
print(seurat_obj)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `counts` | matrix | Yes | - | Gene expression matrix (genes x cells) |
| `project` | string | No | 'SeuratProject' | Project name prefix |
| `min.cells` | int | No | 0 | Include genes detected in at least this many cells |
| `min.features` | int | No | 0 | Include cells with at least this many genes |


| Output | Location | Description |
|--------|----------|-------------|
| Counts | `seurat_obj@assays$RNA@layers$counts` | Raw counts matrix (v5) |
| Metadata | `seurat_obj@meta.data` | Cell-level metadata (nCount_RNA, nFeature_RNA) |

### Reading 10X h5 File

```r
# Read h5 file directly
counts <- Read10X_h5('filtered_feature_bc_matrix.h5')
seurat_obj <- CreateSeuratObject(counts = counts, project = 'PBMC')
```

### Seurat Object Structure (v5)

```r
# Seurat v5 uses layers instead of slots
# - Layers: counts, data, scale.data
# - Metadata: seurat_obj@meta.data
# - Reductions: seurat_obj@reductions
# - Graphs: seurat_obj@graphs

# Access layers (v5 syntax)
counts <- LayerData(seurat_obj, layer = 'counts')
# Or shorthand
counts <- seurat_obj[['RNA']]$counts

# Access metadata
head(seurat_obj@meta.data)
```

### Creating from Matrix

```r
# Create from sparse matrix
counts <- Matrix(rpois(1000 * 500, 1), nrow = 500, ncol = 1000, sparse = TRUE)
rownames(counts) <- paste0('gene_', 1:500)
colnames(counts) <- paste0('cell_', 1:1000)

seurat_obj <- CreateSeuratObject(counts = counts, project = 'MyProject')
```

### Reading/Writing RDS Files

```r
# Save Seurat object
saveRDS(seurat_obj, file = 'seurat_obj.rds')

# Load Seurat object
seurat_obj <- readRDS('seurat_obj.rds')
```

### GEO Non-Standard Formats

```r
source('scripts/r/geo_loaders.R')

# GEO: merged MTX + separate metadata CSV
# Pattern: all cells in one MTX, metadata CSV maps barcodes to samples
obj <- load_geo_mtx_merged(
  mtx_dir = 'GSE12345/',
  metadata_csv = 'GSE12345_cell_metadata.csv',
  sample_col = 'sample'
)

# GEO: H5 file
obj <- load_geo_h5('GSE12345.h5', sample_id = 'PA08')
```

### Adding Metadata

```r
# Add cell metadata
seurat_obj$sample <- 'sample_1'
seurat_obj$batch <- c(rep('batch_1', 500), rep('batch_2', 500))

# Or using AddMetaData
metadata_df <- data.frame(
    cell_type = rep('unknown', ncol(seurat_obj)),
    row.names = colnames(seurat_obj)
)
seurat_obj <- AddMetaData(seurat_obj, metadata = metadata_df)
```

### Subsetting Seurat Objects

```r
# Subset by metadata
seurat_subset <- subset(seurat_obj, subset = batch == 'batch_1')

# Subset by cells
seurat_subset <- subset(seurat_obj, cells = colnames(seurat_obj)[1:500])

# Subset by features
seurat_subset <- subset(seurat_obj, features = rownames(seurat_obj)[1:100])
```

### Merging Objects

```r
# Merge multiple Seurat objects
merged <- merge(seurat_obj1, y = c(seurat_obj2, seurat_obj3), add.cell.ids = c('S1', 'S2', 'S3'))

# Join layers after merge (v5)
merged <- JoinLayers(merged)
```

---

## Format Conversion

**Goal:** Convert single-cell data objects between Seurat (R) and AnnData (Python) formats.

**Approach:** Use SeuratDisk as an intermediary to convert via h5Seurat/h5ad bridge files.

**Input State:** Any (preserved during conversion)
**Output State:** Same as Input State

### Seurat to AnnData

**Input State:** Any Seurat object with any processing state
**Output State:** Same AnnData with equivalent state

```r
# In R: save as h5Seurat
library(SeuratDisk)
SaveH5Seurat(seurat_obj, filename = 'data.h5seurat')
Convert('data.h5seurat', dest = 'h5ad')
```

```python
# In Python: read converted file
adata = sc.read_h5ad('data.h5ad')
```

### AnnData to Seurat

**Input State:** [Any] AnnData object with any processing state
**Output State:** [Same] Seurat object with equivalent state

```python
# In Python: save as h5ad
adata.write_h5ad('data.h5ad')
```

```r
# In R: convert and load
library(SeuratDisk)
Convert('data.h5ad', dest = 'h5seurat')
seurat_obj <- LoadH5Seurat('data.h5seurat')
```

## Common Data Formats

| Format | Extension | Description | Tool |
|--------|-----------|-------------|------|
| 10X MTX | folder | Cellranger output | Both |
| 10X h5 | .h5 | Cellranger HDF5 | Both |
| h5ad | .h5ad | AnnData native | Scanpy |
| RDS | .rds | R serialized | Seurat |
| Loom | .loom | HDF5-based | Both |
| h5Seurat | .h5seurat | Seurat HDF5 | Seurat |

## Related Skills

- bio-single-cell-preprocessing - QC filtering and normalization after loading
- bio-single-cell-clustering - Dimensionality reduction and clustering
- bio-single-cell-cell-annotation - Find marker genes and annotate cell types
