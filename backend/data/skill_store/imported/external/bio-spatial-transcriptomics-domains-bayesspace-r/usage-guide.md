# BayesSpace Usage Guide

## Overview

BayesSpace uses Bayesian hierarchical modeling to cluster spatial transcriptomics data, accounting for spatial dependencies between neighboring spots. It provides probabilistic cluster assignments and supports resolution enhancement to subspot-level.

## When to Use

- **Bayesian approach preferred**: When probabilistic cluster assignments are needed
- **Spatially-aware clustering**: When neighboring spots should have similar labels
- **Resolution enhancement**: When subspot-level analysis is desired
- **Visium/VisiumHD/ST data**: Optimized for these platforms

## When Not to Use

- **Quick exploration**: MCMC is slower than other methods
- **Very large datasets**: Consider GraphST or SpaGCN for >50K spots
- **No spatial coordinates**: BayesSpace requires `array_row` and `array_col`
- **Limited compute**: MCMC requires sufficient iterations for convergence

## Prerequisites

### Installation

```r
# Install Bioconductor
if (!requireNamespace("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

# Install BayesSpace
BiocManager::install("BayesSpace")

# Install dependencies
BiocManager::install(c("SingleCellExperiment", "scater", "scran"))
```

### Data Format

Input requirements:
- **SingleCellExperiment** with:
  - `counts(sce)`: Raw count matrix
  - `colData(sce)$array_row`: Array row coordinates
  - `colData(sce)$array_col`: Array column coordinates
  - Optional: `pxl_row_in_fullres`, `pxl_col_in_fullres` for visualization

## Step-by-Step Guide

### Step 1: Load Data

#### From Space Ranger Output

```r
library(BayesSpace)

# Load 10X Visium data
sce <- readVisium("path/to/spaceranger/outs/")

# Or load from H5
sce <- read10Xh5("path/to/spaceranger/outs/")

# Check data
print(sce)
head(colData(sce)[, c("array_row", "array_col")])
```

#### From Seurat

```r
library(Seurat)
library(SingleCellExperiment)

# Convert Seurat to SCE
seurat_obj <- readRDS("visium_data.rds")

# Extract data
counts <- GetAssayData(seurat_obj, slot = "counts")
col_data <- seurat_obj@meta.data

# Add spatial coordinates
img <- seurat_obj@images[[1]]@coordinates
col_data$array_row <- img$row
col_data$array_col <- img$col

# Create SCE
sce <- SingleCellExperiment(
    assays = list(counts = counts),
    colData = col_data
)
```

### Step 2: Preprocess

```r
# Standard preprocessing
sce <- spatialPreprocess(
    sce,
    platform = "Visium",     # "Visium", "VisiumHD", or "ST"
    n.PCs = 15,              # Number of PCs
    n.HVGs = 2000,           # Number of HVGs
    log.normalize = TRUE,    # Log-normalize
    skip.PCA = FALSE         # Set TRUE if PCA already computed
)

# Check results
sum(rowData(sce)$is.HVG)     # Number of HVGs
ncol(reducedDim(sce, "PCA")) # Number of PCs
```

**Parameters:**
- `platform`: "Visium" (hexagonal), "VisiumHD" or "ST" (square)
- `n.PCs`: 15 recommended for most datasets
- `n.HVGs`: 2000 recommended for standard Visium

### Step 3: Cluster

```r
# Run BayesSpace clustering
set.seed(149)
sce <- spatialCluster(
    sce,
    q = 7,                    # Number of clusters
    platform = "Visium",
    nrep = 10000,             # MCMC iterations
    burn.in = 5000,           # Burn-in iterations
    gamma = 3,                # Spatial smoothing (Visium default)
    model = "t",              # Error model: "t" or "normal"
    init.method = "mclust",   # Initialization: "mclust" or "kmeans"
    save.chain = TRUE,        # Save MCMC chain
    verbose = TRUE
)

# View results
table(sce$spatial.cluster)
```

**Parameters:**
- `q`: Number of clusters (required)
- `nrep`: MCMC iterations (default: 50000)
- `burn.in`: Discard early iterations (default: 1000)
- `gamma`: Spatial smoothing - 3 for Visium, 2 for ST
- `model`: "t" (robust) or "normal"

### Step 4: Enhance Resolution (Optional)

```r
# Enhance to subspot resolution
sce_enhanced <- spatialEnhance(
    sce,
    q = 7,
    platform = "Visium",
    nrep = 100000,            # More iterations for stability
    burn.in = 10000,
    jitter.scale = 5,         # Jittering amount
    jitter.prior = 0.3,       # Prior variance
    cores = 4,                # Parallel threads
    verbose = TRUE
)

# Check results
ncol(sce)           # Original spots (~3000)
ncol(sce_enhanced)  # Enhanced subspots (~18000 = 6x)
```

**Parameters:**
- `jitter.scale`: Controls exploration (5 default)
- `jitter.prior`: Prior variance (0.3 default)
- `cores`: Parallel threads for speed

### Step 5: Enhance Features (Optional)

```r
# Impute expression at subspot resolution
sce_enhanced <- enhanceFeatures(
    sce_enhanced,
    sce,
    features = rownames(sce)[1:100],  # Genes to enhance
    model = "xgboost"                 # "xgboost" or "naive"
)

# Access enhanced expression
assay(sce_enhanced, "enhanced")["EPCAM", ]
```

### Step 6: Visualize

```r
# Plot clusters
clusterPlot(sce)

# With custom palette
library(viridis)
clusterPlot(sce, palette = turbo(7))

# Enhanced clusters
clusterPlot(sce_enhanced, is.enhanced = TRUE)

# Gene expression
featurePlot(sce, feature = "EPCAM")
featurePlot(sce, feature = "PTPRC", diverging = TRUE)
```

### Step 7: Diagnostics

```r
# Extract MCMC chain
zsamples <- mcmcChain(sce, "z")

# Check dimensions
dim(zsamples)  # Iterations x Spots

# Calculate cluster stability
stability <- apply(zsamples, 2, function(x) {
    tab <- table(x)
    max(tab) / sum(tab)
})
mean(stability)

# Check Ychange (for enhancement)
Ychange <- mcmcChain(sce_enhanced, "Ychange")
mean(Ychange)  # Should be 25-40%
```

### Step 8: Export

```r
# Export clusters
write.csv(
    colData(sce)[, c("spatial.cluster", "array_row", "array_col")],
    "clusters.csv"
)

# Export enhanced results
write.csv(
    colData(sce_enhanced)[, c("spatial.cluster", "spot.idx", "subspot.idx")],
    "enhanced_clusters.csv"
)

# Save objects
saveRDS(sce, "bayesspace_results.rds")
saveRDS(sce_enhanced, "bayesspace_enhanced.rds")
```

## Advanced Usage

### Multi-q Comparison

```r
# Test different numbers of clusters
q_values <- 3:10
results <- list()

for (q in q_values) {
    sce_temp <- spatialCluster(sce, q = q, platform = "Visium",
                               nrep = 5000, burn.in = 1000)
    results[[paste0("q", q)]] <- sce_temp$spatial.cluster
}

# Compare with ARI
library(mclust)
ari_matrix <- matrix(NA, length(q_values), length(q_values))
for (i in seq_along(q_values)) {
    for (j in seq_along(q_values)) {
        ari_matrix[i, j] <- adjustedRandIndex(
            results[[i]], results[[j]]
        )
    }
}
```

### Platform Selection

```r
# Visium (hexagonal spots, 6 neighbors)
sce <- spatialCluster(sce, q = 7, platform = "Visium", gamma = 3)

# VisiumHD (square spots, 4 neighbors)
sce <- spatialCluster(sce, q = 7, platform = "VisiumHD", gamma = 2)

# ST legacy (square spots, 4 neighbors)
sce <- spatialCluster(sce, q = 7, platform = "ST", gamma = 2)
```

### Adjust Cluster Labels

```r
# Rerun with different burn-in
sce <- adjustClusterLabels(sce, burn.in = 0.2)  # 20% as burn-in
```

## Parameters Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `q` | Required | Number of clusters |
| `platform` | "Visium" | Platform type |
| `nrep` | 50000 | MCMC iterations |
| `burn.in` | 1000 | Burn-in iterations |
| `gamma` | Platform | Spatial smoothing (Visium: 3, ST: 2) |
| `model` | "t" | Error model ("t" or "normal") |
| `init.method` | "mclust" | Initialization method |

## Troubleshooting

### Missing spatial coordinates
```
Error: 'array_row' not found in colData
```
→ Add `array_row` and `array_col` to `colData(sce)`

### Not enough iterations
```
Error: Please specify a burn-in period shorter than...
```
→ Increase `nrep` or decrease `burn.in`

### Platform error
```
Error: .find_neighbors: Unsupported platform
```
→ Use "Visium", "VisiumHD", or "ST"

### Enhancement without clustering
```
Error: Must run spatialCluster on sce before enhancement
```
→ Run `spatialCluster()` before `spatialEnhance()`

## AI Agent Test Cases

### Basic Clustering
> "Run BayesSpace clustering on my Visium data with 7 clusters"

```r
sce <- readVisium("outs/")
sce <- spatialPreprocess(sce, platform = "Visium")
sce <- spatialCluster(sce, q = 7, platform = "Visium")
```

### With Resolution Enhancement
> "Enhance resolution of my Visium data using BayesSpace"

```r
sce <- spatialCluster(sce, q = 7, nrep = 10000)
sce_enhanced <- spatialEnhance(sce, q = 7, nrep = 100000)
```

### Multi-sample
> "Run BayesSpace on multiple Visium samples"

```r
sce1 <- readVisium("sample1/outs/")
sce2 <- readVisium("sample2/outs/")
sce_combined <- cbind(sce1, sce2)
sce_combined <- spatialPreprocess(sce_combined)
sce_combined <- spatialCluster(sce_combined, q = 10)
```

### Compare q Values
> "Find optimal number of clusters with BayesSpace"

```r
for (q in 3:10) {
    sce_temp <- spatialCluster(sce, q = q, nrep = 5000)
    print(sprintf("q=%d: %s", q, table(sce_temp$spatial.cluster)))
}
```

## Output

| Output | Location | Description |
|--------|----------|-------------|
| Clusters | `sce$spatial.cluster` | Spatial domain labels |
| Initial | `sce$cluster.init` | Initial cluster assignments |
| Enhanced | `sce_enhanced$spatial.cluster` | Subspot labels |
| Chain | `metadata(sce)$chain.h5` | MCMC chain (if saved) |

## Best Practices

1. **q selection**: Use domain knowledge or test multiple values
2. **Iterations**: 10000+ for final analysis, 50000+ for publication
3. **Gamma**: Platform default usually optimal
4. **Enhancement**: Only enhance after final q is selected
5. **Convergence**: Check MCMC chain with `mcmcChain()`

## Comparison with Other Methods

| Feature | BayesSpace | GraphST | SpaGCN | STAGATE |
|---------|------------|---------|--------|---------|
| Bayesian | Yes | No | No | No |
| Enhancement | Yes | No | No | No |
| Speed | Slow | Medium | Fast | Medium |
| Resolution | Subspot | Spot | Spot | Spot |
| Probabilistic | Yes | No | No | No |

## References

1. Zhao et al. (2021). BayesSpace enables the robust characterization of spatial transcriptomic architectures in tissues. *Nature Communications*, 12(1), 6868.
2. BayesSpace Bioconductor: https://bioconductor.org/packages/BayesSpace
3. BayesSpace GitHub: https://github.com/edward130603/BayesSpace
