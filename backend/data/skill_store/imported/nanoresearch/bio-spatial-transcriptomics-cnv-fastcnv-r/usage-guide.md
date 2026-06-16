# fastCNV Usage Guide

## Overview

fastCNV is an R package for fast and accurate copy number variation prediction from spatial transcriptomics (Visium, Visium HD) and single-cell RNA-seq data. Built on SeuratObject, it integrates seamlessly into existing analysis pipelines.

## Key Features

- **Spatial Transcriptomics**: Optimized for 10x Visium and Visium HD data
- **Fast Performance**: ~1 minute for 4,000 cells, ~40 minutes for Visium HD (16 µm)
- **Pooled Reference**: Automatically builds reference across multiple samples
- **CNV Clustering**: Identify tumor subclones by CNV profile
- **Spatial Visualization**: Map CNV fractions and chromosome-arm alterations on tissue
- **CNV Tree**: Build phylogenetic trees from CNV profiles

## When to Use fastCNV

- **Visium/Visium HD**: Primary choice for spatial CNV analysis
- **Multi-sample**: When you need pooled reference across samples
- **Subclone detection**: When identifying CNV-based tumor subclones
- **scRNA-seq**: Alternative to inferCNV/CopyKAT for single-cell data

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

# Load your Seurat object
seurat_obj <- readRDS("visium_data.rds")

# Run fastCNV with reference
result <- fastCNV(
  seuratObj = seurat_obj,
  sampleName = "Sample1",
  referenceVar = "cell_type",
  referenceLabel = "Healthy_Tissue"
)
```

## Step-by-Step

### 1. Data Preparation

#### For Visium Data

```r
library(Seurat)

# Load 10x Visium data
seurat_obj <- Load10X_Spatial(
  data.dir = "path/to/spaceranger/outs",
  filename = "filtered_feature_bc_matrix.h5"
)

# Add annotations if available
annotation_file <- read.csv("annotations.csv")
seurat_obj[["annot"]] <- annotation_file$Annot
```

#### For Visium HD Data

```r
# Load Visium HD data (Seurat5)
seurat_hd <- Load10X_Spatial(
  data.dir = "path/to/hd/data",
  filename = "filtered_feature_bc_matrix.h5"
)

# If annotations are on 8um resolution, map to 16um
seurat_hd[["annots_8um"]] <- annotation_file$Annotations
seurat_hd <- annotations8umTo16um(seurat_hd, referenceVar = "annots_8um")
# Verify mapping
SpatialDimPlot(seurat_hd, group.by = "projected_annots_8um")
```

#### For scRNA-seq

```r
# Standard Seurat object
seurat_obj <- CreateSeuratObject(counts = raw_data)
seurat_obj$cell_type <- cell_type_annotations
```

### 2. Run fastCNV

#### Single Sample with Reference

```r
result <- fastCNV(
  seuratObj = seurat_obj,
  sampleName = "Tumor_Sample",
  referenceVar = "annot",
  referenceLabel = c("Healthy", "Normal_Epithelium"),
  aggregFactor = 15000,
  aggregateByVar = TRUE,
  reCluster = FALSE,
  getCNVPerChromosomeArm = TRUE,
  downsizePlot = FALSE,
  savePath = "./fastcnv_output",
  printPlot = TRUE
)
```

#### Without Reference

```r
result <- fastCNV(
  seuratObj = seurat_obj,
  sampleName = "Tumor_Sample"
)
```

#### Multiple Samples (Pooled Reference)

Provide a **named list** of Seurat objects. fastCNV pools reference spots across all samples automatically.

```r
seuratList <- list(sample1, sample2, sample3)
sampleNames <- c("S1", "S2", "S3")
names(seuratList) <- sampleNames

referencelabels <- c("Healthy", "Normal_Epithelium", "Submucosa")

seuratList <- fastCNV(
  seuratList,
  sampleNames,
  referenceVar = "annot",
  referenceLabel = referencelabels,
  printPlot = TRUE
)
```

> **Important**: Use `list()`, not `c()`. `c()` on Seurat objects produces undefined behavior.

**Reference label behavior in multi-sample mode:**

- `referenceLabel` values are searched **globally across all samples** using exact string match.
- If you pass multiple labels (e.g., `c("Healthy", "Normal")`), fastCNV pools all matching spots for each label separately, computes a scale factor per label, then takes the **median** as the final shared reference.
- Each sample must contribute **>= 5** spots for a given label; otherwise that sample is excluded from that label's pool.

**Scenario A — All samples share the same healthy label:**

```r
results <- fastCNV(
  list(s1, s2, s3),
  c("S1", "S2", "S3"),
  referenceVar = "annot",
  referenceLabel = "Healthy"
)
```

**Scenario B — Different samples use different healthy labels:**

```r
# Sample1: "Normal", Sample2: "Healthy", Sample3: "Submucosa"
results <- fastCNV(
  list(s1, s2, s3),
  c("S1", "S2", "S3"),
  referenceVar = "annot",
  referenceLabel = c("Normal", "Healthy", "Submucosa")
)
```

**Scenario C — Only one sample has healthy tissue:**

```r
# Only s1 has "Healthy" spots; s2 and s3 have none
results <- fastCNV(
  list(s1, s2, s3),
  c("S1", "S2", "S3"),
  referenceVar = "annot",
  referenceLabel = "Healthy"
)
# s1's healthy spots are used as the pooled reference for all three samples
```

**Processing results per sample:**

```r
# results is a named list of Seurat objects
for (name in names(results)) {
  cat(name, ": mean CNV fraction =",
      mean(results[[name]]$cnv_fraction, na.rm = TRUE), "\n")
}
```

### 3. Run on Visium HD

```r
result_hd <- fastCNV_10XHD(
  seurat_hd,
  sampleName = "HD_Sample",
  referenceVar = "projected_annots_8um",
  referenceLabel = "NoTumor",
  printPlot = TRUE
)
```

> Warning: Visium HD samples are very RAM demanding. We recommend ~64GB for 16µm bins and ~200GB for 8µm bins.

### 4. Access and Visualize Results

#### Access CNV Results

```r
# CNV fraction per spot
cnv_fraction <- result@meta.data$cnv_fraction
head(cnv_fraction)

# CNV clusters (subclones)
table(result@meta.data$cnv_clusters)

# Per chromosome arm CNV
grep("_CNV$", colnames(result@meta.data), value = TRUE)
cnv_11q <- result@meta.data$`11.q_CNV`
```

#### Spatial Visualization — CNV Fraction

```r
library(patchwork)

SpatialFeaturePlot(result, "cnv_fraction", pt.size.factor = 3) |
  SpatialPlot(result, group.by = "annot", pt.size.factor = 3)
```

Boxplot:

```r
library(ggplot2)

ggplot(FetchData(result, vars = c("annot", "cnv_fraction")),
       aes(annot, cnv_fraction, fill = annot)) +
  geom_boxplot() +
  theme(axis.text.x = element_text(angle = 45, vjust = 1, hjust = 1, color = "black"))
```

#### Spatial Visualization — Per Chromosome Arm

```r
library(scales)

SpatialFeaturePlot(result, features = "11.q_CNV", pt.size.factor = 3) +
  scale_fill_distiller(
    palette = "RdBu", direction = -1, limits = c(-1, 1),
    rescaler = function(x, to = c(0, 1), from = NULL) {
      rescale_mid(x, to = to, mid = 0)
    }
  ) |
SpatialFeaturePlot(result, features = "8.q_CNV", pt.size.factor = 3) +
  scale_fill_distiller(
    palette = "RdBu", direction = -1, limits = c(-1, 1),
    rescaler = function(x, to = c(0, 1), from = NULL) {
      rescale_mid(x, to = to, mid = 0)
    }
  )
```

#### CNV Classification (Gain / Loss / No Alteration)

```r
result <- CNVClassification(result)

SpatialDimPlot(result, group.by = "11.p_CNV_classification") +
  scale_fill_manual(values = c(gain = "red", no_alteration = "grey", loss = "blue"))
```

#### CNV Clusters

```r
SpatialDimPlot(result, group.by = "cnv_clusters", pt.size.factor = 3)
```

Proportion of annotations per CNV cluster:

```r
ggplot(FetchData(result, vars = c("cnv_clusters", "annot")),
       aes(annot, fill = as.factor(cnv_clusters))) +
  geom_bar(position = "fill") +
  theme(axis.text.x = element_text(angle = 45, vjust = 1, hjust = 1, color = "black"))
```

#### CNV Heatmap

```r
plotCNVResults(
  seuratObj = result,
  referenceVar = "annot",
  clustersVar = "cnv_clusters",
  savePath = "./heatmaps"
)
```

For Visium HD:

```r
plotCNVResultsHD(
  result,
  referenceVar = "projected_annots_8um",
  printPlot = TRUE
)
```

### 5. CNV Clustering and Subclone Analysis

#### Hierarchical CNV Clustering

```r
result <- CNVCluster(result)

# Or cluster only tumor spots
result <- CNVCluster(
  result,
  referenceVar = "annot",
  cellTypesToCluster = "Tumor"
)
```

#### Merge Correlated Clusters

```r
result <- mergeCNVClusters(result, mergeThreshold = 0.95)
```

After merging, re-plot:

```r
plotCNVResults(result, referenceVar = "annot", printPlot = TRUE)
```

#### CNV Subclonality Tree

```r
tree_data <- CNVTree(
  result,
  values = "calls",
  cnv_thresh = 0.09,
  healthyClusters = "1"
)
```

### 6. Prepare Counts for Low-Coverage Data

For Visium samples with low read counts, manually aggregate spots before CNV analysis:

```r
seurat_obj <- prepareCountsForCNVAnalysis(
  seuratObj = seurat_obj,
  sampleName = "Sample1",
  referenceVar = "annot",
  aggregFactor = 15000,
  clusterResolution = 0.8
)
```

## Parameters

### Main Parameters (fastCNV)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `seuratObj` | Seurat object or list | Required |
| `sampleName` | Sample name(s) | Required |
| `referenceVar` | Metadata column for reference | NULL |
| `referenceLabel` | Reference label(s) | NULL |
| `aggregFactor` | Max counts per meta-spot | 15000 |
| `aggregateByVar` | Aggregate by cluster + cell type | TRUE |
| `reCluster` | Recluster on SCT data with 10 PCs | FALSE |
| `getCNVPerChromosomeArm` | Per-arm CNV scores | TRUE |
| `downsizePlot` | Faster meta-cell-level plots | FALSE |
| `savePath` | Directory for saved plots | "." |
| `printPlot` | Print plots to console | TRUE |

## AI Agent Test Cases

### Basic Usage

> "Run fastCNV on my Visium data with healthy tissue as reference"

```r
result <- run_fastcnv(
  seuratObj = seurat_obj,
  sampleName = "Visium_Tumor",
  referenceVar = "cell_type",
  referenceLabel = "Healthy"
)
```

### Visium HD

> "Analyze CNV in my Visium HD sample"

```r
result <- run_fastcnv_hd(
  seuratObj = seurat_hd,
  sampleName = "HD_Sample",
  referenceVar = "annotations",
  referenceLabel = "Healthy"
)
```

### Multi-sample

> "Run fastCNV on 4 Visium samples with pooled reference"

```r
results <- run_fastcnv_multi(
  seuratObjs = list(s1, s2, s3, s4),
  sampleNames = c("S1", "S2", "S3", "S4"),
  referenceVar = "annotations",
  referenceLabel = "Healthy"
)
```

### CNV Clustering

> "Identify CNV-based subclones and merge correlated clusters"

```r
result <- cnv_cluster(result, referenceVar = "annotations")
result <- merge_cnv_clusters(result, mergeThreshold = 0.95)
```

### CNV Classification

> "Classify chromosome-arm CNVs as gain or loss"

```r
result <- cnv_classification(result, cnv_thresh = 0.09)
```

### Spatial Visualization

> "Plot CNV fraction on the tissue"

```r
plot_cnv_fraction_spatial(result)
```

> "Plot chromosome 11q CNV spatially"

```r
plot_chr_arm_spatial(result, feature = "11.q_CNV")
```

### Result Extraction

> "Extract CNV fractions and clusters from fastCNV results"

```r
cnv_data <- extract_cnv_results(result)
head(cnv_data)
```

## Best Practices

1. **Use Reference When Possible**: Include healthy tissue for better CNV calling
2. **Memory for HD**: Use 16 µm bins (~64GB RAM); 8 µm needs ~200GB
3. **Multiple Samples**: Pool reference across samples for consistency
4. **Low Coverage**: Use `prepareCountsForCNVAnalysis()` for Visium with <1000 counts/spot
5. **HD Annotations**: Map 8µm annotations to 16µm before running fastCNV_10XHD

## FAQ

### What data types does fastCNV work on?
scRNA-seq, Visium, and Visium HD. **Human data only** (mouse support in development).

### How long does it take?
- ~1 minute for small scRNA-seq (~4,000 cells)
- ~40 minutes for Visium HD at 16 µm (~150,000 spots)

### Can I run without reference?
Yes, but using a healthy reference is highly recommended.

### How much memory for Visium HD?
- 16 µm bin size: ~64 GB RAM
- 8 µm bin size: up to ~200 GB RAM

### Can I run multiple samples?
Yes, provide a named list of Seurat objects. Pooled reference is automatic.

### What if only one sample has healthy tissue?
When providing multiple samples, fastCNV pools reference across all of them.

## Troubleshooting

### Out of Memory
- Use 16 µm bins instead of 8 µm for Visium HD
- Process samples separately
- Use `downsizePlot = TRUE` for faster plotting

### Poor CNV Calling
- Ensure sufficient healthy reference cells/spots
- Check gene expression quality
- Adjust `cnv_thresh` in downstream classification

### Slow Performance
- Manually run `prepareCountsForCNVAnalysis()` with higher `aggregFactor`
- Set `downsizePlot = TRUE`

## References

1. Cabrejas, G. et al. fastCNV: Fast and accurate copy number variation prediction from High-Definition Spatial Transcriptomics and scRNA-Seq Data. bioRxiv 2025.10.22.683855 (2025).
2. fastCNV documentation: https://must-bioinfo.github.io/fastCNV/
3. fastCNV HD vignette: https://must-bioinfo.github.io/fastCNV/articles/fastCNV_HD.html
4. fastCNV ST vignette: https://must-bioinfo.github.io/fastCNV/articles/fastCNV_ST.html
