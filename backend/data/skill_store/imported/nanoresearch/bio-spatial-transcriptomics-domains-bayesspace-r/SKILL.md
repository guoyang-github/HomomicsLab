---
name: bio-spatial-transcriptomics-domains-bayesspace-r
description: |
  BayesSpace performs spatial domain identification using Bayesian hierarchical modeling.
  Clusters spatial transcriptomics data while accounting for spatial dependencies between
  neighboring spots. Supports resolution enhancement to subspot-level for higher-resolution
  spatial domain identification.
tool_type: r
primary_tool: BayesSpace
languages: [r]
keywords: ["spatial", "domains", "clustering", "BayesSpace", "bayesian", "MCMC",
           "resolution-enhancement", "subspot", "Visium", "R", "Bioconductor"]
---

## Version Compatibility

- **R**: >= 4.0.0
- **Bioconductor**: >= 3.12
- **BayesSpace**: >= 1.10.0
- **SingleCellExperiment**: >= 1.14.0
- **scater**: >= 1.20.0
- **scran**: >= 1.20.0
- **Seurat**: >= 4.3.0 (optional, for input conversion; v4 and v5 compatible via automatic slot/layer detection)

## Installation

```r
# Install Bioconductor
if (!requireNamespace("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

# Install BayesSpace
BiocManager::install("BayesSpace")

# Install dependencies
BiocManager::install(c("SingleCellExperiment", "scater", "scran", "mclust"))
```

## Data Requirements

Input requirements:
- **SingleCellExperiment object** with:
  - `counts(sce)`: Raw count matrix
  - `colData(sce)`: Must include `array_row` and `array_col` for spot positions
  - Optional: `pxl_row_in_fullres` and `pxl_col_in_fullres` for image coordinates
- **Platform**: Visium (hexagonal), VisiumHD (square), or ST (square)

## Core Analysis Workflow

### 1. Data Loading

#### From Space Ranger Output

```r
library(BayesSpace)

# Load 10X Visium data directly
sce <- readVisium("path/to/spaceranger/outs/")

# Or load from H5 file
sce <- read10Xh5("path/to/spaceranger/outs/")

# Check loaded data
print(sce)
colData(sce)[, c("array_row", "array_col", "in_tissue")]
```

#### From Seurat Object

```r
library(Seurat)
library(SingleCellExperiment)

# Convert Seurat to SingleCellExperiment
seurat_obj <- readRDS("visium_data.rds")
logcounts <- GetAssayData(seurat_obj, slot = "data")

# Get spatial coordinates from Seurat
seurat_meta <- seurat_obj@meta.data
seurat_meta$array_row <- seurat_obj@images[[1]]@coordinates$row
seurat_meta$array_col <- seurat_obj@images[[1]]@coordinates$col

# Create SingleCellExperiment
sce <- SingleCellExperiment(
    assays = list(logcounts = logcounts),
    colData = seurat_meta
)
```

### 2. Preprocessing

**Function:** `spatialPreprocess()`

**Purpose:** Preprocess spatial data for BayesSpace analysis.

**Key Parameters:**
- `sce`: SingleCellExperiment object
- `platform`: "Visium", "VisiumHD", or "ST"
- `n.PCs`: Number of principal components (default: 15)
- `n.HVGs`: Number of highly variable genes (default: 2000)
- `skip.PCA`: Skip PCA if already computed (default: FALSE)
- `log.normalize`: Whether to log-normalize (default: TRUE)
- `assay.type`: Assay to use (default: "logcounts")
- `BSPARAM`: PCA algorithm (default: `ExactParam()`)
- `BPPARAM`: Parallel processing (default: `SerialParam()`)

**Process:**
1. Log-normalization (if specified)
2. Identify highly variable genes
3. Run PCA on HVGs
4. Store BayesSpace metadata

**Example:**
```r
# Standard preprocessing
sce <- spatialPreprocess(
    sce,
    platform = "Visium",
    n.PCs = 15,
    n.HVGs = 2000,
    log.normalize = TRUE
)

# Skip PCA if already computed
sce <- spatialPreprocess(sce, platform = "Visium", skip.PCA = TRUE)
```

### 3. Spatial Clustering

**Function:** `spatialCluster()`

**Purpose:** Cluster spots into spatial domains using Bayesian modeling.

**Key Parameters:**
- `sce`: SingleCellExperiment
- `q`: Number of clusters
- `use.dimred`: Name of reduced dim (default: "PCA")
- `d`: Number of top PCs to use (default: 15)
- `platform`: "Visium", "VisiumHD", or "ST"
- `init`: Initial cluster assignments (optional)
- `init.method`: "mclust" or "kmeans" (default: "mclust")
- `model`: Error model - "normal" or "t" (default: "t")
- `precision`: Covariance - "equal" or "variable" (default: "equal")
- `nrep`: MCMC iterations (default: 50000)
- `burn.in`: Burn-in iterations (default: 1000)
- `thin`: Thinning rate (default: 100)
- `gamma`: Spatial smoothing parameter (default: 3 for Visium, 2 for ST)
- `save.chain`: Save MCMC chain to HDF5 (default: FALSE)
- `chain.fname`: Chain file path (optional)

**Process:**
1. Find neighboring spots based on platform geometry
2. Initialize cluster assignments
3. Run MCMC sampling with spatial prior
4. Calculate modal cluster assignments

**Output:**
- `colData(sce)$spatial.cluster`: Final cluster assignments
- `colData(sce)$cluster.init`: Initial cluster assignments
- `metadata(sce)$BayesSpace.data$platform`: Platform info
- `metadata(sce)$chain.h5`: Chain file path (if saved)

**Example:**
```r
# Basic clustering
set.seed(149)
sce <- spatialCluster(
    sce,
    q = 7,                  # Number of clusters
    platform = "Visium",
    nrep = 10000,           # MCMC iterations
    burn.in = 5000,         # Burn-in
    gamma = 3,              # Spatial smoothing
    save.chain = TRUE
)

# View results
table(sce$spatial.cluster)
```

### 4. Resolution Enhancement

**Function:** `spatialEnhance()`

**Purpose:** Enhance resolution to subspot-level clustering.

**Key Parameters:**
- `sce`: SingleCellExperiment (must have spatial.cluster)
- `q`: Number of clusters
- `platform`: "Visium", "VisiumHD", or "ST"
- `use.dimred`: Reduced dimension name (default: "PCA")
- `d`: Number of PCs (default: 15)
- `nsubspots.per.edge`: For square platforms (default: 3)
- `init.method`: "spatialCluster", "mclust", or "kmeans"
- `model`: "t" or "normal" (default: "t")
- `nrep`: MCMC iterations (default: 100000)
- `burn.in`: Burn-in (default: 10000)
- `gamma`: Spatial smoothing (default: platform-specific)
- `jitter.scale`: Jittering amount (default: 5)
- `jitter.prior`: Prior variance scale (default: 0.3)
- `adapt.before`: Adaptive MCMC cutoff (default: burn.in)
- `cores`: Number of threads (default: 1)
- `save.chain`: Save MCMC chain (default: FALSE)

**Process:**
1. Divide each spot into subspots (6 for Visium hex, 9 for square)
2. Run MCMC with jittering to explore subspot positions
3. Assign cluster labels to subspots

**Output:**
- New SingleCellExperiment with subspot-level data
- `reducedDim(enhanced, "PCA")`: Enhanced PCs
- `enhanced$spatial.cluster`: Subspot cluster labels
- `colData` includes `spot.idx`, `subspot.idx`, `spot.neighbors`

**Example:**
```r
# Enhance resolution
sce_enhanced <- spatialEnhance(
    sce,
    q = 7,
    platform = "Visium",
    nrep = 10000,
    burn.in = 5000,
    jitter.scale = 5,
    jitter.prior = 0.3,
    cores = 4
)

# Check enhanced data
dim(sce)          # Original: ~3000 spots
dim(sce_enhanced) # Enhanced: ~18000 subspots (6x)
```

### 5. Visualization

**Function:** `clusterPlot()`

**Purpose:** Plot spatial cluster assignments.

**Key Parameters:**
- `sce`: SingleCellExperiment
- `label`: Column or vector for coloring (default: "spatial.cluster")
- `palette`: Color palette
- `color`: Border color
- `platform`: "Visium", "VisiumHD", or "ST"
- `is.enhanced`: Whether data is subspot-level

**Example:**
```r
# Plot clusters
clusterPlot(sce, label = "spatial.cluster")

# With custom palette
library(viridis)
clusterPlot(sce, palette = turbo(7))

# Plot enhanced clusters
clusterPlot(sce_enhanced, is.enhanced = TRUE)
```

**Function:** `featurePlot()`

**Purpose:** Plot spatial gene expression.

**Key Parameters:**
- `sce`: SingleCellExperiment
- `feature`: Gene name or expression vector
- `assay.type`: Assay to use (default: "logcounts")
- `diverging`: Use diverging color scale
- `low`, `mid`, `high`: Color hex codes

**Example:**
```r
# Plot gene expression
featurePlot(sce, feature = "EPCAM")

# Diverging scale (e.g., for fold changes)
featurePlot(sce, feature = "gene", diverging = TRUE)
```

### 6. Feature Enhancement

**Function:** `enhanceFeatures()`

**Purpose:** Impute expression at subspot resolution.

**Key Parameters:**
- `sce`: Enhanced SingleCellExperiment
- `sce.ref`: Reference SCE (original spot-level)
- `features`: Genes to enhance
- `model`: "xgboost" or "naive"

**Example:**
```r
# Enhance features
sce_enhanced <- enhanceFeatures(
    sce_enhanced,
    sce,
    features = rownames(sce)[1:100],
    model = "xgboost"
)

# Access enhanced expression
assay(sce_enhanced, "enhanced")["EPCAM", ]
```

### 7. MCMC Chain Analysis

**Function:** `mcmcChain()`

**Purpose:** Extract MCMC chain for diagnostics.

**Key Parameters:**
- `sce`: SingleCellExperiment with saved chain
- `param`: Parameter to extract ("z", "mu", "lambda", "Y", "Ychange", "plogLik")

**Example:**
```r
# Extract cluster assignments across iterations
zsamples <- mcmcChain(sce, "z")

# Check convergence
dim(zsamples)  # Iterations x Spots
```

### 8. Export Results

```r
# Export cluster assignments
write.csv(colData(sce)[, "spatial.cluster", drop = FALSE],
          "bayesspace_clusters.csv")

# Export enhanced coordinates
write.csv(colData(sce_enhanced)[, c("array_row", "array_col", "spatial.cluster")],
          "bayesspace_enhanced.csv")

# Save SingleCellExperiment
saveRDS(sce, "bayesspace_results.rds")
```

## Input Requirements

### Required Data Format

```r
print(sce)
# class: SingleCellExperiment
# dim: 31053 2987
# assays(1): logcounts
# rownames(31053): ENSG00000243485 ... ENSG00000287876
# rowData names(2): gene_id gene_name
# colnames(2987): AAACAACGAATAGTTC-1 ... TTGTTTCACATCCAGG-1
# colData names(6): barcode in_tissue array_row array_col ...
# reducedDimNames(1): PCA

# Check spatial coordinates
head(colData(sce)[, c("array_row", "array_col")])
#   array_row array_col
# 1        14        45
# 2        46        25
```

## Output Specifications

### Core Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Clusters | `sce$spatial.cluster` | Spatial domain labels |
| Initial clusters | `sce$cluster.init` | Initial cluster assignments |
| Platform | `metadata(sce)$BayesSpace.data$platform` | Platform info |
| PCA | `reducedDim(sce, "PCA")` | Principal components |
| HVGs | `rowData(sce)$is.HVG` | Highly variable gene flag |

### Enhanced Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Subspot clusters | `enhanced$spatial.cluster` | Subspot labels |
| Subspot info | `enhanced$subspot.idx` | Subspot index within parent |
| Parent info | `enhanced$spot.idx` | Parent spot index |
| Enhanced PCs | `reducedDim(enhanced, "PCA")` | Subspot PCs |

## Key Parameters

### Clustering

| Parameter | Default | Description | When to Adjust |
|-----------|---------|-------------|----------------|
| `q` | Required | Number of clusters | Based on tissue structure |
| `nrep` | 50000 | MCMC iterations | Increase for convergence |
| `burn.in` | 1000 | Burn-in iterations | Discard early samples |
| `gamma` | Platform | Spatial smoothing | Higher for smoother domains |
| `model` | "t" | Error model | "normal" for robustness |

### Enhancement

| Parameter | Default | Description | When to Adjust |
|-----------|---------|-------------|----------------|
| `nrep` | 100000 | MCMC iterations | More for stability |
| `burn.in` | 10000 | Burn-in | Longer for jitter convergence |
| `jitter.scale` | 5 | Jittering amount | Adjust acceptance rate |
| `jitter.prior` | 0.3 | Prior variance | Smaller for less variation |
| `cores` | 1 | Threads | Increase for speed |

### Platform-Specific Defaults

| Platform | Geometry | Default gamma | Subspots |
|----------|----------|---------------|----------|
| Visium | Hexagonal | 3 | 6 |
| VisiumHD | Square | 2 | 9 (3x3) |
| ST | Square | 2 | 9 (3x3) |

## Expected Runtime

| Dataset Size | Preprocessing | Clustering | Enhancement |
|--------------|---------------|------------|-------------|
| 1K spots | 10-30s | 2-5min | 10-20min |
| 5K spots | 30-60s | 10-20min | 30-60min |
| 20K spots | 2-5min | 30-60min | 2-4hours |

*Runtime estimates on 4-core CPU. MCMC is single-threaded per chain.*

## Error Handling

### Missing spatial coordinates
```
Error: 'array_row' not found in colData
```
→ Ensure `colData(sce)` includes `array_row` and `array_col`

### Platform mismatch
```
Error: .find_neighbors: Unsupported platform
```
→ Use "Visium", "VisiumHD", or "ST" for platform parameter

### Not enough iterations
```
Error: Please specify a burn-in period shorter than the total number of iterations
```
→ Increase `nrep` or decrease `burn.in`

### Enhancement without clustering
```
Error: Must run spatialCluster on sce before enhancement
```
→ Run `spatialCluster()` before `spatialEnhance()`

## Common Analysis Patterns

### Pattern 1: Quick Clustering
```r
sce <- readVisium("outs/")
sce <- spatialPreprocess(sce, platform = "Visium")
sce <- spatialCluster(sce, q = 7, platform = "Visium")
```

### Pattern 2: With MCMC Chain Save
```r
sce <- spatialCluster(
    sce,
    q = 7,
    nrep = 100000,
    burn.in = 50000,
    save.chain = TRUE,
    chain.fname = "mcmc_chain.h5"
)

# Analyze chain
zsamples <- mcmcChain(sce, "z")
```

### Pattern 3: Resolution Enhancement
```r
# First cluster at spot level
sce <- spatialCluster(sce, q = 7, nrep = 10000)

# Then enhance to subspots
sce_enhanced <- spatialEnhance(
    sce,
    q = 7,
    nrep = 100000,
    jitter.scale = 5
)

# Enhance gene expression
sce_enhanced <- enhanceFeatures(sce_enhanced, sce)
```

### Pattern 4: Comparing Multiple q Values
```r
results <- list()
for (q in 3:10) {
    sce_temp <- spatialCluster(sce, q = q, nrep = 10000)
    results[[paste0("q", q)]] <- sce_temp$spatial.cluster
}

# Compare using ARI or other metrics
```

### Pattern 5: Multi-sample Integration
```r
# Process samples separately, then combine
sce1 <- readVisium("sample1/outs/")
sce2 <- readVisium("sample2/outs/")

sce1$sample <- "S1"
sce2$sample <- "S2"

# Combine and cluster
sce_combined <- cbind(sce1, sce2)
sce_combined <- spatialPreprocess(sce_combined)
sce_combined <- spatialCluster(sce_combined, q = 10)
```

## Module Structure

```
BayesSpace/
├── R/
│   ├── spatialCluster.R    # Main clustering function
│   ├── spatialEnhance.R    # Resolution enhancement
│   ├── spatialPreprocess.R # Preprocessing
│   ├── readVisium.R        # Data loading
│   ├── spatialPlot.R       # Visualization
│   ├── enhanceFeatures.R   # Feature imputation
│   └── utils.R             # Utilities
└── src/                    # C++ MCMC implementation

scripts/r/
├── utils.R                 # Helper functions
└── visualization.R         # Additional plots

examples/
├── minimal_example.R       # Basic workflow
└── advanced_example.R      # Full pipeline

tests/
└── test_bayesspace.R       # Unit tests
```

## Interpretation Guidelines

### Quality Assessment

**Good clustering:**
- Spatially contiguous domains
- Smooth boundaries between domains
- Biologically expected patterns
- Converged MCMC (check `mcmcChain`)

**Potential issues:**
- Too many small domains: Reduce `q` or increase `gamma`
- No spatial pattern: Check `array_row`/`array_col`
- Uncertain boundaries: Increase `nrep` or adjust `gamma`

### Resolution Enhancement Assessment

**Good enhancement:**
- Subspots align with tissue structure
- Smooth transitions within domains
- Acceptable jitter acceptance (~25-40%)

**Check Ychange:**
```r
Ychange <- mcmcChain(sce_enhanced, "Ychange")
mean(Ychange)  # Should be 25-40%
```

## Related Skills

- [bio-spatial-transcriptomics-domains-spagcn](../bio-spatial-transcriptomics-domains-spagcn/SKILL.md) - SpaGCN graph-based clustering
- [bio-spatial-transcriptomics-domains-graphst](../bio-spatial-transcriptomics-domains-graphst/SKILL.md) - GraphST deep learning clustering
- [bio-spatial-transcriptomics-domains-stagate](../bio-spatial-transcriptomics-domains-stagate/SKILL.md) - STAGATE clustering
- [bio-spatial-transcriptomics-deconvolution-card-r](../bio-spatial-transcriptomics-deconvolution-card-r/SKILL.md) - CARD deconvolution

## References

1. Zhao et al. (2021). BayesSpace enables the robust characterization of spatial transcriptomic architectures in tissues. *Nature Communications*, 12(1), 6868. https://doi.org/10.1038/s41467-021-25757-7
2. BayesSpace Bioconductor: https://bioconductor.org/packages/BayesSpace
3. BayesSpace GitHub: https://github.com/edward130603/BayesSpace
4. BayesSpace Vignette: https://edward130603.github.io/BayesSpace/articles/BayesSpace.html
