# inferCNV Usage Guide

## Overview

inferCNV predicts copy number variations from single-cell RNA-seq data by comparing tumor cells to a reference set of normal cells.

## When to Use

- Cancer scRNA-seq analysis
- Detect large-scale chromosomal CNVs
- Distinguish tumor from microenvironment cells
- Track CNV evolution across samples

## Quick Start

```r
library(infercnv)

# Create inferCNV object
infercnv_obj <- CreateInfercnvObject(
  raw_counts_matrix = counts,
  gene_order_file = gene_order_file,
  annotations_file = annotations_file,
  ref_group_names = c("Immune", "Endothelial")
)

# Run analysis
infercnv_obj <- infercnv::run(
  infercnv_obj,
  cutoff = 0.1,
  out_dir = "./infercnv_output",
  denoise = TRUE,
  HMM = FALSE
)
```

## Step-by-Step

### 1. Prepare Input Files

```r
# Three required inputs:

# 1. Raw counts matrix (genes x cells)
counts <- GetAssayData(seurat_obj, slot = "counts")

# 2. Gene order file (gene positions)
# Format: gene_name chr start end
# Example:
# GENE1  chr1  1000  2000
# GENE2  chr1  5000  6000
gene_order <- read.delim("gene_order_file.txt", header = FALSE)

# 3. Annotations file (cell type labels)
# Format: cell_name  cell_type
# Example:
# Cell1  Tumor
# Cell2  Immune
annotations <- data.frame(
  cell = colnames(seurat_obj),
  type = seurat_obj$cell_type
)
write.table(annotations, "annotations.txt", sep = "\t", quote = FALSE, row.names = FALSE, col.names = FALSE)
```

### 2. Create inferCNV Object

```r
library(infercnv)

infercnv_obj <- CreateInfercnvObject(
  raw_counts_matrix = counts,
  gene_order_file = "gene_order_file.txt",
  annotations_file = "annotations.txt",
  delim = "\t",
  max_cells_per_group = NULL,
  min_max_counts_per_cell = c(100, +Inf),
  ref_group_names = c("Immune", "Endothelial", "Fibroblast")  # Normal cell types
)
```

### 3. Run Analysis

```r
# Basic run (recommended for first pass)
infercnv_obj <- infercnv::run(
  infercnv_obj,
  cutoff = 0.1,                    # Expression cutoff
  out_dir = "./infercnv_output",
  cluster_by_groups = TRUE,        # Cluster by cell type
  denoise = TRUE,                  # Remove noise
  noise_filter = 0.2,
  HMM = FALSE,                     # Set TRUE for HMM predictions
  num_threads = 4,
  no_prelim_plot = TRUE
)
```

### 4. Extract and Visualize

```r
# Load results
expr_matrix <- read.table("infercnv_output/infercnv.observations.txt", header = TRUE, row.names = 1)

# Plot genomic regions
plot_cnv(
  infercnv_obj,
  out_dir = "./infercnv_output",
  cluster_by_groups = TRUE,
  x.center = 0.9,
  x.range = c(0.85, 1.1)
)
```

### 5. With Seurat Integration

```r
# Add CNV scores to Seurat
# Calculate per-cell CNV burden (mean absolute deviation from normal)
cnv_scores <- colMeans(abs(expr_matrix - 1))

# Add to Seurat metadata
seurat_obj$cnv_score <- cnv_scores[match(colnames(seurat_obj), names(cnv_scores))]

# Visualize
FeaturePlot(seurat_obj, features = "cnv_score")
VlnPlot(seurat_obj, features = "cnv_score", group.by = "cell_type")
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cutoff` | float | 0.1 | Min average expression for genes |
| `denoise` | bool | TRUE | Remove noise from signal |
| `HMM` | bool | FALSE | Run HMM for CNV prediction |
| `noise_filter` | float | 0.2 | Remove signal below threshold |
| `cluster_by_groups` | bool | TRUE | Cluster by cell groups |
| `num_threads` | int | 1 | Parallel threads |

## Output Files

| File | Description |
|------|-------------|
| `infercnv.observations.txt` | CNV signal matrix |
| `infercnv.references.txt` | Reference cell signal |
| `infercnv.png` | Heatmap visualization |
| `HMM_CNV_predictions.*` | HMM predictions (if HMM=TRUE) |

## AI Agent Test Cases

### Basic Run
> "Run inferCNV on my tumor data with Immune and Endothelial as reference"

> "Create inferCNV object and run analysis with denoising"

### Advanced Options
> "Run inferCNV with HMM to predict CNV states"

> "Use multiple normal cell types as reference for inferCNV"

> "Adjust cutoff to 0.05 for more sensitive CNV detection"

### Result Analysis
> "Plot inferCNV heatmap showing CNVs by chromosome"

> "Add CNV scores to my Seurat object"

> "Identify cells with high CNV burden"

### Comparison
> "Compare inferCNV results with CopyKAT predictions"

## Best Practices

1. **Reference cells** - Use known normal cell types (Immune, Endothelial, Fibroblast)
2. **Gene order** - Ensure gene positions file matches genome build
3. **Cutoff tuning** - Lower cutoff (0.05) for sparse data, higher (0.1) for dense
4. **Denoising** - Always use denoise=TRUE for cleaner results
5. **HMM** - Enable HMM=TRUE for state prediction (slower but more precise)

## Creating Gene Order File

```r
# Using biomaRt
library(biomaRt)
ensembl <- useMart("ensembl", dataset = "hsapiens_gene_ensembl")

gene_positions <- getBM(
  attributes = c("hgnc_symbol", "chromosome_name", "start_position", "end_position"),
  filters = "hgnc_symbol",
  values = rownames(counts),
  mart = ensembl
)

# Filter and format
gene_positions <- gene_positions[gene_positions$chromosome_name %in% c(1:22, "X", "Y"), ]
gene_positions$chromosome_name <- paste0("chr", gene_positions$chromosome_name)

# Save
write.table(gene_positions[, c("hgnc_symbol", "chromosome_name", "start_position", "end_position")],
            "gene_order_file.txt", sep = "\t", quote = FALSE, row.names = FALSE, col.names = FALSE)
```

## References

1. Patel et al. (2014). Single-cell RNA-seq highlights intratumoral heterogeneity in primary glioblastoma. *Science*.
2. inferCNV documentation: https://github.com/broadinstitute/inferCNV
