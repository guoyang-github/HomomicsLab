# Batch Integration - Usage Guide

## Overview

Batch integration removes technical variation between samples, experiments, or technologies while preserving biological differences. This skill provides methods for both Python (scanpy/scvi-tools) and R (Seurat) ecosystems, with explicit support for Seurat V4 and V5, and both Standard (LogNormalize) and SCTransform normalization strategies.

## Prerequisites

```bash
# Python
pip install scanpy harmonypy scvi-tools bbknn scanorama
```

```r
# R - V4 or V5 (install one, not both)
install.packages("Seurat")          # V5 by default (as of 2024)
remotes::install_version("Seurat", version = "4.4.0")  # For V4

# Additional packages
install.packages("harmony")
BiocManager::install("batchelor")
```

## Quick Start

Tell your AI agent what you want to do:
- "Integrate my samples to remove batch effects"
- "Run Harmony on my merged Seurat object"
- "Use scVI to integrate these batches"
- "I have Seurat V5 and want to use SCTransform"

## How to Choose

### Step 1: Choose Language

| If you use... | Go to |
|---------------|-------|
| Python / scanpy | Python Methods |
| R / Seurat | R Methods |

### Step 2: Use Seurat V5 (Default)

**R 场景默认推荐使用 Seurat V5。** V5 的 `merge()` 自动创建 layers，`IntegrateLayers` 原生支持 Harmony/CCA/RPCA，无需手动 `SplitObject` 或 `JoinLayers`。

```r
packageVersion("Seurat")
# 5.x.x → Use V5 methods (recommended)
# 4.x.x → Use V4 methods (legacy compatibility only)
```

**Do not mix V4 and V5 code.** They have fundamentally different data structures (layers vs single matrix).

### Step 3: Choose Normalization Strategy

| Strategy | Best For | Speed | Complexity |
|----------|----------|-------|------------|
| **Standard (LogNormalize)** | Most use cases | Fast | Low |
| **SCTransform** | Highly variable sequencing depth; strong technical noise | Slower | Medium |

**Recommendation:** Start with Standard. Switch to SCT only if you see strong depth-related batch effects.

### Step 4: Choose Integration Method

| Method | Best For | Speed | When to Use |
|--------|----------|-------|-------------|
| **Harmony** | General purpose | Fast | Default choice for most scenarios |
| **Seurat CCA** | Conserved biology | Medium | Reference atlas mapping |
| **Seurat RPCA** | Large datasets | Fast | Faster alternative to CCA |
| **scVI** | Complex batch effects | Slow | Deep learning, large datasets |
| **fastMNN** | Rare populations | Medium | When preserving rare cell types is critical |
| **BBKNN** | Quick integration | Fast | Preserve local structure |
| **Scanorama** | Partial overlap | Medium | Datasets with asymmetric cell type overlap |

## R Method Selection

### Default: Seurat V5 (Recommended)

**Use this unless you have a specific reason to stay on V4.**

**Recommended:** `integrate_v5_standard()`

```r
# Step 1: Prepare input
source("scripts/r/utils.R")
obj <- prepare_input_v5(
  file_paths = c("sample1.rds", "sample2.rds", "sample3.rds"),
  sample_col = "sample"
)

# Step 2: Run integration
source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_v5_standard(obj = obj, method = "harmony")
```

**Why V5?**
- Official V5-native integration via `IntegrateLayers`
- Works directly on layers (no SplitObject)
- Fast and reliable
- One function covers Harmony, CCA, RPCA, fastMNN via `method` parameter
- Automatically handles JoinLayers for Standard normalization

### Legacy: Seurat V4 (Compatibility Only)

Only use V4 if your pipeline or dependencies require it.

**Recommended:** `harmony_v4_standard()`

```r
# Step 1: Prepare input
source("scripts/r/utils.R")
prep <- prepare_input_v4(
  file_paths = c("sample1.rds", "sample2.rds", "sample3.rds"),
  sample_col = "sample"
)

# Step 2: Run integration
source("scripts/r/seurat-v4/harmony.R")
obj <- harmony_v4_standard(obj = prep$obj, batch_col = "sample")
```

**Why V4?**
- Legacy compatibility for existing V4-based pipelines
- No new assay created (unlike CCA/RPCA)
- Direct PCA correction
- Stops at reduction creation (no downstream clustering)

## Three-Step Workflow

All R integration workflows follow the same two-step pattern:
1. **Prepare input** with `prepare_input_v4()` or `prepare_input_v5()` — handles loading, validation, merging, and splitting
2. **Run integration** with the method-specific function

### Step 1: Input Preparation

```r
source("scripts/r/utils.R")

# From merged object
prep <- prepare_input_v4(obj = merged_obj, sample_col = "sample")
# or: obj <- prepare_input_v5(obj = merged_obj, sample_col = "sample")

# From separate files
prep <- prepare_input_v4(
  file_paths = c("sample1.rds", "sample2.rds", "sample3.rds"),
  sample_col = "sample"
)
# or (V5):
obj <- prepare_input_v5(
  file_paths = c("sample1.rds", "sample2.rds", "sample3.rds"),
  sample_col = "sample"
)

# From pre-split list
prep <- prepare_input_v4(obj_list = list(s1, s2), sample_col = "sample")
# or (V5):
obj <- prepare_input_v5(obj_list = list(s1, s2), sample_col = "sample")
```

**Returns:**
- V4: `prep$obj` (merged object) + `prep$obj_list` (split by batch)
- V5: merged Seurat object with layers

### Step 2: Run Integration

**V4 Harmony Standard** (uses `prep$obj`):
```r
source("scripts/r/seurat-v4/harmony.R")
obj <- harmony_v4_standard(obj = prep$obj, batch_col = "sample")
```

**V4 Harmony SCT / CCA / RPCA** (uses `prep$obj_list`):
```r
source("scripts/r/seurat-v4/harmony.R")
obj <- harmony_v4_sct(obj_list = prep$obj_list, batch_col = "sample")

source("scripts/r/seurat-v4/seurat_cca.R")
integrated <- seurat_cca_v4_standard(obj_list = prep$obj_list)
```

**V5** (all methods use the object directly):
```r
source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_v5_standard(obj = obj, method = "harmony")
```

> **⚠️ Version Compatibility Note (Harmony + Seurat V5)**
>
> When using `IntegrateLayers(..., method = "HarmonyIntegration")` with **Seurat ≥ 5.0 + harmony ≥ 1.0**, you may see a series of deprecation warnings (e.g., `HarmonyMatrix is deprecated`, `tau is deprecated`, `max.iter.harmony replaced with max_iter`). These warnings originate from Seurat's internal `HarmonyIntegration` wrapper using legacy harmony parameter names. **The integration results are correct and unaffected** — harmony falls back to default values for the deprecated parameters.
>
> To completely suppress these warnings, use the `harmony_v5_compat()` function (direct `RunHarmony()` call) instead of `integrate_v5_standard()`:
> ```r
> source("scripts/r/seurat-v5/integrate.R")
> obj <- harmony_v5_compat(obj = obj, batch_col = "sample")
> ```

### Step 3: Downstream Analysis (Not in this skill)

Integration functions stop at reduction creation. Clustering and UMAP are handled by the **bio-single-cell-clustering** skill:

```r
# Use the reduction name returned by your chosen method
obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)
```

**Reduction names by method:**
| Method | Reduction |
|--------|-----------|
| Harmony | `harmony` |
| CCA | `integrated.cca` |
| RPCA | `integrated.rpca` |
| fastMNN | `integrated.mnn` |

## Common Scenarios

### "I just want to merge and integrate as fast as possible"

**Python:**
```python
from scripts.python.harmony import harmony_workflow
adata = harmony_workflow(adata, batch_key='batch')
```

**R V5:**
```r
source("scripts/r/utils.R")
obj <- prepare_input_v5(obj = merged_obj, sample_col = "sample")

source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_v5_standard(obj = obj, method = "harmony")

obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)
```

### "I have strong batch effects across different sequencing runs"

Use scVI (Python) or Seurat RPCA (R).

**Python:**
```python
from scripts.python.scvi import scvi_workflow
adata, model = scvi_workflow(adata, batch_key='batch')
```

**R V5:**
```r
source("scripts/r/utils.R")
obj <- prepare_input_v5(obj = merged_obj, sample_col = "sample")

source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_v5_standard(obj = obj, method = "rpca")

obj <- FindNeighbors(obj, reduction = "integrated.rpca", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "integrated.rpca", dims = 1:30)
```

### "I want to preserve rare cell populations"

Use fastMNN.

```r
source("scripts/r/utils.R")
obj <- prepare_input_v5(obj = merged_obj, sample_col = "sample")

source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_v5_standard(obj = obj, method = "fastmnn")

obj <- FindNeighbors(obj, reduction = "integrated.mnn", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "integrated.mnn", dims = 1:30)
```

### "I'm using SCTransform"

**Important:** SCT integration requires special handling. Use the `_sct` variants.

**R V5:**
```r
source("scripts/r/utils.R")
obj <- prepare_input_v5(obj = merged_obj, sample_col = "sample")

source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_v5_sct(obj = obj, method = "harmony")

obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)

# DE requires PrepSCTFindMarkers
obj <- PrepSCTFindMarkers(obj)
markers <- FindAllMarkers(obj)
```

**R V4:**
```r
source("scripts/r/utils.R")
prep <- prepare_input_v4(obj = merged_obj, sample_col = "sample")

source("scripts/r/seurat-v4/harmony.R")
obj <- harmony_v4_sct(obj_list = prep$obj_list, batch_col = "sample")

obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)

# DE requires PrepSCTFindMarkers
obj <- PrepSCTFindMarkers(obj)
markers <- FindAllMarkers(obj, only.pos = TRUE, min.pct = 0.25)
```

**V4 SCT critical note:** V4 lacks layers, so SCTransform must be run per-batch via SplitObject to avoid mixing batch effects in the regression model. After per-batch SCT and merge, the function sets `DefaultAssay(obj) <- "SCT"` and runs PCA directly on the SCT assay's `scale.data` — no `NormalizeData` or `ScaleData` needed.

### "I need to correct for multiple batch variables"

`IntegrateLayers` infers batches from layer structure and only supports single-variable correction. Use `harmony_v5_compat()` when you need to correct for multiple variables simultaneously (e.g. sample + condition + technology).

```r
source("scripts/r/utils.R")
obj <- prepare_input_v5(obj = merged_obj, sample_col = "sample")

source("scripts/r/seurat-v5/integrate.R")
obj <- harmony_v5_compat(
  obj = obj,
  group.by.vars = c("sample", "condition")
)

obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)
```

**Key differences from `integrate_v5_standard`:**
- Uses `RunHarmony` instead of `IntegrateLayers`
- Supports multiple variables via `group.by.vars`
- Joins layers first (needs unified matrix)
- Always produces `harmony` reduction

### "My data is already merged and I need to split by batch"

**V4:** Call `prepare_input_v4(obj = merged_obj, sample_col = "sample")` which returns both the merged object and the split list. Use `prep$obj` for Harmony/fastMNN, `prep$obj_list` for CCA/RPCA and SCT.

**V5:** Not needed. `merge()` auto-creates layers. Just call `prepare_input_v5(obj = merged_obj, sample_col = "sample")`.

## What the Agent Will Do

1. Check your Seurat version (V4 vs V5)
2. Identify your batch column
3. Choose appropriate method based on dataset size and batch effect strength
4. Run integration (preprocess → integrate → reduction)
5. Generate batch mixing visualizations
6. Run differential expression with correct assay settings

## Differential Expression Checklist

### V4 Standard
- [ ] `DefaultAssay(integrated) <- "RNA"`
- [ ] `NormalizeData(integrated)`
- [ ] `ScaleData(integrated)`
- [ ] Then run `FindAllMarkers`

### V4 SCT
- [ ] `PrepSCTFindMarkers(integrated)`
- [ ] `DefaultAssay(integrated) <- "SCT"`
- [ ] Then run `FindAllMarkers`
- [ ] If subsetting: use `recorrect_umi = FALSE`

### V5 Standard
- [ ] `JoinLayers` already called during integration
- [ ] `DefaultAssay` is already "RNA"
- [ ] Directly run `FindAllMarkers`

### V5 SCT
- [ ] `PrepSCTFindMarkers(obj)` (required!)
- [ ] `DefaultAssay` is already "SCT"
- [ ] Directly run `FindAllMarkers`
- [ ] No `JoinLayers` needed

## Evaluating Integration Quality

### Visual Assessment
- UMAP should show mixing of batches within cell types
- Cell types should cluster together across batches
- No batch-specific clusters

### Quick Metrics (R)
```r
# Before vs After UMAP
DimPlot(obj, reduction = "pca", group.by = "batch")     # Before
DimPlot(obj, reduction = "harmony", group.by = "batch") # After
```

### Quantitative Metrics
- **kBET:** Batch mixing within neighborhoods (higher = better mixing)
- **LISI:** Local inverse Simpson index for batch (higher = better mixing)
- **Silhouette:** Cell type separation (higher = better biology preservation)

## Tips

- **Harmony is the best default** for most cases
- **Preprocess each batch separately** before merging when using V4 CCA/RPCA
- **Check cell type representation** - ensure types are present across batches
- **Use batch as covariate in DE** - not integrated values directly
- **Keep original counts for DE** - use raw counts, not batch-corrected expression
- **Validate integration** - cell types should mix, not batch artifacts
- **V5 merge() auto-creates layers** - no need to manually split

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| "JoinLayers" error in V5 | Trying to access split layers as unified matrix | Call `JoinLayers(obj[["RNA"]])` |
| SCT DE gives weird results | Forgot `PrepSCTFindMarkers` | Run `PrepSCTFindMarkers(obj)` before DE |
| V4 CCA very slow | Too many cells for CCA | Use RPCA instead |
| Batches not mixing | Wrong batch column | Verify batch column has multiple unique values |
| "different assays" error in V4 | Objects have different assays before merge | Ensure all objects have only RNA assay before merge |
| scVI training fails | No GPU / CUDA issue | Set `use_gpu = FALSE` or check CUDA installation |

## File Organization

```
scripts/
├── python/
│   ├── harmony.py          # Harmony (scanpy)
│   ├── scvi.py             # scVI
│   ├── bbknn.py            # BBKNN
│   └── scanorama.py        # Scanorama
└── r/
    ├── utils.R             # Input preparation (prepare_input_v4 / v5)
    ├── seurat-v4/
    │   ├── harmony.R       # RunHarmony (Standard + SCT)
    │   ├── seurat_cca.R    # CCA (Standard + SCT)
    │   ├── seurat_rpca.R   # RPCA (Standard + SCT)
    │   └── fastmnn.R       # fastMNN
    └── seurat-v5/
        └── integrate.R     # Unified IntegrateLayers (Standard + SCT, all methods)
```

## Related Skills

- **bio-single-cell-preprocessing** - QC before integration
- **bio-single-cell-clustering** - Clustering after integration
- **bio-single-cell-cell-annotation** - Annotation after integration
- **bio-single-cell-data-io** - Loading multiple samples
