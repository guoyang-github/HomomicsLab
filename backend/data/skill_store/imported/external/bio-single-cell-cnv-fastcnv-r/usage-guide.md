# fastCNV Usage Guide for Single-Cell Data

## Overview

fastCNV is an R package for fast and accurate copy number variation prediction from single-cell RNA-seq data. It provides genome-wide CNV estimation with integrated subclone identification through CNV clustering.

## Key Features

- **Fast**: ~1 minute for 4,000 cells
- **Genome-wide**: Sliding window approach across all chromosomes
- **Subclone Detection**: Built-in CNV clustering for tumor subclones
- **Flexible Reference**: Can run with or without reference cells
- **Multi-sample**: Pooled reference across samples automatically

## When to Use fastCNV

- Fast CNV inference needed
- Tumor/normal classification
- Subclone identification by CNV profile
- Multi-sample tumor analysis

## Quick Start

### Installation

```r
remotes::install_github("must-bioinfo/fastCNV")
remotes::install_github("must-bioinfo/fastCNVdata")  # Example datasets
```

### Basic Usage

```r
library(Seurat)
library(fastCNV)

source("scripts/r/run_fastcnv.R")

# Run with immune cells as reference
result <- run_fastcnv_sc(
  seurat_obj = seurat_obj,
  sample_name = "Tumor1",
  reference_var = "annot",
  reference_label = c("TNKILC", "Myeloid", "B", "Mast", "Plasma")
)
```

## Step-by-Step

### 1. Prepare Data

```r
library(Seurat)

# Load Seurat object
seurat_obj <- readRDS("tumor_data.rds")

# Ensure you have cell type annotations
# For CNV analysis, identify putative normal cells as reference
table(seurat_obj$annot)

# Or load external annotations
annotation_file <- read.csv("annotations.csv")
seurat_obj[["annot"]] <- annotation_file$Annot
```

### 2. Run fastCNV with Reference

```r
source("scripts/r/run_fastcnv.R")

result <- run_fastcnv_sc(
  seurat_obj = seurat_obj,
  sample_name = "Tumor_Sample",
  reference_var = "annot",
  reference_label = c("TNKILC", "Myeloid", "B", "Mast", "Plasma"),
  reCluster = FALSE,
  getCNVPerChromosomeArm = TRUE,
  savePath = "./fastcnv_output",
  printPlot = TRUE
)
```

### 3. Run Without Reference

```r
# If no normal cells available
result <- run_fastcnv_sc(
  seurat_obj = seurat_obj,
  sample_name = "Tumor_Sample"
)
```

### 4. Multi-Sample Analysis

```r
# Load multiple samples
sample1 <- readRDS("patient1.rds")
sample2 <- readRDS("patient2.rds")
sample3 <- readRDS("patient3.rds")

# IMPORTANT: use list(), NOT c()
seurat_list <- list(sample1, sample2, sample3)
sample_names <- c("P1", "P2", "P3")

reference_labels <- c("Plasma", "TNKILC", "Myeloid", "B", "Mast")

results <- run_fastcnv_multi_sc(
  seurat_list = seurat_list,
  sample_names = sample_names,
  reference_var = "annot",
  reference_label = reference_labels,
  printPlot = TRUE
)

# Access individual results
result_p1 <- results[["P1"]]
```

### 5. Access Results

```r
# CNV fraction per cell
head(result@meta.data$cnv_fraction)

# CNV clusters (subclones)
table(result@meta.data$cnv_clusters)

# Per chromosome arm CNV
grep("_CNV$", colnames(result@meta.data), value = TRUE)

# Example: Chromosome 20p CNV
hist(result@meta.data$`20.p_CNV`)
```

### 6. CNV Clustering and Subclone Analysis

```r
# Hierarchical CNV clustering
result <- cnv_cluster(result, reference_var = "annot")

# Merge correlated clusters
result <- merge_cnv_clusters(result, mergeThreshold = 0.95)

# Re-plot heatmap after merging
plot_cnv_heatmap(result, reference_var = "annot")

# Classify gains/losses
result <- cnv_classification(result, cnv_thresh = 0.1)

# Build phylogenetic tree
tree_data <- cnv_tree(result, values = "scores", cnv_thresh = 0.15, healthyClusters = "1")
```

### 7. Visualize Results

#### CNV Fraction on UMAP

```r
library(ggplot2)

common_theme <- theme(
  plot.title = element_text(size = 10),
  legend.text = element_text(size = 8),
  legend.title = element_text(size = 8),
  axis.title = element_text(size = 8),
  axis.text = element_text(size = 6)
)

FeaturePlot(result, features = "cnv_fraction", reduction = "umap") & common_theme |
  DimPlot(result, reduction = "umap", group.by = "annot") & common_theme
```

#### Boxplot of CNV Fraction by Annotation

```r
ggplot(FetchData(result, vars = c("annot", "cnv_fraction")),
       aes(annot, cnv_fraction, fill = annot)) +
  geom_boxplot() +
  theme(axis.text.x = element_text(angle = 45, vjust = 1, hjust = 1, color = "black"))
```

#### Per-Chromosome Arm on UMAP

```r
library(scales)

FeaturePlot(result, features = "20.p_CNV") +
  scale_color_distiller(
    palette = "RdBu", direction = -1, limits = c(-1, 1),
    rescaler = function(x, to = c(0, 1), from = NULL) {
      rescale_mid(x, to = to, mid = 0)
    }
  ) +
  common_theme |
FeaturePlot(result, features = "X.q_CNV") +
  scale_color_distiller(
    palette = "RdBu", direction = -1, limits = c(-1, 1),
    rescaler = function(x, to = c(0, 1), from = NULL) {
      rescale_mid(x, to = to, mid = 0)
    }
  ) +
  common_theme
```

Convenience wrapper:

```r
plot_chr_arm_umap(result, feature = "20.p_CNV")
plot_chr_arm_umap(result, feature = "X.q_CNV", limits = c(-0.5, 0.5))
```

#### CNV Classification (Gain / Loss / No Alteration)

```r
result <- cnv_classification(result)

DimPlot(result, group.by = "20.p_CNV_classification") &
  scale_color_manual(values = c(gain = "red", no_alteration = "grey", loss = "blue")) &
  common_theme |
DimPlot(result, group.by = "X.q_CNV_classification") &
  scale_color_manual(values = c(gain = "red", no_alteration = "grey", loss = "blue")) &
  common_theme
```

#### CNV Clusters

```r
DimPlot(result, group.by = "cnv_clusters") + common_theme

library(SeuratObject)
ggplot(FetchData(result, vars = c("cnv_clusters", "annot")),
       aes(annot, fill = as.factor(cnv_clusters))) +
  geom_bar(position = "fill") +
  theme(axis.text.x = element_text(angle = 45, vjust = 1, hjust = 1, color = "black"))
```

#### CNV Heatmap

```r
plot_cnv_heatmap(
  result,
  reference_var = "annot",
  output_file = "cnv_heatmap.pdf"
)
```

### 8. Summarize by Cluster

```r
# Compare CNV clusters with cell types
table(result$annot, result$cnv_clusters)

# CNV fraction by cluster
summarize_cnv_by_cluster(result, group_by = "cnv_clusters")

# By cell type
summarize_cnv_by_cluster(result, group_by = "annot")
```

## Parameters

### Main Parameters (fastCNV)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `seurat_obj` | Seurat object or list | Required |
| `sample_name` | Sample identifier(s) | Required |
| `reference_var` | Metadata column for reference | NULL |
| `reference_label` | Reference cell labels | NULL |
| `reCluster` | Recluster if seurat_clusters exists | FALSE |
| `getCNVPerChromosomeArm` | Per-arm CNV scores | TRUE |
| `savePath` | Directory for saved plots | "." |
| `printPlot` | Print plots to console | TRUE |

## AI Agent Test Cases

### Basic Usage

> "Run fastCNV on my tumor single-cell data with immune cells as reference"

```r
result <- run_fastcnv_sc(
  seurat_obj = seurat_obj,
  sample_name = "Tumor",
  reference_var = "annot",
  reference_label = c("TNKILC", "Myeloid", "B", "Mast", "Plasma")
)
```

### No Reference

> "Run fastCNV without reference cells"

```r
result <- run_fastcnv_sc(
  seurat_obj = seurat_obj,
  sample_name = "Tumor"
)
```

### Multi-sample

> "Analyze CNV in 3 tumor samples with pooled reference"

```r
results <- run_fastcnv_multi_sc(
  seurat_list = list(s1, s2, s3),
  sample_names = c("S1", "S2", "S3"),
  reference_var = "annot",
  reference_label = c("Plasma", "TNKILC", "Myeloid", "B", "Mast")
)
```

### Subclone Analysis

> "Identify tumor subclones by CNV profile"

```r
result <- cnv_cluster(result, reference_var = "annot")
result <- merge_cnv_clusters(result, mergeThreshold = 0.95)

# Visualize subclones
DimPlot(result, group.by = "cnv_clusters")
tree_data <- cnv_tree(result, values = "scores", cnv_thresh = 0.15, healthyClusters = "1")
```

### Result Extraction

> "Extract CNV fractions and clusters from fastCNV results"

```r
cnv_data <- extract_cnv_metadata(result)
head(cnv_data)

# Export
write.csv(cnv_data, "cnv_results.csv")
```

### UMAP Visualization

> "Plot CNV fraction on UMAP"

```r
FeaturePlot(result, features = "cnv_fraction", reduction = "umap")
```

> "Plot chromosome 20p CNV on UMAP"

```r
plot_chr_arm_umap(result, feature = "20.p_CNV")
```

## Best Practices

1. **Use Reference When Possible**: Include normal/immune cells for better accuracy
2. **Pooled Reference**: For multi-sample, fastCNV automatically pools reference—useful when individual samples lack healthy cells
3. **Re-clustering**: Leave `reCluster = FALSE` unless you want fastCNV to recluster when seurat_clusters already exists
4. **Aggregation**: Meta-cell aggregation (up to 15,000 counts) happens automatically; for very large datasets you can manually run `prepareCountsForCNVAnalysis()`
5. **Cluster Merging**: Use `merge_cnv_clusters()` to avoid over-splitting
6. **Multi-sample lists**: Always use `list(s1, s2, s3)`, NOT `c(s1, s2, s3)` — the latter merges Seurat objects instead of creating a list

## Troubleshooting

### Poor CNV Signal
- Check gene coverage across chromosomes
- Ensure sufficient cells (minimum ~100)
- Verify reference cells are truly normal

### Too Many Clusters
- Run `merge_cnv_clusters()` with a higher threshold
- Or constrain clustering to tumor cells with `cellTypesToCluster`

### All Cells Similar CNV
- Check reference cells are truly normal
- Ensure enough tumor cells with diverse CNV profiles

### "unused argument" Error
- fastCNV parameter names changed across versions. The wrappers in this skill match the latest fastCNV API. If you see "unused argument", check that your fastCNV version is up to date.

## Comparison with Other Tools

| Feature | fastCNV | CopyKAT | inferCNV |
|---------|---------|---------|----------|
| Speed | Fast | Medium | Slow |
| Subclones | Built-in | Yes | No |
| Reference | Optional | No | Required |
| Spatial | Yes | No | No |

## References

1. Cabrejas, G. et al. fastCNV: Fast and accurate copy number variation prediction from High-Definition Spatial Transcriptomics and scRNA-Seq Data. bioRxiv 2025.10.22.683855 (2025).
2. fastCNV documentation: https://must-bioinfo.github.io/fastCNV/
3. fastCNV scRNA-seq vignette: https://must-bioinfo.github.io/fastCNV/articles/fastCNV_sc.html
