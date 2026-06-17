---
name: bio-spatial-transcriptomics-deconvolution-rctd-r
description: RCTD (Robust Cell Type Decomposition) for spatial transcriptomics with doublet detection and platform effect normalization
tool_type: r
primary_tool: spacexr
supported_tools: [Seurat, Matrix, ggplot2]
languages: [r]
keywords: ["spatial-transcriptomics", "deconvolution", "RCTD", "spacexr", "doublet-detection", "platform-effect"]
---

## Version Compatibility

- **R**: >= 4.2.0
- **spacexr**: >= 2.2.0
- **Seurat**: >= 4.3.0

## Installation

```r
if (!require("devtools", quietly = TRUE))
    install.packages("devtools")

devtools::install_github("dmcable/spacexr", build_vignettes = FALSE)
```

## Import Wrapper Functions

Source the wrapper scripts before using:

```r
# Core functions
source("scripts/r/core_analysis.R")

# Visualization
source("scripts/r/visualization.R")

# Utilities
source("scripts/r/utils.R")
```

## Core Analysis Workflow

RCTD performs reference-based cell type deconvolution with platform effect normalization and doublet detection.

### Input Data Requirements

| Data | Format | Description |
|------|--------|-------------|
| `spatial_counts` | Matrix (genes × spots) | Spatial transcriptomics raw counts |
| `spatial_coords` | DataFrame (spots × 2) | Spatial coordinates with x, y columns (optional) |
| `reference_counts` | Matrix (genes × cells) | Single-cell reference raw counts |
| `cell_types` | Named factor | Cell type labels (names = cell barcodes) |

**Important:** Minimum 25 cells per cell type required. Cell type names must match reference column names.

---

## Analysis Pathways

Choose one pathway based on your needs:

### Pathway 1: Complete Automated Pipeline (Recommended)

Single function call for the entire workflow - **validation → object creation → deconvolution**.

```r
# One-step complete analysis
results <- run_rctd(
  spatial_counts = spatial_counts,
  spatial_coords = spatial_coords,
  reference_counts = reference_counts,
  cell_types = cell_types,
  doublet_mode = "doublet",  # or "full" or "multi"
  max_cores = 4,
  gene_cutoff = 0.000125,
  fc_cutoff = 0.5,
  validate = TRUE            # Enable input validation
)
```

**When to use:** Most users should start here. Handles validation and object creation internally.

---

### Pathway 2: Step-by-Step Pipeline (For Customization)

For when you need to inspect or modify intermediate objects.

#### Step A: Data Validation (Optional but Recommended)

```r
validation <- validate_rctd_input(
  spatial_counts = spatial_counts,
  spatial_coords = spatial_coords,
  reference_counts = reference_counts,
  cell_types = cell_types
)

if (!validation$valid) {
  stop(paste("Validation errors:", paste(validation$errors, collapse = "\n")))
}

# Get parameter recommendations
params <- recommend_rctd_params(
  n_spots = validation$stats$n_spots,
  n_cell_types = validation$stats$n_cell_types
)
cat(params$message)
```

#### Step B: Create RCTD Objects

Convert raw matrices to RCTD-specific objects.

```r
objects <- create_rctd_objects(
  spatial_counts = spatial_counts,
  spatial_coords = spatial_coords,
  reference_counts = reference_counts,
  cell_types = cell_types
)

# Access created objects
spatial_rna <- objects$spatial_rna   # SpatialRNA object
reference <- objects$reference       # Reference object

# You can inspect/modify objects here before deconvolution
print(spatial_rna@nUMI)    # Check spot UMI counts
print(reference@cell_types) # Check cell type distribution
```

**Purpose:** Creates `SpatialRNA` (spatial data + coordinates) and `Reference` (single-cell reference) objects for RCTD.

#### Step C: Run Deconvolution

Use the created objects directly with spacexr functions.

```r
library(spacexr)

# Create RCTD object
rctd <- create.RCTD(
  spatial_rna,
  reference,
  max_cores = 4,
  gene_cutoff = 0.000125,
  fc_cutoff = 0.5
)

# Run deconvolution
rctd <- run.RCTD(rctd, doublet_mode = "doublet")

# Results are in rctd@results
results <- rctd
```

**When to use:** When you need to:
- Inspect intermediate objects before deconvolution
- Modify default RCTD parameters not exposed in `run_rctd()`
- Integrate custom preprocessing steps

---

### Pathway 3: Seurat Integration

Use when your data is already in Seurat format.

#### Option A: Seurat Input → Standard Output

```r
# Prepare from Seurat objects
results <- run_rctd_seurat(
  spatial_seurat = spatial_obj,
  reference_seurat = ref_obj,
  cell_type_column = "cell_type",
  coord_columns = c("imagerow", "imagecol"),
  doublet_mode = "doublet"
)

# Proceed with standard visualization/export
```

#### Option B: Seurat Input → Seurat Output

```r
# Run deconvolution
results <- run_rctd_seurat(
  spatial_seurat = spatial_obj,
  reference_seurat = ref_obj,
  cell_type_column = "cell_type",
  doublet_mode = "doublet"
)

# Export results back to Seurat object
spatial_obj <- export_rctd_to_seurat(
  spatial_obj,
  results,
  assay_name = "RCTD"
)

# Access via Seurat
spatial_obj@assays$RCTD$proportions  # Cell type proportions
```

**Requirements:**
- Spatial Seurat with coordinates in metadata or images slot
- Reference Seurat with cell type annotations in metadata

**When to use:** Your workflow is already Seurat-based and you want seamless integration.

---

## Quick Start: Recommended Defaults

**Parameters:**
- `doublet_mode`: "doublet" (1-2 cell types), "full" (any number), or "multi" (greedy)
- `max_cores`: Parallel cores (default: 4)
- `gene_cutoff`: Minimum gene expression for platform effect normalization (default: 0.000125)
- `fc_cutoff`: Minimum log fold change for marker selection (default: 0.5)
- `UMI_min`: Minimum UMI per spot (default: 100)
- `test_mode`: Set TRUE for quick testing (default: FALSE)

**Mode Selection:**
- `doublet`: Best for Visium (10-20 cells per spot). Classifies as singlet/doublet/reject.
- `full`: Best for high-resolution data (Slide-seq, MERFISH). No limit on cell types per spot.
- `multi`: Intermediate option. Uses greedy algorithm up to MAX_MULTI_TYPES.

---

## Results Analysis

After running RCTD (regardless of pathway), analyze the results:

### Extract Proportions

Get cell type proportions for each spot.

```r
# Extract proportions (normalized)
props <- extract_proportions_rctd(results, normalize = TRUE)

# Summary statistics
summary <- summarize_rctd_results(results)
print(summary$mean_proportions)
print(summary$dominant_cell_types)

# Top cell types per spot
top_types <- get_top_cell_types(results, n_top = 2)
```

**Output:**
- `weights`: Proportion matrix (spots x cell types) - full mode
- `weights_doublet`: Proportions in doublet mode
- `results_df`: Spot classification (singlet/doublet/reject)

### Analyze Doublet Results (Doublet Mode)

For doublet mode, extract detailed predictions.

```r
# Get doublet predictions
doublet_preds <- get_doublet_predictions(results)
head(doublet_preds)

# Summary
summary <- summarize_rctd_results(results)
print(summary$spot_classes)
print(summary$singlet_spots)
print(summary$doublet_certain)
```

**Spot Classes:**
- `singlet`: 1 cell type on pixel
- `doublet_certain`: 2 cell types, confident prediction
- `doublet_uncertain`: 2 cell types, only 1 confident
- `reject`: No prediction (poor quality or ambiguous)

### Visualize Results

Create spatial visualizations of deconvolution results.

**Spatial proportion maps:**
```r
plot_rctd_proportions(
  results,
  cell_types = c("T_cell", "B_cell", "Macrophage"),
  layout = "grid"
)
```

**Dominant cell types:**
```r
plot_rctd_dominant(results, min_proportion = 0.3)
```

**Doublet classification:**
```r
plot_rctd_doublets(results)
```

**Distribution plots:**
```r
plot_rctd_distribution(results, plot_type = "violin")
plot_rctd_mean_props(results)
```

**Comprehensive summary:**
```r
plot_rctd_summary(results, output_dir = "./rctd_plots")
```

### Export Results

Save deconvolution results to files.

```r
export_rctd_results(
  results,
  output_dir = "./rctd_output",
  prefix = "sample1"
)

# Generate report
report <- create_rctd_report(results, "rctd_report.txt")
cat(report)
```

**Exports:**
- `{prefix}_proportions.csv`: Cell type proportions
- `{prefix}_top_cell_types.csv`: Top cell types per spot
- `{prefix}_doublet_predictions.csv`: Doublet predictions (doublet mode only)
- `{prefix}_summary.txt`: Summary report
- `{prefix}_object.rds`: Full RCTD object

---

## Input Requirements

### Required Data Format

```r
# Spatial counts: dgCMatrix or matrix (genes x spots)
spatial_counts <- Matrix::Matrix(rpois(1000, 5), nrow = 100)
rownames(spatial_counts) <- paste0("gene_", 1:100)
colnames(spatial_counts) <- paste0("spot_", 1:10)

# Spatial coordinates: data.frame with x, y (optional)
spatial_coords <- data.frame(
  x = 1:10,
  y = 1:10,
  row.names = colnames(spatial_counts)
)

# Reference counts: dgCMatrix or matrix (genes x cells)
reference_counts <- Matrix::Matrix(rpois(5000, 5), nrow = 100)
rownames(reference_counts) <- rownames(spatial_counts)
colnames(reference_counts) <- paste0("cell_", 1:50)

# Cell types: named factor (CRITICAL: names must match reference columns)
cell_types <- factor(rep(c("A", "B"), each = 25))
names(cell_types) <- colnames(reference_counts)  # IMPORTANT!
```

## Output Specifications

### Proportion Matrix

| Output | Type | Description |
|--------|------|-------------|
| `weights` | matrix | Spots x cell types proportions (full mode) |
| `weights_doublet` | matrix | Proportions in doublet mode |
| `results_df` | data.frame | Spot classification and predictions |

### Spot Classification (Doublet Mode)

| Column | Description |
|--------|-------------|
| `spot_class` | singlet/doublet_certain/doublet_uncertain/reject |
| `first_type` | Primary cell type (index) |
| `second_type` | Secondary cell type (index, doublets only) |

### Summary Statistics

```r
summary <- summarize_rctd_results(results)
# summary$mean_proportions: Mean proportion per cell type
# summary$dominant_cell_types: Count of spots per dominant type
# summary$spot_classes: Classification counts (doublet mode)
# summary$pure_spots: Spots with >80% single type
# summary$mixed_spots: Spots with multiple cell types
```

## Key Parameters

### Deconvolution

| Parameter | Default | Description |
|-----------|---------|-------------|
| `doublet_mode` | "doublet" | "doublet", "full", or "multi" |
| `max_cores` | 4 | Parallel cores |
| `gene_cutoff` | 0.000125 | Min gene expression for platform norm |
| `fc_cutoff` | 0.5 | Min logFC for marker selection |
| `UMI_min` | 100 | Minimum UMI per spot |
| `test_mode` | FALSE | Quick test mode (reduced parameters) |

### Visualization

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cell_types` | NULL | Cell types to plot (NULL = all) |
| `layout` | "grid" | "grid" or "individual" |
| `point_size` | 1 | Size of points in spatial plots |

## Expected Runtime

| Dataset Size | Create Objects | Deconvolution | Visualization |
|--------------|---------------|---------------|---------------|
| 100 spots, 3 types | <5s | 10-30s | <5s |
| 1K spots, 5 types | 10-30s | 2-5min | 10-30s |
| 10K spots, 10 types | 1-5min | 15-30min | 1-5min |

*Runtime estimates on modern CPU with 4 cores. Doublet mode faster than full mode.*

## Error Handling

### Common Errors and Solutions

**No common genes**
```
Error: No common genes between spatial and reference data
```
→ Check that rownames (gene names) match between datasets

**Mismatched dimensions**
```
Error: Length of cell_types must match ncol(reference_counts)
```
→ Ensure cell_types vector has correct length

**Missing cell type names**
```
Error: cell_types must be a named vector with cell barcodes as names
```
→ Add names: `names(cell_types) <- colnames(reference_counts)`

**Too few cells per type**
```
Error: process_cell_type_info error: need a minimum of 25 cells
```
→ Merge rare cell types or collect more reference data

**spacexr not installed**
```
Error: spacexr package required
```
→ Install: `devtools::install_github("dmcable/spacexr")`

## Visualization Functions

### Spatial Plots

```r
# Individual cell type proportions
plot_rctd_proportions(results, cell_types = c("A", "B"))

# Dominant cell types
plot_rctd_dominant(results, min_proportion = 0.3)

# Doublet classification
plot_rctd_doublets(results)
```

### Distribution Plots

```r
# Violin/box plots
plot_rctd_distribution(results, plot_type = "violin")

# Mean proportions bar chart
plot_rctd_mean_props(results)

# Heatmap (sampled spots)
plot_rctd_heatmap(results, n_spots = 100)

# Scatter comparison
plot_rctd_scatter(results, "T_cell", "B_cell")
```

## Utility Functions

### Parameter Recommendations

```r
# Get recommended parameters 根据数据特征（spot数量、细胞类型数）自动推荐最优的 RCTD 运行参数，避免用户手动调参
params <- recommend_rctd_params(n_spots = 1000, n_cell_types = 5)
# params$max_cores: Recommended cores
# params$doublet_mode: Recommended mode
# params$gene_cutoff: Recommended cutoff
```

### Result Filtering

```r
# Filter spots by UMI
filtered <- filter_rctd_spots(results, min_umi = 100, max_umi = 10000)

# Get high purity spots
pure_spots <- get_high_purity_spots(results, purity_threshold = 0.8)

# Get mixed spots
mixed_spots <- get_mixed_spots(results, max_dominant_prop = 0.6)
```

### Comparison

```r
# Compare multiple samples
comparison <- compare_rctd_results(
  list(Sample1 = results1, Sample2 = results2)
)

# Merge cell types
merged <- merge_rctd_cell_types(
  results,
  merge_map = list(
    Immune = c("T_cell", "B_cell", "Macrophage"),
    Stromal = c("Fibroblast", "Endothelial")
  )
)
```

### Entropy Analysis

```r
# Calculate proportion entropy (mixing measure)
entropy <- calculate_proportion_entropy(results, normalized = TRUE)

# High entropy = mixed spots, Low entropy = pure spots
```

## Related Skills

- [bio-spatial-transcriptomics-deconvolution-card-r](../bio-spatial-transcriptomics-deconvolution-card-r/SKILL.md) - CARD deconvolution
- [bio-spatial-transcriptomics-deconvolution-cell2location](../bio-spatial-transcriptomics-deconvolution-cell2location/SKILL.md) - cell2location (Python)
- [bio-spatial-transcriptomics-deconvolution-spotlight-r](../bio-spatial-transcriptomics-deconvolution-spotlight-r/SKILL.md) - SPOTlight (R)

## References

1. Cable et al. (2022). Robust decomposition of cell type mixtures in spatial transcriptomics. *Nature Methods*, 19, 711-718.
2. spacexr GitHub: https://github.com/dmcable/spacexr
