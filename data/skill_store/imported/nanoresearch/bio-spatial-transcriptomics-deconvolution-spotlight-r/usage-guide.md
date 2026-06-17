# SPOTlight Usage Guide

## Overview

SPOTlight is a spatial transcriptomics deconvolution tool that uses Non-negative Matrix Factorization (NMF) combined with Non-negative Least Squares (NNLS) regression to estimate cell type proportions in spatial spots.

### Key Features

- **NMF-based deconvolution**: Learns interpretable topic profiles for each cell type
- **Marker gene integration**: Uses marker genes to seed and guide the NMF model
- **Two-step workflow**: Separate model training and deconvolution for flexibility
- **Spatial visualization**: Built-in functions for spatial scatterpie plots
- **Quality control**: Residual analysis and confidence metrics

### When to Use SPOTlight

| Scenario | Recommended Tool |
|----------|------------------|
| You have reliable marker genes | **SPOTlight** |
| NMF-based interpretability is desired | **SPOTlight** |
| Native R workflow | **SPOTlight** or RCTD |
| Bayesian uncertainty quantification | cell2location |
| Large-scale datasets (>10k spots) | RCTD or CARD |
| No marker genes available | cell2location or Tangram |

## Quick Start

### Installation

```r
# Install SPOTlight from GitHub
if (!requireNamespace("devtools", quietly = TRUE)) {
  install.packages("devtools")
}
devtools::install_github("Marcello-Sergio/SPOTlight")

# Load package
library(SPOTlight)
library(Seurat)
```

### Basic Workflow

```r
# Run SPOTlight
spotlight_ls <- SPOTlight(
  x = ref_counts,        # Single-cell counts (genes x cells)
  y = spatial_counts,    # Spatial counts (genes x spots)
  groups = cell_types,   # Cell type labels for single-cell
  mgs = markers,         # Marker genes data frame
  scale = TRUE,
  min_prop = 0.01
)

# Extract proportions
proportions <- spotlight_ls$mat
```

## Step-by-Step Guide

### Step 1: Load and Prepare Data

#### From Seurat Objects

```r
library(Seurat)

# Load reference scRNA-seq
ref_obj <- readRDS("reference_sc.rds")

# Extract counts
ref_counts <- GetAssayData(ref_obj, slot = "counts")
cell_types <- setNames(ref_obj$cell_type, colnames(ref_obj))

# Load spatial data
spatial_obj <- readRDS("spatial_data.rds")
spatial_counts <- GetAssayData(spatial_obj, slot = "counts")

# Get spatial coordinates
spatial_coords <- GetTissueCoordinates(spatial_obj)
```

#### From Matrix Files

```r
library(Matrix)

# Load single-cell reference
ref_counts <- readMM("reference_counts.mtx")
rownames(ref_counts) <- readLines("reference_genes.txt")
colnames(ref_counts) <- readLines("reference_barcodes.txt")

# Load cell type labels
metadata <- read.csv("reference_metadata.csv", row.names = 1)
cell_types <- setNames(metadata$cell_type, rownames(metadata))

# Load spatial data
spatial_counts <- readMM("spatial_counts.mtx")
rownames(spatial_counts) <- readLines("spatial_genes.txt")
colnames(spatial_counts) <- readLines("spatial_barcodes.txt")

# Load spatial coordinates
coords <- read.csv("spatial_coords.csv", row.names = 1)
```

#### Data Validation

```r
source("scripts/r/utils.R")

validation <- validate_spotlight_data(
  sc_counts = ref_counts,
  sp_counts = spatial_counts,
  cell_types = cell_types,
  min_cells_per_type = 50,
  min_genes = 1000,
  min_spots = 100
)

print_validation_results(validation)
```

### Step 2: Prepare Marker Genes

```r
# Option 1: Find markers using Seurat
markers <- FindAllMarkers(
  ref_obj,
  only.pos = TRUE,
  min.pct = 0.25,
  logfc.threshold = 0.25
)

# Format for SPOTlight
markers$weight <- markers$avg_log2FC

# Option 2: Use custom markers
markers <- data.frame(
  gene = c("CD3D", "CD79A", "LYZ", "COL1A1", "PECAM1", "EPCAM"),
  cluster = c("T_cell", "B_cell", "Myeloid", "Fibroblast", "Endothelial", "Epithelial"),
  weight = c(2.5, 3.0, 2.8, 2.5, 2.2, 3.0)
)
```

### Step 3: Run SPOTlight

#### One-Step Approach

```r
# Run complete analysis
spotlight_ls <- SPOTlight(
  x = ref_counts,
  y = spatial_counts,
  groups = cell_types,
  mgs = markers,
  gene_id = "gene",
  group_id = "cluster",
  weight_id = "avg_log2FC",
  n_top = NULL,        # Use all markers, or specify number
  scale = TRUE,        # Scale to unit variance
  min_prop = 0.01,     # Minimum proportion threshold
  verbose = TRUE
)

proportions <- spotlight_ls$mat
```

#### Two-Step Approach (Advanced)

```r
# Step 1: Train NMF model
nmf_model <- trainNMF(
  x = ref_counts,
  y = rownames(spatial_counts),
  groups = cell_types,
  mgs = markers,
  gene_id = "gene",
  group_id = "cluster",
  weight_id = "avg_log2FC",
  n_top = NULL,
  scale = TRUE,
  verbose = TRUE
)

# Step 2: Deconvolute spatial spots
decon_results <- runDeconvolution(
  x = spatial_counts,
  mod = nmf_model$mod,
  ref = nmf_model$topic,
  scale = TRUE,
  min_prop = 0.01
)

proportions <- decon_results$mat
```

### Step 4: Interpret Results

```r
source("scripts/r/utils.R")

# Summarize results
summary <- summarize_spotlight_results(spotlight_ls)
print(summary)

# Get dominant cell type per spot
dominant <- get_dominant_cell_type(proportions)
table(dominant)

# Filter low-confidence predictions
filtered_props <- filter_proportions(
  proportions,
  min_confidence = 0.5,
  min_proportion = 0.05
)
```

**Understanding Output:**

| Column | Interpretation |
|--------|----------------|
| `mat` | Cell type proportions per spot (spots × cell types) |
| `res_ss` | Residual sum of squares per spot |
| `NMF` | NMF model components (w, h, d) |

### Step 5: Visualize Results

```r
source("scripts/r/visualization.R")

# 1. Spatial scatterpie plot
plot_spatial_scatterpie(
  x = spatial_coords,
  y = proportions,
  cell_types = colnames(proportions),
  pie_scale = 0.4,
  save_path = "scatterpie.png"
)

# 2. Topic profiles
plot_topic_profiles(
  x = spotlight_ls$NMF,
  y = cell_types,
  facet = TRUE,
  save_path = "topic_profiles.png"
)

# 3. Cell type correlation matrix
plot_correlation_matrix(
  x = proportions,
  cor.method = "pearson",
  save_path = "correlation_matrix.png"
)

# 4. Cell-cell interactions
plot_interactions(
  x = proportions,
  which = "heatmap",
  min_prop = 0.1,
  save_path = "interactions.png"
)

# 5. Individual cell type spatial plot
plot_spotlight_cell_type(
  proportions = proportions,
  spatial_coords = spatial_coords,
  cell_type = "T_cell",
  save_path = "t_cell_spatial.png"
)
```

### Step 6: Quality Control

```r
source("scripts/r/utils.R")

# Calculate QC metrics
qc_metrics <- calculate_qc_metrics(spotlight_ls)
print(qc_metrics)

# Plot residuals
plot_residuals(spotlight_ls$res_ss, save_path = "residuals.png")

# Check model convergence (if using trainNMF)
plot_nmf_convergence(spotlight_ls$NMF)
```

**QC Metrics:**

| Metric | Good | Concern |
|--------|------|---------|
| Mean residuals | < 0.3 | > 0.5 |
| Spots with low residuals | > 80% | < 60% |
| Mean entropy | 0.5-1.5 | > 2.0 (mixed) |

### Step 7: Export Results

```r
source("scripts/r/utils.R")

export_spotlight_results(
  spotlight_ls,
  output_dir = "spotlight_results",
  prefix = "sample1",
  export_proportions = TRUE,
  export_nmf = TRUE,
  export_qc = TRUE
)
```

### Step 8: Multi-Sample Analysis

```r
# Run on multiple samples
samples <- c("sample1", "sample2", "sample3")
results_list <- lapply(samples, function(s) {
  sp_counts <- readRDS(paste0(s, "_spatial.rds"))
  SPOTlight(
    x = ref_counts,
    y = sp_counts,
    groups = cell_types,
    mgs = markers
  )
})

names(results_list) <- samples

# Combine proportions
all_proportions <- do.call(rbind, lapply(results_list, function(x) x$mat))
```

## Advanced Topics

### Parameter Tuning

```r
# More stringent filtering
result <- SPOTlight(
  x = ref_counts,
  y = spatial_counts,
  groups = cell_types,
  mgs = markers,
  min_prop = 0.05,    # Higher minimum proportion
  n_top = 20          # Use only top 20 markers per cell type
)

# With highly variable gene selection
hvg_genes <- VariableFeatures(ref_obj)[1:3000]
result <- SPOTlight(
  x = ref_counts,
  y = spatial_counts,
  groups = cell_types,
  mgs = markers,
  hvg = hvg_genes
)
```

### Memory Management for Large Datasets

```r
# For large spatial datasets (>5000 spots)
result <- SPOTlight(
  x = ref_counts,
  y = spatial_counts,
  groups = cell_types,
  mgs = markers,
  scale = TRUE,
  threads = 1  # Reduce memory usage
)
```

### Cross-Validation

```r
# Leave-one-cell-type-out validation
cv_results <- cross_validate_spotlight(
  ref_counts,
  cell_types,
  markers,
  n_folds = 5
)
```

## Troubleshooting

### Insufficient shared genes

```
Error: Insufficient number of features shared between single-cell and mixture dataset
```

→ Check gene name consistency (case, format)
→ Ensure at least 10 common genes

### Missing marker genes

```
Error: Groups not present in mgs
```

→ Verify all cell types in `groups` have markers in `mgs`
→ Check column names in markers data frame

### NMF convergence issues

```
Warning: NMF did not converge
```

→ Check marker quality
→ Reduce number of cell types
→ Use more cells per cell type

### Memory issues

```
Error: cannot allocate vector of size X Gb
```

→ Reduce `hvg` to fewer genes
→ Use sparse matrices
→ Reduce threads: `threads = 1`

## AI Agent Test Cases

### Basic Usage
> "Run SPOTlight deconvolution on my Visium data"

```r
spotlight_ls <- SPOTlight(
  x = ref_counts,
  y = spatial_counts,
  groups = cell_types,
  mgs = markers
)
```

### With Custom Parameters
> "Run SPOTlight with top 20 markers per cell type"

```r
spotlight_ls <- SPOTlight(
  x = ref_counts,
  y = spatial_counts,
  groups = cell_types,
  mgs = markers,
  n_top = 20
)
```

### Two-Step Workflow
> "Train NMF model first, then deconvolute"

```r
nmf_model <- trainNMF(ref_counts, rownames(spatial_counts), cell_types, markers)
decon_results <- runDeconvolution(spatial_counts, nmf_model$mod, nmf_model$topic)
```

### Visualization
> "Plot SPOTlight results on tissue"

```r
plot_spatial_scatterpie(spatial_coords, proportions, colnames(proportions))
```

### Multi-Sample
> "Run SPOTlight on multiple samples"

```r
results <- lapply(sample_list, function(s) {
  SPOTlight(ref_counts, spatial_counts[[s]], cell_types, markers)
})
```

## Interpretation Guidelines

### Understanding NMF Topics

- Each topic corresponds to a cell type
- Well-trained model: cells from same type cluster in same topic
- Topic profiles: median topic weights per cell type

### Quality Metrics

**Good deconvolution:**
- Low residuals (res_ss)
- Clear spatial patterns matching expectations
- Correlation matrix shows expected cell type relationships

**Potential issues:**
- High residuals: Poor model fit, check marker quality
- No spatial pattern: Cell type may not be present
- Uniform proportions: Over-smoothing, reduce min_prop

### Cell Type Proportions

- Sum to 1 per spot (after normalization)
- Values < min_prop set to 0
- Dominant cell type: highest proportion per spot

## Best Practices

1. **Reference Quality**: Use high-quality scRNA-seq with clear cell type annotations
2. **Marker Genes**: Use validated markers specific to each cell type
3. **Cell Type Balance**: Ensure sufficient cells per cell type (>50)
4. **Gene Overlap**: Maximize shared genes between reference and spatial
5. **QC Review**: Always check residual plots and topic profiles
6. **Biological Validation**: Compare with known tissue structure

## References

1. Elosua-Bayes et al. (2021). SPOTlight: seeded NMF regression to deconvolute spatial transcriptomics spots. *Nucleic Acids Research*, 49(19): e95. https://doi.org/10.1093/nar/gkab043
2. SPOTlight GitHub: https://github.com/Marcello-Sergio/SPOTlight
3. SPOTlight Vignette: https://marcello-sergio.github.io/SPOTlight/
