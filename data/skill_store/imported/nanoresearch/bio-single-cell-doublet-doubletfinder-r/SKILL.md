---
name: bio-single-cell-doublet-doubletfinder-r
description: |
  DoubletFinder doublet detection for single-cell RNA-seq. Generates artificial
  doublets, computes pANN (proportion of artificial nearest neighbors), and
  classifies cells via thresholding. Requires parameter sweep for optimal pK
  (neighborhood size) and supports homotypic doublet adjustment using cluster
  annotations.
tool_type: r
primary_tool: DoubletFinder
languages: [r]
keywords: ["single-cell", "doublet-detection", "DoubletFinder", "Seurat", "pANN", "quality-control"]
---

## Version Compatibility

| Package | Required Version | Notes |
|---------|-----------------|-------|
| R | ≥ 4.2.0 | |
| DoubletFinder | ≥ 2.0.4 | Install from GitHub, not CRAN/Bioconductor |
| Seurat | ≥ 4.3.0 or ≥ 5.0 | v5 compatible; v4 also supported |
| SeuratObject | ≥ 4.1.0 | |

## Installation

```r
remotes::install_github('chris-mcginnis-ucsf/DoubletFinder')
```

DoubletFinder is **not on CRAN or Bioconductor** — must install from GitHub.

## Skill Overview

DoubletFinder detects doublets in single-cell RNA-seq data by generating artificial doublets from real cells, computing the proportion of artificial nearest neighbors (pANN) for each cell, and classifying cells via pANN thresholding. It requires a parameter sweep to optimize the pK (neighborhood size) parameter using the mean-variance normalized bimodality coefficient (BCmvn).

**Core workflow**: Validate preprocessing → Parameter sweep for optimal pK → Estimate expected doublets → Run DoubletFinder → Optional homotypic adjustment → Filter and export

**When to use:**
- **Seurat-based scRNA-seq workflows** requiring doublet removal
- Need **parameter-optimized** detection (pK sweep via BCmvn)
- Want **homotypic adjustment** using existing cluster annotations
- Using **SCTransform** or standard log-normalization
- Prefer **pANN-based** classification over generative-model approaches

**When NOT to use:**
- **Aggregated data from multiple distinct samples** (e.g., WT vs mutant from different lanes) — artificial doublets may mix cell types that cannot co-occur
- **Integrated/batch-corrected data** — integration distorts local neighborhoods; run per-sample before integration
- **Data with unresolved batch effects** — batch structure mimics doublet signal
- Already ran another doublet detector and want a **quick second opinion** — use Scrublet or scDblFinder instead (faster, no parameter sweep)

**Input requirements:**
- **Seurat object**: Fully pre-processed with `NormalizeData` (or `SCTransform`), `FindVariableFeatures`, `ScaleData` (unless SCT), and `RunPCA`
- **PCA**: Required dimensionality reduction
- **Clustering**: Required for homotypic adjustment (`FindNeighbors` + `FindClusters`); optional for basic run

**Preprocessing validation:**
```r
source("scripts/r/utils.R")
check_seurat_for_df(seurat_obj)  # Verifies required processing steps
```

## Core Workflow

### Step 1 — Validate Preprocessing

**Input**: Seurat object  
**Output**: Validated Seurat object (or error with specific fix)

```r
source("scripts/r/core_analysis.R")

check_seurat_for_df(seurat_obj)
# → Checks: inherits Seurat, has commands history, PCA reduction exists
# → Messages: n_cells, n_genes, n_PCs
```

**If validation fails:**
| Error | Cause | Fix |
|-------|-------|-----|
| `no processing history` | Missing preprocessing steps | Run `NormalizeData` → `FindVariableFeatures` → `ScaleData` → `RunPCA` |
| `PCA not found` | `RunPCA()` not run | `seurat_obj <- RunPCA(seurat_obj, npcs = 30)` |

### Step 2 — Parameter Sweep for Optimal pK

**Input**: Pre-processed Seurat object  
**Output**: List with `$sweep.res`, `$sweep.stats`, `$bcmvn`, `$optimal_pk`

```r
sweep_results <- run_param_sweep(
  seurat_obj,
  PCs = 1:20,      # Based on elbow plot or recommend_pcs()
  sct = FALSE,     # TRUE if data normalized with SCTransform
  num.cores = 1,   # Increase for large datasets
  subsample = TRUE # Auto-subsample >10k cells for speed
)

optimal_pk <- sweep_results$optimal_pk
```

**How pK selection works:**
1. Tests pN ∈ {0.05, 0.1, 0.15, 0.2, 0.25, 0.3} (proportion of artificial doublets)
2. Tests pK ∈ {0.0005, 0.001, 0.005, seq(0.01, 0.3, by=0.01)}
3. Computes pANN for each pN-pK combination
4. Calculates bimodality coefficient (BC) of pANN distribution
5. Selects pK with maximum BCmvn = mean(BC) / var(BC)

**State after Step 2:** `sweep_results$optimal_pk` is a numeric scalar (typically 0.01–0.3).

### Step 3 — Estimate Expected Doublets

**Input**: Number of cells, platform name  
**Output**: Expected doublet count (`nExp`)

```r
# Platform-specific (recommended)
nExp_poi <- estimate_expected_doublets(ncol(seurat_obj), platform = "10x_v3")

# Or based on actual loading density
n_loaded <- 15000  # Cells loaded into device
n_recovered <- ncol(seurat_obj)
doublet_rate <- get_10x_doublet_rate(n_loaded)
nExp_poi <- round(doublet_rate * n_recovered)

# Validate range
validate_expected_doublets(ncol(seurat_obj), nExp_poi)
# → Warns if < 0.5% or > 15%
```

| Platform | Rate per 1000 cells |
|----------|---------------------|
| `10x_v2` / `10x_v3` | ~0.8% |
| `10x_v3_1` | ~0.4% |
| `10x_ht` | ~1.6% |
| `parse` | ~0.6% |
| `dropseq` | ~0.5% |

**State after Step 3:** `nExp_poi` is an integer (typically 2–10% of total cells).

### Step 4 — Run DoubletFinder

**Input**: Seurat object + `PCs` + `pK` + `nExp`  
**Output**: Seurat object with `pANN_*`, `DF.classifications_*`, and `doublet` columns

```r
seurat_obj <- run_doubletfinder(
  seurat_obj,
  PCs = 1:20,
  pN = 0.25,        # DoubletFinder is pN-invariant; 0.25 is standard
  pK = optimal_pk,  # From parameter sweep
  nExp = nExp_poi,  # From step 3
  reuse.pANN = NULL,# Set to pANN column name for reclassification
  sct = FALSE       # TRUE if SCTransform used
)
```

**Metadata columns added:**
| Column | Example name | Content |
|--------|-------------|---------|
| `pANN_*` | `pANN_0.25_0.09_500` | pANN score per cell (0–1) |
| `DF.classifications_*` | `DF.classifications_0.25_0.09_500` | `"Singlet"` or `"Doublet"` |
| `doublet` | `doublet` | Simplified access column |

**State after Step 4:** `seurat_obj$doublet` contains `"Singlet"` / `"Doublet"` classifications.

### Step 5 — Homotypic Adjustment (Optional but Recommended)

**When to use**: Clusters are well-defined; want to reduce false positives from same-type doublets.

**Input**: Seurat object with cluster annotations  
**Output**: Re-classified Seurat object with adjusted `nExp`

```r
# One-step wrapper
seurat_obj <- run_doubletfinder_adjusted(
  seurat_obj,
  PCs = 1:20,
  cluster_col = "seurat_clusters",  # Must exist in metadata
  pK = optimal_pk,
  sct = FALSE
)
# → Runs: unadjusted DF → modelHomotypic() → adjusted DF (reuses pANN)
# → Adds: doublet_adjusted column; updates doublet column
```

**Manual workflow (if you need custom logic):**
```r
# Step 1: Unadjusted run to get pANN
seurat_obj <- DoubletFinder::doubletFinder(
  seurat_obj, PCs = 1:20, pN = 0.25, pK = optimal_pk,
  nExp = nExp_poi, reuse.pANN = NULL, sct = FALSE
)

# Step 2: Model homotypic proportion
annotations <- seurat_obj$seurat_clusters
homotypic.prop <- DoubletFinder::modelHomotypic(annotations)
nExp_poi.adj <- round(nExp_poi * (1 - homotypic.prop))

# Step 3: Reclassify with adjusted nExp (reuse pANN for speed)
pann_col <- grep("^pANN", colnames(seurat_obj@meta.data), value = TRUE)[1]
seurat_obj <- DoubletFinder::doubletFinder(
  seurat_obj, PCs = 1:20, pN = 0.25, pK = optimal_pk,
  nExp = nExp_poi.adj, reuse.pANN = pann_col, sct = FALSE
)
```

**State after Step 5:** Fewer predicted doublets than unadjusted run; `doublet` column reflects adjusted calls.

### Step 6 — Filter and Export

```r
# Filter doublets
seurat_filtered <- filter_doublets(seurat_obj, keep = "Singlet")
# → Messages: Before / After / Removed counts and percentages

# Summary statistics
get_doublet_summary(seurat_obj)
# → Overall: total_cells, n_doublets, n_singlets, doublet_rate

get_doublet_summary(seurat_obj, group_by = "seurat_clusters")
# → Per-cluster doublet rates

# Export predictions
export_doublet_predictions(seurat_obj, "doublet_predictions.csv", include_pANN = TRUE)
# → CSV: cell_id, doublet, pANN

# Generate text report
generate_df_report(seurat_obj, "report.txt")
```

---

## Complete Pipeline

Copy-pasteable single script:

```r
library(DoubletFinder)
source("scripts/r/core_analysis.R")
source("scripts/r/utils.R")
source("scripts/r/visualization.R")

# Validate
stopifnot(check_seurat_for_df(seurat_obj))

# 1. Parameter sweep
sweep_results <- run_param_sweep(seurat_obj, PCs = 1:20, sct = FALSE)

# 2. Estimate doublets
nExp_poi <- estimate_expected_doublets(ncol(seurat_obj), platform = "10x_v3")

# 3. Run with homotypic adjustment
seurat_obj <- run_doubletfinder_adjusted(
  seurat_obj,
  PCs = 1:20,
  cluster_col = "seurat_clusters",
  pK = sweep_results$optimal_pk,
  sct = FALSE
)

# 4. Filter and save
seurat_filtered <- filter_doublets(seurat_obj)
saveRDS(seurat_filtered, "seurat_no_doublets.rds")
```

Shortcut: `run_doubletfinder_workflow()` wraps sweep → detection → optional filter.

```r
seurat_obj <- run_doubletfinder_workflow(
  seurat_obj,
  PCs = 1:20,
  sct = FALSE,
  adjust_homotypic = TRUE,
  cluster_col = "seurat_clusters",
  filter = TRUE
)
```

---

## Skill-Provided Functions

### Core Detection
| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `check_seurat_for_df()` | Validate preprocessing | Checks command history + PCA; specific error messages |
| `run_param_sweep()` | Find optimal pK | Wraps `paramSweep` → `summarizeSweep` → `find.pK`; extracts optimal automatically |
| `run_doubletfinder()` | Run DoubletFinder | Auto-infers pK and nExp if NULL; adds simplified `doublet` column; reports counts |
| `run_doubletfinder_adjusted()` | Homotypic-adjusted detection | Full 3-step workflow: unadjusted → `modelHomotypic()` → adjusted (reuses pANN) |
| `run_doubletfinder_workflow()` | One-liner full pipeline | sweep → detection → optional filter with progress messages |
| `filter_doublets()` | Remove predicted doublets | Safe `subset()` with `rlang::sym`; reports before/after stats |

### Results & Export
| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `get_doublet_summary()` | Summary by group | Overall or per-cluster/per-sample doublet rates |
| `export_doublet_predictions()` | Export to CSV | Extracts pANN + classification; handles column name detection |
| `generate_df_report()` | Text report | Parameters, counts, rates; optional file output |

### Parameter Estimation
| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `estimate_expected_doublets()` | Platform-specific nExp | 10x v2/v3/v3.1/HT, Parse, Drop-seq rates |
| `get_10x_doublet_rate()` | Rate from loading density | Based on 0.8% per 1000 cells loaded |
| `validate_expected_doublets()` | Sanity check | Warns if < 0.5% or > 15% |
| `recommend_pcs()` | Auto-recommend PC range | Cumulative variance threshold (default 90%) |
| `get_loading_recommendation()` | 10x loading advice | ~1.6× target for ~60% recovery |

### Metadata Helpers
| Function | Purpose |
|----------|---------|
| `get_pann_columns()` | Extract all `pANN_*` column names from metadata |
| `get_df_classification_columns()` | Extract all `DF.classifications_*` column names |
| `parse_df_column_name()` | Parse `DF.classifications_pN_pK_nExp` → list(pN, pK, nExp) |
| `summarize_by_sample()` | Per-sample doublet rate table |
| `get_high_confidence_doublets()` | Cells with pANN ≥ threshold |
| `compare_df_runs()` | Agreement matrix between two DF runs |

### Visualization
| Function | Purpose |
|----------|---------|
| `plot_pk_optimization()` | BCmvn curve with optimal pK marked |
| `plot_doublet_embedding()` | DimPlot colored by Singlet/Doublet |
| `plot_pann_distribution()` | Density plot of pANN scores |
| `plot_pann_violin()` | Violin plot by doublet status (optional grouping) |
| `plot_doublet_rate_by_cluster()` | Bar plot of % doublets per cluster |
| `plot_doublet_summary()` | patchwork combined figure (UMAP + pANN + pK) |
| `plot_method_comparison()` | Agreement histogram across multiple methods |

---

## Official API — Agents Often Miss These

### Native DoubletFinder functions

```r
# Parameter sweep
DoubletFinder::paramSweep(seu, PCs = 1:20, sct = FALSE, num.cores = 1)
DoubletFinder::summarizeSweep(sweep.res, GT = FALSE)
DoubletFinder::find.pK(sweep.stats)  # Returns data frame with pK and BCmetric columns

# Doublet detection
DoubletFinder::doubletFinder(
  seu, PCs = 1:20, pN = 0.25, pK = 0.09, nExp = 500,
  reuse.pANN = NULL,  # Set to "pANN_0.25_0.09_500" to reuse
  sct = FALSE
)

# Homotypic modeling
DoubletFinder::modelHomotypic(annotations)  # annotations = factor vector of cluster labels
# Returns: proportion of doublets expected to be homotypic
```

### Result structure

DoubletFinder adds columns to `seurat_obj@meta.data`:
- `pANN_{pN}_{pK}_{nExp}` — numeric, 0 to 1
- `DF.classifications_{pN}_{pK}_{nExp}` — `"Singlet"` or `"Doublet"`

When `reuse.pANN` is used, only a new `DF.classifications_*` column is added (pANN is reused).

---

## Common Pitfalls

1. **⚠️ Do NOT run on aggregated multi-sample data**  
   WT and mutant from different 10x lanes should be run separately. Artificial doublets may average cells that never shared a droplet.

2. **⚠️ Do NOT run on integrated/batch-corrected data**  
   Integration alters local neighborhoods. Run DoubletFinder **per sample before integration**, then integrate the filtered objects.

3. **⚠️ Pre-filter low-quality cells BEFORE DoubletFinder**  
   High-mito, low-UMI debris clusters inflate the artificial doublet pool. Remove them, re-process, then run DoubletFinder.

4. **⚠️ BCmvn with multiple peaks**  
   If `bcmvn$BCmetric` has multiple peaks, the automated `optimal_pk` may not be biologically optimal. Visualize with `plot_pk_optimization()` and manually inspect. See DoubletFinder GitHub issues #62 and #40.

5. **⚠️ `nExp` must reflect LOADED cells, not recovered cells**  
   Doublet rate depends on loading density (Poisson loading). If you only know recovered cells, use `estimate_expected_doublets()` with platform default. If you know loaded cells, use `get_10x_doublet_rate(n_loaded) * n_recovered`.

6. **⚠️ SCTransform requires `sct = TRUE` in ALL DoubletFinder calls**  
   Forgetting this in `run_param_sweep()` or `run_doubletfinder()` causes silent failures or incorrect pANN computation.

7. **⚠️ Homotypic adjustment requires clustering**  
   `run_doubletfinder_adjusted()` needs a cluster column in metadata. Run `FindNeighbors()` + `FindClusters()` first.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No command history found` | Missing preprocessing | Run `NormalizeData` → `FindVariableFeatures` → `ScaleData` → `RunPCA` |
| `PCA not found` | `RunPCA()` not executed | `seurat_obj <- RunPCA(seurat_obj, npcs = 30)` |
| Parameter sweep extremely slow | Large dataset (>10k cells) | Set `subsample = TRUE` in `run_param_sweep()` |
| BCmvn has multiple peaks | Complex cell type composition | Visualize with `plot_pk_optimization()`; manually select pK |
| Doublet rate > 15% | Overloaded sample or wrong nExp | Verify platform; check actual loading density |
| All cells called doublets | `nExp` ≥ total cells | `nExp` must be < ncol(seurat_obj); re-estimate |
| `cluster_col not found` | Missing clustering before homotypic adjustment | Run `FindClusters()` first |
| `reuse.pANN` column not found | Typo in pANN column name | Use `get_pann_columns(seurat_obj)` to list valid names |


## Related Skills

- [bio-single-cell-doublet-scdblfinder-r](../bio-single-cell-doublet-scdblfinder-r/SKILL.md) — Alternative: generative model, faster, no parameter sweep
- [bio-single-cell-doublet-scrublet](../bio-single-cell-doublet-scrublet/SKILL.md) — Python-based doublet detection
- [bio-single-cell-qc-preprocessing-r](../bio-single-cell-qc-preprocessing-r/SKILL.md) — Pre-filtering low-quality cells before doublet detection

## References

1. McGinnis et al. (2019). DoubletFinder: Doublet Detection in Single-Cell RNA Sequencing Data Using Artificial Nearest Neighbors. *Cell Systems*, 8(4):329-337. https://doi.org/10.1016/j.cels.2019.03.003
2. DoubletFinder GitHub: https://github.com/chris-mcginnis-ucsf/DoubletFinder
