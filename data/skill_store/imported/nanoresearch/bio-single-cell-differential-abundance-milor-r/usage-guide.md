# miloR Usage Guide

## Overview

miloR tests for differential abundance (DA) of cell populations between conditions using graph-based neighborhoods. Unlike traditional DA methods, miloR works without requiring discrete clustering, making it ideal for identifying changes in continuous cell states or trajectory regions.

## When to Use

- **Compare cell abundance between conditions** without discrete clustering
- **Identify DA regions in trajectories** or continuous cell states
- **Test for subtle compositional changes** that clustering might miss
- **Analyze datasets with continuous cell transitions**

## Prerequisites

### Required Packages

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("miloR")
```

### Optional Packages

```r
# For visualization
BiocManager::install("ComplexHeatmap")
install.packages("ggplot2")

# For data conversion
install.packages("Seurat")
```

### Data Format

Input must be a `SingleCellExperiment` with:
- Expression data (`counts` or `logcounts` assay)
- Sample metadata in `colData` (sample IDs, conditions)
- Reduced dimensions (recommended: `PCA`)

## Step-by-Step Guide

### Step 1: Setup and Load Data

```r
library(miloR)
library(SingleCellExperiment)

# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Load SingleCellExperiment
sce <- readRDS("your_data.rds")

# Or convert from Seurat
seurat_obj <- readRDS("seurat_data.rds")
sce <- seurat_to_sce(seurat_obj, assay = "RNA", dimreducs = c("pca", "umap"))

# Check colData
colData(sce)
```

### Step 2: Validate and Prepare Data

```r
# Validate input
validate_milor_input(sce, sample_col = "sample_id", condition_col = "condition")

# Create Milo object
milo_obj <- create_milo_object(sce)

# Check the object
milo_obj
```

### Step 3: Build kNN Graph

```r
# Build graph with default parameters
milo_obj <- build_milo_graph(
  milo_obj,
  k = 30,              # Number of nearest neighbors
  d = 30,              # PCA dimensions to use
  reduced.dim = "PCA"
)

# For large datasets (>100K cells), increase k
# milo_obj <- build_milo_graph(milo_obj, k = 50, d = 30)

# Check graph
graph(milo_obj)
```

**k Parameter Guidelines:**
- `k = 10-20`: Small datasets (<5K cells)
- `k = 30`: Standard datasets (5K-100K cells)
- `k = 50-100`: Large datasets (>100K cells)

### Step 4: Define Neighborhoods

```r
# Make neighborhoods with refined sampling
milo_obj <- make_milo_neighborhoods(
  milo_obj,
  prop = 0.1,          # Proportion of cells to sample
  k = 30,              # Same k as graph building
  d = 30,
  refined = TRUE,      # Recommended for better coverage
  seed = 42            # For reproducibility
)

# Check number of neighborhoods
ncol(nhoods(milo_obj))
```

**prop Parameter Guidelines:**
- `prop = 0.2`: Small datasets (<10K cells)
- `prop = 0.1`: Standard datasets (10K-100K cells)
- `prop = 0.05`: Large datasets (>100K cells)

### Step 5: Calculate Distances (Optional but Recommended)

```r
# Calculate neighborhood distances for spatial FDR
milo_obj <- calc_milo_distances(
  milo_obj,
  d = 30,
  reduced.dim = "PCA"
)

# This enables fdr.weighting = "k-distance" or "neighbour-distance"
```

### Step 6: Count Cells per Neighborhood

```r
# Count cells from each sample
milo_obj <- count_milo_cells(
  milo_obj,
  sample_col = "sample_id"
)

# Check counts matrix
head(nhoodCounts(milo_obj))

# Check dimensions
# rows = neighborhoods, columns = samples
dim(nhoodCounts(milo_obj))
```

### Step 7: Create Design Matrix

```r
# Extract sample metadata
sample_meta <- unique(data.frame(
  sample_id = colData(milo_obj)$sample_id,
  condition = colData(milo_obj)$condition
))
rownames(sample_meta) <- sample_meta$sample_id

# For batch correction, include batch column
sample_meta <- unique(data.frame(
  sample_id = colData(milo_obj)$sample_id,
  condition = colData(milo_obj)$condition,
  batch = colData(milo_obj)$batch
))
rownames(sample_meta) <- sample_meta$sample_id

# View design matrix
sample_meta
```

### Step 8: Test Differential Abundance

**Basic two-group comparison:**
```r
da_results <- test_milo_da(
  milo_obj,
  design = ~ condition,
  design.df = sample_meta,
  fdr.weighting = "k-distance",
  norm.method = "TMM"
)

# View results
head(da_results)
```

**With batch correction:**
```r
da_results <- test_milo_da(
  milo_obj,
  design = ~ batch + condition,
  design.df = sample_meta,
  fdr.weighting = "k-distance",
  norm.method = "TMM"
)
```

**Paired design (same patient, multiple timepoints):**
```r
da_results <- test_milo_da(
  milo_obj,
  design = ~ patient + timepoint,
  design.df = sample_meta,
  fdr.weighting = "k-distance"
)
```

### Step 9: View and Interpret Results

```r
# Summarize results
summarize_milo_results(da_results, alpha = 0.1)

# Get top DA neighborhoods
top_da <- get_top_da_nhoods(da_results, n_top = 10)
print(top_da[, c("logFC", "PValue", "SpatialFDR")])

# Get significant neighborhoods
sig_nhoods <- get_significant_nhoods(da_results, alpha = 0.1, min.logFC = 1)
cat(sprintf("Found %d significant neighborhoods\n", length(sig_nhoods)))

# Distribution of logFC
hist(da_results$logFC, breaks = 50, main = "Distribution of logFC")
```

### Step 10: Annotate Neighborhoods with Cell Types

```r
# Requires cell_type column in colData
da_results <- annotate_milo_neighborhoods(
  milo_obj,
  da.res = da_results,
  colData_col = "cell_type",
  nlargest = 1
)

# View cell type composition of DA neighborhoods
sig_results <- da_results[da_results$SpatialFDR < 0.1, ]
table(sig_results$cell_type)
```

### Step 11: Group DA Neighborhoods

```r
# Group overlapping DA neighborhoods
da_results <- group_milo_neighborhoods(
  milo_obj,
  da.res = da_results,
  da.fdr = 0.1,
  overlap = 5,
  merge.discord = FALSE
)

# View group sizes
table(da_results$NhoodGroup)
```

### Step 12: Find Marker Genes

```r
# Find markers for DA neighborhood groups
marker_results <- find_milo_markers(
  milo_obj,
  da.res = da_results,
  da.fdr = 0.1,
  assay = "logcounts",
  gene.offset = TRUE
)

# View top markers
head(marker_results)
```

### Step 13: Visualize Results

```r
library(ggplot2)

# Beeswarm plot by cell type
p1 <- plot_milo_beeswarm(da_results, group.by = "cell_type", alpha = 0.1)
ggsave("da_beeswarm.pdf", p1, width = 8, height = 6)

# Volcano plot
p2 <- plot_milo_volcano(da_results, alpha = 0.1, logfc.threshold = 1)
ggsave("da_volcano.pdf", p2, width = 6, height = 5)

# DA on UMAP
p3 <- plot_milo_umap_da(milo_obj, da_results, dimred = "UMAP", alpha = 0.1)
ggsave("da_umap.pdf", p3, width = 7, height = 6)

# Neighborhood graph with DA
p4 <- plot_milo_graph_da(milo_obj, da_results, alpha = 0.1)
ggsave("da_graph.pdf", p4, width = 7, height = 6)

# Neighborhood group plot
p5 <- plot_milo_groups(milo_obj, da_results, alpha = 0.1)
ggsave("da_groups.pdf", p5, width = 8, height = 6)

# Multi-panel summary
plots <- plot_milo_summary(milo_obj, da_results, dimred = "UMAP")
save_milo_plots(plots, output_dir = "./milo_plots")
```

### Step 14: Complete Pipeline (Shortcut)

```r
# Run everything in one call
results <- run_milo_pipeline(
  x = sce,
  sample_col = "sample_id",
  condition_col = "condition",
  design = ~ condition,
  design.df = sample_meta,
  k = 30,
  d = 30,
  prop = 0.1,
  refined = TRUE,
  fdr.weighting = "k-distance",
  norm.method = "TMM",
  calc.distances = TRUE,
  seed = 42,
  verbose = TRUE
)

# Extract results
milo_obj <- results$milo
da_results <- results$da_results
```

## Advanced Usage

### Parameter Sensitivity Analysis

```r
# Test different k values
k_values <- c(20, 30, 50)
results_list <- list()

for (k in k_values) {
  milo_k <- build_milo_graph(milo_obj, k = k, d = 30)
  milo_k <- make_milo_neighborhoods(milo_k, prop = 0.1, k = k, d = 30)
  milo_k <- count_milo_cells(milo_k, sample_col = "sample_id")
  da_k <- test_milo_da(milo_k, design = ~ condition, design.df = sample_meta)

  results_list[[paste0("k", k)]] <- list(
    n_nhoods = ncol(nhoods(milo_k)),
    n_sig = sum(da_k$SpatialFDR < 0.1, na.rm = TRUE)
  )
}

# Compare results
do.call(rbind, results_list)
```

### Comparing Multiple Conditions

```r
# Test all pairwise comparisons with custom contrasts
da_all <- test_milo_da(
  milo_obj,
  design = ~ 0 + condition,
  design.df = sample_meta,
  model.contrasts = c(
    "conditionA - conditionB",
    "conditionA - conditionC",
    "conditionB - conditionC"
  )
)
```

### Filtering Low-Abundance Neighborhoods

```r
# Filter before testing
milo_filtered <- filter_milo_by_abundance(
  milo_obj,
  min_cells = 20,
  min_samples = 3
)

# Re-run DA on filtered data
da_filtered <- test_milo_da(
  milo_filtered,
  design = ~ condition,
  design.df = sample_meta
)
```

## Common Workflows

### Workflow 1: Basic Two-Group Comparison

```r
# 1. Prepare data
milo_obj <- create_milo_object(sce)

# 2. Build graph and neighborhoods
milo_obj <- build_milo_graph(milo_obj, k = 30, d = 30)
milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.1, k = 30, d = 30)

# 3. Count cells
milo_obj <- count_milo_cells(milo_obj, sample_col = "sample_id")

# 4. Test DA
design_df <- unique(data.frame(
  sample_id = sce$sample_id,
  condition = sce$condition
))
rownames(design_df) <- design_df$sample_id

da_results <- test_milo_da(milo_obj, design = ~ condition, design.df = design_df)

# 5. Visualize
plot_milo_beeswarm(da_results)
plot_milo_umap_da(milo_obj, da_results)
```

### Workflow 2: Batch Correction

```r
# Include batch in design formula
da_results <- test_milo_da(
  milo_obj,
  design = ~ batch + condition,
  design.df = sample_meta  # must include batch column
)

# Annotate with cell types
da_results <- annotate_milo_neighborhoods(milo_obj, da_results, colData_col = "cell_type")
plot_milo_beeswarm(da_results, group.by = "cell_type")
```

### Workflow 3: Trajectory Analysis

```r
# miloR works well on trajectory data without clustering
# Just ensure you have the trajectory embedding in reducedDims

milo_obj <- build_milo_graph(milo_obj, k = 30, d = 30, reduced.dim = "PCA")
milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.1, k = 30, d = 30)

# Visualize DA on trajectory embedding (e.g., UMAP, diffusion map)
plot_milo_umap_da(milo_obj, da_results, dimred = "umap")
```

## Troubleshooting

### Error: "No reduced dimensions found"

```r
# Compute PCA if not present
library(scater)
sce <- runPCA(sce, ncomponents = 30)
```

### Error: "No neighbourhoods to test"

```r
# Check that countCells was run
colnames(colData(milo_obj))  # Check sample column name
head(nhoodCounts(milo_obj))  # Check counts matrix
```

### Too Few Significant Neighborhoods

```r
# Try increasing prop for more neighborhoods
milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.2, k = 30, d = 30)

# Or try different FDR weighting
da_results <- test_milo_da(milo_obj, design = ~ condition,
                          design.df = sample_meta,
                          fdr.weighting = "none")  # Less stringent
```

### Batch Effects Dominating Results

```r
# Include batch in design formula
da_results <- test_milo_da(milo_obj, design = ~ batch + condition,
                          design.df = sample_meta)
```

## AI Agent Test Cases

### Basic DA Analysis
> "Run miloR differential abundance analysis on my single-cell data"
```r
results <- run_milo_pipeline(sce, sample_col = "sample", condition_col = "group",
                             design = ~ group)
```

### Batch Correction
> "Run miloR with batch correction"
```r
da_results <- test_milo_da(milo_obj, design = ~ batch + condition,
                          design.df = sample_meta)
```

### Cell Type Annotation
> "Annotate miloR neighborhoods with cell types"
```r
da_results <- annotate_milo_neighborhoods(milo_obj, da_results,
                                         colData_col = "cell_type")
```

### Parameter Adjustment
> "Increase k to 50 for miloR analysis"
```r
milo_obj <- build_milo_graph(milo_obj, k = 50, d = 30)
milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.1, k = 50, d = 30)
```

## References

1. Dann et al. (2022). Milo detects differentially abundant cell populations in single-cell data. *Nature Biotechnology*, 40, 245-253.
2. miloR Bioconductor: https://bioconductor.org/packages/miloR
3. miloR GitHub: https://github.com/MarioniLab/miloR
