# CARD Usage Guide

## Overview

CARD (Conditional Autoregressive-based Deconvolution) is a statistical method for spatial transcriptomics deconvolution that leverages spatial correlation structure between neighboring spots. It uses a conditional autoregressive (CAR) model to estimate cell type proportions while accounting for spatial dependencies.

## When to Use

- **Spatial correlation matters**: When neighboring spots should have similar cell type compositions
- **Tissue architecture analysis**: For studying spatial organization of cell types
- **High-resolution imputation**: When you need refined cell type maps beyond original spot resolution
- **Reference-free analysis**: When scRNA-seq reference is unavailable but marker genes are known

## When Not to Use

- **Fast results needed**: CARD is slower than non-spatial methods like SPOTlight
- **No spatial pattern**: If cell types are randomly distributed without spatial structure
- **Very small datasets**: CARD benefits from sufficient spots to model spatial correlation

## Prerequisites

### Installation

```r
# Install CARD from GitHub
if (!requireNamespace("devtools", quietly = TRUE)) {
    install.packages("devtools")
}
devtools::install_github("YingMa0107/CARD")

# Install dependencies
install.packages(c("Matrix", "ggplot2"))
BiocManager::install(c("SingleCellExperiment", "SummarizedExperiment"))

# Optional for visualization
install.packages(c("scatterpie", "ggcorrplot"))

# Optional for imputation
install.packages("concaveman")
```

### Data Requirements

- **Reference scRNA-seq**: Gene expression matrix (genes x cells) with cell type labels
- **Spatial data**: Gene expression matrix (genes x spots) with spatial coordinates
- **Spatial coordinates**: Data frame with x, y coordinates matching spot barcodes
- **Minimum requirements**:
  - Reference: 20+ cells per cell type
  - Spatial: 50+ spots
  - Genes: 100+ common genes between reference and spatial

## Step-by-Step Guide

### Step 1: Data Preparation

#### From Seurat Objects

```r
library(Seurat)
library(CARD)

# Load Seurat objects
ref_obj <- readRDS("reference_sc.rds")
spatial_obj <- readRDS("spatial_data.rds")

# Extract counts and metadata
sc_count <- GetAssayData(ref_obj, slot = "counts")
sc_meta <- data.frame(
    cell_type = ref_obj$cell_type,
    sample = ref_obj$sample,
    row.names = colnames(ref_obj)
)

spatial_count <- GetAssayData(spatial_obj, slot = "counts")
spatial_location <- GetTissueCoordinates(spatial_obj)

# Ensure column names match
head(colnames(spatial_count))
head(rownames(spatial_location))
```

#### From Matrix Files

```r
library(Matrix)

# Load matrix files
sc_count <- readMM("reference_counts.mtx")
spatial_count <- readMM("spatial_counts.mtx")

# Load metadata
sc_meta <- read.csv("reference_meta.csv", row.names = 1)
spatial_location <- read.csv("spatial_coords.csv", row.names = 1)

# Ensure gene names are set
rownames(sc_count) <- readLines("reference_genes.txt")
rownames(spatial_count) <- readLines("spatial_genes.txt")
```

### Step 2: Data Validation

```r
# Basic validation
cat("scRNA-seq dimensions:", nrow(sc_count), "genes x", ncol(sc_count), "cells\n")
cat("Spatial dimensions:", nrow(spatial_count), "genes x", ncol(spatial_count), "spots\n")
cat("Cell types:", length(unique(sc_meta$cell_type)), "\n")

# Check gene overlap
common_genes <- intersect(rownames(sc_count), rownames(spatial_count))
cat("Common genes:", length(common_genes), "\n")

if (length(common_genes) < 100) {
    stop("Insufficient common genes. Check gene naming consistency.")
}

# Check barcode matching
if (!all(rownames(sc_meta) == colnames(sc_count))) {
    stop("scRNA-seq metadata rownames must match count matrix colnames")
}

if (!all(rownames(spatial_location) == colnames(spatial_count))) {
    stop("Spatial location rownames must match spatial count colnames")
}
```

### Step 3: Create CARD Object

```r
# Create CARD object with quality control
CARD_obj <- createCARDObject(
    sc_count = sc_count,
    sc_meta = sc_meta,
    spatial_count = spatial_count,
    spatial_location = spatial_location,
    ct.varname = "cell_type",        # Column name for cell type in sc_meta
    ct.select = NULL,                # Use all cell types (or specify vector)
    sample.varname = NULL,           # NULL for single sample
    minCountGene = 100,              # Min count per gene for filtering
    minCountSpot = 5                 # Min count per spot for filtering
)

# Check object contents
cat("CARD object created:\n")
cat("  Cell types:", paste(CARD_obj@info_parameters$ct.select, collapse = ", "), "\n")
```

### Step 4: Run CARD Deconvolution

```r
# Run deconvolution (this may take several minutes)
cat("Running CARD deconvolution...\n")
CARD_obj <- CARD_deconvolution(CARD_obj)

# Extract results
proportions <- CARD_obj@Proportion_CARD

# View summary
cat("\nResults summary:\n")
cat("  Spots:", nrow(proportions), "\n")
cat("  Cell types:", ncol(proportions), "\n")
cat("  Optimal phi:", CARD_obj@info_parameters$phi, "\n")

# View first few spots
head(round(proportions, 3))

# Cell type distribution
cat("\nMean proportions:\n")
print(round(colMeans(proportions), 3))
```

### Step 5: Analyze Results

```r
# Get dominant cell type per spot
dominant_ct <- colnames(proportions)[apply(proportions, 1, which.max)]
table(dominant_ct)

# Calculate spatial entropy (cell type diversity per spot)
entropy <- apply(proportions, 1, function(x) {
    p <- x[x > 0]
    -sum(p * log(p))
})
summary(entropy)

# Find spots with mixed cell types
mixed_spots <- names(which(entropy > quantile(entropy, 0.75)))
cat("High-diversity spots:", length(mixed_spots), "\n")
```

### Step 6: Visualization

```r
# Spatial proportion maps
if (requireNamespace("ggplot2", quietly = TRUE)) {
    p <- CARD.visualize.prop(
        proportion = proportions,
        spatial_location = spatial_location,
        ct.visualize = c("T_cell", "B_cell", "Myeloid"),
        colors = c("lightblue", "lightyellow", "red"),
        NumCols = 3,
        pointSize = 3.0
    )
    print(p)
    ggplot2::ggsave("spatial_proportions.png", p, width = 12, height = 4)
}

# Scatterpie plot (shows all cell types per spot)
if (requireNamespace("scatterpie", quietly = TRUE)) {
    p <- CARD.visualize.pie(
        proportion = proportions,
        spatial_location = spatial_location,
        radius = NULL,  # Auto-calculate
        seed = 12345
    )
    print(p)
    ggplot2::ggsave("scatterpie.png", p, width = 10, height = 8)
}

# Correlation matrix between cell types
if (requireNamespace("ggcorrplot", quietly = TRUE)) {
    p <- CARD.visualize.Cor(
        proportion = proportions,
        colors = c("#91a28c", "white", "#8f2c37")
    )
    print(p)
    ggplot2::ggsave("correlation_matrix.png", p, width = 8, height = 8)
}

# Two cell type comparison on same plot
p <- CARD.visualize.prop.2CT(
    proportion = proportions,
    spatial_location = spatial_location,
    ct2.visualize = c("T_cell", "B_cell"),
    colors = list(
        c("lightblue", "lightyellow", "red"),
        c("lightblue", "lightyellow", "black")
    )
)
print(p)
```

### Step 7: Export Results

```r
# Create output directory
output_dir <- "card_results"
if (!dir.exists(output_dir)) {
    dir.create(output_dir)
}

# Export proportions
write.csv(proportions, file.path(output_dir, "proportions.csv"))

# Export dominant cell types
dominant_df <- data.frame(
    spot = rownames(proportions),
    dominant_celltype = dominant_ct,
    max_proportion = apply(proportions, 1, max)
)
write.csv(dominant_df, file.path(output_dir, "dominant_celltypes.csv"), row.names = FALSE)

# Export entropy
entropy_df <- data.frame(
    spot = names(entropy),
    entropy = entropy
)
write.csv(entropy_df, file.path(output_dir, "entropy.csv"), row.names = FALSE)

# Save full CARD object
saveRDS(CARD_obj, file.path(output_dir, "CARD_object.rds"))
```

## Advanced Usage

### High-Resolution Imputation

Impute cell type compositions at higher resolution grid locations:

```r
# Requires concaveman package
if (requireNamespace("concaveman", quietly = TRUE)) {
    cat("Running high-resolution imputation...\n")

    CARD_obj <- CARD.imputation(
        CARD_obj,
        NumGrids = 2000,    # Number of new grid locations
        ineibor = 10,       # Number of neighbors for imputation
        exclude = NULL      # Spots to exclude (optional)
    )

    # Access refined results
    refined_props <- CARD_obj@refined_prop
    refined_expr <- CARD_obj@refined_expression

    cat("Refined proportions:", nrow(refined_props), "spots\n")
    cat("Refined expression:", nrow(refined_expr), "genes\n")

    # Visualize refined proportions
    refined_coords <- data.frame(
        x = as.numeric(sapply(strsplit(rownames(refined_props), "x"), "[", 1)),
        y = as.numeric(sapply(strsplit(rownames(refined_props), "x"), "[", 2)),
        row.names = rownames(refined_props)
    )

    p <- CARD.visualize.prop(
        proportion = refined_props,
        spatial_location = refined_coords,
        ct.visualize = colnames(refined_props)[1:4],
        NumCols = 2,
        pointSize = 2.0
    )
    ggplot2::ggsave("refined_proportions.png", p, width = 12, height = 10)
}
```

### Reference-Free Deconvolution (CARDfree)

When scRNA-seq reference is unavailable, use marker genes only:

```r
# Define marker genes for each cell type
markerList <- list(
    T_cell = c("CD3D", "CD3E", "CD8A", "TRAC", "CD4"),
    B_cell = c("CD79A", "CD79B", "MS4A1", "CD19", "IGHM"),
    Myeloid = c("LYZ", "CD14", "CD68", "CSF1R", "MARCO"),
    Fibroblast = c("COL1A1", "COL1A2", "ACTA2", "PDGFRA"),
    Endothelial = c("PECAM1", "VWF", "CDH5", "ENG"),
    Epithelial = c("EPCAM", "KRT18", "KRT19", "CDH1")
)

# Create CARDfree object
CARDfree_obj <- createCARDfreeObject(
    markerList = markerList,
    spatial_count = spatial_count,
    spatial_location = spatial_location,
    minCountGene = 100,
    minCountSpot = 5
)

# Run reference-free deconvolution
CARDfree_obj <- CARD_refFree(CARDfree_obj)

# Extract results
proportions_free <- CARDfree_obj@Proportion_CARD
estimated_ref <- CARDfree_obj@estimated_refMatrix

cat("Reference-free deconvolution complete!\n")
cat("Optimal phi:", CARDfree_obj@info_parameters$phi, "\n")

# Export results
write.csv(proportions_free, file.path(output_dir, "cardfree_proportions.csv"))
write.csv(estimated_ref, file.path(output_dir, "estimated_reference.csv"))
```

### Single-Cell Mapping

Map single cells to spatial locations based on deconvolution results:

```r
# Map cells to spatial locations
# Note: This requires the original single-cell data
sce_mapped <- CARD_SCMapping(
    CARD_obj,
    shapeSpot = "Square",    # or "Circle"
    numCell = 7,             # Cells per spot (Visium: ~7, ST: ~20)
    ncore = 10               # Parallel cores
)

# Access mapped data
mapped_counts <- SummarizedExperiment::assays(sce_mapped)$counts
mapped_coords <- SummarizedExperiment::colData(sce_mapped)[, c("x", "y")]

# Summarize mapping
mapping_summary <- table(sce_mapped$cellType_list)
print(mapping_summary)
```

### Multi-Sample Analysis

```r
# Process multiple samples with same reference
samples <- c("S1", "S2", "S3")
results_list <- lapply(samples, function(s) {
    cat("Processing", s, "...\n")

    # Load sample-specific data
    sp_count <- readMM(paste0("spatial_", s, ".mtx"))
    sp_loc <- read.csv(paste0("coords_", s, ".csv"), row.names = 1)

    # Create and run CARD
    CARD_obj <- createCARDObject(
        sc_count = sc_count,           # Same reference
        sc_meta = sc_meta,
        spatial_count = sp_count,
        spatial_location = sp_loc,
        ct.varname = "cell_type",
        sample.varname = "sample"      # Specify sample info
    )

    CARD_deconvolution(CARD_obj)
})

names(results_list) <- samples

# Compare mean proportions across samples
prop_comparison <- sapply(results_list, function(x) {
    colMeans(x@Proportion_CARD)
})
print(round(prop_comparison, 3))
```

## Parameters Reference

### createCARDObject Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sc_count` | Required | Single-cell count matrix (genes x cells) |
| `sc_meta` | Required | Metadata with cell type info |
| `spatial_count` | Required | Spatial count matrix (genes x spots) |
| `spatial_location` | Required | Data frame with x, y coordinates |
| `ct.varname` | Required | Column name for cell type in sc_meta |
| `ct.select` | NULL | Cell types to include (NULL = all) |
| `sample.varname` | NULL | Sample column name (NULL = single sample) |
| `minCountGene` | 100 | Min count per gene for QC |
| `minCountSpot` | 5 | Min count per spot for QC |

### CARD_deconvolution Parameters

Set internally in CARD object:
- `isigma`: Gaussian kernel scale (default: 0.1)
- `epsilon`: Convergence threshold (default: 1e-4)
- `phi`: Grid of spatial correlation values (default: c(0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 0.99))
- `max_iter`: Maximum iterations (default: 1000)

### CARD.imputation Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `NumGrids` | 2000 | Approximate number of grid locations |
| `ineibor` | 10 | Neighbors for spatial imputation |
| `exclude` | NULL | Spots to exclude from shape detection |

### CARD_SCMapping Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `shapeSpot` | "Square" | Cell distribution shape |
| `numCell` | 5 | Cells per spot |
| `ncore` | 10 | Parallel cores |

## Understanding Phi Parameter

The phi parameter controls spatial correlation strength:

- **Low phi (<0.3)**: Weak spatial correlation, proportions more independent
- **Medium phi (0.3-0.7)**: Moderate spatial smoothing (typical for most tissues)
- **High phi (>0.7)**: Strong spatial correlation, extensive smoothing

The optimal phi is automatically selected via grid search to maximize the objective function.

## Expected Runtime

| Dataset Size | Create Object | Deconvolution | Imputation |
|--------------|---------------|---------------|------------|
| 100 spots, 3 types | <5s | 30-60s | 10-30s |
| 1K spots, 5 types | 10-30s | 5-10min | 1-5min |
| 5K spots, 10 types | 1-2min | 30-60min | 10-20min |

*Runtime estimates on 8-core CPU with 32GB RAM*

## Troubleshooting

### Error: "No common genes"

```r
# Check gene naming
head(rownames(sc_count))
head(rownames(spatial_count))

# Check case consistency
sum(toupper(rownames(sc_count)) %in% toupper(rownames(spatial_count)))

# Convert to consistent format
rownames(sc_count) <- toupper(rownames(sc_count))
rownames(spatial_count) <- toupper(rownames(spatial_count))
```

### Error: "Cell name in scRNAseq count data does not match"

```r
# Check scRNA-seq metadata alignment
cat("sc_count columns:", length(colnames(sc_count)), "\n")
cat("sc_meta rows:", length(rownames(sc_meta)), "\n")
cat("Match:", sum(rownames(sc_meta) == colnames(sc_count)), "\n")

# Fix if needed
rownames(sc_meta) <- colnames(sc_count)
```

### Error: "Insufficient markers (CARDfree)"

```r
# Check marker gene availability
for (ct in names(markerList)) {
    markers <- markerList[[ct]]
    found <- sum(markers %in% rownames(spatial_count))
    cat(ct, ":", found, "/", length(markers), "markers found\n")
}

# Add more markers or check gene naming
```

### Convergence Issues

```r
# If deconvolution doesn't converge, adjust parameters
# Create object with stricter QC
CARD_obj <- createCARDObject(
    ...,
    minCountGene = 200,   # Increase
    minCountSpot = 10     # Increase
)
```

### Memory Issues

```r
# Run with smaller dataset first
spatial_count_subset <- spatial_count[, 1:500]
spatial_location_subset <- spatial_location[1:500, ]

# Then run CARD on subset
```

## Comparison with Other Methods

| Feature | CARD | RCTD | SPOTlight | cell2location |
|---------|------|------|-----------|---------------|
| Spatial correlation | CAR model | Mixture model | No | Yes |
| Reference-free mode | Yes | No | No | No |
| High-res imputation | Yes | No | No | No |
| Speed | Slow | Slow | Fast | Medium |
| Platform effect correction | No | Yes | No | Yes |

## AI Agent Test Cases

### Basic Deconvolution
> "Run CARD deconvolution on my Visium data"

```r
CARD_obj <- createCARDObject(
    sc_count = sc_count,
    sc_meta = sc_meta,
    spatial_count = spatial_count,
    spatial_location = spatial_location,
    ct.varname = "cell_type"
)
CARD_obj <- CARD_deconvolution(CARD_obj)
proportions <- CARD_obj@Proportion_CARD
```

### With Cell Type Selection
> "Run CARD with only T cells, B cells, and myeloid cells"

```r
CARD_obj <- createCARDObject(
    ...,
    ct.select = c("T_cell", "B_cell", "Myeloid")
)
CARD_obj <- CARD_deconvolution(CARD_obj)
```

### With High-Resolution Imputation
> "Run CARD and create high-resolution cell type maps"

```r
CARD_obj <- CARD_deconvolution(CARD_obj)
CARD_obj <- CARD.imputation(CARD_obj, NumGrids = 5000, ineibor = 15)
refined_props <- CARD_obj@refined_prop
```

### Reference-Free Analysis
> "Run CARD without a reference, using marker genes"

```r
CARDfree_obj <- createCARDfreeObject(
    markerList = markerList,
    spatial_count = spatial_count,
    spatial_location = spatial_location
)
CARDfree_obj <- CARD_refFree(CARDfree_obj)
proportions <- CARDfree_obj@Proportion_CARD
```

### Multi-Sample Analysis
> "Run CARD on multiple tissue sections"

```r
results_list <- lapply(samples, function(s) {
    CARD_obj <- createCARDObject(
        sc_count = sc_count,
        sc_meta = sc_meta,
        spatial_count = spatial_counts[[s]],
        spatial_location = spatial_locs[[s]],
        ct.varname = "cell_type"
    )
    CARD_deconvolution(CARD_obj)
})
```

## References

1. Ma et al. (2022). CARD: Computational deconvolution of spatial transcriptomics with conditional autoregressive model. *Nature Communications*, 13: 5871. https://doi.org/10.1038/s41467-022-35027-3
2. CARD GitHub: https://github.com/YingMa0107/CARD
3. CARD Tutorial: https://yingma0107.github.io/CARD/
