---
name: bio-spatial-transcriptomics-batch-integration
description: Integrate multiple spatial transcriptomics slices/samples to remove technical batch effects while preserving biological spatial patterns. Handles image slot management during merge, supports Seurat V5 with Harmony/CCA/RPCA/fastMNN, and provides spatial-specific validation.
tool_type: mixed
primary_tool: Seurat
supported_tools: [harmony, batchelor]
keywords: ["spatial", "batch-integration", "harmony", "seurat", "visium", "multi-slice", "batch-correction"]
---

## Version Compatibility

Reference examples tested with: Seurat 5.0+, harmony 1.0+, batchelor 1.18+

This skill requires **Seurat V5**. Spatial transcriptomics workflows in the community have largely migrated to V5 for its improved layer-based data structures.

## Quick Reference: ST vs scRNA-seq Integration

| Aspect | scRNA-seq | Spatial Transcriptomics |
|--------|-----------|------------------------|
| Merge | Direct `merge()` | Must rename image slots first |
| Batch source | Sample, sequencing run | Slice, capture area, patient, section position |
| Validation | `DimPlot` | `SpatialDimPlot` per slice |
| Platform mixing | Generally OK | **Never mix platforms** (Visium/Xenium/etc.) |
| SCTransform | Directly applicable | Spot-level data; assumptions less exact |
| Python path | Harmony, scVI, BBKNN | Same as scRNA-seq (use bio-single-cell-batch-integration) |

---

# Spatial Batch Integration

## Core Differences from Single-Cell

### 1. Image Slot Conflicts During Merge

Seurat `merge()` overwrites `@images` slots with identical names. `Load10X_Spatial()` names all images `slice1` by default, so merging multiple slices causes image loss.

**This skill handles this automatically.** `prepare_input_spatial()` renames each object's images using the batch/sample identifier before merge.

### 2. Platform Consistency is Critical

Different platforms have fundamentally different resolutions and gene panels:

| Platform | Resolution | Genes | Integrate with |
|----------|-----------|-------|---------------|
| Visium | ~55um spots | ~20k | Visium only |
| Visium HD | ~2um | ~20k | Visium HD only |
| Xenium | Single-cell | ~300-400 | Xenium only |
| Slide-seq | ~10um beads | ~20k | Slide-seq only |
| CosMx | Single-cell | ~1k | CosMx only |

**Cross-platform integration produces artifacts.** Platform effects dominate biological signal.

### 3. Batch Effect Sources in ST

Beyond sample/sequencing batch, spatial data has additional batch sources:
- **Capture area:** Different Visium slides have different barcode sets
- **Section position:** Adjacent sections may differ in tissue composition
- **Tissue block:** Different blocks from the same patient
- **Staining variation:** H&E staining intensity differences

---

# R Methods (Seurat V5)

## Input Preparation

All spatial integration functions receive data through `prepare_input_spatial()`, which:
1. Validates all inputs are spatial objects (have `@images` slot)
2. Detects platform type (Visium/Xenium/CosMx/MERFISH)
3. Warns if multiple platforms detected
4. **Auto-renames image slots** to prevent merge overwrite
5. **Sets `Project()`** on each object for consistent layer suffixes after merge
6. Merges objects with `add.cell.ids`
7. **Auto-detects spatial assay** and sets it as `DefaultAssay`
8. Validates V5 `StdAssay`

Source: `scripts/r/utils.R`

### From RDS files

```r
source("scripts/r/utils.R")
obj <- prepare_input_spatial(
  file_paths = c("slice1.rds", "slice2.rds", "slice3.rds"),
  sample_col = "sample"
)
```

### From object list

```r
source("scripts/r/utils.R")

s1 <- Load10X_Spatial("sample1/", slice = "slice1")
s2 <- Load10X_Spatial("sample2/", slice = "slice1")

obj <- prepare_input_spatial(
  obj_list = list(s1, s2),
  sample_col = "sample"
)
```

### From already-merged object

```r
source("scripts/r/utils.R")
obj <- prepare_input_spatial(obj = merged_obj, sample_col = "sample")
```

**Returns:** Merged Seurat spatial object with:
- Layers (V5) for batch-aware integration (layer suffixes match `add.cell.ids`)
- Multiple uniquely-named image slots
- `sample_col` present in metadata
- Spatial assay set as `DefaultAssay`

**sample_col参数及add.cell.ids名称推断详解**

| 输入来源 | `sample_col` 的行为 |
|---------|-------------------|
| `file_paths` / `obj_list` | 1. 尝试从每个对象的元数据读取该列的唯一值，作为批次名<br>2. 若该列不存在、不唯一、或为 NA，则回退到 文件名 / list names<br>3. **最终将该列的值统一覆盖为确定的批次名** |
| `obj`（已合并） | 仅验证该列已存在；不修改其值；用于 `split()` |

**名称推断优先级（由高到低）：**

  1. `obj_list[[i]]@meta.data[[sample_col]]` 的唯一非空值
  2. `basename(file_paths[i])`（去掉 `.rds`）或 `names(obj_list)[i]`
  3. `S1`, `S2`, ... fallback

**Name sanitization:** Values from `sample_col` and `file_paths` are automatically cleaned to ensure compatibility with `merge(add.cell.ids)` and R list element names. Spaces and special characters (`/ \ ( ) [ ] < > : ; " ' , ? * ~ ! @ # $ % ^ & + = | `` ` ``) are converted to underscores; consecutive underscores are compressed; duplicates receive numeric suffixes (e.g. `Sample_1`, `Sample_1_1`).

---

## Integration Methods

All methods share the same `IntegrateLayers` workflow. Only the `method` parameter differs.

Source: `scripts/r/seurat-v5/integrate.R`

### Standard (LogNormalize)

```r
source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_spatial_v5_standard(obj = obj, method = "harmony")
```

### SCTransform

```r
obj <- integrate_spatial_v5_sct(obj = obj, method = "harmony")
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `obj` | Seurat | Yes | - | Merged spatial object with layers |
| `method` | string | No | 'harmony' | Integration method (see table below) |
| `npcs` | int | No | 50 | PCs for PCA |

**Method selection:**

| method | Reduction name | Best for |
|--------|---------------|----------|
| `"harmony"` | `harmony` | General purpose, fast (default) |
| `"cca"` | `integrated.cca` | Conserved biology, reference mapping |
| `"rpca"` | `integrated.rpca` | Large datasets (>50k spots) |
| `"fastmnn"` | `integrated.mnn` | Preserving rare spatial domains |

**What the function does:**
1. Preprocess: Normalize/Scale/PCA (Standard) or SCTransform/PCA (SCT)
2. `IntegrateLayers()` with chosen method
3. `JoinLayers()` on the spatial assay (Standard only)
4. Preserves all image slots and spatial coordinates

**What the function does NOT do:**
- `FindNeighbors`, `FindClusters`, `RunUMAP` — see Downstream Analysis below
- `SpatialDimPlot` — see Spatial Validation below

#### SCTransform Notes

##### When to Use SCTransform with ST

- When sequencing depth varies strongly across slices
- When you specifically need SCT's variance-stabilizing properties

##### Caveats for Spot-Level Data

Visium spots (~55um diameter) contain multiple cells. SCTransform's regularized negative binomial regression assumes single-cell resolution. For spot-level data:
- The "sequencing depth" parameter models total UMIs per spot, not per cell
- Overdispersion estimates may differ from true single-cell data
- **Recommendation:** Start with Standard normalization; use SCT only if Standard produces depth-related artifacts

##### V5 SCT Behavior

`SCTransform()` auto-runs per-layer in V5 on the default assay. The function asserts that the default assay is a v5 `StdAssay`. `IntegrateLayers(..., normalization.method = "SCT")` handles batch correction. No `JoinLayers` needed for SCT.

### Multi-Variable Batch Correction

When you need to correct for multiple batch variables simultaneously (e.g. sample + condition + capture_area):

```r
obj <- harmony_spatial_v5_compat(
  obj = obj,
  group.by.vars = c("sample", "condition")
)
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `obj` | Seurat | Yes | - | Merged spatial object |
| `group.by.vars` | string vector | Yes | - | Metadata columns for batch correction |
| `npcs` | int | No | 50 | PCs for PCA |

**Key differences from `integrate_spatial_v5_standard`:**
- Uses `RunHarmony` instead of `IntegrateLayers`
- Supports multiple variables via `group.by.vars`
- Joins layers first (needs unified matrix)
- Always produces `harmony` reduction

---

## Downstream Analysis

Integration functions stop at reduction creation. Use the integrated reduction for clustering and visualization.

### Clustering and UMAP

```r
# Use the reduction name returned by your chosen method
obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)
```

**Reduction names by method:**

| Method | Reduction | `reduction` parameter |
|--------|-----------|----------------------|
| Harmony | `harmony` | `reduction = "harmony"` |
| CCA | `integrated.cca` | `reduction = "integrated.cca"` |
| RPCA | `integrated.rpca` | `reduction = "integrated.rpca"` |
| fastMNN | `integrated.mnn` | `reduction = "integrated.mnn"` |

### Spatial Validation

After clustering, validate that batches mix within spatial domains (not batch-specific domains):

```r
# Batch mixing per slice
SpatialDimPlot(obj, group.by = "sample", ncol = 3)

# Domain consistency per slice
SpatialDimPlot(obj, group.by = "seurat_clusters", ncol = 3)
```

Good integration: each cluster contains spots from multiple slices.

### Quantitative Metrics

Same metrics as single-cell apply:
- **kBET:** Batch mixing within neighborhoods (higher = better)
- **LISI:** Local inverse Simpson index (higher = better mixing)
- **Silhouette:** Domain separation (higher = better biology preservation)

### Differential Expression After Integration

#### Standard (LogNormalize)

After `integrate_spatial_v5_standard()`, `JoinLayers` is already called during integration. Default assay is "RNA". Run DE directly:

```r
markers <- FindAllMarkers(obj, only.pos = TRUE, min.pct = 0.25, logfc.threshold = 0.25)
```

#### SCTransform

After `integrate_spatial_v5_sct()`, **must** call `PrepSCTFindMarkers()` before DE:

```r
obj <- PrepSCTFindMarkers(obj)
markers <- FindAllMarkers(obj, only.pos = TRUE, min.pct = 0.25)
```

**Key difference from Standard:** SCT does NOT need `JoinLayers`. `PrepSCTFindMarkers` handles multi-layer complexity internally.

---

# Complete Workflow

## Standard: Integrate Multiple Visium Slices

```r
library(Seurat)

# Step 1: Prepare input (handles image renaming + merge)
source("scripts/r/utils.R")
obj <- prepare_input_spatial(
  file_paths = c("slice1.rds", "slice2.rds", "slice3.rds"),
  sample_col = "sample"
)

# Step 2: Run integration
source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_spatial_v5_standard(obj = obj, method = "harmony")

# Step 3: Clustering and UMAP
obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)

# Step 4: Validate integration spatially
SpatialDimPlot(obj, group.by = "sample", ncol = 3)
SpatialDimPlot(obj, group.by = "seurat_clusters", ncol = 3)

# Step 5: DE (V5 Standard)
markers <- FindAllMarkers(obj, only.pos = TRUE, min.pct = 0.25, logfc.threshold = 0.25)
```

## SCTransform Variant

```r
library(Seurat)

# Step 1: Prepare input
source("scripts/r/utils.R")
obj <- prepare_input_spatial(
  file_paths = c("slice1.rds", "slice2.rds"),
  sample_col = "sample"
)

# Step 2: Run integration (SCT)
source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_spatial_v5_sct(obj = obj, method = "harmony")

# Step 3: Clustering and UMAP
obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)

# Step 4: Spatial validation
SpatialDimPlot(obj, group.by = "sample", ncol = 3)
SpatialDimPlot(obj, group.by = "seurat_clusters", ncol = 3)

# Step 5: DE (V5 SCT — requires PrepSCTFindMarkers)
obj <- PrepSCTFindMarkers(obj)
markers <- FindAllMarkers(obj, only.pos = TRUE, min.pct = 0.25)
```

## Multi-Variable Batch Correction

```r
library(Seurat)

source("scripts/r/utils.R")
obj <- prepare_input_spatial(
  file_paths = c("slice1.rds", "slice2.rds"),
  sample_col = "sample"
)

source("scripts/r/seurat-v5/integrate.R")
obj <- harmony_spatial_v5_compat(
  obj = obj,
  group.by.vars = c("sample", "condition")
)

# Downstream (always produces "harmony" reduction)
obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)
```

## From Space Ranger Output (Full Pipeline)

```r
library(Seurat)

# Load each slice
s1 <- Load10X_Spatial("sample1/outs/", slice = "slice1")
s2 <- Load10X_Spatial("sample2/outs/", slice = "slice1")
s3 <- Load10X_Spatial("sample3/outs/", slice = "slice1")

# Add sample metadata
s1$sample <- "S1"
s2$sample <- "S2"
s3$sample <- "S3"

# Prepare and integrate
source("scripts/r/utils.R")
obj <- prepare_input_spatial(obj_list = list(s1, s2, s3), sample_col = "sample")

source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_spatial_v5_standard(obj = obj, method = "harmony")

# Downstream
obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)
```

---

# File Organization

```
scripts/
└── r/
    ├── utils.R              # Input preparation (image renaming, platform detection)
    └── seurat-v5/
        └── integrate.R      # Unified integration (Harmony/CCA/RPCA/fastMNN)
```

---

## Related Skills

- **bio-single-cell-batch-integration** - For pure scRNA-seq integration (Python methods, V4 support, scVI/BBKNN/Scanorama)
- **bio-spatial-transcriptomics-data-io** - Loading Visium/Xenium spatial data
- **bio-spatial-transcriptomics-domains** - Spatial domain detection after integration
- **bio-spatial-transcriptomics-visualization** - Spatial plotting