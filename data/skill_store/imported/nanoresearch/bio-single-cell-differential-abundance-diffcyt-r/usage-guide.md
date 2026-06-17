# diffcyt Usage Guide

## Overview

diffcyt is an R package for differential abundance (DA) and differential state (DS) analysis in high-dimensional cytometry data (flow cytometry, mass cytometry/CyTOF, oligonucleotide-tagged cytometry). It uses high-resolution clustering (FlowSOM) and empirical Bayes moderated tests adapted from transcriptomics.

## When to Use

- **Differential Abundance (DA)**: Compare cell cluster proportions across conditions
- **Differential State (DS)**: Compare marker expression within clusters across conditions
- **High-dimensional cytometry**: Flow cytometry, CyTOF, CITE-seq
- **Cluster-based analysis**: Cell populations defined by clustering

## Prerequisites

### Required Packages

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("diffcyt")
```

### Optional Packages

```r
# For visualization
BiocManager::install("CATALYST")
BiocManager::install("ComplexHeatmap")
install.packages("ggplot2")
install.packages("reshape2")
```

### Data Format

Input can be:
- `flowSet` object from flowCore
- List of matrices, data.frames, or `flowFrame` objects
- `SingleCellExperiment` from CATALYST

Required metadata:
- `experiment_info`: Sample IDs and group information
- `marker_info`: Marker names and classes ("type", "state", "none")

## Step-by-Step Guide

### Step 1: Setup and Load Data

```r
library(diffcyt)
library(flowCore)

# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Load FCS files
fs <- read.flowSet(path = "fcs_files/", pattern = "*.fcs")

# Or create from matrices
d_input <- list(
  sample1 = matrix(rnorm(20000), nrow = 1000, ncol = 20),
  sample2 = matrix(rnorm(20000), nrow = 1000, ncol = 20),
  sample3 = matrix(rnorm(20000), nrow = 1000, ncol = 20),
  sample4 = matrix(rnorm(20000), nrow = 1000, ncol = 20)
)
```

### Step 2: Create Metadata

```r
# Experiment information
experiment_info <- data.frame(
  sample_id = factor(paste0("sample", 1:4)),
  group_id = factor(c("control", "control", "treated", "treated")),
  stringsAsFactors = FALSE
)

# Marker information
# Crucial: Correctly classify markers!
marker_info <- data.frame(
  channel_name = paste0("channel", sprintf("%03d", 1:20)),
  marker_name = paste0("marker", sprintf("%02d", 1:20)),
  marker_class = factor(
    c(rep("type", 10), rep("state", 10)),  # First 10 for clustering, last 10 for DS
    levels = c("type", "state", "none")
  ),
  stringsAsFactors = FALSE
)

# View marker classification
table(marker_info$marker_class)
```

**Marker Class Guidelines:**
- `type`: Lineage markers for clustering (CD3, CD4, CD8, CD19, etc.)
- `state`: Functional markers for DS testing (pSTAT, cytokines, activation markers)
- `none`: Ignore (time, barcodes, unwanted channels)

### Step 3: Validate and Prepare Data

```r
# Validate input
validate_diffcyt_input(d_input, experiment_info, marker_info)

# Prepare data
d_se <- prepare_diffcyt_data(
  d_input = d_input,
  experiment_info = experiment_info,
  marker_info = marker_info,
  subsampling = FALSE,  # Set TRUE if sample sizes differ greatly
  n_sub = NULL,
  seed_sub = 123
)

# Check prepared data
table(SummarizedExperiment::rowData(d_se)$sample_id)
```

### Step 4: Transform Data

```r
# Apply arcsinh transformation
d_se <- diffcyt::transformData(d_se, cofactor = 5)
```

**Cofactor Selection:**
- `cofactor = 5` for mass cytometry (CyTOF) data
- `cofactor = 150` for fluorescence flow cytometry data

### Step 5: Generate Clusters

```r
# Generate clusters with FlowSOM
d_se <- generate_diffcyt_clusters(
  d_se,
  cols_clustering = NULL,  # Use type markers
  xdim = 10,               # Grid width
  ydim = 10,               # Grid height
  meta_clustering = FALSE, # Set TRUE for meta-clusters
  meta_k = 40,
  seed_clustering = 123
)

# Check cluster distribution
cluster_ids <- SummarizedExperiment::rowData(d_se)$cluster_id
table(cluster_ids)
```

**Clustering Guidelines:**
- `xdim * ydim` = total clusters (default: 100)
- More clusters = higher resolution
- Use `meta_clustering` for broader cell populations

### Step 6: Calculate Features

```r
# Calculate cluster counts (for DA)
d_counts <- diffcyt::calcCounts(d_se)

# Calculate cluster medians (for DS)
d_medians <- diffcyt::calcMedians(d_se)

# View dimensions
print(d_counts)
print(d_medians)
```

### Step 7: Create Design and Contrast

```r
# Create design matrix
design <- diffcyt::createDesignMatrix(
  experiment_info,
  cols_design = "group_id"
)
print(design)

# Create contrast (group2 vs group1)
contrast <- diffcyt::createContrast(c(0, 1))

# Or for more complex designs, use formula
formula <- diffcyt::createFormula(
  experiment_info,
  fixed_effects = "group_id",
  random_effects = NULL
)
```

### Step 8: Test Differential Abundance (DA)

**Option A: edgeR (default for two-group comparison)**
```r
da_res <- test_da_edger(
  d_counts = d_counts,
  design = design,
  contrast = contrast,
  min_cells = 3,
  min_samples = NULL,  # Defaults to n_samples/2
  normalize = FALSE    # Set TRUE for composition effects
)
```

**Option B: voom (with random effects for paired designs)**
```r
da_res <- diffcyt::testDA_voom(
  d_counts = d_counts,
  design = design,
  contrast = contrast,
  block_id = experiment_info$patient_id,  # For paired design
  min_cells = 3,
  plot = TRUE,          # Save diagnostic plots
  path = "./plots"
)
```

**Option C: GLMM (mixed models)**
```r
da_res <- diffcyt::testDA_GLMM(
  d_counts = d_counts,
  formula = formula,
  contrast = contrast,
  min_cells = 3
)
```

### Step 9: Test Differential State (DS)

```r
ds_res <- diffcyt::testDS_limma(
  d_medians = d_medians,
  d_counts = d_counts,
  design = design,
  contrast = contrast,
  trend = TRUE,         # Fit mean-variance trend
  weights = TRUE,       # Use precision weights
  markers_to_test = NULL,  # All state markers
  min_cells = 3,
  plot = TRUE,
  path = "./plots"
)
```

### Step 10: View and Export Results

```r
# View top DA clusters
top_da <- get_top_results(da_res, n_top = 10)
print(top_da)

# View top DS cluster-marker combinations
top_ds <- get_top_results(ds_res, n_top = 10)
print(top_ds)

# Get significant clusters
sig_da <- get_significant_clusters(da_res, p_threshold = 0.05)
sig_ds <- get_significant_clusters(ds_res, p_threshold = 0.05)

cat(sprintf("DA: %d significant clusters\n", length(sig_da)))
cat(sprintf("DS: %d significant cluster-marker combinations\n", length(sig_ds)))

# Export results
export_results(da_res, "da_results.csv", significant_only = TRUE)
export_results(ds_res, "ds_results.csv", significant_only = TRUE)

# Print summary
print_results_summary(da_res)
print_results_summary(ds_res)
```

### Step 11: Visualize Results

```r
library(ggplot2)

# DA heatmap
p1 <- diffcyt::plotHeatmap(d_se, da_res, analysis_type = "DA", threshold = 0.1)
ggsave("da_heatmap.pdf", p1, width = 10, height = 8)

# DS heatmap
p2 <- diffcyt::plotHeatmap(d_se, ds_res, analysis_type = "DS", threshold = 0.1)
ggsave("ds_heatmap.pdf", p2, width = 10, height = 8)

# Volcano plot for DA
p3 <- plot_volcano(da_res, p_threshold = 0.05, logfc_threshold = 1)
ggsave("da_volcano.pdf", p3, width = 8, height = 6)

# MA plot for DA
p4 <- plot_ma(da_res)
ggsave("da_ma_plot.pdf", p4, width = 8, height = 6)

# Cluster abundance
p5 <- plot_cluster_abundance(d_counts)
ggsave("cluster_abundance.pdf", p5, width = 10, height = 6)

# Save all plots at once
save_diffcyt_plots(d_se, da_res, analysis_type = "DA", 
                   output_dir = "./diffcyt_plots")
```

### Step 12: Complete Pipeline (Shortcut)

```r
# Run everything in one call
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
  xdim = 10,
  ydim = 10,
  min_cells = 3,
  verbose = TRUE
)

# Extract results
da_res <- results$res
d_se <- results$d_se
d_counts <- results$d_counts
```

## Advanced Usage

### Using CATALYST Input

```r
library(CATALYST)

# Prepare data with CATALYST
sce <- prepData(fs)
sce <- cluster(sce)

# Pass directly to diffcyt
results <- run_diffcyt_pipeline(
  d_input = sce,  # CATALYST SingleCellExperiment
  analysis_type = "DA",
  contrast = contrast
)
```

### Filtering Low-Abundance Clusters

```r
# Filter before testing
d_counts_filtered <- filter_clusters_by_abundance(
  d_counts,
  min_cells = 10,
  min_samples = 4
)

# Re-run DA on filtered data
da_res_filtered <- test_da_edger(
  d_counts_filtered,
  design,
  contrast
)
```

### Normalization for Composition Effects

```r
# DA with TMM normalization
da_res <- test_da_edger(
  d_counts,
  design,
  contrast,
  normalize = TRUE,
  norm_factors = "TMM"
)

# Or calculate custom normalization factors
norm_counts <- normalize_counts(d_counts, method = "TMM")
```

### Comparing Multiple DA Methods

```r
# Test with multiple methods
da_edgeR <- test_da_edger(d_counts, design, contrast)
da_voom <- diffcyt::testDA_voom(d_counts, design, contrast)

# Compare overlap
sig_edgeR <- get_significant_clusters(da_edgeR)
sig_voom <- get_significant_clusters(da_voom)

cat(sprintf("edgeR: %d, voom: %d, overlap: %d\n",
            length(sig_edgeR), length(sig_voom),
            length(intersect(sig_edgeR, sig_voom))))
```

## Common Workflows

### Workflow 1: Basic Two-Group Comparison

```r
# 1. Prepare data
d_se <- prepare_diffcyt_data(d_input, experiment_info, marker_info)

# 2. Transform and cluster
d_se <- diffcyt::transformData(d_se, cofactor = 5)
d_se <- generate_diffcyt_clusters(d_se, xdim = 10, ydim = 10)

# 3. Calculate features
d_counts <- diffcyt::calcCounts(d_se)

# 4. Test DA
design <- diffcyt::createDesignMatrix(experiment_info, "group_id")
contrast <- diffcyt::createContrast(c(0, 1))
da_res <- test_da_edger(d_counts, design, contrast)

# 5. Visualize
diffcyt::plotHeatmap(d_se, da_res, analysis_type = "DA")
```

### Workflow 2: Paired Design (Same Patient, Multiple Timepoints)

```r
# Include patient ID as random effect
da_res <- diffcyt::testDA_voom(
  d_counts,
  design,
  contrast,
  block_id = experiment_info$patient_id
)

# Or use GLMM with formula
formula <- diffcyt::createFormula(
  experiment_info,
  fixed_effects = "timepoint",
  random_effects = "patient_id"
)
da_res <- diffcyt::testDA_GLMM(d_counts, formula, contrast)
```

### Workflow 3: Both DA and DS Analysis

```r
# Calculate both counts and medians
d_counts <- diffcyt::calcCounts(d_se)
d_medians <- diffcyt::calcMedians(d_se)

# DA analysis
da_res <- test_da_edger(d_counts, design, contrast)

# DS analysis
ds_res <- diffcyt::testDS_limma(d_medians = d_medians, d_counts = d_counts, design = design, contrast = contrast)

# Merge results for integrated view
merged <- merge_da_ds_results(da_res, ds_res)
```

## Troubleshooting

### Error: "No clusters pass filtering"

```r
# Check cluster sizes
counts <- assay(d_counts)
rowSums(counts > 0)

# Lower thresholds
da_res <- test_da_edger(d_counts, design, contrast, 
                        min_cells = 1, min_samples = 2)
```

### Error: "Contrasts not estimable"

```r
# Check design matrix
design
qr(design)$rank  # Should equal ncol(design)

# Simplify contrast
contrast <- diffcyt::createContrast(c(0, 1))
```

### Large Sample Size Differences

```r
# Use subsampling
d_se <- prepare_diffcyt_data(
  d_input, experiment_info, marker_info,
  subsampling = TRUE,
  n_sub = 5000,  # Cells per sample
  seed_sub = 123
)
```

## AI Agent Test Cases

### Basic DA Analysis
> "Run diffcyt differential abundance analysis on my CyTOF data"
```r
d_se <- prepare_diffcyt_data(d_input, experiment_info, marker_info)
d_se <- diffcyt::transformData(d_se, cofactor = 5)
d_se <- generate_diffcyt_clusters(d_se, xdim = 10, ydim = 10)
d_counts <- diffcyt::calcCounts(d_se)
da_res <- test_da_edger(d_counts, design, contrast)
```

### DS Analysis
> "Test for differential marker expression within clusters"
```r
ds_res <- diffcyt::testDS_limma(d_medians = d_medians, d_counts = d_counts, design = design, contrast = contrast, 
                        trend = TRUE, weights = TRUE)
```

### Complete Pipeline
> "Run complete diffcyt pipeline with both DA and DS"
```r
da_results <- run_diffcyt_pipeline(d_input, experiment_info, marker_info,
                                   analysis_type = "DA")
ds_results <- run_diffcyt_pipeline(d_input, experiment_info, marker_info,
                                   analysis_type = "DS")
```

## References

1. Weber et al. (2019). diffcyt: Differential discovery in high-dimensional cytometry via high-resolution clustering. *Communications Biology*, 2, 183.
2. diffcyt Bioconductor: https://bioconductor.org/packages/diffcyt
3. CATALYST: Chevrier et al. (2018), *Nature Methods*, 15, 275-278.
4. FlowSOM: Van Gassen et al. (2015), *Cytometry A*, 87, 251-262.
