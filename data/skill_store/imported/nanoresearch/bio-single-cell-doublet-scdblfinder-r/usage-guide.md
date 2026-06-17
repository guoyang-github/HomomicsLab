# scDblFinder Usage Guide

## Overview

scDblFinder is a fast and accurate doublet detection method using gradient-boosted classification of artificial doublets. It generates artificial doublets from real cells, evaluates their prevalence in the neighborhood of each cell, and uses this along with additional features to classify doublets.

## When to Use

- **Fast and accurate detection needed**: Benchmarked as top-performing method
- **Multi-sample data**: Native support for batch handling
- **Bioconductor workflow**: Integrates with SingleCellExperiment ecosystem
- **10X Genomics data**: Optimized for standard and HT chips

## When Not to Use

- **Homotypic doublets only**: Cannot distinguish same-type cell doublets without hashing/genotypes
- **Very small datasets**: Needs minimum 50 cells
- **Non-R workflow**: Python-based alternatives available

## Prerequisites

### Required Packages

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("scDblFinder")
```

Additional dependencies:
```r
install.packages(c("ggplot2", "SingleCellExperiment", "BiocParallel"))
```

### Data Format

Input requirements:
- **SingleCellExperiment** or count matrix (genes x cells)
- **Raw counts**: Not normalized
- **Minimum 50 cells**: Recommend 200+ for accuracy

## Step-by-Step Guide

### Step 1: Prepare Data

```r
library(SingleCellExperiment)
library(SummarizedExperiment)

# From count matrix
counts <- readMM("counts.mtx")
sce <- SingleCellExperiment(assays = list(counts = counts))

# From 10X output
sce <- DropletUtils::read10xCounts("filtered_gene_bc_matrices/")

# Add sample info (for multi-sample)
sce$sample_id <- rep(c("Sample1", "Sample2"), each = ncol(sce)/2)
```

### Step 2: Validate Input

```r
source("scripts/r/core_analysis.R")

validation <- validate_scdblfinder_input(sce)
if (!validation$valid) {
  stop(validation$errors)
}

cat(sprintf("Cells: %d, Genes: %d\n",
            validation$stats$n_cells, validation$stats$n_genes))
```

### Step 3: Get Parameter Recommendations

```r
source("scripts/r/utils.R")

params <- recommend_scdblfinder_params(
  n_cells = ncol(sce),
  n_samples = length(unique(sce$sample_id)),
  is_10x = TRUE
)

cat(params$message)
```

### Step 4: Run scDblFinder

#### Basic Run

```r
# Simple run
sce <- run_scdblfinder(sce)
```

#### With Auto-Clustering

```r
# Recommended for clustered data
sce <- run_scdblfinder(
  sce,
  clusters = TRUE,
  nfeatures = 1500,
  dims = 20
)
```

#### Multi-Sample Processing

```r
# Process samples separately (recommended)
sce <- run_scdblfinder(
  sce,
  samples = sce$sample_id,
  multiSampleMode = "split",
  BPPARAM = BiocParallel::MulticoreParam(4)
)
```

#### Full Control

```r
sce <- run_scdblfinder(
  sce,
  clusters = TRUE,              # Auto-clustering
  samples = sce$sample_id,      # Multi-sample
  nfeatures = 1500,             # Number of features
  dims = 20,                    # PCA dimensions
  dbr.per1k = 0.008,            # 10X standard rate
  iter = 1,                     # Scoring iterations
  verbose = TRUE,
  BPPARAM = BiocParallel::MulticoreParam(4)
)
```

### Step 5: Extract and Explore Results

```r
# Get all scores
scores <- extract_doublet_scores(sce)
head(scores)

# Summary statistics
summary <- summarize_scdblfinder_results(sce)
print(summary$class_table)
cat(sprintf("Doublet rate: %.1f%%\n", 100 * summary$doublet_rate))

# Get cell lists
doublets <- get_doublet_cells(sce)
singlets <- get_singlet_cells(sce)
```

### Step 6: Visualize

```r
source("scripts/r/visualization.R")

# Score distribution
plot_doublet_score_distribution(sce)

# By classification
plot_doublet_scores_by_class(sce, plot_type = "violin")

# On dimensionality reduction
plot_doublets_reduced(sce, dimred = "UMAP")

# Doublet map (if cluster-based)
plot_doublet_map(sce)

# By sample (if multi-sample)
plot_doublet_rate_by_sample(sce)

# Comprehensive summary
plot_scdblfinder_summary(sce, output_dir = "./scdblfinder_plots")
```

### Step 7: Filter Doublets

```r
# Remove doublets
sce_filtered <- filter_scdblfinder(sce, remove_doublets = TRUE)

# Or keep only singlets
sce_singlets <- filter_doublets(sce, keep_singlets = TRUE)
```

### Step 8: Export Results

```r
export_scdblfinder_results(
  sce,
  output_dir = "./scdblfinder_output",
  prefix = "sample1"
)

# Generate report
report <- create_scdblfinder_report(sce)
cat(report)
```

## Advanced Usage

### Seurat Integration

```r
# Run with Seurat
seurat_obj <- run_scdblfinder_seurat(
  seurat_obj,
  samples = "sample_id",
  clusters = "seurat_clusters"
)

# Visualize
DimPlot(seurat_obj, group.by = "scDblFinder_class")
FeaturePlot(seurat_obj, features = "scDblFinder_score")

# Filter
seurat_filtered <- subset(
  seurat_obj,
  subset = scDblFinder_class == "singlet"
)
```

### With Known Doublets

```r
# If some doublets are known (e.g., from hashing)
known_doublets <- colnames(sce)[sce$hash_doublet == TRUE]

sce <- run_scdblfinder(
  sce,
  knownDoublets = known_doublets,
  knownUse = "discard"  # or "positive"
)
```

### Compare Multiple Samples

```r
# Run on multiple samples separately
results_list <- list(
  Sample1 = sce1,
  Sample2 = sce2,
  Sample3 = sce3
)

# Compare doublet rates
comparison <- compare_scdblfinder_results(results_list)
print(comparison)
```

### Check Cluster Enrichment

```r
# Check if doublets are enriched in specific clusters
enrichment <- check_doublet_enrichment(
  sce,
  cluster_col = "seurat_clusters"
)
print(enrichment)
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `clusters` | FALSE | TRUE/FALSE/vector for cluster-based generation |
| `samples` | NULL | Sample IDs for multi-sample processing |
| `nfeatures` | 1500 | Number of top features to use |
| `dims` | 20 | Number of PCA dimensions |
| `k` | NULL | k for kNN graph |
| `dbr` | NULL | Expected doublet rate (NULL = auto) |
| `dbr.sd` | NULL | Uncertainty in doublet rate |
| `dbr.per1k` | 0.008 | Doublet rate per 1000 cells |
| `iter` | 1 | Scoring iterations |
| `multiSampleMode` | "split" | "split", "singleModel", "asOne" |

## Output

| Output | Location | Description |
|--------|----------|-------------|
| Score | `$scDblFinder.score` | Doublet probability (0-1) |
| Class | `$scDblFinder.class` | "singlet" or "doublet" |
| Origin | `$scDblFinder.mostLikelyOrigin` | Likely origin clusters |
| Sample | `$scDblFinder.sample` | Sample ID |

### Classification Interpretation

| Class | Interpretation |
|-------|----------------|
| `singlet` | Single cell (keep) |
| `doublet` | Multiple cells (remove) |

## Best Practices

1. **Multi-sample**: Always use `samples` parameter for independent captures
2. **Clusters**: Use `clusters=TRUE` for better performance on clustered data
3. **Platform**: Set correct `dbr.per1k` (0.008 standard, 0.004 HT)
4. **Parallel**: Use `BPPARAM` for multi-sample processing
5. **QC**: Visualize doublets on UMAP before filtering
6. **Iterative**: Run `iter=2` for difficult datasets

## Comparison with Other Tools

| Feature | scDblFinder | DoubletFinder | Scrublet |
|---------|-------------|---------------|----------|
| Speed | 🚀 Fast | 🐢 Slow | 🚀 Fast |
| Accuracy | ⭐⭐⭐ #1 | ⭐⭐⭐ Excellent | ⭐⭐ Good |
| Multi-sample | ✅ Native | ⚠️ Manual | ❌ No |
| Bioconductor | ✅ Yes | ❌ No | ❌ No |

Use scDblFinder for best accuracy and native multi-sample support.

## AI Agent Test Cases

### Basic Usage
> "Run scDblFinder on my Seurat object"

```r
seurat_obj <- run_scdblfinder_seurat(seurat_obj)
```

### Multi-Sample
> "Run scDblFinder with sample information to handle batch effects"

```r
sce <- run_scdblfinder(sce, samples = sce$sample_id)
```

### Cluster-Aware
> "Use scDblFinder with cluster information for better accuracy"

```r
sce <- run_scdblfinder(sce, clusters = TRUE)
```

### Seurat Workflow
> "Detect doublets and filter from my Seurat object"

```r
seurat_obj <- run_scdblfinder_seurat(seurat_obj)
seurat_filtered <- subset(seurat_obj, subset = scDblFinder_class == "singlet")
```

### QC Check
> "Visualize scDblFinder results before filtering"

```r
plot_doublets_reduced(sce, dimred = "UMAP")
plot_scdblfinder_summary(sce)
```

## Troubleshooting

### All cells predicted as singlets
```r
# Check parameters
table(sce$scDblFinder.class)

# May need to adjust dbr
sce <- run_scdblfinder(sce, dbr.sd = 1)  # Disable expected rate constraint
```

### All cells predicted as doublets
```r
# Check if samples were processed separately
# Use samples parameter
sce <- run_scdblfinder(sce, samples = sce$sample_id)

# Increase uncertainty
sce <- run_scdblfinder(sce, dbr.sd = 0.1)
```

### Poor separation
```r
# Increase features
sce <- run_scdblfinder(sce, nfeatures = 3000)

# Increase iterations
sce <- run_scdblfinder(sce, iter = 2)

# Use cluster-based generation
sce <- run_scdblfinder(sce, clusters = TRUE)
```

### Slow performance
```r
# Use parallel processing
sce <- run_scdblfinder(
  sce,
  BPPARAM = BiocParallel::MulticoreParam(4)
)
```

## References

1. Germain et al. (2021). PipeComp, a general framework for the evaluation of computational pipelines. *Genome Biology*.
2. Xi & Li (2021). Benchmarking Computational Doublet-Detection Methods. *Cell Systems*.
3. scDblFinder documentation: https://github.com/plger/scDblFinder
