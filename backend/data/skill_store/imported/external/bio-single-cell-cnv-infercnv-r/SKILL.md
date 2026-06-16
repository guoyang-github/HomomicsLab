---
name: bio-single-cell-cnv-infercnv-r
description: Copy number variation inference from single-cell RNA-seq using inferCNV (R). Compares tumor cells to reference normal cells to detect large-scale chromosomal CNVs. Includes Seurat integration and automatic gene order generation via biomaRt.
tool_type: r
primary_tool: infercnv
supported_tools: [Seurat, biomaRt]
languages: [r]
keywords: ["single-cell", "CNV", "inferCNV", "copy-number", "cancer", "r", "biomaRt"]
code_location: scripts/r/
version_compatibility:
  r: ">=4.0"
  infercnv: ">=1.14"
  seurat: ">=4.3"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.0 | |
| infercnv | >= 1.14 | Bioconductor |
| Seurat | >= 4.3 | For `run_infercnv_seurat()` |
| biomaRt | >= 2.54 | For `create_gene_order()` |
| ComplexHeatmap | >= 2.14 | For `plot_cnv()` |

## Installation

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")
BiocManager::install("infercnv")
BiocManager::install("biomaRt")
```

## Skill Overview

inferCNV detects large-scale copy number variations (gains/losses of entire chromosomes or chromosome arms) by comparing gene expression levels between tumor (observation) cells and reference normal cells. It operates on raw counts and produces a smoothed expression matrix where deviations from 1.0 indicate CNVs.

**Core workflow**: Prepare gene order + annotations → Create inferCNV object → Run analysis → Extract/visualize results

**When to use**:
- Cancer scRNA-seq data with known normal cell types as reference
- Need to distinguish malignant cells from tumor microenvironment
- Detecting large-scale chromosomal aberrations (whole-chromosome or arm-level)
- Tracking CNV clonal architecture across samples

**When NOT to use**:
- No reference normal cells in the dataset — inferCNV is comparative
- Looking for focal CNVs (< 1 Mb) — scRNA-seq resolution is too low
- Non-cancer data without expected CNVs
- Need per-cell CNV breakpoints — use SCEVAN or CopyKAT instead
- Gene names are Ensembl IDs without conversion — inferCNV requires gene symbols matching the gene order file

## Quick Reference

| Goal | Entry Point | Key Difference |
|------|-------------|---------------|
| Raw counts matrix | `run_infercnv(raw_counts, gene_order, annotations, ref_group_names)` | You provide all inputs directly |
| Seurat object | `run_infercnv_seurat(seurat_obj, cell_type_column, ref_cell_types)` | Extracts counts, annotations, and auto-creates gene order from Seurat |

## Core Workflow (Step-by-Step)

### Step 1: Prepare Gene Order

**Goal**: Map each gene to its chromosomal position.

**Option A: Auto-generate from biomaRt (recommended)**

```r
source("scripts/r/run_infercnv.R")

gene_order <- create_gene_order(
    gene_symbols = rownames(counts),   # Must match rownames of counts matrix
    genome = "hg38",                   # or "hg19", "mm10"
    organism = "human",                # or "mouse"
    dedup_method = "longest",          # "first" (fastest), "longest" (most accurate), "all"
    missing_action = "warn",           # "warn", "error", "ignore"
    output_file = "gene_order.txt"     # Optional: save for reproducibility
)
```

**What this wrapper adds**: Queries Ensembl biomaRt for gene positions, filters to standard chromosomes, handles duplicate genes (3 strategies), sorts by chromosome and position, reports missing genes.

| `dedup_method` | Use When |
|----------------|----------|
| `"first"` | Speed priority; default behavior |
| `"longest"` | Accuracy priority; keeps longest transcript |
| `"all"` | Rarely needed; appends `_dup1`, `_dup2` suffixes |

**Option B: Load existing file**

```r
gene_order <- load_gene_order("gene_order.txt")
# Validates 4-column format (gene, chr, start, end) and converts types
```

**After this step**: `gene_order` DataFrame with columns `gene`, `chr`, `start`, `end`.

---

### Step 2: Prepare Annotations

**Goal**: Label each cell as tumor (observation) or reference (normal).

```r
# Two-column data frame: cell_name, cell_type
annotations <- data.frame(
    cell = colnames(counts),
    cell_type = cell_type_vector,   # e.g., "Tumor", "Immune", "Endothelial"
    stringsAsFactors = FALSE
)
```

**⚠️ Critical**: `ref_group_names` must match values that actually exist in `annotations$cell_type`. If your reference cells are labeled "Macrophage" but you pass `ref_group_names = c("Immune")`, inferCNV will error.

**After this step**: `annotations` DataFrame ready for inferCNV.

---

### Step 3: Run inferCNV

**Goal**: Execute the CNV inference pipeline.

```r
infercnv_obj <- run_infercnv(
    raw_counts = counts,                  # Genes × cells matrix
    gene_order = gene_order,
    annotations = annotations,
    ref_group_names = c("Immune", "Endothelial"),
    cutoff = 0.1,                         # Expression cutoff
    out_dir = "./infercnv_output",
    cluster_by_groups = FALSE,
    denoise = TRUE,
    HMM = FALSE,
    num_threads = 4
)
```

**What this wrapper adds**: Accepts DataFrame inputs (writes temp files internally), sets `no_plot = TRUE` (avoids intermediate plots), exposes key parameters while hiding verbose defaults.

| Parameter | Default | When to Change |
|-----------|---------|----------------|
| `cutoff` | 0.1 | **snRNA-seq / low depth → 0.05**; Smart-seq2 / dense → 0.15 |
| `denoise` | TRUE | Denoising removes technical noise; set FALSE only if you want raw, unsmoothed CNV estimates |
| `HMM` | FALSE | Set TRUE for HMM state prediction; **very slow** |
| `cluster_by_groups` | FALSE | TRUE to cluster by cell type; FALSE for subclone detection |

**Runtime**: 10 min – 2 hours depending on cell count. HMM adds 2–5×.

**After this step**: `infercnv_obj` with `@expr.data` (genes × cells CNV matrix).

---

### Step 3B: Seurat Shortcut

**Goal**: Skip manual extraction if working with Seurat.

```r
infercnv_obj <- run_infercnv_seurat(
    seurat_obj,
    cell_type_column = "cell_type",
    ref_cell_types = c("Immune", "Endothelial"),
    gene_order_file = NULL,    # NULL = auto-create via biomaRt
    assay = "RNA",
    cutoff = 0.1,
    denoise = TRUE,
    HMM = FALSE
)
```

**What this wrapper adds**: Extracts counts matrix (handles Seurat v4 `slot=` vs v5 `layer=`), builds annotations from `meta.data`, optionally calls `create_gene_order()` automatically, then delegates to `run_infercnv()`.

**After this step**: Same as Step 3.

---

### Step 4: Extract and Interpret Results

**Goal**: Get CNV scores per cell and interpret.

```r
# CNV matrix: values ~1.0 = normal, >1.0 = gain, <1.0 = loss
cnv_matrix <- infercnv_obj@expr.data

# Per-cell CNV burden score (average absolute deviation from normal)
cnv_score <- colMeans(abs(cnv_matrix - 1))

# Add to Seurat (if applicable)
seurat_obj$cnv_score <- cnv_score[colnames(seurat_obj)]
```

| CNV Value | Interpretation |
|-----------|----------------|
| ~1.0 | Normal diploid (reference level) |
| > 1.0 | Gene amplification |
| < 1.0 | Gene deletion |
| > 1.3 | High-confidence amplification |
| < 0.7 | High-confidence deletion |

**Recommended thresholding strategy**:

```r
# Use reference cell distribution (most robust)
ref_indices <- unlist(infercnv_obj@reference_grouped_cell_indices)
ref_scores <- cnv_score[ref_indices]
threshold <- mean(ref_scores) + 2 * sd(ref_scores)  # or quantile(ref_scores, 0.95)
seurat_obj$cnv_status <- ifelse(seurat_obj$cnv_score > threshold, "Tumor", "Normal")
```

**After this step**: Per-cell CNV scores and binary tumor/normal calls.

---

### Step 5: Visualize

```r
# Plot heatmap (requires ComplexHeatmap)
plot_infercnv(infercnv_obj, "cnv_heatmap.png")

# Or use inferCNV's native plotting
plot_cnv(
    infercnv_obj,
    out_dir = "./infercnv_output",
    output_filename = "heatmap.pdf",
    x.center = 1,
    x.range = c(0.5, 1.5)
)
```

---

### Step 6: Export

```r
export_infercnv_results(infercnv_obj, output_dir = "./infercnv_export")
# Exports: cnv_matrix.csv, gene_order.csv
```

---

## Complete Pipeline

```r
library(Seurat)
source("scripts/r/run_infercnv.R")

# 1. Load clustered Seurat object
seurat_obj <- readRDS("tumor_data.rds")

# 2. Run inferCNV with Seurat wrapper
infercnv_obj <- run_infercnv_seurat(
    seurat_obj,
    cell_type_column = "cell_type",
    ref_cell_types = c("Immune", "Endothelial"),
    cutoff = 0.1,
    denoise = TRUE,
    HMM = FALSE,
    num_threads = 4
)

# 3. Extract CNV scores
cnv_score <- colMeans(abs(infercnv_obj@expr.data - 1))
seurat_obj$cnv_score <- cnv_score[colnames(seurat_obj)]

# 4. Classify tumor vs normal using reference distribution
ref_idx <- unlist(infercnv_obj@reference_grouped_cell_indices)
threshold <- quantile(cnv_score[ref_idx], 0.95)
seurat_obj$cnv_status <- ifelse(seurat_obj$cnv_score > threshold, "Tumor", "Normal")

# 5. Visualize
FeaturePlot(seurat_obj, features = "cnv_score")
DimPlot(seurat_obj, group.by = "cnv_status")

# 6. Export
export_infercnv_results(infercnv_obj, "./cnv_export")
```

## Skill-Provided Functions

Source: `scripts/r/run_infercnv.R`

### Main Pipeline

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `run_infercnv(raw_counts, gene_order, annotations, ...)` | `ref_group_names`, `cutoff`, `denoise`, `HMM`, `num_threads` | Core inferCNV wrapper. Accepts DataFrames (auto-writes temp files) or file paths. Sets `no_plot = TRUE` to suppress intermediate plots |
| `run_infercnv_seurat(seurat_obj, ...)` | `cell_type_column`, `ref_cell_types`, `gene_order_file` (NULL = auto), `assay` | Seurat shortcut: extracts counts, builds annotations, optionally auto-creates gene order. Handles Seurat v4/v5 compatibility |

### Gene Order

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `create_gene_order(gene_symbols, ...)` | `genome` (hg38/hg19/mm10), `organism`, `dedup_method`, `output_file` | Queries biomaRt with mirror fallback. Filters standard chromosomes. Deduplicates via first/longest/all strategy. Sorts by chr + position |
| `load_gene_order(file_path, ...)` | `expected_genes` (optional) | Reads 4-column TSV, validates format, converts types, warns about missing expected genes |

### Utilities

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `plot_infercnv(infercnv_obj, output_file)` | — | Thin wrapper around `plot_cnv()` with `x.center = 1`, `x.range = c(0.5, 1.5)` |
| `export_infercnv_results(infercnv_obj, output_dir)` | — | Exports `@expr.data` and `@gene_order` as CSVs |

### Internal Helpers

| Function | Description |
|----------|-------------|
| `.deduplicate_genes(gene_positions, symbol_col, method)` | First / longest / all-suffix strategies for genes with multiple chromosomal locations |
| `.sort_gene_order(gene_order, organism)` | Sorts by canonical chromosome order (human: chr1–22, X, Y, MT; mouse: chr1–19, X, Y, MT) |

## Official API — Agents Often Miss These

| Pattern | Key Point |
|---------|-----------|
| `CreateInfercnvObject(..., chr_exclude = c("chrX", "chrY", "chrMT"))` | Our wrapper excludes sex chromosomes and **chrMT** (not "chrM"). This matches `create_gene_order()` output format. |
| `cutoff` semantics | Minimum mean expression per gene across all cells. Genes below this are excluded. **Not a p-value or confidence threshold.** |
| `run()` vs `infercnv::run()` | Our `run_infercnv()` calls `infercnv::run(no_plot = TRUE, plot_steps = FALSE)` to avoid generating intermediate plots. Call `plot_cnv()` manually after completion. |
| `cluster_by_groups = TRUE` | Clusters observation cells separately by their annotation group. Set **FALSE** if you want to detect subclones within the tumor population. |
| HMM runtime | `HMM = TRUE` triggers 6-state HMM prediction. Adds **2–5× runtime**. For large datasets (>10k cells), consider running without HMM first. |
| `@expr.data` dimensions | Genes × cells (same orientation as input counts). Values centered around 1.0. Do NOT confuse with `@reference_grouped_cell_indices` which contains cell indices. |
| `colMeans(abs(cnv_matrix - 1))` | Correct way to compute per-cell CNV burden. `rowMeans` would give per-gene averages — a common agent mistake. |
| biomaRt connectivity | `create_gene_order()` tries `www.ensembl.org` first, then falls back to `useast.ensembl.org`. Network failures produce clear error messages. |

## Common Pitfalls

1. **Gene name mismatch between counts and gene order**  
   If `rownames(counts)` uses Ensembl IDs but `gene_order$gene` uses HGNC symbols (or vice versa), inferCNV will run but produce no meaningful results. Verify overlap: `length(intersect(rownames(counts), gene_order$gene))`.

2. **Reference cell types not in annotations**  
   `ref_group_names` must exactly match values in `annotations$cell_type`. A typo like `"Immune"` vs `"immune"` (case) or `"Endothelial"` vs `"Endothelium"` will cause errors.

3. **All cells labeled as reference**  
   If your annotation column contains only the reference types (e.g., all cells are "Immune"), inferCNV has no observations to compare. Ensure tumor cells are labeled distinctly.

4. **`rowMeans` instead of `colMeans` for CNV score**  
   `infercnv_obj@expr.data` is genes × cells. Per-cell score requires `colMeans(abs(cnv_matrix - 1))`. `rowMeans` averages across cells per gene.

5. **Forgetting `denoise = TRUE`**  
   Without denoising, the heatmap is dominated by technical noise. Our wrapper now defaults to `denoise = TRUE`. If you explicitly set `denoise = FALSE`, expect noisier results.

6. **Running HMM on large datasets without planning**  
   HMM scales poorly. For >10k cells, expect hours of runtime. Start with `HMM = FALSE`, inspect the denoised heatmap, then re-run with HMM on a subset if needed.

## Troubleshooting

### `Error in CreateInfercnvObject: Reference group names not found in annotations`

`ref_group_names` contains values not present in `annotations$cell_type`.

```r
# Debug: check available cell types
unique(annotations$cell_type)
# Fix: use exact matching names
ref_group_names = c("Immune", "Endothelial")  # must match exactly
```

### `Error: No genes found with standard chromosome annotations`

Gene symbols don't match biomaRt records, or organism/genome mismatch.

```r
# Debug: check overlap
length(intersect(rownames(counts), gene_order$gene))
# Fix: verify organism (human vs mouse) and genome build (hg38 vs hg19)
```

### `Error in useMart: Cannot connect to BioMart`

biomaRt server unavailable.

```r
# Fix: the wrapper already tries useast mirror automatically.
# If both fail, use a pre-built gene order file:
gene_order <- load_gene_order("gene_order.txt")
```

### Heatmap is all noise / no clear CNV patterns

```r
# Fix 1: Enable denoising
infercnv_obj <- run_infercnv(..., denoise = TRUE)

# Fix 2: Lower cutoff for sparse data
infercnv_obj <- run_infercnv(..., cutoff = 0.05)

# Fix 3: Check reference quality — are reference cells truly normal?
table(annotations$cell_type)
```

### Empty or near-zero `@expr.data`

All genes were filtered out. Check cutoff and gene overlap.

```r
# Debug
dim(infercnv_obj@expr.data)
dim(infercnv_obj@gene_order)
# If 0 rows, reduce cutoff or check gene name compatibility
```

## Related Skills

- [bio-single-cell-cnv-infercnvpy](../bio-single-cell-cnv-infercnvpy/SKILL.md) — Python infercnvpy alternative with Scanpy integration
- [bio-single-cell-cnv-scevan-r](../bio-single-cell-cnv-scevan-r/SKILL.md) — SCEVAN: joint CNV calling + tumor/normal classification
- [bio-single-cell-cnv-copykat-r](../bio-single-cell-cnv-copykat-r/SKILL.md) — CopyKAT: genome-wide ploidy + CNV at single-cell resolution

## References

1. Patel et al. (2014). Single-cell RNA-seq highlights intratumoral heterogeneity in primary glioblastoma. *Science*.
2. inferCNV documentation: https://github.com/broadinstitute/inferCNV
