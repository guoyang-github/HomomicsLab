---
name: bio-single-cell-batch-integration
description: Integrate multiple scRNA-seq samples/batches using Harmony, scVI, Seurat anchors (CCA/RPCA), and fastMNN. Remove technical variation while preserving biological differences. Organized by language (Python/R), Seurat version (V4/V5), and normalization strategy (Standard/SCTransform).
tool_type: mixed
primary_tool: Harmony
supported_tools: [scvi-tools, scanpy, seurat, anndata]
keywords: ["single-cell", "batch-integration", "harmony", "scVI", "seurat", "fastMNN", "batch-correction", "SCTransform"]
---

## Version Compatibility

Reference examples tested with:
- Python: anndata 0.10+, scanpy 1.10+, scikit-learn 1.4+, scvi-tools 1.1+, harmonypy 0.0.10+
- R: Seurat 4.4+ / 5.0+, harmony 1.0+, batchelor 1.18+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

## Quick Reference: Method Selection

| Scenario | Recommended | Why |
|----------|-------------|-----|
| Quick integration, most cases | Harmony | Fast, works well for most scenarios |
| Large datasets (>500k cells) | scVI or BBKNN | Scalable, GPU-accelerated options |
| Strong batch effects | scVI | Deep learning handles complex effects |
| Reference mapping | scArches | Transfer learning from atlases |
| Preserving rare populations | fastMNN | Local structure preservation |
| CITE-seq multi-modal | totalVI | Joint RNA+protein modeling |

## Comprehensive Method Comparison

| Method | Algorithm | Input | Output | Speed | Memory | Batch Effect Strength | Rare Populations | Best Use Case |
|--------|-----------|-------|--------|-------|--------|----------------------|------------------|---------------|
| **Harmony** | Linear correction | PCA | Corrected PCA | Fast | Low | Mild-Moderate | Preserved | General purpose, most cases |
| **scVI** | Deep VAE | Raw/Normalized | Latent space | Medium | Medium-High | Strong | Can be lost | Complex batch effects, large datasets |
| **Seurat CCA** | CCA + anchors | Normalized | Integrated expression | Medium | Medium | Moderate | Preserved | Reference-based integration |
| **Seurat RPCA** | Reciprocal PCA | Normalized | Integrated expression | Fast | Low | Moderate | Preserved | Large datasets, faster alternative to CCA |
| **fastMNN** | MNN correction | Normalized | Corrected expression | Medium | Medium | Moderate | Well preserved | Preserving rare populations |
| **BBKNN** | Graph-based | PCA | Corrected graph | Fast | Low | Mild-Moderate | Preserved | Quick integration, preserve local structure |
| **Scanorama** | MNN + correction | Normalized | Corrected expression | Medium | Medium | Mild | Preserved | Partial cell type overlap |

## Method Selection Decision Tree

```
What is your data type?
|
├── CITE-seq (RNA + Protein)
│   └── Use: totalVI
|
├── scRNA-seq only
│   │
│   ├── Mapping query to reference?
│   │   └── Use: scArches
│   │
│   ├── >500k cells?
│   │   ├── Strong batch effects? → scVI
│   │   └── Otherwise → BBKNN or Harmony
│   │
│   ├── Preserving rare populations critical?
│   │   └── Use: fastMNN or BBKNN
│   │
│   ├── Partial overlap of cell types?
│   │   └── Use: Scanorama
│   │
│   ├── Have reference atlas?
│   │   └── Use: Seurat CCA (reference-based)
│   │
│   └── General purpose, quick?
│       ├── Python → Harmony (scanpy)
│       └── R → Harmony or Seurat RPCA
```

## Performance Benchmarks

| Dataset Size | Method | Runtime | Memory |
|-------------|--------|---------|--------|
| 10k cells | Harmony | ~1 min | ~2 GB |
| 10k cells | scVI | ~5 min | ~4 GB |
| 10k cells | Seurat CCA | ~3 min | ~3 GB |
| 100k cells | Harmony | ~5 min | ~8 GB |
| 100k cells | scVI | ~20 min | ~16 GB |
| 100k cells | Seurat RPCA | ~10 min | ~10 GB |
| 500k cells | BBKNN | ~15 min | ~20 GB |
| 500k cells | scVI (GPU) | ~30 min | ~24 GB |

---

# Python Methods

## Harmony (Scanpy)

**Goal:** Remove batch effects from merged scRNA-seq datasets using Harmony's iterative correction of PCA embeddings.

**Approach:** Preprocess merged data (normalize, HVG, scale, PCA), run Harmony on PCA embeddings, cluster on corrected coordinates.

**Input State:** Merged AnnData with raw counts and batch labels in `obs`
**Output State:** AnnData with `obsm['X_pca_harmony']` and clusters

Source: `scripts/python/harmony.py`

```python
from scripts.python.harmony import harmony_workflow

# adata: merged AnnData with raw counts
adata = harmony_workflow(adata, batch_key='batch', resolution=0.5)
# Result: obsm['X_pca_harmony'], obs['leiden_harmony']
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `adata` | AnnData | Yes | - | Merged data with raw counts |
| `batch_key` | string | Yes | 'batch' | Column in obs defining batches |
| `n_top_genes` | int | No | 2000 | Highly variable genes |
| `n_pcs` | int | No | 50 | PCs for PCA |
| `resolution` | float | No | 0.5 | Leiden resolution |

## scVI

**Goal:** Integrate batches using a deep generative model that learns a shared latent space.

**Approach:** Train a variational autoencoder conditioned on batch to learn batch-invariant latent representations.

**Input State:** Merged AnnData with raw counts
**Output State:** AnnData with `obsm['X_scVI']` and trained model

Source: `scripts/python/scvi.py`

```python
from scripts.python.scvi import scvi_workflow

adata, model = scvi_workflow(adata, batch_key='batch',
                              n_latent=30, max_epochs=100)
# Result: obsm['X_scVI'], obs['leiden_scvi']
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `adata` | AnnData | Yes | - | Merged data (uses adata.raw if available) |
| `batch_key` | string | Yes | 'batch' | Batch column |
| `n_latent` | int | No | 30 | Latent dimensions |
| `max_epochs` | int | No | 100 | Training epochs |
| `use_gpu` | bool | No | True | Use GPU |

## BBKNN

**Goal:** Fast batch-balancing k-nearest neighbors integration that preserves local cell-type structure.

**Approach:** Compute neighbors within each batch separately, then connect batches via mutual nearest neighbor graph.

**Input State:** Merged AnnData with raw counts
**Output State:** AnnData with corrected neighbor graph in `obsp['connectivities']`

Source: `scripts/python/bbknn.py`

```python
from scripts.python.bbknn import bbknn_workflow

adata = bbknn_workflow(adata, batch_key='batch')
# Result: obsp['connectivities'] corrected, obs['leiden_bbknn']
```

## Scanorama

**Goal:** Integrate datasets with partial cell-type overlap using mutual nearest neighbor matching and correction.

**Approach:** Find MNN pairs between datasets, compute correction vectors, apply transformations.

**Input State:** List of AnnData objects (preprocess each separately)
**Output State:** Merged AnnData with corrected expression matrix

Source: `scripts/python/scanorama.py`

```python
from scripts.python.scanorama import scanorama_workflow

# adatas: list of AnnData objects (raw counts)
corrected = scanorama_workflow(adatas, dimred=50)
# Result: corrected AnnData with obs['leiden_scanorama']
```

---

# R Methods

**Default recommendation: Use Seurat V5 methods.** V5 provides native layer-based integration via `IntegrateLayers`, eliminating the need for manual `SplitObject` and `JoinLayers`. Only use V4 methods if your pipeline explicitly requires Seurat 4.x compatibility.

## Seurat V4 vs V5 Core Differences

| Feature | V4 | V5 |
|---------|-----|-----|
| Data structure | Single matrix (`assays$RNA@counts`) | Layers (`layers(counts)`, `JoinLayers()`) |
| Merge behavior | Concatenates to single matrix | Auto-creates split layers |
| Consensus HVG | Must call `SelectIntegrationFeatures` | `FindVariableFeatures` auto-selects across layers |
| Integration CCA/RPCA | `FindIntegrationAnchors + IntegrateData` | `IntegrateLayers` |
| New assay created | Yes (`integrated`) | No (reduction only) |
| Post-DE (Standard) | Switch to `RNA`, re-normalize | `JoinLayers` |
| Post-DE (SCT) | `PrepSCTFindMarkers` | `PrepSCTFindMarkers` (no JoinLayers) |

## Seurat V5 Methods (Default)

### Input Preparation (V5)

All V5 integration functions receive data through `prepare_input_v5()`, which:
1. Validates all inputs are Seurat objects
2. Names objects and sets `Project()` for consistent layer suffixes after merge
3. Merges objects with `add.cell.ids`
4. **Auto-detects v5 assay** and sets it as `DefaultAssay`
5. Validates V5 `StdAssay`

```r
source("scripts/r/utils.R")

# From merged object
obj <- prepare_input_v5(obj = merged_obj, sample_col = "sample")

# From separate files
obj <- prepare_input_v5(
  file_paths = c("sample1.rds", "sample2.rds", "sample3.rds"),
  sample_col = "sample"
)

# From object list
obj <- prepare_input_v5(obj_list = list(s1, s2), sample_col = "sample")
```

Returns a merged Seurat object with:
- Layers (V5) for batch-aware integration (layer suffixes match `add.cell.ids`)
- v5 assay set as `DefaultAssay`

All V5 functions take this object directly.

**sample_col参数及add.cell.ids名称推断详解**

| 输入来源 | `sample_col` 的行为 |
|---------|-------------------|
| `file_paths` / `obj_list` | 1. 尝试从每个对象的元数据读取该列的唯一值，作为批次名<br>2. 若该列不存在、不唯一、或为 NA，则回退到 文件名 / list names<br>3. **最终将该列的值统一覆盖为确定的批次名** |
| `obj`（已合并） | 仅验证该列已存在；不修改其值；用于 `split()` |

**名称推断优先级（由高到低）：**

  1. `obj_list[[i]]@meta.data[[sample_col]]` 的唯一非空值
  2. `basename(file_paths[i])`（去掉 `.rds`）或 `names(obj_list)[i]`
  3. `S1`, `S2`, ... fallback

### V5 Integration Template

All V5 methods share the same `IntegrateLayers` workflow. Only the `method` parameter differs.

Source: `scripts/r/seurat-v5/integrate.R`

#### Standard (LogNormalize)

```r
source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_v5_standard(obj = obj, method = "harmony")
```

#### SCTransform

```r
obj <- integrate_v5_sct(obj = obj, method = "harmony")
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `obj` | Seurat | Yes | - | Merged object with layers |
| `method` | string | No | 'harmony' | Integration method (see table below) |
| `npcs` | int | No | 50 | PCs for PCA |

**Method selection:**

| method | Reduction name | Best for |
|--------|---------------|----------|
| `"harmony"` | `harmony` | General purpose, fast (default) |
| `"cca"` | `integrated.cca` | Conserved biology, reference mapping |
| `"rpca"` | `integrated.rpca` | Large datasets (>100k cells) |
| `"fastmnn"` | `integrated.mnn` | Preserving rare populations |

**What the function does:**
1. Preprocess: Normalize/Scale/PCA (Standard) or SCTransform/PCA (SCT)
2. `IntegrateLayers()` with chosen method
3. `JoinLayers()` on the default assay (Standard only)

#### Multi-Variable Batch Correction

When you need to correct for multiple batch variables simultaneously (e.g. sample + condition + technology), use `harmony_v5_compat()` instead of `IntegrateLayers`.

```r
obj <- harmony_v5_compat(
  obj = obj,
  group.by.vars = c("sample", "condition")
)
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `obj` | Seurat | Yes | - | Merged object |
| `group.by.vars` | string vector | Yes | - | Metadata column(s) for batch correction |
| `npcs` | int | No | 50 | PCs for PCA |

**Key differences from `integrate_v5_standard`:**
- Uses `RunHarmony` instead of `IntegrateLayers`
- Reads batch information from metadata columns, not layer structure
- Supports multiple variables via `group.by.vars`
- Joins layers first (needs unified matrix)
- Always produces `harmony` reduction

**What the function does NOT do:**
- `FindNeighbors`, `FindClusters`, `RunUMAP` — handled by the clustering skill

**Downstream reduction selection:**
- Use `reduction = "harmony"` for Harmony method
- Use `reduction = "integrated.cca"` for CCA method
- Use `reduction = "integrated.rpca"` for RPCA method
- Use `reduction = "integrated.mnn"` for fastMNN method

**Critical differences from V4:**
- No `SplitObject` needed (layers auto-created by `merge()`)
- No new assay created (reduction only)
- Standard: `JoinLayers` called internally
- SCT: `normalization.method = "SCT"` passed to `IntegrateLayers`

---


## Seurat V4 Methods (Legacy Compatibility)

### Input Preparation (V4)

All V4 integration functions receive data through `prepare_input_v4()`, which:
1. Validates all inputs are Seurat objects
2. Merges objects with `add.cell.ids`
3. Detects and resolves `orig.ident` duplicates across objects
4. Switches `DefaultAssay` back to `"RNA"` if it was `"SCT"`
5. Splits object by `sample_col` into per-batch list

```r
source("scripts/r/utils.R")

# From merged object
prep <- prepare_input_v4(obj = merged_obj, sample_col = "sample")

# From separate files
prep <- prepare_input_v4(
  file_paths = c("sample1.rds", "sample2.rds", "sample3.rds"),
  sample_col = "sample"
)

# From pre-split list
prep <- prepare_input_v4(obj_list = list(s1, s2), sample_col = "sample")
```

Returns a list with:
- `prep$obj`: merged Seurat object — use for **Harmony Standard**, **fastMNN**
- `prep$obj_list`: list split by batch — use for **Harmony SCT**, **CCA**, **RPCA**

### Harmony V4

**Goal:** Remove batch effects directly on PCA embeddings without creating a new assay.

**Input:** `prep$obj` (Standard) or `prep$obj_list` (SCT)
**Output:** Seurat object with `reductions$harmony`

Source: `scripts/r/seurat-v4/harmony.R`

#### Standard (LogNormalize)

```r
source("scripts/r/seurat-v4/harmony.R")
obj <- harmony_v4_standard(obj = prep$obj, batch_col = "sample")
```

#### SCTransform

```r
obj <- harmony_v4_sct(obj_list = prep$obj_list, batch_col = "sample")
```

**harmony_v4_standard:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `obj` | Seurat | Yes | - | Merged object |
| `batch_col` | string | No | 'orig.ident' | Metadata column for batches |
| `nfeatures` | int | No | 2000 | HVG count |
| `npcs` | int | No | 50 | PCs for PCA |
| `dims_use` | numeric | No | 1:30 | PCs for Harmony |

**harmony_v4_sct:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `obj_list` | list | Yes | - | List of objects per batch |
| `batch_col` | string | No | 'orig.ident' | Metadata column for batches |
| `npcs` | int | No | 50 | PCs for PCA |
| `dims_use` | numeric | No | 1:30 | PCs for Harmony |

**What the function does NOT do:** `FindNeighbors`, `FindClusters`, `RunUMAP` — handled by the clustering skill.

**V4 SCT flow:** per-batch SCTransform → merge → `DefaultAssay(obj) <- "SCT"` → RunPCA(SCT assay) → RunHarmony. The SCT assay's `scale.data` is used directly for PCA; no `NormalizeData` or `ScaleData` needed.

### Seurat CCA V4

**Goal:** Anchor-based integration using Canonical Correlation Analysis.

**Input:** `prep$obj_list` (list of objects, one per batch)
**Output:** Integrated Seurat object with `assays$integrated`

Source: `scripts/r/seurat-v4/seurat_cca.R`

#### Standard

```r
source("scripts/r/seurat-v4/seurat_cca.R")
integrated <- seurat_cca_v4_standard(obj_list = prep$obj_list)
```

#### SCTransform

```r
integrated <- seurat_cca_v4_sct(obj_list = prep$obj_list)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `obj_list` | list | Yes | - | List of Seurat objects per batch |
| `anchor_features` | int | No | 2000/3000 | Integration features |
| `dims` | numeric | No | 1:30 | Dimensions for anchors |

**What the function does:** per-object NormalizeData+HVG (Standard) or SCTransform (SCT) → SelectIntegrationFeatures → FindIntegrationAnchors(reduction="cca") → IntegrateData → ScaleData → RunPCA. Stops at PCA; use clustering skill for downstream.

### Seurat RPCA V4

**Goal:** Faster anchor-based integration using Reciprocal PCA for large datasets.

Source: `scripts/r/seurat-v4/seurat_rpca.R`

#### Standard

```r
source("scripts/r/seurat-v4/seurat_rpca.R")
integrated <- seurat_rpca_v4_standard(obj_list = prep$obj_list)
```

#### SCTransform

```r
integrated <- seurat_rpca_v4_sct(obj_list = prep$obj_list)
```

Same parameters as CCA. Key difference: `reduction = "rpca"` in `FindIntegrationAnchors`. Stops at PCA; use clustering skill for downstream.

### fastMNN V4

**Goal:** MNN-based correction preserving rare cell populations.

**Input:** `prep$obj` (single merged object)
**Output:** Seurat object with `reductions$mnn`

Source: `scripts/r/seurat-v4/fastmnn.R`

```r
source("scripts/r/seurat-v4/fastmnn.R")
obj <- fastmnn_v4(obj = prep$obj, batch_col = "sample")
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `obj` | Seurat | Yes | - | Merged object |
| `batch_col` | string | No | 'orig.ident' | Batch metadata column |
| `d` | int | No | 30 | MNN dimensions |
| `k` | int | No | 20 | MNN k parameter |

**What the function does NOT do:** `FindNeighbors`, `FindClusters`, `RunUMAP` — handled by the clustering skill.

---

## SCTransform Integration Notes

### When to Use SCTransform

- Batch effects include significant differences in sequencing depth
- Want regularized negative binomial regression instead of global log-normalization
- Better for datasets with highly variable library sizes

**V4 SCT critical note:** V4 lacks layers. Running SCTransform on a merged matrix mixes batch effects into the regression model. The corrected approach runs SCT per-batch on a pre-split list, then merges and uses the SCT assay's `scale.data` directly for PCA. The `harmony_v4_sct()` function accepts `obj_list` directly (no internal `SplitObject`).

**V5 SCT:** `SCTransform()` auto runs per-layer on the default assay. The function asserts that the default assay is a v5 `StdAssay`. `IntegrateLayers(..., normalization.method = "SCT")` handles batch correction. No `JoinLayers` needed for SCT.

---

# Differential Expression After Integration

## V4 Standard (LogNormalize)

```r
# After CCA/RPCA integration, switch back to RNA assay
DefaultAssay(integrated) <- "RNA"

# Must re-normalize and scale the unified object
integrated <- NormalizeData(integrated)
integrated <- ScaleData(integrated)

# Run DE
markers <- FindAllMarkers(integrated, only.pos = TRUE, min.pct = 0.25, logfc.threshold = 0.25)
```

**Why:** Integration前的标准化是各样本独立进行的，整合后的统一对象需要全局重新计算校正因子和z-score。

## V4 SCTransform

```r
# Prep corrected counts
integrated <- PrepSCTFindMarkers(integrated)

# Use SCT assay
DefaultAssay(integrated) <- "SCT"
markers <- FindAllMarkers(integrated, only.pos = TRUE, min.pct = 0.25)

# If subsetting before DE
subset_obj <- subset(integrated, idents = c("A", "B"))
markers <- FindMarkers(subset_obj, ident.1 = "A", ident.2 = "B",
                       recorrect_umi = FALSE)
```

## V5 Standard (LogNormalize)

```r
# After IntegrateLayers with LogNormalize
# JoinLayers must have been called during integration
# DefaultAssay is already "RNA"
markers <- FindAllMarkers(obj, only.pos = TRUE, min.pct = 0.25, logfc.threshold = 0.25)
```

## V5 SCTransform

```r
# After IntegrateLayers with SCT
# Must PrepSCTFindMarkers before DE
obj <- PrepSCTFindMarkers(obj)

# DefaultAssay is already "SCT"
markers <- FindAllMarkers(obj, only.pos = TRUE, min.pct = 0.25)
```

**Key difference:** V5 SCT does NOT need `JoinLayers` before DE. `PrepSCTFindMarkers` handles multi-layer complexity internally.

---

# Complete Workflow: Two-Step Pattern

All R integration workflows follow the same three-step pattern:
1. **Prepare input** with `prepare_input_v4()` or `prepare_input_v5()`
2. **Run integration** with the method-specific function
3. **Cluster + visualize** with `FindNeighbors` / `FindClusters` / `RunUMAP`

## V4 Example: Harmony Standard

```r
library(Seurat)

# Step 1: Prepare input
source("scripts/r/utils.R")
prep <- prepare_input_v4(obj = merged_obj, sample_col = "sample")

# Step 2: Run integration
source("scripts/r/seurat-v4/harmony.R")
obj <- harmony_v4_standard(obj = prep$obj, batch_col = "sample")

# Step 3: Clustering + UMAP
obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)

# Step 4: DE (V4 Standard)
DefaultAssay(obj) <- "RNA"
obj <- NormalizeData(obj)
obj <- ScaleData(obj)
markers <- FindAllMarkers(obj, only.pos = TRUE, min.pct = 0.25)
```

## V4 Example: Harmony SCT

```r
library(Seurat)

# Step 1: Prepare input
source("scripts/r/utils.R")
prep <- prepare_input_v4(obj = merged_obj, sample_col = "sample")

# Step 2: Run integration (SCT uses obj_list)
source("scripts/r/seurat-v4/harmony.R")
obj <- harmony_v4_sct(obj_list = prep$obj_list, batch_col = "sample")

# Step 3: Clustering + UMAP
obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)

# Step 4: DE (V4 SCT)
obj <- PrepSCTFindMarkers(obj)
markers <- FindAllMarkers(obj, only.pos = TRUE, min.pct = 0.25)
```

## V4 Example: CCA from Separate Files

```r
library(Seurat)

# Step 1: Prepare input from files
source("scripts/r/utils.R")
prep <- prepare_input_v4(
  file_paths = c("sample1.rds", "sample2.rds", "sample3.rds"),
  sample_col = "sample"
)

# Step 2: Run integration (CCA needs obj_list)
source("scripts/r/seurat-v4/seurat_cca.R")
integrated <- seurat_cca_v4_standard(obj_list = prep$obj_list)

# Step 3: Clustering + UMAP
integrated <- FindNeighbors(integrated, reduction = "pca", dims = 1:30)
integrated <- FindClusters(integrated, resolution = 0.5)
integrated <- RunUMAP(integrated, reduction = "pca", dims = 1:30)

# Step 4: DE (V4 Standard)
DefaultAssay(integrated) <- "RNA"
integrated <- NormalizeData(integrated)
integrated <- ScaleData(integrated)
markers <- FindAllMarkers(integrated, only.pos = TRUE, min.pct = 0.25)
```

## V5 Example: Harmony IntegrateLayers from Files

```r
library(Seurat)

# Step 1: Prepare input from files
source("scripts/r/utils.R")
obj <- prepare_input_v5(
  file_paths = c("sample1.rds", "sample2.rds", "sample3.rds"),
  sample_col = "sample"
)

# Step 2: Run integration
source("scripts/r/seurat-v5/integrate.R")
obj <- integrate_v5_standard(obj = obj, method = "harmony")

# Step 3: Clustering + UMAP
obj <- FindNeighbors(obj, reduction = "harmony", dims = 1:30)
obj <- FindClusters(obj, resolution = 0.5)
obj <- RunUMAP(obj, reduction = "harmony", dims = 1:30)

# Step 4: DE (V5 Standard)
markers <- FindAllMarkers(obj, only.pos = TRUE, min.pct = 0.25)
```

## Input Patterns Summary

| Pattern | Function | Input | V4 Returns | V5 Returns |
|---------|----------|-------|-----------|-----------|
| Merged object | `prepare_input_v4/5(obj=merged_obj)` | Seurat object | `obj` + `obj_list` | `obj` |
| Separate files | `prepare_input_v4/5(file_paths=c(...))` | .rds paths | `obj` + `obj_list` | `obj` |
| Pre-split list | `prepare_input_v4/5(obj_list=list(...))` | List of objects | `obj` + `obj_list` | `obj` |

Default `batch_col` for both V4 and V5: `"sample"`.

---

# Evaluate Integration

## Mixing Metrics (R)

```r
library(lisi)
lisi_scores <- compute_lisi(Embeddings(merged, 'harmony'),
                            merged@meta.data, c('batch', 'cell_type'))
mean(lisi_scores$batch)      # Want high (batches mixed)
mean(lisi_scores$cell_type)  # Want low (types separated)
```

## Visual Assessment

```r
# Before integration
DimPlot(merged, reduction = 'pca', group.by = 'batch')
# After integration
DimPlot(merged, reduction = 'harmony', group.by = 'batch')
```

## Silhouette Score (Python)

```python
from sklearn.metrics import silhouette_score
batch_sil = silhouette_score(adata.obsm['X_scVI'], adata.obs['batch'])
celltype_sil = silhouette_score(adata.obsm['X_scVI'], adata.obs['cell_type'])
```

---

## Related Skills

- bio-single-cell-preprocessing - QC before integration
- bio-single-cell-clustering - Clustering after integration
- bio-single-cell-cell-annotation - Annotation after integration
- bio-single-cell-data-io - Loading multiple samples
