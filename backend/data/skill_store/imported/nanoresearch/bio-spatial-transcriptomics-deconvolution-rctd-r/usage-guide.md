# RCTD Usage Guide

## Overview

RCTD (Robust Cell Type Deconvolution) is a statistical method for spatial transcriptomics deconvolution that models platform effects and performs doublet detection. It uses maximum likelihood estimation with platform effect normalization to accurately estimate cell type proportions at each spatial spot.

## When to Use

- **Doublet detection needed**: When you need to classify spots as singlets, doublets, or uncertain
- **Platform effects matter**: When correcting differences between scRNA-seq and spatial platforms
- **Rigorous statistical inference**: Maximum likelihood estimation with iterative refinement
- **Multiple modes**: Support for full deconvolution, doublet mode (1-2 cell types), or multi-cell mode

## When Not to Use

- **Very fast results needed**: RCTD is slower than lightweight methods like SPOTlight
- **No reference available**: Requires annotated single-cell reference
- **Simple visualization only**: For quick exploration, consider SPOTlight first

## Prerequisites

### Required Packages

```r
if (!require("devtools", quietly = TRUE))
    install.packages("devtools")

devtools::install_github("dmcable/spacexr", build_vignettes = FALSE)
```

### Data Format

Input requirements:
- **Spatial counts**: Raw count matrix (genes x spots)
- **Spatial coordinates**: DataFrame with x, y columns (optional but recommended)
- **Reference counts**: Single-cell count matrix (genes x cells)
- **Cell type labels**: Named factor of cell types (names = cell barcodes)

## Step-by-Step Guide

### Step 1: Prepare Data

```r
library(Matrix)

# Load your data
spatial_counts <- readMM("spatial_counts.mtx")  # or from Seurat
spatial_coords <- read.csv("spatial_coords.csv")
ref_counts <- readMM("reference_counts.mtx")
cell_types <- readRDS("cell_types.rds")  # named factor

# Ensure proper formatting
rownames(spatial_coords) <- colnames(spatial_counts)
colnames(spatial_coords) <- c("x", "y")
```

### Step 2: Validate Input

```r
source("scripts/r/core_analysis.R")

validation <- validate_rctd_input(
  spatial_counts = spatial_counts,
  spatial_coords = spatial_coords,
  reference_counts = ref_counts,
  cell_types = cell_types
)

if (!validation$valid) {
  stop(validation$errors)
}

cat(sprintf("Common genes: %d\n", validation$stats$n_common_genes))
cat(sprintf("Cell types: %d\n", validation$stats$n_cell_types))
cat(sprintf("Spots: %d\n", validation$stats$n_spots))
```

### Step 3: Get Parameter Recommendations

```r
source("scripts/r/utils.R")

params <- recommend_rctd_params(
  n_spots = validation$stats$n_spots,
  n_cell_types = validation$stats$n_cell_types
)

cat(sprintf("Recommended mode: %s\n", params$doublet_mode))
cat(sprintf("Recommended cores: %d\n", params$max_cores))
cat(params$message)
```

**Recommendation Logic and Rationale:**

The `recommend_rctd_params()` function provides heuristic parameter recommendations based on your dataset characteristics to optimize runtime and accuracy without manual tuning.

| Parameter | Recommendation Logic | Rationale |
|-----------|---------------------|-----------|
| **`max_cores`** | < 500 spots → 2 cores<br>500-5000 spots → 4 cores<br>> 5000 spots → 8 cores | Small datasets have high parallelization overhead; large datasets benefit from more cores |
| **`doublet_mode`** | ≤ 8 cell types → "doublet"<br>> 8 cell types → "full" | Visium spots typically contain 1-2 cell types; high-resolution data (Slide-seq, MERFISH) may have more |
| **`gene_cutoff`** | < 1000 spots → 0.000125<br>≥ 1000 spots → 0.0001 | Platform effect normalization threshold; slightly relaxed for larger datasets |
| **`fc_cutoff`** | Fixed at 0.5 | Minimum log fold change for selecting marker genes (RCTD default) |
| **`UMI_min`** | Fixed at 100 | Minimum UMI count per spot to filter low-quality spots |

**When to Override Recommendations:**

- Use `doublet_mode = "full"` for high-resolution technologies (Slide-seq, MERFISH) even with few cell types
- Reduce `max_cores` if memory is limited
- Adjust `gene_cutoff` if marker gene selection appears too strict (increase) or too lenient (decrease)

### Step 4: Run RCTD

```r
results <- run_rctd(
  spatial_counts = spatial_counts,
  spatial_coords = spatial_coords,
  reference_counts = ref_counts,
  cell_types = cell_types,
  doublet_mode = params$doublet_mode,  # "doublet", "full", or "multi"
  max_cores = params$max_cores,
  gene_cutoff = 0.000125,
  fc_cutoff = 0.5
)
```

**Parameters explained:**
- `doublet_mode`: "doublet" (1-2 cell types, best for Visium), "full" (unlimited cell types, best for high-res), or "multi" (greedy algorithm)
- `max_cores`: Parallel cores for faster computation
- `gene_cutoff`: Minimum gene expression for platform effect normalization
- `fc_cutoff`: Minimum log fold change for marker gene selection

### Step 5: Extract and Explore Results

```r
# Get cell type proportions
props <- extract_proportions_rctd(results, normalize = TRUE)
head(props)

# Summary statistics
summary <- summarize_rctd_results(results)
print(summary$mean_proportions)
print(summary$dominant_cell_types)

# Top cell types per spot
top_types <- get_top_cell_types(results, n_top = 2)
head(top_types)
```

### Step 6: Doublet Analysis (Doublet Mode Only)

```r
# Get doublet predictions
doublet_preds <- get_doublet_predictions(results)
head(doublet_preds)

# Summary of spot classification
print(summary$spot_classes)
cat(sprintf("Singlet spots: %d\n", summary$singlet_spots))
cat(sprintf("Doublet spots: %d\n", summary$doublet_certain))
```

### Step 7: Visualize

```r
source("scripts/r/visualization.R")

# Spatial proportion maps for specific cell types
plot_rctd_proportions(results, cell_types = c("T_cell", "B_cell", "Macrophage"))

# Dominant cell type per spot
plot_rctd_dominant(results, min_proportion = 0.3)

# Doublet classification map (doublet mode only)
plot_rctd_doublets(results)

# Distribution of proportions
plot_rctd_distribution(results, plot_type = "violin")

# Mean proportions bar chart
plot_rctd_mean_props(results)

# Comprehensive summary
plot_rctd_summary(results, output_dir = "./rctd_plots")
```

### Step 8: Export Results

```r
export_rctd_results(
  results,
  output_dir = "./rctd_output",
  prefix = "sample1"
)

# Generate text report
report <- create_rctd_report(results, "rctd_report.txt")
cat(report)
```

## Advanced Usage

### Seurat Integration

```r
# Use Seurat objects directly
results <- run_rctd_seurat(
  spatial_seurat = spatial_obj,
  reference_seurat = ref_obj,
  cell_type_column = "cell_type",
  coord_columns = c("imagerow", "imagecol"),
  doublet_mode = "doublet"
)

# Export results back to Seurat
spatial_obj <- export_rctd_to_seurat(
  spatial_obj,
  results,
  assay_name = "RCTD"
)
```

### Filtering Results

```r
# Filter spots by UMI
filtered <- filter_rctd_spots(results, min_umi = 100, max_umi = 10000)

# Get high purity spots (>80% single cell type)
pure_spots <- get_high_purity_spots(results, purity_threshold = 0.8)

# Get mixed spots (<60% dominant type)
mixed_spots <- get_mixed_spots(results, max_dominant_prop = 0.6)

# Calculate entropy (mixing measure)
entropy <- calculate_proportion_entropy(results, normalized = TRUE)
```

### Comparing Multiple Samples

```r
# Run RCTD on multiple samples
results_list <- list(
  Sample1 = run_rctd(...),
  Sample2 = run_rctd(...)
)

# Compare proportions
comparison <- compare_rctd_results(results_list)
print(comparison)
```

### Merging Cell Types

```r
# Merge related cell types in results
merged <- merge_rctd_cell_types(
  results,
  merge_map = list(
    Immune = c("T_cell", "B_cell", "Macrophage"),
    Stromal = c("Fibroblast", "Endothelial")
  )
)
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `doublet_mode` | "doublet" | "doublet", "full", or "multi" |
| `max_cores` | 4 | Parallel cores |
| `gene_cutoff` | 0.000125 | Min gene expression for platform norm |
| `fc_cutoff` | 0.5 | Min logFC for marker selection |
| `UMI_min` | 100 | Minimum UMI per spot |
| `UMI_max` | 20000000 | Maximum UMI per spot |
| `test_mode` | FALSE | Quick test mode (reduced params) |

## Output

| Output | Description |
|--------|-------------|
| `weights` | Cell type proportions per spot (full mode) |
| `weights_doublet` | Proportions in doublet mode |
| `results_df` | Spot classification (singlet/doublet/reject) |
| `cell_type_info` | Cell type information from reference |

### Spot Classification (Doublet Mode)

| Class | Description |
|-------|-------------|
| `singlet` | 1 cell type on pixel |
| `doublet_certain` | 2 cell types, confident prediction |
| `doublet_uncertain` | 2 cell types, only 1 confident |
| `reject` | No prediction (poor quality or ambiguous) |

## Best Practices

1. **Reference quality**: Use high-quality annotated scRNA-seq with ≥25 cells per type
2. **Cell type selection**: Include all expected cell types
3. **Mode selection**: Use "doublet" for Visium, "full" for high-resolution data (Slide-seq, MERFISH)
4. **Multiple cores**: Use `max_cores > 1` for faster computation
5. **Validation**: Always validate input before running
6. **Platform effects**: RCTD normalizes automatically, but check results

## Comparison with Other Methods

| Feature | RCTD | CARD | SPOTlight |
|---------|------|------|-----------|
| Doublet detection | ✅ Yes | ❌ No | ❌ No |
| Platform effect correction | ✅ Yes | ❌ No | ❌ No |
| Speed | 🐢 Medium | 🐢 Slow | 🚀 Fast |
| ct2loc imputation | ❌ No | ✅ Yes | ❌ No |
| Multi-sample | ✅ Yes | ✅ Yes | ❌ No |

Use RCTD when:
- You need doublet detection
- Platform effects may be significant
- You want rigorous statistical inference

Use CARD when spatial smoothing is important. Use SPOTlight for fast exploration.

## AI Agent Test Cases

### Basic Usage
> "Run RCTD on my Visium data with scRNA-seq reference"

```r
results <- run_rctd(
  spatial_counts = spatial_counts,
  spatial_coords = spatial_coords,
  reference_counts = ref_counts,
  cell_types = cell_types,
  doublet_mode = "doublet",
  max_cores = 4
)
```

### With Seurat
> "Use RCTD with my Seurat objects"

```r
results <- run_rctd_seurat(
  spatial_seurat = spatial_obj,
  reference_seurat = ref_obj,
  cell_type_column = "cell_type",
  doublet_mode = "doublet"
)
```

### Doublet Analysis
> "Run RCTD in doublet mode and identify mixed spots"

```r
results <- run_rctd(..., doublet_mode = "doublet")
doublet_preds <- get_doublet_predictions(results)
```

### Visualization
> "Plot RCTD cell type proportions on tissue"

```r
plot_rctd_proportions(results, cell_types = c("T_cell", "B_cell"))
plot_rctd_dominant(results)
plot_rctd_summary(results)
```

### High Purity Spots
> "Get spots with >80% of a single cell type"

```r
pure_spots <- get_high_purity_spots(results, purity_threshold = 0.8)
```

## Troubleshooting

### No common genes
```r
# Check gene overlap
validation <- validate_rctd_input(...)
cat(sprintf("Common genes: %d\n", validation$stats$n_common_genes))

# If low, check gene naming
head(rownames(spatial_counts))
head(rownames(reference_counts))
```

### Missing cell type names
```
Error: cell_types must be a named vector with cell barcodes as names
```
Fix:
```r
names(cell_types) <- colnames(reference_counts)
```

### Too few cells per type
```
Error: process_cell_type_info error: need a minimum of 25 cells
```
Fix: Merge rare cell types or collect more reference data
```r
# Merge rare types
cell_types <- ifelse(cell_types %in% c("Rare1", "Rare2"), "Rare_combined", cell_types)
```

### Memory issues
```r
# Run with fewer cores
results <- run_rctd(..., max_cores = 1)

# Or subset spots
spatial_counts <- spatial_counts[, 1:1000]
spatial_coords <- spatial_coords[1:1000, ]
```

### Poor convergence
- Check that reference includes all expected cell types
- Try adjusting `gene_cutoff` (lower for more genes, higher for fewer)
- Ensure spatial data quality (sufficient UMIs per spot)

## References

1. Cable et al. (2022). Robust decomposition of cell type mixtures in spatial transcriptomics. *Nature Methods*, 19, 711-718.
2. spacexr GitHub: https://github.com/dmcable/spacexr
