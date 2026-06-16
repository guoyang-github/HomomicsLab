# Ro/e Differential Abundance - Usage Guide

## Overview

The Ro/e (Ratio of Observed to Expected) method quantifies how cell type proportions differ from what would be expected if cells were randomly distributed across groups. It's particularly useful for:

- **Case-control studies**: Tumor vs Normal, Disease vs Healthy
- **Treatment comparisons**: Before vs After, Drug vs Vehicle
- **Stratified analysis**: High vs Low risk groups

## When to Use Ro/e vs Other Methods

| Method | Use When | Output |
|--------|----------|--------|
| **Ro/e** | Comparing proportions across discrete groups | Enrichment/depletion ratios |
| **Milo** | Finding DA on cell neighborhood graph | DA neighborhoods |
| **Diffcyt** | Cytometry data with clusters | Statistical tests per cluster |
| **scCODA** | Compositional data with covariates | Bayesian credible intervals |

## Quick Start

### 1. Basic Analysis

```r
library(Seurat)

# Source functions
source("scripts/r/roe_analysis.R")
source("scripts/r/roe_visualization.R")

# Load your data
seurat_obj <- readRDS("your_data.rds")

# Run Ro/e analysis
roe_result <- run_roe_analysis(
    seurat_obj,
    cell_type_col = "cell_type",
    group_col = "condition"  # e.g., "High_NI", "Low_NI"
)

# View results
print(roe_result)

# Convert to data frame
roe_df <- roe_to_dataframe(roe_result)
head(roe_df)
```

### 2. Create Lollipop Plot

```r
# Lollipop chart for comparing High_NI vs Low_NI
p <- plot_roe_lollipop(
    roe_result,
    compare_group = "High_NI",
    highlight_sig = TRUE,
    color_by_depletion = TRUE,
    title = "Cell Type Enrichment in High NI"
)
print(p)

# Save plot
ggsave("roe_lollipop.png", p, width = 8, height = 6, dpi = 300)
```

## Common Use Cases

### Use Case 1: PDAC Neural Invasion Analysis

Reproduce the PDAC paper analysis comparing High NI vs Low NI:

```r
# Load PDAC data with NI annotations
pdac <- readRDS("pdac_annotated.rds")

# Run Ro/e
roe_result <- run_roe_analysis(
    pdac,
    cell_type_col = "cell_subtype",  # Use fine-grained annotations
    group_col = "NI_status"          # "High_NI" or "Low_NI"
)

# Lollipop plot for High_NI group
p_high <- plot_roe_lollipop(
    roe_result,
    compare_group = "High_NI",
    title = "Cell Type Enrichment in High Neural Invasion"
)

# Lollipop plot for Low_NI group
p_low <- plot_roe_lollipop(
    roe_result,
    compare_group = "Low_NI",
    title = "Cell Type Enrichment in Low Neural Invasion"
)

# Arrange together
cowplot::plot_grid(p_high, p_low, ncol = 2)
```

### Use Case 2: Bootstrap Confidence Intervals

When you need statistical confidence in the Ro/e estimates:

```r
# Calculate with bootstrap CIs (takes longer)
roe_result <- calculate_roe_bootstrap(
    cell_types = seurat_obj$cell_type,
    groups = seurat_obj$condition,
    n_bootstrap = 1000,
    conf_level = 0.95
)

# Results include confidence intervals
roe_df <- roe_to_dataframe(roe_result)

# Plot with CI
library(ggplot2)
ggplot(roe_df, aes(x = cell_type, y = roe)) +
    geom_pointrange(aes(ymin = ci_lower, ymax = ci_upper, color = group)) +
    geom_hline(yintercept = 1, linetype = "dashed") +
    coord_flip() +
    theme_minimal()
```

### Use Case 3: Multi-Region Analysis

Analyze separately by tissue region:

```r
# Run subset analysis
roe_result <- run_roe_analysis(
    seurat_obj,
    cell_type_col = "cell_type",
    group_col = "NI_status",
    subset_col = "tissue_region"  # Analyzes each region separately
)

# Access individual region results
roe_result$tumor$roe
roe_result$normal$roe
roe_result$stroma$roe

# Plot all regions
plots <- plot_roe_multi(roe_result, plot_type = "lollipop")
```

### Use Case 4: Heatmap Visualization

For comparing multiple groups simultaneously:

```r
# Create heatmap
p_heatmap <- plot_roe_heatmap(
    roe_result,
    cluster_rows = TRUE,
    cluster_cols = FALSE,
    value_text_size = 3,
    title = "Ro/e Across All Groups"
)
print(p_heatmap)
```

### Use Case 5: Dot Plot

Alternative visualization showing both Ro/e and proportions:

```r
# Dot plot with significance highlighting
p_dot <- plot_roe_dotplot(
    roe_result,
    size_by = "proportion",  # Size by observed proportion
    color_scale = "roe",     # Color by Ro/e value
    title = "Cell Type Enrichment and Abundance"
)
print(p_dot)
```

### Use Case 6: Custom Cell Type Ordering

Control the order of cell types in plots:

```r
# Get results as data frame
roe_df <- roe_to_dataframe(roe_result)

# Define custom order
cell_type_order <- c(
    "Schwann_cells",
    "Neurons",
    "Cancer_cells_EMT",
    "Cancer_cells_classical",
    "Macrophages_M1",
    "Macrophages_M2",
    "T_cells_CD4",
    "T_cells_CD8"
)

# Apply order
roe_df$cell_type <- factor(roe_df$cell_type, levels = cell_type_order)

# Create custom lollipop plot
ggplot(roe_df, aes(x = cell_type, y = roe)) +
    geom_segment(aes(x = cell_type, xend = cell_type, y = 1, yend = roe)) +
    geom_point(aes(size = observed_prop, color = roe > 1)) +
    coord_flip() +
    theme_minimal()
```

## Output Interpretation

### Ro/e Values

| Range | Interpretation | Biological Meaning |
|-------|----------------|-------------------|
| > 2.0 | Strong enrichment | Cell type preferentially located in this group |
| 1.5 - 2.0 | Moderate enrichment | Cell type more common than expected |
| 1.0 - 1.5 | Slight enrichment | Weak enrichment |
| 0.8 - 1.0 | Near expected | Approximately random distribution |
| 0.5 - 0.8 | Slight depletion | Cell type less common than expected |
| < 0.5 | Strong depletion | Cell type excluded from this group |

### Statistical Significance

- **Overall test**: Chi-square test of independence
- **Per-cell-type**: Fisher's exact test (adjusted for multiple testing)
- **Bootstrap CI**: Non-overlapping CI with 1 indicates significance

### Lollipop Chart Elements

- **Horizontal position**: Ro/e value (center line = 1, no enrichment)
- **Point size**: Proportion of cells (larger = more abundant)
- **Point color**: Red = enriched, Blue = depleted, Grey = neutral
- **Point shape**: Circle = significant (FDR < 0.05), X = not significant

## Troubleshooting

### Issue: All Ro/e values close to 1

**Cause**: Groups have very similar cell type compositions

**Solutions**:
- Check grouping variable is correct
- Verify cell type annotations are meaningful
- Consider finer cell type resolution

### Issue: Many "Unknown" or NA Ro/e values

**Cause**: Missing data or zero counts for some cell types

**Solutions**:
```r
# Check for NAs in input
sum(is.na(seurat_obj$cell_type))
sum(is.na(seurat_obj$condition))

# Remove cells with missing annotations
seurat_obj <- subset(seurat_obj, 
                     cell_type != "Unknown" & 
                     !is.na(condition))
```

### Issue: Bootstrap too slow

**Cause**: Large dataset with many bootstrap iterations

**Solutions**:
```r
# Reduce bootstrap iterations
roe_result <- calculate_roe_bootstrap(
    cell_types, groups,
    n_bootstrap = 500  # Faster but less precise
)

# Or skip bootstrap for initial exploration
roe_result <- calculate_roe(cell_types, groups)
```

## Best Practices

1. **Pre-filtering**: Remove cell types with very few cells (< 10)
2. **Annotation quality**: Use well-validated cell type labels
3. **Group balance**: Ideally have similar total cell numbers per group
4. **Multiple testing**: Always consider FDR-adjusted p-values
5. **Visualization**: Use lollipop plots for 2-group comparisons, heatmaps for multi-group

## Example Workflow

```r
# Complete analysis workflow
library(Seurat)
library(dplyr)

# 1. Load data
seurat_obj <- readRDS("annotated_data.rds")

# 2. Quality check
print(table(seurat_obj$cell_type, seurat_obj$condition))

# 3. Run Ro/e
roe_result <- run_roe_analysis(
    seurat_obj,
    cell_type_col = "cell_type",
    group_col = "condition"
)

# 4. Get tidy results
roe_df <- roe_to_dataframe(roe_result)

# 5. Filter significant results
sig_results <- roe_df %>%
    filter(significant, roe > 1.5 | roe < 0.67) %>%
    arrange(desc(roe))

print(sig_results)

# 6. Visualize
p1 <- plot_roe_heatmap(roe_result)
p2 <- plot_roe_lollipop(roe_result, compare_group = "Treatment")

# 7. Save
ggsave("roe_heatmap.pdf", p1, width = 8, height = 10)
ggsave("roe_lollipop.pdf", p2, width = 8, height = 6)
```
