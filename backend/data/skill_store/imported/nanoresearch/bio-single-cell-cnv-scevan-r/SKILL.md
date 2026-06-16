---
name: bio-single-cell-cnv-scevan-r
description: Single-cell CNV inference and tumor/normal classification using SCEVAN. Variational algorithm for detecting copy-number alterations, distinguishing malignant from non-malignant cells, and identifying tumor subclones from scRNA-seq data.
tool_type: r
primary_tool: SCEVAN
supported_tools: [Seurat, devtools]
languages: [r]
keywords: ["single-cell", "CNV", "SCEVAN", "subclone", "copy-number", "tumor", "malignant", "R"]
code_location: scripts/r/
version_compatibility:
  r: ">=4.2.0"
  scevan: "GitHub latest"
  seurat: ">=4.3.0"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.2.0 | |
| SCEVAN | GitHub latest | devtools::install_github("AntonioDeFalco/SCEVAN") |
| Seurat | >= 4.3.0 | Optional; v4/v5 both supported |

## Installation

```r
if (!require("devtools", quietly = TRUE))
    install.packages("devtools")
devtools::install_github("AntonioDeFalco/SCEVAN")
```

## Skill Overview

SCEVAN infers copy-number alterations (CNAs) from scRNA-seq expression profiles using a variational approach. It classifies cells as malignant or non-malignant, profiles genome-wide CNVs, and identifies tumor subclones.

**Core workflow**: Prepare count matrix -> run_scevan() -> Add results to Seurat -> Visualize

**When to use**: Tumor samples where you need to distinguish malignant from normal cells, profile CNVs, or identify subclones. Works best with solid tumors (high CNV burden).

**When NOT to use**:
- Non-tumor samples (no CNVs to detect)
- Samples with very low CNV burden (SCEVAN may misclassify)
- If you need chromosome-level breakpoint resolution -> consider inferCNV

## Quick Reference: Method Comparison

| Feature | SCEVAN | CopyKAT | inferCNV |
|---------|--------|---------|----------|
| Speed | Fast | Medium | Slow |
| Auto normal detection | Yes | Yes | No |
| Subclones | Yes | Yes | No |
| Reference normal required | Optional | No | Yes |
| Best for | Large tumor datasets | Accuracy | Custom references |

## Core Workflow (Step-by-Step)

Source skill helpers before using convenience functions:

```r
source("scripts/r/run_scevan.R")
```

### Step 1: Prepare Count Matrix

**Goal**: Get a raw count matrix with gene symbols as rownames.

**Input**: Raw counts (NOT normalized). Genes x cells matrix.
**Output**: Count matrix ready for SCEVAN

```r
# From Seurat
counts <- GetAssayData(seurat_obj, slot = "counts")  # v4
# or
counts <- GetAssayData(seurat_obj, layer = "counts") # v5

# Verify gene symbols
head(rownames(counts))  # Should be "TP53", "BRCA1", etc. NOT "ENSG..."
```

**CRITICAL: Gene symbols required**

SCEVAN expects gene symbols (e.g. "TP53") as rownames. If your data uses ENSEMBL IDs, convert them first.

---

### Step 2: Run SCEVAN

**Goal**: Classify cells and infer CNVs.

#### Option A: From count matrix

```r
results <- run_scevan(
  count_mtx = counts,
  sample_name = "Tumor1",
  par_cores = 4,
  norm_cell = NULL,        # NULL = auto-detect normal cells
  SUBCLONES = TRUE,        # Enable subclone detection
  beta_vega = 0.5,         # Segmentation parameter
  organism = "human"
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sample_name` | string | "Sample" | Used for naming output files |
| `par_cores` | int | 4 | Parallel cores |
| `norm_cell` | character vector | NULL | Known normal cell barcodes. NULL = auto-detect |
| `SUBCLONES` | bool | TRUE | Detect tumor subclones |
| `beta_vega` | float | 0.5 | Segmentation strictness. Lower = more segments |
| `organism` | string | "human" | "human" or "mouse" |

#### Option B: From Seurat (v4/v5 auto-detected)

```r
results <- run_scevan_seurat(
  seurat_obj,
  sample_name = "Tumor1",
  norm_cell = known_normal_cells,  # Optional
  SUBCLONES = TRUE,
  par_cores = 4
)
```

#### Option C: With known normal cells

If you have confident normal cells (e.g. immune cells from a tumor sample), providing them improves accuracy:

```r
normal_cells <- colnames(seurat_obj)[seurat_obj$cell_type %in% c("T_cell", "B_cell", "Macrophage")]

results <- run_scevan_seurat(
  seurat_obj,
  sample_name = "Tumor1",
  norm_cell = normal_cells,
  SUBCLONES = TRUE
)
```

---

### Step 3: Understand the Output

SCEVAN produces **two kinds of outputs**:

**A. Return value** (results data frame):

```r
# results is a data frame with cells as rownames
head(results)
#                    class    subclone
# AAACCTGAGC... malignant subclone_1
# AAACCTGAGT... malignant subclone_1
# AAACCTGCAA...non-malig.        <NA>
```

| Column | Description |
|--------|-------------|
| `class` | "malignant" or "non-malignant" |
| `subclone` | Subclone ID (if SUBCLONES = TRUE; NA for non-malignant) |

**B. Files saved to working directory** (automatically):

| File | Content |
|------|---------|
| `{sample}_CNAmtx.RData` | CNV matrix (load with load()) |
| `{sample}_CNV_plot.png` | CNV heatmap |
| `{sample}_confidentNormal` | High-confidence normal cells |
| `{sample}_subclones.png` | Subclone visualization (if enabled) |

---

### Step 4: Add Results to Seurat

**Goal**: Integrate classifications into your Seurat object for downstream analysis.

```r
# Using skill helper
seurat_obj <- add_scevan_to_seurat(seurat_obj, results, prefix = "scevan_")

# Manual equivalent
seurat_obj$scevan_class <- results[colnames(seurat_obj), "class"]
if ("subclone" %in% colnames(results)) {
  seurat_obj$scevan_subclone <- results[colnames(seurat_obj), "subclone"]
}
```

---

### Step 5: Visualize

```r
# Classification on UMAP
DimPlot(seurat_obj, group.by = "scevan_class", label = TRUE)

# Subclones (tumor cells only)
DimPlot(seurat_obj, group.by = "scevan_subclone", label = TRUE)

# Using skill helper (wraps DimPlot)
plot_scevan_classification(seurat_obj, reduction = "umap")

# Summary statistics
summarize_scevan(results)
```

**SCEVAN-generated plots** (in working directory):
- `{sample}_CNV_plot.png` -- Genome-wide CNV heatmap
- `{sample}_subclones.png` -- Subclone CNV profiles

---

### Step 6: Load CNV Matrix (Optional)

SCEVAN saves the CNV matrix to disk, not in the return value:

```r
# Load saved CNV matrix
load("Tumor1_CNAmtx.RData")  # Creates object 'CNA_mtx' in environment

# CNA_mtx is a gene x cell matrix with CNV values
```

---

## Complete Pipeline via Skill Wrapper

```r
source("scripts/r/run_scevan.R")

# Run annotation
results <- run_scevan_seurat(
  seurat_obj,
  sample_name = "Tumor1",
  norm_cell = NULL,
  SUBCLONES = TRUE,
  par_cores = 4
)

# Add to Seurat
seurat_obj <- add_scevan_to_seurat(seurat_obj, results)

# Summary
summarize_scevan(results)

# Visualize
plot_scevan_classification(seurat_obj)

# Load CNV matrix for custom analysis
load("Tumor1_CNAmtx.RData")
```

---

## Skill-Provided Helper Functions

Source: `scripts/r/run_scevan.R`

| Function | Parameters | What it adds |
|----------|-----------|-------------|
| `run_scevan(count_mtx, sample_name, par_cores=4, norm_cell=NULL, SUBCLONES=TRUE, beta_vega=0.5, organism="human")` | -- | Validates input, runs pipelineCNA, reports output files |
| `run_scevan_seurat(seurat_obj, assay="RNA", sample_name, norm_cell=NULL, ...)` | Auto-detects v4/v5 | Extracts counts, validates barcodes, delegates to run_scevan() |
| `add_scevan_to_seurat(seurat_obj, scevan_results, prefix="scevan_")` | -- | Safely merges class and subclone into Seurat metadata |
| `plot_scevan_classification(seurat_obj, reduction="umap", output_file=NULL)` | -- | Wraps DimPlot for SCEVAN classifications |
| `summarize_scevan(scevan_results)` | -- | Prints classification and subclone tables |

---

## Official API -- Agents Often Miss These

| Function / Pattern | Key Point |
|-------------------|-----------|
| `SCEVAN::pipelineCNA(count_mtx, sample_name=..., norm_cell=...)` | **Output is a classDf (data frame), NOT a list**. CNV matrix is saved to disk, not returned. |
| `norm_cell = NULL` | NULL = auto-detect normal cells. Providing known normal barcodes improves accuracy. |
| `sample_name` | Used to name **output files on disk**, not just for display. |
| `beta_vega = 0.5` | Segmentation strictness. Lower = more sensitive to small CNVs but more noise. Range: 0.1-1.0. |
| `SUBCLONES = TRUE` | Adds subclone detection but increases runtime. Disable for quick tumor/normal screening. |
| `organism = "human"` | Must match your data. Mouse references are available but less comprehensive. |
| Gene symbols | **ENSEMBL IDs will silently fail**. Must convert to gene symbols before running. |

---

## Common Pitfalls

1. **Expecting CNV matrix in return value**: pipelineCNA() returns a cell classification data frame. The CNV matrix is saved to `{sample}_CNAmtx.RData` on disk.
2. **ENSEMBL IDs**: SCEVAN matches genes to its internal reference using gene symbols. ENSEMBL IDs cause near-zero overlap and nonsense results.
3. **Wrong sample_name**: If you run multiple samples, each needs a unique sample_name or output files will overwrite each other.
4. **Norm_cell barcodes not found**: If norm_cell contains barcodes not in the count matrix, SCEVAN may error or ignore them. Always validate overlap first.
5. **Seurat v5 layer vs slot**: GetAssayData(seurat_obj, slot="counts") is deprecated in v5. The skill helper handles this, but manual extraction needs care.
6. **Very small tumors**: If the tumor has few CNVs, SCEVAN may classify all cells as non-malignant. Cross-check with known markers.

---

## Hyperparameter Guide

| Parameter | Default | When to Change |
|-----------|---------|---------------|
| `beta_vega` | 0.5 | Lower (0.2-0.3) for detecting small focal CNVs; higher (0.7-1.0) for broad arm-level changes only |
| `SUBCLONES` | TRUE | FALSE for quick tumor/normal screening; TRUE for clonal evolution analysis |
| `par_cores` | 4 | Increase for large datasets (>10k cells); decrease if memory-limited |
| `norm_cell` | NULL | Provide known immune/stromal barcodes if available for better accuracy |

---

## Troubleshooting

### All cells classified as non-malignant

```r
# Check if tumor actually has CNVs
# Compare with known tumor markers (e.g. epithelial markers in carcinoma)
# Try lowering beta_vega for more sensitivity
results <- run_scevan(counts, sample_name = "Tumor1", beta_vega = 0.2)
```

### "Some barcodes not found" error

```r
# Validate overlap before running
sum(norm_cells %in% colnames(counts)) / length(norm_cells)
# Should be 1.0 (100%)
```

### Output files not found

SCEVAN writes to the **current working directory** (getwd()). Check:
```r
list.files(getwd(), pattern = "_CNAmtx\\.RData$")
```

---

## Multi-Sample Analysis

```r
samples <- c("Tumor1", "Tumor2", "Tumor3")
results_list <- lapply(samples, function(samp) {
  counts <- readRDS(paste0(samp, "_counts.rds"))
  run_scevan(counts, sample_name = samp, par_cores = 4, SUBCLONES = TRUE)
})

# Compare classifications
lapply(results_list, function(res) table(res$class))
```

**Important**: Run each sample separately. SCEVAN is designed for per-sample analysis; merging samples before running may confound batch effects with CNV signals.

---

## Related Skills

- [bio-single-cell-cnv-infercnv-r](../bio-single-cell-cnv-infercnv-r/SKILL.md) - CNV inference with custom references
- [bio-single-cell-cnv-copykat-r](../bio-single-cell-cnv-copykat-r/SKILL.md) - CNV + cell cycle inference

## References

1. De Falco et al. (2023). A variational algorithm to detect the clonal copy number substructure of tumors from scRNA-seq data. *Nature Communications*, 14, 7544.
2. SCEVAN GitHub: https://github.com/AntonioDeFalco/SCEVAN
