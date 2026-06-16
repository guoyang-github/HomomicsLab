---
name: bio-single-cell-differential-abundance-milor-r
description: miloR is an R package for differential abundance analysis on single-cell data using graph-based neighborhoods. Tests for changes in cell population abundance between conditions without requiring discrete clustering.
tool_type: r
primary_tool: miloR
supported_tools: [SingleCellExperiment, edgeR, limma, ggplot2]
languages: [r]
keywords: ["differential-abundance", "DA", "miloR", "neighborhood", "single-cell", "kNN-graph", "spatial-FDR"]
---

## Version Compatibility

- **R**: >= 4.0
- **miloR**: >= 1.6
- **SingleCellExperiment**: >= 1.16
- **edgeR**: >= 3.34
- **Seurat**: >= 4.3.0 (optional, for input conversion; v4 and v5 compatible via automatic slot/layer detection)

## Installation

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("miloR")
```

## Import Wrapper Functions

Source the wrapper scripts before using the functions:

```r
# Load required libraries
library(miloR)
library(SingleCellExperiment)

# Source wrapper functions
source("scripts/r/core_analysis.R")    # Core analysis functions
source("scripts/r/visualization.R")    # Plotting functions
source("scripts/r/utils.R")            # Utility functions
```

**Note:** Adjust the path based on your working directory:
- If running from `examples/`: `source("../scripts/r/core_analysis.R")`
- If running from skill root: `source("scripts/r/core_analysis.R")`
- If running from elsewhere: Use absolute or relative path accordingly

## Core Analysis Workflow

miloR performs differential abundance analysis by testing changes in cell neighborhood abundance between conditions. Follow this step-by-step workflow.

### Step 1: Data Validation and Preparation

Validate input data and create Milo object from SingleCellExperiment.

```r
library(miloR)
library(SingleCellExperiment)

# Validate input
validation <- validate_milor_input(
  x = sce,
  sample_col = "sample_id",
  condition_col = "condition"
)

# Create Milo object
milo_obj <- create_milo_object(sce)
```

**Key Points:**
- Input must be SingleCellExperiment with reduced dimensions (PCA) or logcounts
- colData must contain sample_id column for cell counting
- Recommended: UMAP in reducedDims for visualization

### Step 2: Build kNN Graph

Construct k-nearest neighbor graph representing cell-cell similarity.

```r
# Build graph with default parameters
milo_obj <- build_milo_graph(
  milo_obj,
  k = 30,              # Number of nearest neighbors
  d = 30,              # PCA dimensions to use
  reduced.dim = "PCA"  # Name of reduced dimension
)
```

**Parameter Guidelines:**
- `k = 30`: Default for most single-cell datasets
- `k = 50`: For large/dense datasets (>100K cells)
- `k = 10`: For small datasets (<1K cells)

### Step 3: Define Neighborhoods

Sample cells and define local neighborhoods on the graph.

```r
milo_obj <- make_milo_neighborhoods(
  milo_obj,
  prop = 0.1,                  # Proportion of cells to sample
  k = 30,                      # Use same k as graph building
  d = 30,                      # PCA dimensions
  refined = TRUE,              # Use refined sampling
  reduced_dims = "PCA",
  refinement_scheme = "reduced_dim",
  seed = 42                    # For reproducibility
)
```

**Parameter Guidelines:**
- `prop = 0.1`: Default for datasets 10K-100K cells
- `prop = 0.05`: For datasets >100K cells
- `prop = 0.2`: For datasets <10K cells
- `refined = TRUE`: Recommended for better coverage

### Step 4: Calculate Distances (Optional but Recommended)

Calculate neighborhood distances for spatial FDR correction.

```r
milo_obj <- calc_milo_distances(
  milo_obj,
  d = 30,
  reduced.dim = "PCA"
)
```

**Why this matters:**
- Required for `fdr.weighting = "k-distance"` or `"neighbour-distance"`
- Accounts for overlap between neighborhoods in multiple testing correction
- Provides more powerful and accurate FDR control

### Step 5: Count Cells per Neighborhood

Count cells from each sample in each neighborhood.

```r
milo_obj <- count_milo_cells(
  milo_obj,
  sample_col = "sample_id"
)
```

**Output:**
- `nhoodCounts(milo_obj)`: Matrix of nhoods x samples
- Used as input for differential testing

### Step 6: Create Design Matrix

Define experimental design for differential testing.

```r
# Simple two-group comparison
design_df <- data.frame(
  sample_id = factor(samples),
  condition = factor(conditions)
)
rownames(design_df) <- design_df$sample_id

# With batch correction
design_df <- data.frame(
  sample_id = factor(samples),
  condition = factor(conditions),
  batch = factor(batches)
)
rownames(design_df) <- design_df$sample_id
```

### Step 7: Test Differential Abundance

Perform statistical testing for DA neighborhoods.

**Basic two-group comparison:**
```r
da_results <- test_milo_da(
  milo_obj,
  design = ~ condition,
  design.df = design_df,
  fdr.weighting = "k-distance",
  norm.method = "TMM"
)
```

**With batch correction:**
```r
da_results <- test_milo_da(
  milo_obj,
  design = ~ batch + condition,
  design.df = design_df,
  fdr.weighting = "k-distance",
  norm.method = "TMM"
)
```

**Custom contrasts:**
```r
da_results <- test_milo_da(
  milo_obj,
  design = ~ 0 + condition,
  design.df = design_df,
  model.contrasts = c("conditionTreatment - conditionControl")
)
```

### Step 8: Annotate and Group Neighborhoods

Annotate neighborhoods with cell type labels and group overlapping DA neighborhoods.

**Cell type annotation:**
```r
da_results <- annotate_milo_neighborhoods(
  milo_obj,
  da.res = da_results,
  colData_col = "cell_type",
  nlargest = 1
)
```

**Neighborhood grouping:**
```r
da_results <- group_milo_neighborhoods(
  milo_obj,
  da.res = da_results,
  da.fdr = 0.1,
  overlap = 5,
  merge.discord = FALSE
)
```

### Step 9: Find Marker Genes

Identify marker genes that distinguish DA neighborhood groups.

```r
marker_results <- find_milo_markers(
  milo_obj,
  da.res = da_results,
  da.fdr = 0.1,
  assay = "logcounts",
  gene.offset = TRUE
)
```

### Step 10: Complete Pipeline (Shortcut)

Run the entire workflow with a single function.

```r
results <- run_milo_pipeline(
  x = sce,
  sample_col = "sample_id",
  condition_col = "condition",
  design = ~ condition,
  k = 30,
  d = 30,
  prop = 0.1,
  refined = TRUE,
  fdr.weighting = "k-distance",
  norm.method = "TMM",
  calc.distances = TRUE,
  seed = 42
)

# Extract results
milo_obj <- results$milo
da_results <- results$da_results
```

## Input Requirements

### Required Data Format

```r
# SingleCellExperiment with:
# - logcounts or counts assay
# - Reduced dimensions (recommended: PCA)
# - Sample metadata in colData

sce <- SingleCellExperiment(
  assays = list(logcounts = logcounts_matrix),
  colData = data.frame(
    sample_id = factor(c("S1", "S1", "S2", "S2", ...)),
    condition = factor(c("Ctrl", "Ctrl", "Treat", "Treat", ...))
  ),
  reducedDims = SimpleList(PCA = pca_matrix)
)
```

### Converting from Seurat

```r
sce <- seurat_to_sce(seurat_obj, assay = "RNA", dimreducs = c("pca", "umap"))
```

## Output Specifications

### DA Results Columns

| Column | Description |
|--------|-------------|
| `logFC` | Log fold change in abundance |
| `logCPM` | Log counts per million |
| `PValue` | Raw p-value |
| `SpatialFDR` | Spatially-weighted FDR |
| `FDR` | Standard FDR |
| `Nhood_center` | Index of neighborhood center cell |
| `cell_type` | Cell type annotation (if annotated) |
| `NhoodGroup` | Neighborhood group (if grouped) |

### Marker Gene Results

| Column | Description |
|--------|-------------|
| `GeneID` | Gene identifier |
| `logFC_X` | Log fold change for group X |
| `adj.P.Val_X` | Adjusted p-value for group X |

## Key Parameters

### Graph Building

| Parameter | Default | Description |
|-----------|---------|-------------|
| `k` | 30 | Number of nearest neighbors |
| `d` | 30 | Number of PCA dimensions |
| `reduced.dim` | "PCA" | Reduced dimension name |

### Neighborhood Definition

| Parameter | Default | Description |
|-----------|---------|-------------|
| `prop` | 0.1 | Proportion of cells to sample |
| `refined` | TRUE | Use refined sampling |
| `k` | 30 | k for neighborhood (use same as graph) |

### DA Testing

| Parameter | Default | Description |
|-----------|---------|-------------|
| `fdr.weighting` | "k-distance" | Spatial FDR method |
| `norm.method` | "TMM" | Normalization (TMM/RLE/logMS) |
| `min.mean` | 0 | Minimum mean count threshold |

### Spatial FDR Methods

| Method | Description |
|--------|-------------|
| `k-distance` | Uses kth nearest neighbor distance |
| `neighbour-distance` | Uses average neighbor distance |
| `max` | Uses maximum of distances |
| `graph-overlap` | Uses graph overlap |
| `none` | No spatial weighting |

## Expected Runtime

| Dataset Size | Graph Build | Make Nhoods | Count Cells | DA Test |
|--------------|-------------|-------------|-------------|---------|
| 10K cells, 10 samples | 10-30s | 5-15s | <5s | 5-10s |
| 100K cells, 20 samples | 1-5min | 30-60s | 10-30s | 10-30s |
| 1M cells, 50 samples | 10-30min | 5-10min | 1-3min | 30-60s |

*Runtime estimates on modern CPU with 16GB RAM*

## Error Handling

### Common Errors and Solutions

**No reduced dimensions found**
```
Error: Input must have reducedDims or logcounts assay for PCA computation
```
→ Add PCA to reducedDims or provide logcounts assay

**Sample column not found**
```
Error: Sample column 'sample_id' not found in colData
```
→ Ensure colData contains the specified sample column

**No neighborhoods pass filtering**
```
Error: No neighbourhoods to test
```
→ Check that countCells was run and sample_col is correct

**Design matrix mismatch**
```
Error: Design matrix dimensions don't match nhoodCounts
```
→ Ensure design.df rows match nhoodCounts columns

## Visualization Functions

### DA Plots

```r
# Beeswarm plot
plot_milo_beeswarm(da_results, group.by = "cell_type", alpha = 0.1)

# Volcano plot
plot_milo_volcano(da_results, alpha = 0.1)

# UMAP with DA coloring
plot_milo_umap_da(milo_obj, da_results, dimred = "UMAP")

# Neighborhood graph
plot_milo_graph_da(milo_obj, da_results, alpha = 0.1)
```

### Diagnostic Plots

```r
# Neighborhood size distribution
plot_milo_size_distribution(milo_obj)

# Cell counts per neighborhood
plot_milo_counts(milo_obj, n.top = 50)

# Multi-panel summary
plots <- plot_milo_summary(milo_obj, da_results)
```

## Utility Functions

### Parameter Recommendations

```r
# Recommend k based on dataset size
k <- recommend_milo_k(ncol(sce))

# Recommend prop based on dataset size
prop <- recommend_milo_prop(ncol(sce))
```

### Result Processing

```r
# Get top DA neighborhoods
top_nhoods <- get_top_da_nhoods(da_results, n_top = 10)

# Get significant neighborhoods
sig_nhoods <- get_significant_nhoods(da_results, alpha = 0.1, min.logFC = 1)

# Summarize results
summary <- summarize_milo_results(da_results)

# Export results
export_milo_results(da_results, "da_results.csv", significant_only = TRUE)
```

## Related Skills

- [bio-single-cell-differential-abundance-diffcyt-r](../bio-single-cell-differential-abundance-diffcyt-r/SKILL.md) - DA for cytometry data
- [bio-single-cell-differential-abundance-sccoda](../bio-single-cell-differential-abundance-sccoda/SKILL.md) - Compositional DA analysis
- [bio-single-cell-clustering](../bio-single-cell-clustering/SKILL.md) - Cell clustering methods

## References

1. Dann et al. (2022). Milo detects differentially abundant cell populations in single-cell data. *Nature Biotechnology*, 40, 245-253.
2. miloR Bioconductor: https://bioconductor.org/packages/miloR
3. miloR GitHub: https://github.com/MarioniLab/miloR
4. edgeR: Robinson et al. (2010), *Bioinformatics*, 26, 139-140.
