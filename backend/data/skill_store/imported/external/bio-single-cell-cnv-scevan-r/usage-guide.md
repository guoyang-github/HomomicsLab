# SCEVAN Usage Guide

## Overview

SCEVAN (Single Cell CNV ANalysis) is a fast and accurate pipeline for detecting CNVs and distinguishing tumor from normal cells in scRNA-seq data.

## When to Use

- Fast tumor/normal classification
- Genome-wide CNV profiling
- Subclone detection and phylogenetic analysis
- Large-scale scRNA-seq datasets

## When NOT to Use

- Non-tumor samples (no CNVs to detect)
- Very low CNV burden tumors (may misclassify)
- If you need custom reference-based CNV calling (use inferCNV instead)

## Quick Start

```r
library(SCEVAN)

# Run pipeline
res_classify <- SCEVAN::pipelineCNA(
  count_mtx = counts_matrix,
  sample_name = "Tumor1",
  norm_cells = NULL,           # Optional: known normal cell names
  par_cores = 4,
  SUBCLONES = TRUE             # Enable subclone detection
)

# View results
head(res_classify)
```

## Step-by-Step

### 1. Prepare Data

```r
library(Seurat)
library(SCEVAN)

# Load Seurat object
seurat_obj <- readRDS("tumor_data.rds")

# Extract counts
counts_matrix <- GetAssayData(seurat_obj, slot = "counts")

# Ensure gene symbols are used (NOT ENSEMBL IDs)
head(rownames(counts_matrix))  # Should show "TP53", "BRCA1", etc.
```

### 2. Run SCEVAN Pipeline

```r
# Basic run (auto-detects normal cells)
results <- SCEVAN::pipelineCNA(
  count_mtx = counts_matrix,
  sample_name = "MyTumor",
  par_cores = 4,
  SUBCLONES = TRUE
)

# Results contain:
# - Cell classification (malignant vs non-malignant)
# - CNV profiles (saved to disk)
# - Subclone assignments (if SUBCLONES=TRUE)
```

### 3. With Known Normal Cells

```r
# If you have known normal cells
normal_cells <- colnames(seurat_obj)[seurat_obj$cell_type %in% c("T_cell", "B_cell", "Macrophage")]

results <- SCEVAN::pipelineCNA(
  counts_mtx = counts_matrix,
  sample_name = "MyTumor",
  norm_cells = normal_cells,    # Provide reference normal cells
  par_cores = 4,
  SUBCLONES = TRUE
)
```

### 4. Integrate with Seurat

```r
# Add classifications to Seurat
seurat_obj$scevan_class <- results[colnames(seurat_obj), "class"]
if ("subclone" %in% colnames(results)) {
  seurat_obj$scevan_subclone <- results[colnames(seurat_obj), "subclone"]
}

# Visualize
DimPlot(seurat_obj, group.by = "scevan_class", label = TRUE)
```

### 5. Load CNV Matrix

```r
# CNV matrix is saved to disk, not in the return value
load("MyTumor_CNAmtx.RData")  # Loads 'CNA_mtx' into environment
```

### 6. Visualize CNV Heatmap

SCEVAN generates plots automatically during execution:
- `MyTumor_CNV_plot.png` -- Genome-wide CNV heatmap
- `MyTumor_subclones.png` -- Subclone visualization (if SUBCLONES=TRUE)

## Skill Helper Usage

```r
source("scripts/r/run_scevan.R")

# End-to-end with Seurat
results <- run_scevan_seurat(seurat_obj, sample_name = "Tumor1", SUBCLONES = TRUE)

# Add to Seurat
seurat_obj <- add_scevan_to_seurat(seurat_obj, results)

# Summary
summarize_scevan(results)

# Plot classification on UMAP
plot_scevan_classification(seurat_obj)
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `count_mtx` | matrix | -- | Raw counts matrix (genes x cells) |
| `sample_name` | char | -- | Sample name for output files |
| `norm_cells` | vector | NULL | Known normal cell barcodes |
| `par_cores` | int | 1 | Parallel cores |
| `SUBCLONES` | bool | FALSE | Enable subclone detection |
| `beta_vega` | float | 0.5 | Segmentation parameter |
| `organism` | char | "human" | "human" or "mouse" |

## Output

| Output | Description |
|--------|-------------|
| `class` (return value) | Malignant vs non-malignant labels |
| `subclone` (return value) | Subclone assignments (if enabled) |
| `{sample}_CNAmtx.RData` | Gene-level CNV matrix |
| `{sample}_CNV_plot.png` | CNV heatmap visualization |
| `{sample}_subclones.png` | Subclone visualization |

## Best Practices

1. **Gene symbols** -- Ensure rownames are gene symbols, not ENSEMBL IDs
2. **Normal reference** -- Provide if available, but auto-detection works well
3. **Subclones** -- Enable SUBCLONES=TRUE for clonal analysis
4. **Parallel** -- Use par_cores > 1 for faster analysis
5. **Multiple samples** -- Run separately for each sample, then compare
6. **Output location** -- SCEVAN writes to getwd(); use unique sample_name per run

## Multi-Sample Analysis

```r
# Run SCEVAN on multiple samples
samples <- c("Tumor1", "Tumor2", "Tumor3")
results_list <- lapply(samples, function(samp) {
  counts <- readRDS(paste0(samp, "_counts.rds"))
  SCEVAN::pipelineCNA(counts, sample_name = samp, par_cores = 4, SUBCLONES = TRUE)
})

# Compare classifications across samples
classifications <- lapply(results_list, function(res) table(res$class))
```

## References

1. De Falco et al. (2023). A variational algorithm to detect the clonal copy number substructure of tumors from scRNA-seq data. *Nature Communications*.
2. SCEVAN documentation: https://github.com/AntonioDeFalco/SCEVAN
