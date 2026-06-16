---
name: bio-single-cell-doublet-scdblfinder-r
description: |
  Fast and accurate doublet detection using gradient-boosted classification of
  artificial doublets. Native multi-sample support, cluster-aware generation,
  and Bioconductor integration via SingleCellExperiment.
tool_type: r
primary_tool: scDblFinder
languages: [r]
keywords: ["single-cell", "doublet-detection", "scDblFinder", "Bioconductor", "quality-control"]
---

## Version Compatibility

| Package | Required Version | Notes |
|---------|-----------------|-------|
| R | ≥ 4.2.0 | |
| scDblFinder | ≥ 1.12.0 | Bioconductor 3.17+ |
| SingleCellExperiment | ≥ 1.20.0 | Bioconductor |
| Seurat | ≥ 4.3.0 or ≥ 5.0 | Optional; v5 fully supported |

## Installation

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("scDblFinder")
```

## Skill Overview

scDblFinder detects doublets by generating artificial doublets from real cells, training a gradient-boosted classifier to distinguish real cells from doublets, and scoring each cell. It is benchmarked as a top-performing method (Xi & Li 2021) with native multi-sample support.

**Core workflow**: Validate input → Run scDblFinder → Extract scores/classifications → Filter → Export

**When to use:**
- Need **fast, accurate** doublet detection without parameter sweeps
- **Multi-sample data** with batch effects across captures
- **Bioconductor/SingleCellExperiment** workflow
- Want **cluster-aware** artificial doublet generation
- Using **Seurat v4 or v5**

**When NOT to use:**
- Need **homotypic doublet adjustment** with cluster annotations — use DoubletFinder instead
- **Very small datasets** (< 50 cells) — scDblFinder requires minimum 50 cells
- **Non-R workflow** — use Scrublet (Python) instead
- Want **pANN-based nearest-neighbor classification** — use DoubletFinder instead

**Input requirements:**
- **SingleCellExperiment** or raw count matrix (genes × cells)
- **Raw counts**: Not normalized, not log-transformed
- **Minimum 50 cells**: Recommend 200+ for reliable accuracy
- Gene names in `rownames`, cell barcodes in `colnames`

**Preprocessing validation:**
```r
source("scripts/r/core_analysis.R")
validate_scdblfinder_input(sce)
# → Checks: SCE/matrix format, counts assay, ≥50 cells, row/col names
# → Returns: valid (TRUE/FALSE), errors, warnings, stats (n_cells, n_genes)
```

## Core Workflow

### Step 1 — Validate Input

**Input**: SCE or count matrix  
**Output**: Validation result (or error with specific message)

```r
validation <- validate_scdblfinder_input(sce)
stopifnot(validation$valid)
```

**Common validation failures:**
| Error | Cause | Fix |
|-------|-------|-----|
| `No 'counts' assay found` | Normalized data passed in | Use raw count matrix |
| `Too few cells: X - need at least 50` | < 50 cells | Merge with other samples or skip doublet detection |
| `Count matrix has no gene names` | Missing `rownames` | `rownames(counts) <- gene_ids` |

### Step 2 — Run scDblFinder

**Input**: Validated SCE/count matrix  
**Output**: SCE with `scDblFinder.score`, `scDblFinder.class`, and optional origin/sample columns

```r
# Basic run (fastest, no clustering)
sce <- run_scdblfinder(sce)

# Cluster-aware (recommended for clustered data)
sce <- run_scdblfinder(sce, clusters = TRUE)

# Multi-sample (processes each sample separately)
sce <- run_scdblfinder(
  sce,
  samples = sce$sample_id,
  multiSampleMode = "split",
  BPPARAM = BiocParallel::MulticoreParam(4)
)

# From Seurat (auto-converts, v5 compatible)
seurat_obj <- run_scdblfinder_seurat(
  seurat_obj,
  samples = "sample_id",        # Column name or NULL
  clusters = "seurat_clusters", # Column name, TRUE, or FALSE
  return_seurat = TRUE          # Returns Seurat with metadata added
)
```

**Key Parameters:**
| Parameter | Default | What It Does | When to Change |
|-----------|---------|--------------|----------------|
| `clusters` | `NULL` | `TRUE`=auto-cluster, `FALSE`=random, `vector`=manual | `TRUE` for better accuracy on clustered data |
| `samples` | `NULL` | Sample IDs for multi-sample | Set to `sce$sample_id` for independent captures |
| `nfeatures` | `1000` | Top variable features used | `1500` for >5k cells; `2000` for >50k cells |
| `dims` | `20` | PCA dimensions | Reduce to `10` for <500 cells |
| `dbr.per1k` | `0.008` | Doublet rate per 1000 cells | `0.004` for 10x HT; `0.01` for non-10x |
| `iter` | `1` | Scoring iterations | `2` for difficult datasets with poor separation |
| `multiSampleMode` | `"split"` | How to handle multi-sample | `"split"`=separate models per sample (recommended); `"asOne"`=pooled |

**State after Step 2:** `colData(sce)` contains classification columns.

### Step 3 — Extract and Summarize Results

```r
# Extract all scores as data frame
scores <- extract_doublet_scores(sce)
# → Columns: scDblFinder.score, scDblFinder.class, cell, [origin, sample]

# Get cell names
doublet_cells <- get_doublet_cells(sce)   # Cells classified as "doublet"
singlet_cells <- get_singlet_cells(sce)   # Cells classified as "singlet"

# Summary statistics
summary <- summarize_scdblfinder_results(sce)
# → n_cells, n_doublets, n_singlets, doublet_rate, class_table
# → mean_score, median_score, score_range (if scores available)
# → origin_table (if cluster-based)
# → doublets_by_sample (if multi-sample)
```

**Output columns added to `colData(sce)`:**
| Column | Type | Content |
|--------|------|---------|
| `scDblFinder.score` | numeric (0–1) | Doublet probability (higher = more likely doublet) |
| `scDblFinder.class` | factor | `"singlet"` or `"doublet"` |
| `scDblFinder.mostLikelyOrigin` | character | Likely origin clusters (cluster-based only) |
| `scDblFinder.sample` | character | Sample ID (multi-sample only) |

### Step 4 — Filter Doublets

```r
# From SCE
sce_filtered <- filter_scdblfinder(sce, remove_doublets = TRUE)
# → Messages: "Keeping X of Y cells (Z%)"

# Alternative utility
sce_singlets <- filter_doublets(sce, keep_singlets = TRUE)
```

### Step 5 — Export and Report

```r
# Export CSV + summary text
export_scdblfinder_results(
  sce,
  output_dir = "./scdblfinder_output",
  prefix = "sample1"
)

# Generate formatted text report
report <- create_scdblfinder_report(sce)
cat(report)

# QC report with recommendations
create_scdblfinder_qc_report(sce, "qc_report.txt")
```

---

## Complete Pipeline

Copy-pasteable single script:

```r
library(SingleCellExperiment)
source("scripts/r/core_analysis.R")
source("scripts/r/utils.R")

# 1. Validate
stopifnot(validate_scdblfinder_input(sce)$valid)

# 2. Run (cluster-aware, multi-sample if applicable)
sce <- run_scdblfinder(
  sce,
  clusters = TRUE,
  samples = if("sample_id" %in% colnames(colData(sce))) sce$sample_id else NULL,
  BPPARAM = BiocParallel::MulticoreParam(4)
)

# 3. Summarize
summary <- summarize_scdblfinder_results(sce)
cat(sprintf("Doublet rate: %.1f%%\n", 100 * summary$doublet_rate))

# 4. Filter
sce_filtered <- filter_scdblfinder(sce)

# 5. Export
export_scdblfinder_results(sce, output_dir = "./scdblfinder_output")
```

**From Seurat:**
```r
seurat_obj <- run_scdblfinder_seurat(
  seurat_obj,
  clusters = "seurat_clusters",
  return_seurat = TRUE
)
seurat_filtered <- subset(seurat_obj, subset = scDblFinder_class == "singlet")
```

---

## Skill-Provided Functions

### Core Detection
| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `validate_scdblfinder_input()` | Validate input format | Checks SCE/matrix, counts assay, ≥50 cells, row/col names |
| `run_scdblfinder()` | Run scDblFinder | Auto-converts matrix→SCE; runs `validate_scdblfinder_input()`; `match.arg` safety |
| `run_scdblfinder_seurat()` | Seurat wrapper | **v5 compatible**: detects Assay5 → converts to v3 → `as.SingleCellExperiment()`; handles column-name `samples`/`clusters` |
| `extract_doublet_scores()` | Extract results | Returns all `scDblFinder.*` columns as data frame with cell names |
| `get_doublet_cells()` / `get_singlet_cells()` | Get cell names | Pre-checks classification exists |
| `summarize_scdblfinder_results()` | Comprehensive summary | Conditional stats: scores, origin, sample breakdowns only if present |
| `filter_scdblfinder()` | Filter SCE | Supports `remove_unclassified`; reports keep rate |
| `export_scdblfinder_results()` | Batch export | CSV + text summary with `sink()` |
| `create_scdblfinder_report()` | Formatted report | Human-readable text with score stats |
| `add_scdblfinder_to_seurat()` | Results back to Seurat | Cell-name matching; column-name transformation (`scDblFinder.score` → `scDblFinder_score`) |

### Parameter Estimation
| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `recommend_scdblfinder_params()` | Auto-recommend params | Heuristic based on cell count: nfeatures (1000–2000), dims (5–20), k (5–30), clusters (T/F) |
| `estimate_doublet_rate()` | Platform-specific dbr | `10x_standard` (0.8%), `10x_ht` (0.4%), `other` (1%) per 1k cells |

### Multi-Sample & Comparison
| Function | Purpose |
|----------|---------|
| `compare_scdblfinder_results()` | Compare doublet rates across multiple SCEs |
| `merge_scdblfinder_results()` | `cbind` multiple SCEs with scDblFinder results |
| `get_cells_by_origin()` | Get cells from specific origin cluster(s) |
| `check_doublet_enrichment()` | Fisher-style enrichment of doublets per cluster |

### Visualization
| Function | Purpose |
|----------|---------|
| `plot_doublet_score_distribution()` | Histogram of scores (optional `color_by`) |
| `plot_doublet_scores_by_class()` | Violin/boxplot by class |
| `plot_doublets_reduced()` | Scatter on UMAP/t-SNE/PCA |
| `plot_doublet_rate_by_sample()` | Bar plot of % doublets per sample |
| `plot_score_vs_libsize()` | Score vs total counts scatter |
| `plot_doublet_map()` | Observed vs expected heatmap (wraps `scDblFinder::plotDoubletMap`) |
| `plot_doublet_thresholds()` | Threshold optimization curve (extracts from SCE metadata) |
| `plot_scdblfinder_summary()` | Batch-export 4–5 standard plots to PDF |

---

## Official API — Agents Often Miss These

### Native scDblFinder functions

```r
# Core function
scDblFinder::scDblFinder(
  sce,
  samples = NULL,        # Sample IDs or colData column name
  clusters = NULL,       # TRUE/FALSE/vector
  nfeatures = 1000,      # Top features
  dims = 20,             # PCA dims
  dbr = NULL,            # Expected doublet rate (NULL = auto)
  dbr.sd = 0.015,        # Uncertainty in dbr
  dbr.per1k = 0.008,     # Rate per 1000 cells
  iter = 1,              # Scoring iterations
  multiSampleMode = "split",  # "split", "singleModel", "asOne"
  BPPARAM = BiocParallel::SerialParam()
)

# Built-in visualization
scDblFinder::plotDoubletMap(sce)
scDblFinder::plotThresholds(d, ths = (0:100)/100)
```

### Result structure

scDblFinder adds columns to `colData(sce)`:
- `scDblFinder.score` — numeric, doublet probability
- `scDblFinder.class` — `"singlet"` or `"doublet"`
- `scDblFinder.mostLikelyOrigin` — origin cluster(s) (cluster-based only)
- `scDblFinder.sample` — sample assignment (multi-sample only)

Thresholds and model info are stored in `metadata(sce)$scDblFinder`.

---

## Common Pitfalls

1. **⚠️ Pass raw counts, NOT normalized data**  
   scDblFinder expects raw count matrix. Passing log-normalized or scaled data causes incorrect artificial doublet generation and poor classification.

2. **⚠️ `clusters = TRUE` requires sufficient cells for clustering**  
   On datasets < 500 cells, auto-clustering may fail or produce unstable clusters. Use `clusters = FALSE` (random doublets) for small datasets.

3. **⚠️ Multi-sample: use `samples` parameter, NOT pre-merged integration**  
   scDblFinder processes each sample separately when `samples` is provided. Do NOT integrate first — integration distorts local neighborhoods and breaks doublet detection.

4. **⚠️ `multiSampleMode = "split"` vs `"asOne"`**  
   `"split"` (default): separate model per sample. Use for independent captures with different doublet rates. `"asOne"`: pooled model. Use only if samples are technical replicates from the same capture.

5. **⚠️ All cells predicted as singlets**  
   Usually indicates `dbr` is too restrictive or the dataset has genuinely very few doublets. Try `dbr.sd = 1` to disable expected-rate constraint.

6. **⚠️ All cells predicted as doublets**  
   Often happens when samples were not declared via `samples` parameter. scDblFinder sees batch structure as doublet signal. Fix: `run_scdblfinder(sce, samples = sce$sample_id)`.

7. **⚠️ Seurat v5: `as.SingleCellExperiment` fails with v5 assays**  
   The wrapper handles this automatically (`Assay5` → `Assay` conversion), but if calling native `scDblFinder::scDblFinder()` directly, convert first.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No 'counts' assay found` | Normalized data passed in | Use raw count matrix; `assay(sce, "counts")` must exist |
| `Too few cells - need at least 50` | < 50 cells in input | Merge samples or skip doublet detection |
| All cells = singlets | `dbr` constraint too strict | `dbr.sd = 1` to disable constraint |
| All cells = doublets | Missing `samples` on multi-sample data | `samples = sce$sample_id` |
| Poor singlet/doublet separation | Too few features or noisy data | Increase `nfeatures = 3000`, `iter = 2`, or `clusters = TRUE` |
| Slow on large dataset (>50k cells) | Single-threaded | `BPPARAM = BiocParallel::MulticoreParam(4)` |
| `scDblFinder.score not found` | Results not yet computed | Run `scDblFinder()` first |
| `Dimred UMAP not found` for plotting | UMAP not computed on SCE | Run `scater::runUMAP(sce)` or plot from Seurat |

---

## Related Skills

- [bio-single-cell-doublet-doubletfinder-r](../bio-single-cell-doublet-doubletfinder-r/SKILL.md) — Alternative with parameter sweep and homotypic adjustment
- [bio-single-cell-doublet-scrublet](../bio-single-cell-doublet-scrublet/SKILL.md) — Python-based doublet detection
- [bio-single-cell-qc-preprocessing-r](../bio-single-cell-qc-preprocessing-r/SKILL.md) — Pre-filtering before doublet detection

## References

1. Germain et al. (2021). PipeComp, a general framework for the evaluation of computational pipelines, reveals performant single cell RNA-seq preprocessing tools. *Genome Biology*, 22:1-29.
2. Xi & Li (2021). Benchmarking Computational Doublet-Detection Methods for Single-Cell RNA Sequencing Data. *Cell Systems*, 12(6):551-561.
3. scDblFinder Bioconductor: https://bioconductor.org/packages/scDblFinder
