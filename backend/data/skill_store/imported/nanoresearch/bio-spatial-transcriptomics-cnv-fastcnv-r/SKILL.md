---
name: bio-spatial-transcriptomics-cnv-fastcnv-r
description: CNV analysis for spatial transcriptomics and scRNA-seq using fastCNV (R)
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
  - Memory: 64GB+ recommended for Visium HD
keywords: ["spatial-transcriptomics", "CNV", "fastCNV", "copy-number", "Visium", "Visium-HD", "cancer", "R"]
---

## Version Compatibility & Installation

| Component | Version |
|-----------|---------|
| R | ≥ 4.2.0 |
| Seurat | ≥ 5.0.0 |
| fastCNV | Latest from GitHub |
| SeuratObject | ≥ 5.0.0 |

```r
remotes::install_github("must-bioinfo/fastCNV")
remotes::install_github("must-bioinfo/fastCNVdata")  # Optional: example datasets
```

---

## Skill Overview

**Fast and accurate copy number variation (CNV) prediction** for spatial transcriptomics (Visium, Visium HD) and scRNA-seq data. Built on SeuratObject, fastCNV computes per-chromosome-arm CNV scores, identifies tumor subclones, and supports spatial mapping of CNV fractions.

### When to Use fastCNV

- **Visium / Visium HD**: Primary choice for spatial CNV analysis (~1 min for 4K cells, ~40 min for Visium HD 16 µm)
- **Multi-sample cohorts**: Automatic pooled reference across samples for cross-sample consistency
- **Subclone detection**: CNV-based clustering (`CNVCluster`) + phylogenetic tree (`CNVTree`)
- **scRNA-seq**: Alternative to inferCNV/CopyKAT; same API works on single-cell data

### When NOT to Use fastCNV

- **Mouse data**: Human-only (mouse support in development)
- **Non-Seurat data**: Requires Seurat v5 object as input
- **No gene symbols**: CNV arm-level annotation requires gene symbols; ENSEMBL IDs need mapping first

---

## Core Workflow

> **Precondition**: Seurat v5 object with counts and metadata annotations. For Visium HD, ensure annotations are on the same resolution (16 µm) as the assay.

### Step 1 — Run fastCNV (Single Sample or Multi-Sample)

**Input**: `Seurat object` with metadata annotations (e.g., `"cell_type"`, `"annot"`)  
**Output**: `Seurat object` with CNV results added to `meta.data` and `CNV` assay

```r
source("scripts/r/fastcnv_analysis.R")

# Single sample — pass object directly, NOT wrapped in list()
result <- run_fastcnv(
  seuratObj   = seurat_obj,
  sampleName  = "Tumor_Sample",
  referenceVar    = "annotations",     # metadata column with healthy labels
  referenceLabel  = "Healthy",         # label value(s) for reference
  aggregFactor    = 15000,             # max counts per meta-spot
  aggregateByVar  = TRUE,              # aggregate by cluster + cell type
  reCluster       = FALSE,             # recluster on SCT data with 10 PCs
  getCNVPerChromosomeArm = TRUE,       # per-arm CNV scores
  savePath        = "./fastcnv_output",
  printPlot       = FALSE              # set FALSE for batch runs
)
```

| Parameter | Type | Default | What It Does | When to Change |
|-----------|------|---------|--------------|----------------|
| `seuratObj` | Seurat / list | required | Input object(s) | For multi-sample, pass a `list()` of objects |
| `sampleName` | char / vector | required | Sample name(s) | Must match length of `seuratObj` |
| `referenceVar` | char | `NULL` | Metadata column for reference | Set to column with healthy/normal annotations |
| `referenceLabel` | char / vector | `NULL` | Reference label(s) | See **⚠️ Reference Label Behavior** below |
| `aggregFactor` | int | 15000 | Max counts per meta-spot | Lower (e.g., 10000) for HD/high-density data |
| `aggregateByVar` | bool | `TRUE` | Aggregate by cluster + cell type | **Keep TRUE** — significantly denoises CNV |
| `reCluster` | bool | `FALSE` | Recluster if `seurat_clusters` exists | Only if you need expression-based reclustering |
| `getCNVPerChromosomeArm` | bool | `TRUE` | Per-chromosome-arm CNV | **Keep TRUE** for downstream arm-level analysis |
| `savePath` | char | `"."` | Directory for saved heatmaps | Use per-sample subdirectories for cohorts |
| `printPlot` | bool | `TRUE` | Print plots to console | Set `FALSE` in batch/slurm runs |

#### ⚠️ Reference Label Behavior (Critical)

`referenceLabel` uses **global exact matching across ALL samples** — it is **not** per-sample isolated:

- **Single label** (`referenceLabel = "Healthy"`): Searches all samples for spots annotated as `"Healthy"`, pools them into one reference.
- **Multiple labels** (`referenceLabel = c("Normal", "Healthy")`): Searches **all samples** for both labels. Each matched label group computes its own scale factor; the final reference is the **median** across all label groups.
- **Minimum threshold**: Each sample must have **≥ 5** spots matching a given label, or that sample is silently excluded from that label's pool.
- **Zero-match fallback**: If no spots match any label across all samples, fastCNV falls back to reference-free mode with a warning.

> **Practical implication**: If your samples use different annotation names for healthy tissue (e.g., Sample1 uses `"Normal"`, Sample2 uses `"Healthy"`), pass **both** labels: `referenceLabel = c("Normal", "Healthy")`.

#### Multi-Sample (Pooled Reference)

```r
results_list <- run_fastcnv_multi(
  seuratObjs   = list(s1, s2, s3),
  sampleNames  = c("S1", "S2", "S3"),
  referenceVar     = "annotations",
  referenceLabel   = c("Normal", "Healthy"),  # pools across all samples
  printPlot = FALSE
)
# Returns named list of Seurat objects
```

**Input validation** that `run_fastcnv_multi` adds:
- `seuratObjs` must be a `list()` (not `c()`)
- All elements must be Seurat objects
- Lengths of `seuratObjs` and `sampleNames` must match
- Results are auto-named with `sampleNames`

#### Visium HD

```r
result_hd <- run_fastcnv_hd(
  seuratObj  = seurat_hd,
  sampleName = "HD_Sample",
  referenceVar   = "projected_annots_8um",
  referenceLabel = "NoTumor",
  getCNVPerChromosomeArm = TRUE
)
```

> **Memory warning**: Visium HD is very RAM-demanding. ~64GB for 16 µm bins; ~200GB for 8 µm bins.

### Step 2 — Access CNV Results

**Input**: `Seurat object` after `run_fastcnv()`  
**Output**: Extracted vectors / data frames

```r
# Overall CNV burden per spot
head(result@meta.data$cnv_fraction)

# CNV-based subclonal clusters
table(result@meta.data$cnv_clusters)

# Per chromosome arm CNV (e.g., "11.q_CNV", "8.q_CNV")
chr_arm_cols <- grep("_CNV$", colnames(result@meta.data), value = TRUE)

# Full CNV matrix
# Seurat v5: use LayerData; v4: use GetAssayData
cnv_matrix <- result@assays$CNV$data

# Extract all results to a flat data.frame
cnv_df <- extract_cnv_results(result, include_chromosomes = TRUE)
```

### Step 3 — CNV Clustering & Classification (Subclone Analysis)

**Input**: `Seurat object` with fastCNV results  
**Output**: `Seurat object` with `cnv_clusters`, classification columns

```r
# Hierarchical clustering on CNV profiles
result <- cnv_cluster(
  result,
  referenceVar     = "annotations",     # optional: subset to non-reference for clustering
  cellTypesToCluster = "Tumor",         # optional: cluster only tumor spots
  k_clusters = NULL,                      # NULL = auto; set to fixed k if desired
  h_clusters = NULL                       # NULL = auto; set height for dendrogram cut
)

# Merge highly correlated clusters
result <- merge_cnv_clusters(result, mergeThreshold = 0.95)

# Classify gains/losses per chromosome arm
result <- cnv_classification(result, cnv_thresh = 0.09)
# Adds columns like: "11.q_CNV_classification" → gain / loss / no_alteration

# Build CNV phylogenetic tree
tree_data <- cnv_tree(
  result,
  values         = "calls",       # "calls" or "fractions"
  cnv_thresh     = 0.09,
  healthyClusters = "1"           # cluster ID(s) representing healthy tissue
)
```

### Step 4 — Visualize

**Input**: `Seurat object` with CNV results  
**Output**: Plots (ggplot2 or ComplexHeatmap)

```r
# CNV heatmap (with auto-rasterization fallback)
plot_fastcnv_heatmap(
  result,
  referenceVar  = "annotations",
  clustersVar   = "cnv_clusters",
  savePath      = "./heatmaps",
  outputFile    = "cnv_heatmap.pdf"   # auto-detects PDF vs PNG
)

# Spatial CNV fraction
plot_cnv_fraction_spatial(result, pt.size.factor = 3)

# Spatial CNV clusters
plot_cnv_fraction_spatial(result, group.by = "cnv_clusters", pt.size.factor = 3)

# Chromosome arm CNV with diverging color scale
plot_chr_arm_spatial(result, feature = "11.q_CNV", limits = c(-1, 1))

# ggplot2 boxplot of CNV fraction by annotation
library(ggplot2)
ggplot(FetchData(result, vars = c("annotations", "cnv_fraction")),
       aes(annotations, cnv_fraction, fill = annotations)) +
  geom_boxplot() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1))
```

### Step 5 — Export Results

```r
# Export metadata + CNV matrix + full Seurat object
export_cnv_results(
  result,
  output_dir    = "./fastcnv_results",
  prefix        = "sample1",
  export_matrix = TRUE   # Seurat v5-aware: uses LayerData() fallback
)

# Summary statistics by group
summary_df <- summarize_cnv_by_group(
  result,
  group.by = "cnv_clusters",
  metric   = "cnv_fraction"
)
```

---

## Complete Pipeline

Copy-pasteable single script for a full CNV analysis workflow:

```r
source("scripts/r/fastcnv_analysis.R")

# 1. Run fastCNV
result <- run_fastcnv(
  seuratObj   = seurat_obj,
  sampleName  = "Sample1",
  referenceVar    = "cell_type",
  referenceLabel  = "Healthy",
  getCNVPerChromosomeArm = TRUE,
  printPlot   = FALSE
)

# 2. Subclone analysis
result <- cnv_cluster(result, referenceVar = "cell_type")
result <- merge_cnv_clusters(result, mergeThreshold = 0.95)
result <- cnv_classification(result, cnv_thresh = 0.09)

# 3. Spatial visualization (if spatial coordinates exist)
plot_cnv_fraction_spatial(result, pt.size.factor = 3)
plot_chr_arm_spatial(result, feature = "11.q_CNV")

# 4. Heatmap
plot_fastcnv_heatmap(
  result,
  referenceVar = "cell_type",
  clustersVar  = "cnv_clusters",
  savePath     = "./heatmaps",
  outputFile   = "cnv_heatmap.pdf"
)

# 5. Export
export_cnv_results(result, output_dir = "./results", prefix = "sample1")
```

---

## Skill-Provided Functions

### Main Analysis

| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `run_fastcnv()` | Run `fastCNV()` with consistent naming | Auto-unpacks single object from list return |
| `run_fastcnv_hd()` | Visium HD wrapper (`fastCNV_10XHD`) | Consistent parameter naming with main wrapper |
| `run_fastcnv_multi()` | Multi-sample with pooled reference | Validates `list()` input, auto-names results |

### Preprocessing

| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `prepare_counts_for_cnv()` | Aggregate low-count spots | Consistent snake_case naming |
| `annotations_8um_to_16um()` | Project 8 µm annotations to 16 µm | Reports new column name to console |

### Subclone Analysis

| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `cnv_cluster()` | Hierarchical CNV clustering | Maps `k_clusters`/`h_clusters` → native `k`/`h` |
| `merge_cnv_clusters()` | Merge correlated clusters | Consistent snake_case naming |
| `cnv_classification()` | Classify gain/loss/no alteration | Maps `cnv_thresh` → native `peaks = c(-thresh, 0, thresh)` |
| `cnv_tree()` | CNV phylogenetic tree | Consistent snake_case naming |

### Visualization

| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `plot_fastcnv_heatmap()` | CNV heatmap | Auto-rasterization fallback; auto-detects output format from filename |
| `plot_cnv_fraction_spatial()` | Spatial CNV fraction | Validates spatial coordinates exist; handles both feature & dim plots |
| `plot_chr_arm_spatial()` | Chromosome arm spatial plot | Pre-configured diverging `RdBu` scale with `rescale_mid()` |

### Utilities

| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `extract_cnv_results()` | Flatten CNV metadata to data.frame | Auto-discovers `_CNV$` columns; graceful fallback if no results |
| `summarize_cnv_by_group()` | Summary stats by group | Computes mean, median, sd, min, max, n per group |
| `export_cnv_results()` | Export metadata, matrix, and RDS | Seurat v5-aware (`LayerData()` fallback); creates output directory |

---

## Official API — Agents Often Miss These

### Native fastCNV Functions (Direct from Package)

These are the underlying fastCNV functions. The wrappers above call these — use native functions directly if you need parameters not exposed by wrappers.

```r
# Main analysis
fastCNV::fastCNV(seuratObj, sampleName, ...)
fastCNV::fastCNV_10XHD(seuratObjHD, sampleName, ...)

# Clustering (note parameter names differ from wrappers!)
fastCNV::CNVCluster(seuratObj, k = NULL, h = NULL, referenceVar, cellTypesToCluster)
fastCNV::mergeCNVClusters(seuratObj, mergeThreshold = 0.95)

# Classification (note: uses peaks vector, not threshold)
fastCNV::CNVClassification(seuratObj, peaks = c(-0.09, 0, 0.09))

# Tree
fastCNV::CNVTree(seuratObj, values = "calls", cnv_thresh = 0.09, healthyClusters)

# Plotting
fastCNV::plotCNVResults(seuratObj, referenceVar, clustersVar, ...)
fastCNV::plotCNVResultsHD(seuratObj, referenceVar, ...)

# Preprocessing
fastCNV::prepareCountsForCNVAnalysis(seuratObj, sampleName, aggregFactor = 15000, ...)
fastCNV::annotations8umTo16um(seuratObj, referenceVar)
```

### Native Parameter Names That Differ from Wrappers

| Wrapper Param | Native Param | Notes |
|---------------|-------------|-------|
| `k_clusters` | `k` | `cnv_cluster()` wrapper maps this |
| `h_clusters` | `h` | `cnv_cluster()` wrapper maps this |
| `cnv_thresh` | `peaks = c(-thresh, 0, thresh)` | `cnv_classification()` wrapper maps this |
| `reCluster` | `reCluster` | Same name, but note native default behavior |
| `getCNVPerChromosomeArm` | `getCNVPerChromosomeArm` | Same name; used in both `fastCNV()` and `fastCNV_10XHD()` |

---

## Common Pitfalls

1. **⚠️ Single sample wrapped in `list()` returns a list**  
   Native `fastCNV()` always returns a list, even for a single object. The wrapper `run_fastcnv()` auto-unpacks: if you pass a single Seurat object, you get a single Seurat object back. But if you call native `fastCNV()` directly, remember to access `result[[1]]`.

2. **⚠️ `c()` on Seurat objects produces undefined behavior**  
   Always use `list(s1, s2, s3)` for multi-sample. `c(s1, s2, s3)` corrupts the objects.

3. **⚠️ `referenceLabel` is global, not per-sample**  
   If Sample1 uses `"Normal"` and Sample2 uses `"Healthy"`, pass `referenceLabel = c("Normal", "Healthy")` to pool both labels across all samples. Do not assume per-sample isolation.

4. **⚠️ Each label needs ≥ 5 spots per sample**  
   If a sample has fewer than 5 spots matching a label, that sample is silently excluded from that label's reference pool.

5. **⚠️ Visium HD annotations must be on 16 µm resolution**  
   If your annotations are on 8 µm bins, project them first: `annotations_8um_to_16um(seurat_hd, referenceVar = "annots_8um")`. The new column will be named `projected_annots_8um`.

6. **⚠️ Seurat v5 matrix access**  
   Use `result@assays$CNV$data` or `SeuratObject::LayerData(result, assay = "CNV", layer = "data")`. The old `Seurat::GetAssayData()` is deprecated in v5.

7. **⚠️ `cnv_cluster()` without reference clusters all cells**  
   If you don't pass `referenceVar`, clustering includes reference cells too. Pass `referenceVar` and optionally `cellTypesToCluster = "Tumor"` to cluster only tumor spots.

8. **⚠️ `fastCNV` is human-only**  
   Gene-to-chromosome mapping uses human gene symbols. Running on mouse data will produce incorrect or empty CNV profiles.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `unused argument` errors from fastCNV | Parameter name mismatch between wrapper and native API | Use wrapper functions; they map parameter names correctly |
| `seuratObj and sampleName must have the same length` | Passed single object but `sampleName` is a vector | Single sample: `sampleName = "S1"`; multi-sample: `list(s1, s2)` + `c("S1", "S2")` |
| `No spatial coordinates found` | Called spatial plot on non-spatial Seurat object | Check `seurat_obj@images` is not empty; use `SpatialFeaturePlot()` only for Visium |
| Out of memory on Visium HD | 8 µm bins or too many spots | Use 16 µm bins; process samples separately; set `downsizePlot = TRUE` |
| Heatmap rasterization fails | ComplexHeatmap raster issue | `plot_fastcnv_heatmap()` auto-retries without rasterization |
| CNV fraction all near zero | Insufficient reference or poor gene expression quality | Check `referenceVar` / `referenceLabel` match metadata exactly; increase healthy reference spots |
| `genomicScores is not an assay` | Called `cnv_cluster()` before running `fastCNV()` | Run `run_fastcnv()` first to populate the CNV assay |
| Empty CNV matrix export | Seurat v4/v5 API mismatch | `export_cnv_results()` handles both; use it instead of manual extraction |

---

## Related Skills

- [bio-single-cell-cnv-infercnv-r](../bio-single-cell-cnv-infercnv-r/SKILL.md) — Alternative CNV tool for scRNA-seq
- [bio-single-cell-cnv-copykat-r](../bio-single-cell-cnv-copykat-r/SKILL.md) — Another CNV alternative
- [bio-spatial-transcriptomics-deconvolution-cell2location](../bio-spatial-transcriptomics-deconvolution-cell2location/SKILL.md) — Cell type deconvolution for Visium

---

## References

1. Cabrejas et al. (2025). fastCNV: Fast and accurate copy number variation prediction from High-Definition Spatial Transcriptomics and scRNA-Seq Data. *bioRxiv* 2025.10.22.683855.
2. fastCNV documentation: https://must-bioinfo.github.io/fastCNV/
3. fastCNV HD tutorial: https://must-bioinfo.github.io/fastCNV/articles/fastCNV_HD.html
4. fastCNV ST tutorial: https://must-bioinfo.github.io/fastCNV/articles/fastCNV_ST.html
