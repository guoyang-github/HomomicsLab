# Spatial Ro/e Usage Guide

## Overview

Spatial Ro/e analysis quantifies whether cell types co-occur in spatial proximity more or less frequently than expected by chance. This is useful for:

- **Identifying cellular niches**: Groups of cell types that spatially cluster
- **Detecting exclusion patterns**: Cell types that avoid each other
- **Comparing samples**: How spatial organization changes across conditions
- **Validating deconvolution**: Check if predicted proportions make spatial sense

## When to Use Spatial Ro/e

### Use Cases

| Scenario | Example |
|----------|---------|
| Tumor microenvironment | Do cancer cells co-localize with immunosuppressive macrophages? |
| Neural invasion | Do Schwann cells cluster with EMT+ cancer cells in high NI? |
| Immune organization | Are T cells excluded from tumor cores? |
| Development | How do cell types organize during tissue formation? |

### Comparison to Other Methods

| Method | Measures | Best For |
|--------|----------|----------|
| **Spatial Ro/e** | Co-occurrence ratios | Global spatial patterns |
| **MISTy** | Interactions at multiple scales | Multi-scale analysis |
| **Giotto/CellCharter** | Cell type niches | Unbiased niche discovery |
| **Ligand-receptor** | Molecular interactions | Specific L-R pairs |

## Quick Start

### 1. Basic Workflow

```r
library(Seurat)

# Source functions
source("scripts/r/spatial_roe_analysis.R")
source("scripts/r/spatial_roe_visualization.R")

# Load spatial data
seurat_obj <- Load10X_Spatial("path/to/spatial/")

# Add cell type annotations (from deconvolution or mapping)
seurat_obj$cell_type <- cell_type_labels

# Run spatial Ro/e
result <- run_spatial_roe(
    seurat_obj,
    cell_type_col = "cell_type",
    method = "radius",
    radius = 150  # Adjust based on your data
)

# Visualize
plot_spatial_roe_heatmap(result)
plot_spatial_roe_network(result, min_roe = 1.5)
```

### 2. Determine Optimal Radius

```r
# Test different radii
radii <- c(50, 100, 150, 200, 250)
results <- list()

for (r in radii) {
    results[[as.character(r)]] <- calculate_spatial_roe(
        cell_types, coords,
        method = "radius",
        radius = r
    )
}

# Compare number of significant interactions
sig_counts <- sapply(results, function(res) {
    sum(res$roe > 1.5 & res$statistics$p_values_adj < 0.05, na.rm = TRUE)
})

print(sig_counts)
```

## Common Use Cases

### Use Case 1: Compare High NI vs Low NI Samples

```r
# Analyze each sample separately
samples <- unique(seurat_obj$sample_id)
roe_results <- list()

for (sample in samples) {
    sub_obj <- subset(seurat_obj, sample_id == sample)

    roe_results[[sample]] <- run_spatial_roe(
        sub_obj,
        cell_type_col = "cell_subtype",
        method = "radius",
        radius = 150
    )
}

# Compare Schwann cell - Cancer cell interactions
schwann_cancer_roe <- data.frame(
    sample = samples,
    NI_status = seurat_obj$NI_status[match(samples, seurat_obj$sample_id)],
    roe = sapply(roe_results, function(r) {
        r$roe["Schwann", "Cancer_EMT"]
    })
)

# Plot
ggplot(schwann_cancer_roe, aes(x = NI_status, y = roe, fill = NI_status)) +
    geom_boxplot() +
    geom_jitter(width = 0.2) +
    labs(title = "Schwann-Cancer EMT Co-localization by NI Status")
```

### Use Case 2: Post-Deconvolution Analysis

```r
# After cell2location deconvolution
deconv_props <- t(as.matrix(seurat_obj@assays[["predictions"]]@data))

# Run spatial Ro/e on proportions
result <- calculate_spatial_roe(
    cell_types = deconv_props,
    coords = GetTissueCoordinates(seurat_obj),
    method = "radius",
    radius = 100
)

# Find strongest co-localizations
roe_df <- spatial_roe_to_dataframe(result)
top_coloc <- roe_df %>%
    filter(cell_type_a != cell_type_b, roe > 2) %>%
    arrange(desc(roe))

print(top_coloc)
```

### Use Case 3: Neighborhood Visualization

```r
# Show neighborhoods for specific spots
highlight_spots <- c("AAACAACGAATAGTTC-1", "AAACCGGGTAGGTACC-1")

# Create neighborhood map
p <- plot_neighborhood_map(result, coords) +
    geom_point(
        data = coords[highlight_spots, ],
        aes(x = x, y = y),
        color = "red", size = 3, shape = 21, stroke = 2
    )

print(p)
```

### Use Case 4: Cell Type Specific Analysis

```r
# Focus on macrophage interactions
macrophage_types <- c("Macrophage_M1", "Macrophage_M2", "Macrophage_NLRP3")

# Subset Ro/e matrix
macrophage_idx <- match(macrophage_types, colnames(result$roe))
macrophage_roe <- result$roe[macrophage_idx, macrophage_idx]

# Visualize
heatmap(macrophage_roe,
        main = "Macrophage Subtype Co-localization",
        col = colorRampPalette(c("blue", "white", "red"))(100))
```

### Use Case 5: Network Analysis

```r
# Create network with significance filtering
p_network <- plot_spatial_roe_network(
    result,
    min_roe = 1.5,
    layout = "fr",          # Fruchterman-Reingold layout
    node_color_by = "degree"
)

print(p_network)
ggsave("spatial_network.pdf", p_network, width = 10, height = 10)
```

## Parameter Selection Guide

### Choosing Radius

| Platform | Typical Spot Size | Recommended Radius |
|----------|------------------|-------------------|
| 10x Visium | 55μm | 100-150μm |
| Slide-seq | 10μm | 20-30μm |
| MERFISH | 1-2μm | 5-10μm |

### Choosing k for k-NN

- **Small k (5-10)**: Local interactions, sensitive to noise
- **Medium k (15-25)**: Balanced view
- **Large k (50+)**: Regional patterns, smoother results

### min_neighbors

Spots with fewer neighbors are excluded from analysis:
- Lower values (1-2): Include edge spots, more noise
- Higher values (5+): More stringent, fewer spots

## Output Interpretation

### Ro/e Values

```r
# Example Ro/e matrix interpretation
#               Macrophage  T_cell  Cancer
# Macrophage        2.5      1.2     1.8
# T_cell            1.2      1.8     0.6
# Cancer            1.8      0.6     2.2
```

- Macrophages self-cluster (2.5) and co-localize with cancer (1.8)
- T cells avoid cancer areas (0.6)
- All cell types self-cluster (diagonal > 1)

### Statistical Significance

```r
# Check significant interactions
sig_pairs <- spatial_roe_to_dataframe(result) %>%
    filter(significant, roe > 1.5, cell_type_a != cell_type_b) %>%
    arrange(desc(roe))

# These represent robust co-localizations
```

## Troubleshooting

### Issue: All Ro/e ≈ 1

**Causes**:
- Radius too large (whole tissue = one neighborhood)
- Cell types not spatially patterned
- Insufficient cell type resolution

**Solutions**:
```r
# Try smaller radius
result <- calculate_spatial_roe(cell_types, coords, radius = 50)

# Use k-NN instead
result <- calculate_spatial_roe(cell_types, coords, method = "knn", k = 5)
```

### Issue: Too many NAs

**Causes**:
- min_neighbors too high
- Sparse data at edges
- Cell types with very few spots

**Solutions**:
```r
# Lower min_neighbors
result <- calculate_spatial_roe(cell_types, coords, min_neighbors = 1)

# Filter rare cell types
cell_counts <- table(cell_types)
common_types <- names(cell_counts)[cell_counts >= 10]
cell_types_filtered <- cell_types[cell_types %in% common_types]
coords_filtered <- coords[cell_types %in% common_types, ]
```

### Issue: Network plot too cluttered

**Solutions**:
```r
# Increase min_roe threshold
plot_spatial_roe_network(result, min_roe = 2.0)

# Show only top N interactions
roe_df <- spatial_roe_to_dataframe(result)
top_10 <- head(roe_df[roe_df$cell_type_a != roe_df$cell_type_b, ], 10)
# Create custom network from top_10
```

## Best Practices

1. **Validate radius choice**: Visualize neighborhoods on tissue image
2. **Compare methods**: Try both radius and k-NN, compare results
3. **Subsample for testing**: Run on subset first to optimize parameters
4. **Account for tissue structure**: Consider different radii for different regions
5. **Validate with images**: Compare Ro/e results to H&E or IF images

## Advanced: Custom Analysis

### Region-Specific Analysis

```r
# Analyze tumor vs stroma separately
regions <- c("tumor", "stroma", "interface")
results_by_region <- list()

for (region in regions) {
    mask <- seurat_obj$region == region
    results_by_region[[region]] <- calculate_spatial_roe(
        cell_types[mask],
        coords[mask, ],
        method = "radius",
        radius = 100
    )
}

# Compare tumor-stroma interface vs tumor core
interface_roe <- results_by_region[["interface"]]$roe
tumor_roe <- results_by_region[["tumor"]]$roe

# Calculate difference
diff_roe <- interface_roe - tumor_roe
```

### Integration with Cell-Cell Communication

```r
# Run Ro/e to find co-localized pairs
roe_result <- calculate_spatial_roe(cell_types, coords)

# Find co-localized cell type pairs
co_df <- spatial_roe_to_dataframe(roe_result) %>%
    filter(roe > 1.5, cell_type_a != cell_type_b)

# Check if these pairs have ligand-receptor interactions
for (i in 1:nrow(co_df)) {
    ct_a <- co_df$cell_type_a[i]
    ct_b <- co_df$cell_type_b[i]

    # Run CellChat or Liana on these cell types
    # ... LR analysis code ...
}
```
