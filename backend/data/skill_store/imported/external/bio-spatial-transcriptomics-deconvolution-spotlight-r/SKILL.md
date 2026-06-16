---
name: bio-spatial-transcriptomics-deconvolution-spotlight-r
description: |
  SPOTlight performs NMF-based spatial transcriptomics deconvolution with marker gene integration.
  Uses Non-negative Matrix Factorization (NMF) combined with Non-negative Least Squares (NNLS)
  regression to estimate cell type proportions in spatial spots. Supports marker gene-guided
tool_type: r
primary_tool: SPOTlight
languages: [r]
keywords: ["spatial", "deconvolution", "SPOTlight", "NMF", "NNLS", "markers",
           "spotlight", "cell-proportions", "visium", "R"]
---

## Version Compatibility

- **R**: >= 4.2.0
- **SPOTlight**: >=1.0 (GitHub: Marcello-Sergio/SPOTlight)
- **Seurat**: >=4.3.0
- **SingleCellExperiment**: >=1.20.0
- **SpatialExperiment**: >=1.8.0
- **Matrix**: >=1.5
- **ggplot2**: >=3.4.0

## Installation

```r
# Install SPOTlight from GitHub
if (!requireNamespace("devtools", quietly = TRUE)) {
  install.packages("devtools")
}
devtools::install_github("Marcello-Sergio/SPOTlight")

# Install dependencies
install.packages(c("Matrix", "ggplot2", "ggcorrplot"))
BiocManager::install(c("SingleCellExperiment", "SpatialExperiment"))
```

## Data Requirements

Input requirements:
- **Reference scRNA-seq**: Gene expression matrix (genes × cells) with cell type labels
- **Spatial data**: Gene expression matrix (genes × spots) or SpatialExperiment object
- **Marker genes**: Data frame with gene, cluster, and weight columns (optional but recommended)
- **Minimum requirements**:
  - Reference: 100+ cells per cell type
  - Spatial: 100+ spots
  - Genes: 1000+ common genes between reference and spatial

**Data Validation:**
```r
source("scripts/r/utils.R")

# Validate input data
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

## Core Analysis Workflow

### 1. Data Loading and Preparation

**Input formats supported:**
```r
# From Seurat objects
library(Seurat)
ref_obj <- readRDS("reference_sc.rds")
spatial_obj <- readRDS("spatial_data.rds")

# Extract counts
# Seurat v5 uses 'layer' instead of 'slot'
ref_counts <- GetAssayData(ref_obj, layer = "counts")
sp_counts <- GetAssayData(spatial_obj, layer = "counts")
cell_types <- setNames(ref_obj$cell_type, colnames(ref_obj))

# From Matrix files
library(Matrix)
ref_counts <- readMM("reference_counts.mtx")
sp_counts <- readMM("spatial_counts.mtx")
```

**Prepare marker genes:**
```r
# Find markers using Seurat
markers <- FindAllMarkers(
  ref_obj,
  only.pos = TRUE,
  min.pct = 0.25,
  logfc.threshold = 0.25
)

# Format for SPOTlight
markers$weight <- markers$avg_log2FC  # Use logFC as weight

# Or use custom markers
markers <- data.frame(
  gene = c("CD3D", "CD79A", "LYZ", "PPBP"),
  cluster = c("T_cell", "B_cell", "Myeloid", "Platelet"),
  weight = c(2.5, 3.0, 2.8, 3.5)
)
```

### 2. Run SPOTlight Deconvolution

Function: `run_spotlight(x, y, groups, mgs, ...)`

**Purpose:** Deconvolute spatial spots using NMF with marker gene integration.

**Key Parameters:**
- `x`: Single-cell expression matrix (genes × cells) or SingleCellExperiment
- `y`: Spatial expression matrix (genes × spots) or SpatialExperiment
- `groups`: Character vector of cell type labels for single-cell data
- `mgs`: Marker gene data frame with columns: gene, cluster, weight
- `n_top`: Number of top markers per cell type (default: NULL = all)
- `gene_id`, `group_id`, `weight_id`: Column names in mgs (default: "gene", "cluster", "weight")
- `hvg`: Character vector of highly variable genes to include (optional)
- `scale`: Whether to scale single-cell counts to unit variance (default: TRUE)
- `min_prop`: Minimum cell type proportion (default: 0.01)
- `L1_nmf`, `L2_nmf`: LASSO and RIDGE penalties for NMF (default: 0)
- `tol`: Convergence tolerance (default: 1e-5)
- `maxit`: Maximum iterations (default: 100)
- `threads`: Number of threads (default: 0 = all)

**Process:**
1. **Train NMF model**: Learn topic profiles for each cell type using single-cell data
2. **Seed NMF**: Initialize basis matrix using marker genes
3. **Deconvolute spots**: Use NNLS to estimate cell type proportions
4. **Return proportions**: Matrix with cell type proportions per spot

**Output:**
List containing:
- `mat`: Proportion matrix (spots × cell types)
- `res_ss`: Residual sum of squares per spot
- `NMF`: NMF model with w (basis), h (coefficients), d (diagonal)

**Example:**
```r
source("scripts/r/run_spotlight.R")

# Run SPOTlight
spotlight_ls <- run_spotlight(
  x = ref_counts,
  y = sp_counts,
  groups = cell_types,
  mgs = markers,
  n_top = 10,
  gene_id = "gene",
  group_id = "cluster",
  weight_id = "avg_log2FC",
  scale = TRUE,
  min_prop = 0.01,
  verbose = TRUE
)

# Extract proportions
proportions <- spotlight_ls$mat
```

### 3. Two-Step Deconvolution (Advanced)

For more control, use trainNMF and runDeconvolution separately:

```r
# Step 1: Train NMF model on single-cell data
nmf_model <- trainNMF(
  x = ref_counts,
  y = rownames(sp_counts),  # Genes to use
  groups = cell_types,
  mgs = markers,
  n_top = 10,
  scale = TRUE,
  verbose = TRUE
)

# Step 2: Deconvolute spatial spots
decon_results <- runDeconvolution(
  x = sp_counts,
  mod = nmf_model$mod,
  ref = nmf_model$topic,
  scale = TRUE,
  min_prop = 0.01
)

proportions <- decon_results$mat
```

### 4. Result Interpretation

```r
source("scripts/r/utils.R")

# Summarize results
summary <- summarize_spotlight_results(spotlight_ls)
print(summary)

# Get dominant cell type per spot
dominant <- get_dominant_cell_type(spotlight_ls$mat)
table(dominant)

# Filter low-confidence predictions
filtered_props <- filter_proportions(
  spotlight_ls$mat,
  min_confidence = 0.5,
  min_proportion = 0.05
)
```

### 5. Visualization

**Available plots:**
```r
source("scripts/r/visualization.R")

# Spatial scatterpie plot
plot_spatial_scatterpie(
  x = spatial_coords,  # Data frame with x, y coordinates
  y = proportions,
  cell_types = colnames(proportions),
  pie_scale = 0.4,
  save_path = "scatterpie.png"
)

# Topic profiles from NMF
plot_topic_profiles(
  x = spotlight_ls$NMF,
  y = cell_types,
  facet = TRUE,
  save_path = "topic_profiles.png"
)

# Cell type correlation matrix
plot_correlation_matrix(
  x = proportions,
  cor.method = "pearson",
  save_path = "correlation_matrix.png"
)

# Cell-cell interactions
plot_interactions(
  x = proportions,
  which = "heatmap",
  min_prop = 0.1,
  save_path = "interactions.png"
)

# Single cell type spatial plot
plot_spotlight_cell_type(
  proportions = proportions,
  spatial_coords = spatial_coords,
  cell_type = "T_cell",
  save_path = "t_cell_spatial.png"
)
```

### 6. Quality Control and Diagnostics

```r
source("scripts/r/utils.R")

# Check model convergence
plot_nmf_convergence(spotlight_ls$NMF)

# Assess deconvolution quality
qc_metrics <- calculate_qc_metrics(spotlight_ls)
print(qc_metrics)

# Spot-wise residuals
plot_residuals(spotlight_ls$res_ss, save_path = "residuals.png")

# Compare with ground truth (if available)
accuracy <- evaluate_accuracy(
  predicted = proportions,
  ground_truth = true_proportions
)
```

### 7. Export Results

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

### 8. Complete Pipeline

```r
source("scripts/r/run_spotlight.R")

# Run complete analysis
results <- run_spotlight_pipeline(
  sc_counts = ref_counts,
  sp_counts = sp_counts,
  cell_types = cell_types,
  spatial_coords = spatial_coords,
  markers = markers,
  output_dir = "results",
  create_plots = TRUE,
  verbose = TRUE
)
```

## Input Requirements

### Required Data Format

```r
# Reference single-cell data
class(ref_counts)  # matrix, dgCMatrix, or SingleCellExperiment
dim(ref_counts)    # genes × cells
rownames(ref_counts)  # Gene symbols
colnames(ref_counts)  # Cell barcodes

# Cell type labels
length(cell_types)  # Should equal ncol(ref_counts)
head(cell_types)    # Named vector: cell barcode -> cell type

# Spatial data
class(sp_counts)    # matrix, dgCMatrix, or SpatialExperiment
dim(sp_counts)      # genes × spots
rownames(sp_counts) # Gene symbols (must overlap with ref_counts)

# Marker genes data frame
head(markers)
#      gene cluster avg_log2FC
# 1   CD3D  T_cell       2.50
# 2  CD79A  B_cell       3.00
# 3    LYZ Myeloid       2.80
```

## Output Specifications

### Core Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Proportions | `result$mat` | Cell type proportions per spot (spots × cell types) |
| NMF Model | `result$NMF` | w (basis), h (coefficients), d (diagonal) |
| Residuals | `result$res_ss` | Sum of squared residuals per spot |

### NMF Model Components

| Component | Description | Dimensions |
|-----------|-------------|------------|
| `NMF$w` | Basis matrix (genes × topics) | n_genes × n_cell_types |
| `NMF$h` | Coefficient matrix (topics × cells) | n_cell_types × n_cells |
| `NMF$d` | Scaling diagonal | n_topics |

## Key Parameters

### NMF Training

| Parameter | Default | Description | When to Adjust |
|-----------|---------|-------------|----------------|
| `n_top` | NULL | Top markers per cell type | Reduce if too many markers |
| `scale` | TRUE | Scale to unit variance | Disable if data already normalized |
| `L1_nmf` | 0 | LASSO penalty for sparsity | Increase (0.01-0.1) for sparser topics |
| `L2_nmf` | 0 | RIDGE penalty | Increase if overfitting |
| `tol` | 1e-5 | Convergence tolerance | Decrease for stricter convergence |
| `maxit` | 100 | Max iterations | Increase if not converging |

### Deconvolution

| Parameter | Default | Description | When to Adjust |
|-----------|---------|-------------|----------------|
| `min_prop` | 0.01 | Minimum proportion | Increase to filter noise |
| `scale` | TRUE | Scale spatial data | Match training scale |

## Expected Runtime

| Dataset Size | NMF Training | Deconvolution | Total |
|--------------|--------------|---------------|-------|
| 1k cells, 500 spots | 1-2 min | 10-20s | 2-3 min |
| 5k cells, 1k spots | 3-5 min | 30-60s | 5-7 min |
| 10k cells, 3k spots | 8-12 min | 2-3 min | 12-15 min |
| 50k cells, 5k spots | 30-45 min | 5-8 min | 40-55 min |

*Runtime estimates on 8-core CPU with 32GB RAM*

## Error Handling

### Common Errors and Solutions

**Insufficient shared genes**
```
Error: Insufficient number of features shared between single-cell and mixture dataset
```
→ Check gene name consistency (case, format)
→ Ensure at least 10 common genes

**Missing marker genes**
```
Error: Groups not present in mgs
```
→ Verify all cell types in `groups` have markers in `mgs`
→ Check `group_id` column name matches

**NMF convergence issues**
```
Warning: NMF did not converge
```
→ Increase `maxit` (e.g., to 200)
→ Adjust `tol` (e.g., to 1e-4)
→ Check marker quality

**Memory issues**
```
Error: cannot allocate vector of size X Gb
```
→ Reduce `hvg` to fewer genes
→ Use sparse matrices
→ Reduce threads: `threads = 1`

## Common Analysis Patterns

### Pattern 1: Quick Deconvolution
```r
spotlight_ls <- SPOTlight(
  x = ref_counts,
  y = sp_counts,
  groups = cell_types,
  mgs = markers
)
proportions <- spotlight_ls$mat
```

### Pattern 2: With HVG Selection
```r
# Find HVGs in reference
hvg_genes <- FindVariableFeatures(ref_obj, nfeatures = 3000)
hvg_genes <- hvg_genes@var.features

# Run with HVGs
spotlight_ls <- SPOTlight(
  x = ref_counts,
  y = sp_counts,
  groups = cell_types,
  mgs = markers,
  hvg = hvg_genes,
  n_top = 20
)
```

### Pattern 3: Multi-Sample Analysis
```r
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
```

### Pattern 4: Cross-Validation
```r
# Leave-one-cell-type-out validation
cv_results <- cross_validate_spotlight(
  ref_counts,
  cell_types,
  markers,
  n_folds = 5
)
```

## Module Structure

```
scripts/r/
├── run_spotlight.R       # run_spotlight(), run_spotlight_seurat(),
│                         # run_spotlight_pipeline()
├── visualization.R       # plot_spatial_scatterpie(), plot_topic_profiles(),
│                         # plot_correlation_matrix(), plot_interactions(),
│                         # plot_spotlight_cell_type()
└── utils.R               # validate_spotlight_data(), summarize_spotlight_results(),
                          # get_dominant_cell_type(), filter_proportions(),
                          # export_spotlight_results(), calculate_qc_metrics()

examples/
├── minimal_example.R     # Basic SPOTlight usage
└── advanced_example.R    # Full pipeline with visualization

tests/
└── test_spotlight.R      # Unit tests
```

## Interpretation Guidelines

### Understanding NMF Topics

- Each topic should correspond to a cell type
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

## Related Skills

- [bio-spatial-transcriptomics-deconvolution-cell2location](../bio-spatial-transcriptomics-deconvolution-cell2location/SKILL.md) - Bayesian deconvolution
- [bio-spatial-transcriptomics-deconvolution-rctd-r](../bio-spatial-transcriptomics-deconvolution-rctd-r/SKILL.md) - RCTD deconvolution
- [bio-spatial-transcriptomics-deconvolution-card-r](../bio-spatial-transcriptomics-deconvolution-card-r/SKILL.md) - CARD deconvolution
- [bio-spatial-transcriptomics-deconvolution-tangram](../bio-spatial-transcriptomics-deconvolution-tangram/SKILL.md) - Tangram mapping

## References

1. Elosua-Bayes et al. (2021). SPOTlight: seeded NMF regression to deconvolute spatial transcriptomics spots. *Nucleic Acids Research*, 49(19): e95. https://doi.org/10.1093/nar/gkab043
2. SPOTlight GitHub: https://github.com/Marcello-Sergio/SPOTlight
3. SPOTlight Vignette: https://marcello-sergio.github.io/SPOTlight/
