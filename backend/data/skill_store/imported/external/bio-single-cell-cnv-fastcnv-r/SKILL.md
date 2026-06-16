---
name: bio-single-cell-cnv-fastcnv-r
description: Single-cell CNV analysis using fastCNV (R)
version: 1.2
tool_type: r
primary_tool: fastCNV
language: r
dependencies:
  - fastCNV
  - Seurat >= 5.0.0
  - SeuratObject
  - ComplexHeatmap
  - dplyr
  - scales
system_requirements:
  - R >= 4.2.0
keywords: ["single-cell", "CNV", "fastCNV", "copy-number", "cancer", "aneuploidy", "subclone", "R"]
---

## Version Compatibility & Installation

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.2.0 | |
| fastCNV | Latest GitHub | `remotes::install_github("must-bioinfo/fastCNV")` |
| Seurat | >= 5.0.0 | Seurat v5 assay access compatible |
| SeuratObject | >= 5.0.0 | Required for `LayerData()` in v5 |
| scales | >= 1.0.0 | Required for `rescale_mid()` in UMAP plots |

```r
remotes::install_github("must-bioinfo/fastCNV")
remotes::install_github("must-bioinfo/fastCNVdata")  # Optional example datasets
```

## Skill Overview

fastCNV infers copy number variation (CNV) from scRNA-seq data using genome-wide sliding windows, with integrated subclone identification via CNV clustering.

**When to use:**
- Fast CNV inference on scRNA-seq data (~1 min for 4K cells)
- Tumor/normal cell classification using CNV burden
- CNV-based subclone identification and phylogenetic tree building
- Multi-sample analysis with pooled reference

**When NOT to use:**
- Non-cancer tissues without expected large-scale CNVs (most normal cells have flat CNV profiles)
- Detecting focal sub-gene-level CNVs (fastCNV operates at chromosome-arm resolution)
- When you need single-cell DNA-level CNV precision (scRNA-seq CNV is indirect and noisy)

## Core Workflow

### Step 1: Prepare Data

**Input:** Seurat object with raw counts  
**Output:** Seurat object ready for fastCNV

```r
library(Seurat)

seurat_obj <- readRDS("tumor_data.rds")

# Identify reference (normal) cells
# fastCNV uses these to calibrate baseline CNV = 0
table(seurat_obj$annot)
```

**Requirements:**
- Raw counts in the assay (fastCNV handles normalization internally)
- Gene symbols (not ENSEMBL) for chromosome mapping
- Cell type or sample annotations in `meta.data`

### Step 2: Run fastCNV

**Input:** Seurat object  
**Output:** Seurat object with CNV results in `meta.data`

```r
source("scripts/r/run_fastcnv.R")

# With reference (RECOMMENDED)
result <- run_fastcnv_sc(
  seurat_obj = seurat_obj,
  sample_name = "Tumor1",
  reference_var = "annot",
  reference_label = c("TNKILC", "Myeloid", "B", "Mast", "Plasma"),
  reCluster = FALSE,
  getCNVPerChromosomeArm = TRUE,
  savePath = "./fastcnv_output",
  printPlot = TRUE
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat / list | Required | Single Seurat object (NOT wrapped in `list()` for single sample) |
| `sample_name` | char | Required | Sample identifier |
| `reference_var` | char | `NULL` | Metadata column containing cell type labels |
| `reference_label` | char vector | `NULL` | Which labels are normal/reference cells |
| `reCluster` | bool | `FALSE` | Recluster if `seurat_clusters` already exists |
| `getCNVPerChromosomeArm` | bool | `TRUE` | Compute per-chromosome-arm CNV scores |
| `savePath` | char | `"."` | Directory for saved heatmap PDFs/PNGs |
| `printPlot` | bool | `TRUE` | Print plots to console |
| `denoise` | bool | `TRUE` | Denoise CNV profiles before clustering |
| `outputType` | char | `"png"` | Plot format: `"png"` or `"pdf"` |

### Step 3: Multi-Sample Analysis

**Input:** List of Seurat objects  
**Output:** Named list of Seurat objects with CNV results

```r
# IMPORTANT: use list(), NOT c()
results <- run_fastcnv_multi_sc(
  seurat_list = list(sample1, sample2, sample3),
  sample_names = c("S1", "S2", "S3"),
  reference_var = "annot",
  reference_label = c("Plasma", "TNKILC", "Myeloid", "B", "Mast")
)

# Access individual results
result_p1 <- results[["S1"]]
```

fastCNV automatically pools reference cells across all samples.

### Step 4: CNV Clustering and Subclone Analysis

**Input:** Seurat object with fastCNV results  
**Output:** Modified Seurat object + optionally tree data

```r
# Hierarchical clustering on CNV profiles
result <- cnv_cluster(result, reference_var = "annot")

# Merge correlated clusters to avoid over-splitting
result <- merge_cnv_clusters(result, mergeThreshold = 0.95)

# Classify chromosome-arm alterations (gain / loss / no alteration)
result <- cnv_classification(result, cnv_thresh = 0.1)

# Build phylogenetic tree
tree_data <- cnv_tree(
  result,
  values = "scores",
  cnv_thresh = 0.15,
  healthyClusters = "1"
)
```

### Step 5: Extract and Visualize Results

```r
# Extract CNV metadata as data frame
cnv_data <- extract_cnv_metadata(result, include_chromosomes = TRUE)

# Summary statistics by cluster/group
summarize_cnv_by_cluster(result, group_by = "cnv_clusters", metric = "cnv_fraction")
summarize_cnv_by_cluster(result, group_by = "cell_type", metric = "cnv_fraction")

# Export to CSV + RDS
export_cnv_results(result, output_dir = "./results", prefix = "sample1")

# CNV heatmap
plot_cnv_heatmap(result, reference_var = "annot", output_file = "cnv_heatmap.pdf")

# Chromosome arm on UMAP
plot_chr_arm_umap(result, feature = "20.p_CNV", limits = c(-1, 1))
```

**Output columns added to `meta.data`:**

| Column | Description |
|--------|-------------|
| `cnv_fraction` | Overall CNV burden per cell (0 = flat, higher = more aberrant) |
| `cnv_clusters` | CNV-based subclonal cluster ID |
| `*_CNV` (e.g., `20.p_CNV`) | Per chromosome arm CNV score |
| `*_CNV_classification` | Gain / loss / no_alteration call per arm |

## Complete Pipeline (Copy-Pasteable)

```r
library(Seurat)
source("scripts/r/run_fastcnv.R")

# Load data
seurat_obj <- readRDS("tumor_data.rds")

# 1. Run fastCNV with reference
result <- run_fastcnv_sc(
  seurat_obj = seurat_obj,
  sample_name = "Tumor1",
  reference_var = "annot",
  reference_label = c("TNKILC", "Myeloid", "B", "Mast", "Plasma"),
  reCluster = FALSE,
  getCNVPerChromosomeArm = TRUE,
  savePath = "./fastcnv_output",
  printPlot = FALSE
)

# 2. Subclone analysis
result <- cnv_cluster(result, reference_var = "annot")
result <- merge_cnv_clusters(result, mergeThreshold = 0.95)
result <- cnv_classification(result, cnv_thresh = 0.1)

# 3. Extract and export
cnv_data <- extract_cnv_metadata(result)
export_cnv_results(result, output_dir = "./results", prefix = "tumor1")

# 4. Visualize
FeaturePlot(result, features = "cnv_fraction", reduction = "umap")
DimPlot(result, group.by = "cnv_clusters", label = TRUE)
plot_cnv_heatmap(result, reference_var = "annot")
```

## Skill-Provided Functions

**Main analysis**
- `run_fastcnv_sc(seurat_obj, sample_name, reference_var, reference_label, reCluster, ...)` — single-sample CNV inference with auto list-unwrapping
- `run_fastcnv_multi_sc(seurat_list, sample_names, reference_var, reference_label, ...)` — multi-sample with pooled reference; validates list input and length matching

**Subclone analysis**
- `cnv_cluster(seurat_obj, reference_var, cellTypesToCluster, k, h)` — hierarchical CNV clustering
- `merge_cnv_clusters(seurat_obj, mergeThreshold)` — merge correlated clusters
- `cnv_classification(seurat_obj, cnv_thresh)` — classify gain/loss/no alteration (translates `cnv_thresh` to fastCNV's `peaks`)
- `cnv_tree(seurat_obj, values, cnv_thresh, healthyClusters)` — phylogenetic tree from CNV profiles

**Extraction & summarization**
- `extract_cnv_metadata(seurat_obj, include_chromosomes)` — extract CNV columns from meta.data as data frame; warns if no CNV data found
- `summarize_cnv_by_cluster(seurat_obj, group_by, metric)` — per-group mean/median/sd/min/max/n statistics; handles NA groups
- `export_cnv_results(seurat_obj, output_dir, prefix, export_matrix)` — exports metadata CSV + Seurat RDS; optionally exports CNV matrix (Seurat v5 compatible)

**Visualization**
- `plot_cnv_heatmap(seurat_obj, reference_var, clusters_var, output_file, ...)` — CNV heatmap with auto output-type detection; rasterization fallback on error
- `plot_chr_arm_umap(seurat_obj, feature, reduction, limits)` — UMAP with diverging RdBu color scale; validates feature and reduction existence

## Official API — Agents Often Miss These

**1. Single sample = pass object directly; multi-sample = pass `list()`**
```r
# Single sample — do NOT wrap in list()
fastCNV(seuratObj = seurat_obj, sampleName = "T1")

# Multi-sample — MUST wrap in list()
fastCNV(seuratObj = list(s1, s2, s3), sampleName = c("S1", "S2", "S3"))
```
Using `c(s1, s2, s3)` instead of `list(s1, s2, s3)` merges Seurat objects into one, which is almost never what you want.

**2. fastCNV parameter `reCluster` (not `reClusterSeurat`)**
The fastCNV native function uses `reCluster = FALSE`, not `reClusterSeurat`. Our wrapper accepts `reCluster` and maps it correctly.

**3. `CNVCluster` uses `k` and `h`, not `k_clusters` / `h_clusters`**
```r
# WRONG: fastCNV::CNVCluster(seuratObj, k_clusters = 3)
# RIGHT:
fastCNV::CNVCluster(seuratObj, k = 3, h = NULL)
```

**4. `CNVClassification` uses `peaks`, not `cnv_thresh`**
```r
# fastCNV native: peaks = c(-0.1, 0, 0.1) means:
#   < -0.1  → loss
#   -0.1~0.1 → no alteration
#   > 0.1   → gain
# Our wrapper: cnv_classification(seurat_obj, cnv_thresh = 0.1)
#   internally converts to peaks = c(-0.1, 0, 0.1)
```

**5. `CNVTree` default is `values = "scores"`, not `"calls"`**
fastCNV's `CNVTree` defaults to `"scores"` (continuous CNV scores). `"calls"` uses discrete gain/loss calls. The wrapper defaults to `"scores"` to match fastCNV.

**6. fastCNV returns a list even for single objects**
`fastCNV()` always returns a list. Our `run_fastcnv_sc()` wrapper automatically unwraps single-element lists.

**7. fastCNV auto-aggregates cells into meta-cells**
By default, fastCNV aggregates cells up to 15,000 counts per meta-cell. For very large datasets this happens automatically; you rarely need to call `prepareCountsForCNVAnalysis()` manually.

**8. `plotCNVResults` rasterization can fail on some systems**
The wrapper `plot_cnv_heatmap()` includes a tryCatch fallback that disables `raster_resize_mat` if the first attempt fails.

## Common Pitfalls

1. **⚠️ Wrapping single sample in `list()`**
   `run_fastcnv_sc(list(seurat_obj), ...)` returns a list, not a Seurat object. Pass the object directly for single-sample analysis.

2. **⚠️ Using `c()` instead of `list()` for multi-sample**
   `c(sample1, sample2)` merges Seurat objects. Always use `list(sample1, sample2)`.

3. **⚠️ No reference labels match the data**
   If `reference_label` values don't exist in `reference_var`, fastCNV runs without reference (silently). Always verify:
   ```r
   table(seurat_obj$annot)
   ```

4. **⚠️ Trying to run `cnv_cluster()` before `run_fastcnv_sc()`**
   `cnv_cluster` requires CNV data. Run `run_fastcnv_sc()` first.

5. **⚠️ UMAP reduction missing when plotting**
   `plot_chr_arm_umap()` and `FeaturePlot()` require a UMAP reduction. Run `RunUMAP()` first if needed.

6. **⚠️ Confusing `cnv_clusters` with `seurat_clusters`**
   `cnv_clusters` = CNV-based subclones. `seurat_clusters` = expression-based Leiden/Louvain clusters. They are different things.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `unused argument (reClusterSeurat = ...)` | Old code / wrong parameter name | Use `reCluster = FALSE` |
| `unused argument (k_clusters = ...)` | Parameter name mismatch | Use `k = 3` in `cnv_cluster()` |
| `unused argument (cnv_thresh = ...)` | Calling `CNVClassification` directly with wrong param | Use wrapper `cnv_classification()` or pass `peaks = c(-0.1, 0, 0.1)` |
| `No features overlap` / poor CNV signal | Too few cells or genes | Ensure ≥100 cells; check gene coverage across chromosomes |
| All cells have similar CNV | Reference cells are not truly normal | Re-verify reference labels; try running without reference |
| Too many CNV clusters | Over-splitting | Run `merge_cnv_clusters(result, mergeThreshold = 0.95)` |
| Heatmap plot fails / rasterization error | Graphics backend issue | Wrapper auto-retries with `raster_resize_mat = FALSE` |
| `Reduction 'umap' not found` | UMAP not computed | Run `RunUMAP(seurat_obj)` after `RunPCA` + `FindNeighbors` |

## Related Skills

- [bio-single-cell-cnv-copykat-r](../bio-single-cell-cnv-copykat-r/SKILL.md) — CNV with GMM-based tumor/normal classification
- [bio-single-cell-cnv-infercnv-r](../bio-single-cell-cnv-infercnv-r/SKILL.md) — CNV with Bayesian HMM and gene ordering
- [bio-single-cell-cnv-scevan-r](../bio-single-cell-cnv-scevan-r/SKILL.md) — Pipeline integrating CNV + clone + expression
- [bio-spatial-transcriptomics-cnv-fastcnv-r](../bio-spatial-transcriptomics-cnv-fastcnv-r/SKILL.md) — Spatial transcriptomics CNV with fastCNV

## References

1. Cabrejas et al. (2025). fastCNV: Fast and accurate copy number variation prediction from High-Definition Spatial Transcriptomics and scRNA-Seq Data. *bioRxiv*, 2025.10.22.683855.
2. fastCNV documentation: https://must-bioinfo.github.io/fastCNV/
3. fastCNV scRNA-seq vignette: https://must-bioinfo.github.io/fastCNV/articles/fastCNV_sc.html
