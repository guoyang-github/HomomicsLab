# DoubletFinder Usage Guide

## Overview

DoubletFinder detects doublets in Seurat objects using artificial nearest neighbor (pANN) classification. It performs parameter sweep to optimize the pK neighborhood parameter.

## When to Use

- Native Seurat workflow
- Need parameter optimization
- pANN-based classification preferred
- R-based analysis

## Quick Start

```r
library(DoubletFinder)
library(Seurat)

# Preprocess through clustering
seurat_obj <- NormalizeData(seurat_obj)
seurat_obj <- FindVariableFeatures(seurat_obj)
seurat_obj <- ScaleData(seurat_obj)
seurat_obj <- RunPCA(seurat_obj)
seurat_obj <- RunUMAP(seurat_obj, dims = 1:20)
seurat_obj <- FindNeighbors(seurat_obj, dims = 1:20)
seurat_obj <- FindClusters(seurat_obj, resolution = 0.5)

# Parameter sweep
sweep.res <- paramSweep(seurat_obj, PCs = 1:20, sct = FALSE)
sweep.stats <- summarizeSweep(sweep.res, GT = FALSE)
bcmvn <- find.pK(sweep.stats)

# Find optimal pK
optimal_pk <- as.numeric(as.character(bcmvn$pK[which.max(bcmvn$BCmetric)]))

# Expected doublets
nExp_poi <- round(0.06 * ncol(seurat_obj))

# Run DoubletFinder
seurat_obj <- doubletFinder(
  seurat_obj,
  PCs = 1:20,
  pN = 0.25,
  pK = optimal_pk,
  nExp = nExp_poi,
  reuse.pANN = FALSE,
  sct = FALSE
)

# Filter
df_col <- grep('DF.classifications', colnames(seurat_obj@meta.data), value = TRUE)
seurat_obj$doublet <- seurat_obj@meta.data[[df_col]]
seurat_obj <- subset(seurat_obj, subset = doublet == 'Singlet')
```

## Step-by-Step

### 1. Preprocess

```r
library(DoubletFinder)
library(Seurat)

# Standard preprocessing
seurat_obj <- NormalizeData(seurat_obj)
seurat_obj <- FindVariableFeatures(seurat_obj)
seurat_obj <- ScaleData(seurat_obj)
seurat_obj <- RunPCA(seurat_obj)
seurat_obj <- RunUMAP(seurat_obj, dims = 1:20)
seurat_obj <- FindNeighbors(seurat_obj, dims = 1:20)
seurat_obj <- FindClusters(seurat_obj, resolution = 0.5)
```

### 2. Parameter Sweep

```r
# Sweep pK values
sweep.res <- paramSweep(seurat_obj, PCs = 1:20, sct = FALSE)
sweep.stats <- summarizeSweep(sweep.res, GT = FALSE)
bcmvn <- find.pK(sweep.stats)

# Visualize pK selection
plot(bcmvn$BCmetric)

# Optimal pK
optimal_pk <- as.numeric(as.character(bcmvn$pK[which.max(bcmvn$BCmetric)]))
cat("Optimal pK:", optimal_pk, "\n")
```

### 3. Run DoubletFinder

```r
# Expected doublet rate
n_cells <- ncol(seurat_obj)
doublet_rate <- n_cells / 1000 * 0.008
nExp_poi <- round(doublet_rate * n_cells)

# Run
seurat_obj <- doubletFinder(
  seurat_obj,
  PCs = 1:20,
  pN = 0.25,
  pK = optimal_pk,
  nExp = nExp_poi,
  reuse.pANN = FALSE,
  sct = FALSE
)
```

### 4. Filter

```r
# Get classification column
df_col <- grep('DF.classifications', colnames(seurat_obj@meta.data), value = TRUE)
seurat_obj$doublet <- seurat_obj@meta.data[[df_col]]

# Visualize
DimPlot(seurat_obj, group.by = 'doublet')

# Filter
seurat_obj <- subset(seurat_obj, subset = doublet == 'Singlet')
```

### 5. With SCTransform

```r
# If using SCTransform
seurat_obj <- SCTransform(seurat_obj)
seurat_obj <- RunPCA(seurat_obj)
seurat_obj <- RunUMAP(seurat_obj, dims = 1:30)
seurat_obj <- FindNeighbors(seurat_obj, dims = 1:30)
seurat_obj <- FindClusters(seurat_obj, resolution = 0.5)

# Sweep with sct=TRUE
sweep.res <- paramSweep(seurat_obj, PCs = 1:30, sct = TRUE)
sweep.stats <- summarizeSweep(sweep.res, GT = FALSE)
bcmvn <- find.pK(sweep.stats)

optimal_pk <- as.numeric(as.character(bcmvn$pK[which.max(bcmvn$BCmetric)]))
nExp_poi <- round(0.06 * ncol(seurat_obj))

seurat_obj <- doubletFinder(
  seurat_obj,
  PCs = 1:30,
  pN = 0.25,
  pK = optimal_pk,
  nExp = nExp_poi,
  reuse.pANN = FALSE,
  sct = TRUE
)
```

## AI Agent Test Cases

### Basic Usage
> "Run DoubletFinder on my Seurat object"

> "Use DoubletFinder with parameter sweep for optimal pK"

### SCTransform
> "Run DoubletFinder with SCTransform workflow"

> "Adjust DoubletFinder for SCT normalized data"

### Filtering
> "Filter out predicted doublets from Seurat object"

> "Visualize DoubletFinder results on UMAP"

## References

1. McGinnis et al. (2019). DoubletFinder: Doublet Detection in Single-Cell RNA Sequencing Data Using Artificial Nearest Neighbors. *Cell Systems*.
