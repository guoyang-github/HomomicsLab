---
name: bio-single-cell-differential-abundance-diffcyt-r
description: diffcyt differential abundance (DA) and differential state (DS) analysis for high-dimensional cytometry and single-cell data. Uses FlowSOM clustering and empirical Bayes moderated tests (edgeR/limma/voom/GLMM).
tool_type: r
primary_tool: diffcyt
supported_tools: [flowCore, CATALYST, edgeR, limma]
languages: [r]
keywords: ["differential-abundance", "DA", "differential-state", "DS", "diffcyt", "cytometry", "CyTOF", "flow-cytometry", "FlowSOM", "clustering"]
---

## Version Compatibility & Installation

| Package | Version | Notes |
|---------|---------|-------|
| R | ≥ 4.0 | |
| diffcyt | ≥ 1.14 | Bioconductor |
| flowCore | ≥ 2.0 | For FCS file I/O |
| CATALYST | ≥ 1.14 | Optional; for SCE input/output |
| SummarizedExperiment | ≥ 1.20 | Core data structure |

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("diffcyt")
BiocManager::install(c("CATALYST", "ComplexHeatmap"))  # optional
install.packages(c("ggplot2", "reshape2"))
```

---

## Skill Overview

**When to use:**
- **Differential Abundance (DA)**: Compare cell cluster proportions across conditions (e.g., treatment vs control)
- **Differential State (DS)**: Compare marker expression *within* clusters across conditions (e.g., phosphorylation levels)
- **High-dimensional cytometry**: Flow cytometry, CyTOF, CITE-seq, spectral flow
- You have samples with group labels and want cluster-level statistical testing

**When NOT to use:**
- **scRNA-seq without predefined markers** → use `bio-single-cell-differential-expression` or `bio-single-cell-de-deseq2-r`
- **Continuous pseudotime analysis** → use `bio-single-cell-trajectory-monocle3-r`
- **Simple 2-marker gating** → use flowJo/FlowKit manually; diffcyt is overkill
- **Need single-cell-level DE** → diffcyt operates on cluster medians/counts, not individual cells
- **No replicates per group** → diffcyt requires ≥2 samples per group for statistical testing

**Two analysis types:**

| Type | Tests | Question | Requires |
|------|-------|----------|----------|
| **DA** | edgeR / voom / GLMM | "Are cluster proportions different?" | `d_counts` |
| **DS** | limma / LMM | "Is marker expression different within clusters?" | `d_counts` + `d_medians` |

**Three DA method families:**

| Method | Best For | Random Effects | Normalization |
|--------|----------|----------------|---------------|
| **edgeR** (default) | Two-group comparison | ❌ | Optional TMM |
| **voom** | Paired/multi-factor designs | ✅ `block_id` | TMM via voom |
| **GLMM** | Complex mixed models | ✅ in formula | Internal |

---

## Core Workflow

> **Precondition**: `d_input` (list of matrices or `flowSet`) + `experiment_info` (sample metadata) + `marker_info` (marker classes: `"type"`, `"state"`, `"none"`).

### Step 1 — Prepare & Transform Data

**Input**: `d_input` + `experiment_info` + `marker_info`  
**Output**: `SummarizedExperiment` with arcsinh-transformed values  

```r
library(diffcyt)
source("scripts/r/core_analysis.R")
source("scripts/r/utils.R")
source("scripts/r/visualization.R")

# Prepare into SummarizedExperiment
d_se <- prepare_diffcyt_data(
  d_input = d_input,
  experiment_info = experiment_info,
  marker_info = marker_info,
  subsampling = FALSE,   # Set TRUE if sample sizes differ greatly
  n_sub = NULL
)

# Arcsinh transform
d_se <- diffcyt::transformData(d_se, cofactor = 5)
```

| Parameter | Default | What It Does | When to Change |
|-----------|---------|--------------|----------------|
| `cofactor` | `5` | Arcsinh denominator | `150` for fluorescence flow; `5` for CyTOF |
| `subsampling` | `FALSE` | Equalize cells per sample | `TRUE` if largest sample > 2× smallest |

**State after Step 1:** `d_se` is a `SummarizedExperiment` with transformed expression in `assay(d_se)`.

### Step 2 — Cluster with FlowSOM

**Input**: `d_se`  
**Output**: `d_se` with `cluster_id` in `rowData`  

```r
d_se <- generate_diffcyt_clusters(
  d_se,
  cols_clustering = NULL,   # auto-uses markers where marker_class == "type"
  xdim = 10,                # grid width
  ydim = 10,                # grid height → 100 clusters total
  meta_clustering = FALSE,  # TRUE for broader meta-clusters
  seed_clustering = 123
)
```

| Parameter | Default | What It Does | When to Change |
|-----------|---------|--------------|----------------|
| `xdim * ydim` | `100` | Total clusters | More = finer resolution; fewer = broader pops |
| `meta_clustering` | `FALSE` | Meta-clustering with ConsensusClusterPlus | `TRUE` if 100 clusters are too granular |
| `meta_k` | `40` | Target meta-cluster count | Adjust if `meta_clustering = TRUE` |

**State after Step 2:** `rowData(d_se)$cluster_id` contains cluster assignments.

### Step 3 — Calculate Features

**Input**: `d_se`  
**Output**: `d_counts` (for DA) + `d_medians` (for DS)  

```r
d_counts <- diffcyt::calcCounts(d_se)      # required for DA & DS
d_medians <- diffcyt::calcMedians(d_se)    # required for DS only
```

**State after Step 3:** `d_counts` = cluster × sample count matrix; `d_medians` = cluster × marker median matrix.

### Step 4 — Create Design & Contrast

**Input**: `experiment_info`  
**Output**: `design` matrix + `contrast` vector  

```r
design <- diffcyt::createDesignMatrix(experiment_info, cols_design = "group_id")
contrast <- diffcyt::createContrast(c(0, 1))   # group2 vs group1

# For paired designs, use formula instead
formula <- diffcyt::createFormula(
  experiment_info,
  fixed_effects = "group_id",
  random_effects = "patient_id"
)
```

**State after Step 4:** `design` has one column per factor level + intercept; `contrast` is a numeric vector.

### Step 5 — Test DA or DS

#### Differential Abundance (DA)

```r
# Default: edgeR for two-group comparison
da_res <- test_da_edger(
  d_counts = d_counts,
  design = design,
  contrast = contrast,
  min_cells = 3,          # min cells per cluster
  min_samples = NULL,     # defaults to n_samples/2
  normalize = FALSE       # TRUE for composition effects
)

# Paired design: voom with random effects
da_res <- diffcyt::testDA_voom(
  d_counts = d_counts,
  design = design,
  contrast = contrast,
  block_id = experiment_info$patient_id,
  plot = TRUE
)

# Complex mixed model: GLMM
da_res <- diffcyt::testDA_GLMM(
  d_counts = d_counts,
  formula = formula,
  contrast = contrast,
  min_cells = 3
)
```

#### Differential State (DS)

```r
# Default: limma
ds_res <- diffcyt::testDS_limma(
  d_medians = d_medians,
  d_counts = d_counts,
  design = design,
  contrast = contrast,
  trend = TRUE,
  weights = TRUE,
  markers_to_test = NULL    # NULL = all state markers
)

# Mixed model: LMM
ds_res <- diffcyt::testDS_LMM(
  d_counts = d_counts,
  d_medians = d_medians,
  formula = formula,
  contrast = contrast,
  weights = TRUE
)
```

**State after Step 5:** `da_res` / `ds_res` are `SummarizedExperiment` objects with `rowData(res)` containing `logFC`, `p_val`, `p_adj`.

### Step 6 — Extract & Export Results

```r
# Top hits
top_da <- get_top_results(da_res, n_top = 10)
sig_da <- get_significant_clusters(da_res, p_threshold = 0.05)

# Summary
print_results_summary(da_res, p_threshold = 0.05)

# Export
export_results(da_res, "da_results.csv", significant_only = TRUE)
```

---

## Complete Pipeline

Copy-pasteable single script for DA:

```r
library(diffcyt)
source("scripts/r/core_analysis.R")
source("scripts/r/utils.R")
source("scripts/r/visualization.R")

# 1. Prepare & transform
d_se <- prepare_diffcyt_data(d_input, experiment_info, marker_info)
d_se <- diffcyt::transformData(d_se, cofactor = 5)

# 2. Cluster
d_se <- generate_diffcyt_clusters(d_se, xdim = 10, ydim = 10)

# 3. Calculate features
d_counts <- diffcyt::calcCounts(d_se)

# 4. Design & contrast
design <- diffcyt::createDesignMatrix(experiment_info, "group_id")
contrast <- diffcyt::createContrast(c(0, 1))

# 5. Test DA
da_res <- test_da_edger(d_counts, design, contrast)

# 6. Summarize & export
top_da <- get_top_results(da_res, n_top = 10)
export_results(da_res, "da_results.csv")
```

Shortcut: `run_diffcyt_pipeline()` wraps steps 1–5.

```r
results <- run_diffcyt_pipeline(
  d_input = d_input,
  experiment_info = experiment_info,
  marker_info = marker_info,
  analysis_type = "DA",
  method_DA = "edgeR",
  design = design,
  contrast = contrast,
  transform = TRUE,
  cofactor = 5,
  xdim = 10, ydim = 10,
  min_cells = 3
)
da_res <- results$res
```

---

## Skill-Provided Functions

### Data Preparation
| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `prepare_diffcyt_data()` | Wrap `diffcyt::prepareData()` + cell count stats | Adds per-sample cell count summary |
| `generate_diffcyt_clusters()` | FlowSOM clustering | Reports detected cluster count post-clustering |
| `validate_diffcyt_input()` | Validate inputs before prep | Catches missing `sample_id` / `marker_class` early |

### Statistical Testing
| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `test_da_edger()` | DA with edgeR | Auto-sets `min_samples = n/2`; reports significant cluster count |
| `run_diffcyt_pipeline()` | One-liner full workflow | Runs prepare → transform → cluster → calc → test with validation |

### Pipeline & Results
| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `run_diffcyt_pipeline()` | One-liner for full workflow | Runs prepare → transform → cluster → calc → test |
| `get_top_results()` | Top N significant hits | Sorts by `p_adj`, returns `rowData` subset |
| `get_significant_clusters()` | Cluster IDs passing threshold | Filters `rowData(res)` by `p_adj` |
| `export_results()` | Export to CSV | Wraps `utils::write.csv()` on `rowData(res)` |
| `summarize_results()` | Summary stats (n_sig, n_up, n_down) | Computes from `rowData(res)` |
| `print_results_summary()` | Human-readable summary | Prints n_sig / n_up / n_down |
| `merge_da_ds_results()` | Merge DA + DS into one table | Joins by cluster_id |

### Utilities
| Function | Purpose |
|----------|---------|
| `create_experiment_info()` | Build `experiment_info` data frame |
| `create_marker_info()` | Build `marker_info` data frame with validation |
| `create_test_data()` | Generate simulated data for testing |
| `filter_clusters_by_abundance()` | Pre-filter low-abundance clusters |
| `normalize_counts()` | TMM normalization on cluster counts |
| `convert_sce_to_diffcyt()` | Convert CATALYST `SingleCellExperiment` to diffcyt input |
| `subsample_cells()` | Equalize cells per sample |

### Visualization
| Function | Purpose |
|----------|---------|
| `plot_volcano()` | Volcano plot (logFC vs -log10 p) |
| `plot_ma()` | MA plot |
| `plot_cluster_abundance()` | Cluster proportions by sample |
| `save_diffcyt_plots()` | Batch-save all standard plots |

---

## Official API — Agents Often Miss These

### Native diffcyt functions (direct from package)

```r
# Preparation
diffcyt::prepareData(d_input, experiment_info, marker_info)
diffcyt::transformData(d_se, cofactor = 5)
diffcyt::generateClusters(d_se, cols_clustering, xdim, ydim, meta_clustering)
diffcyt::calcCounts(d_se)
diffcyt::calcMedians(d_se)

# Testing
diffcyt::testDA_edgeR(d_counts, design, contrast, min_cells, min_samples)
diffcyt::testDA_voom(d_counts, design, contrast, block_id)
diffcyt::testDA_GLMM(d_counts, formula, contrast)
diffcyt::testDS_limma(d_counts, d_medians, design, contrast)
diffcyt::testDS_LMM(d_counts, d_medians, formula, contrast)

# Visualization
diffcyt::plotHeatmap(d_se, res, analysis_type = "DA")
```

### Result structure

All test results are `SummarizedExperiment` with statistics in `rowData(res)`.

diffcyt supports two analysis types. The table below shows which columns appear in each:

| Column | 差异丰度 (DA) | 差异状态 (DS) | Meaning |
|--------|:--:|:--:|---------|
| `logFC` | ✅ | ✅ | Log fold change |
| `logCPM` | ✅ | ❌ | Log counts per million（仅 DA 的 edgeR） |
| `p_val` | ✅ | ✅ | Raw p-value |
| `p_adj` | ✅ | ✅ | FDR-adjusted p-value |

- **DA (Differential Abundance)**: Tests whether cluster proportions differ across conditions
- **DS (Differential State)**: Tests whether marker expression within clusters differs across conditions

---

## Common Pitfalls

1. **⚠️ `marker_class` must be `"type"`, `"state"`, or `"none"`**  
   Any other value (e.g., `"Type"`, `"marker"`) causes `generate_diffcyt_clusters()` to fail or ignore markers silently. Use `validate_diffcyt_input()` to catch this.

2. **⚠️ `experiment_info$sample_id` must be `factor`**  
   Character vectors may cause design matrix mismatches. The wrapper coerces to factor, but verify with `validate_diffcyt_input()`.

3. **⚠️ DA and DS require different inputs**  
   - DA only needs `d_counts`  
   - DS needs **both** `d_counts` (for filtering) **and** `d_medians` (for expression values)  
   Calling `diffcyt::testDS_limma()` without `d_medians` will fail.

4. **⚠️ `contrast` vector length must match `ncol(design)`**  
   If design has intercept + 2 groups = 3 columns, contrast must be length 3 (e.g., `c(0, -1, 1)`). Use `diffcyt::createContrast()` to avoid mismatches.

5. **⚠️ `min_cells` filtering can remove ALL clusters**  
   If every cluster has < 3 cells in < 50% of samples, `test_da_edger()` returns empty. Check with `summarize_results()` or lower `min_cells` to 1.

6. **⚠️ Raw data must NOT be arcsinh-transformed before `prepare_diffcyt_data()`**  
   diffcyt expects raw channel values (e.g., raw ion counts for CyTOF, raw fluorescence for flow). Transformation happens in `diffcyt::transformData()`.

7. **⚠️ `diffcyt::testDA_voom()` `block_id` must match `rownames(design)` order**  
   The `block_id` vector is assumed to be in the same order as design matrix rows (sample order). Pass `experiment_info$patient_id` in sample order.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `experiment_info must contain sample_id` | Missing or misspelled column | Rename to `sample_id`; use `validate_diffcyt_input()` |
| `marker_class must be one of: type, state, none` | Invalid marker classes | Check `marker_info$marker_class` values |
| `No clusters pass filtering` | `min_cells` too strict | Lower `min_cells` to 1 or 2 |
| `Contrasts not estimable` | Design matrix rank deficient | Check `qr(design)$rank == ncol(design)`; simplify contrast |
| `d_medians is missing` | Called `test_ds_*` without medians | Run `d_medians <- diffcyt::calcMedians(d_se)` first |
| All p-values ≈ 1 | No biological signal or wrong contrast | Verify group labels; check `logFC` distribution |
| `diffcyt::plotHeatmap` fails | Missing `ComplexHeatmap` | `BiocManager::install("ComplexHeatmap")` |
| Memory error during clustering | Too many cells × too many markers | Subsample with `subsample_cells()` or enable `subsampling` in prep |


## Related Skills

- [bio-single-cell-differential-abundance-sccoda](../bio-single-cell-differential-abundance-sccoda/SKILL.md) — Compositional DA for scRNA-seq
- [bio-single-cell-clustering](../bio-single-cell-clustering/SKILL.md) — General clustering methods
- [bio-single-cell-de-deseq2-r](../bio-single-cell-de-deseq2-r/SKILL.md) — Single-cell differential expression

## References

1. Weber et al. (2019). diffcyt: Differential discovery in high-dimensional cytometry via high-resolution clustering. *Communications Biology*, 2, 183.
2. diffcyt Bioconductor: https://bioconductor.org/packages/diffcyt
3. FlowSOM: Van Gassen et al. (2015), *Cytometry A*, 87, 251-262.
4. edgeR: Robinson et al. (2010), *Bioinformatics*, 26, 139-140.
5. limma: Ritchie et al. (2015), *Nucleic Acids Res*, 43, e47.
