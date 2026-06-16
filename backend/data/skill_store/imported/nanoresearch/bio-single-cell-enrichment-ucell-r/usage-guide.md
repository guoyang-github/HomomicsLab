# UCell Usage Guide

## Overview

UCell calculates gene signature scores using the Mann-Whitney U statistic. It's fast, robust, and works well with small gene sets.

## When to Use

- Fast signature scoring for large datasets
- Small gene sets (10-100 genes)
- Batch correction not required
- Memory-efficient alternative to AUCell

## Quick Start

```r
library(UCell)
library(Seurat)

# Add signature scores directly
gene_sets <- list(
  HIF_targets = c("VEGFA", "GLUT1", "CA9"),
  MYC_targets = c("MYC", "LDHA", "ENO1")
)

seurat_obj <- AddModuleScore_UCell(seurat_obj, features = gene_sets)

# Visualize
FeaturePlot(seurat_obj, features = "HIF_targets_UCell")
```

## Step-by-Step

### 1. Prepare Data

```r
library(UCell)
library(Seurat)

# Load Seurat object
seurat_obj <- readRDS("your_data.rds")
```

### 2. Define Gene Sets

```r
# Define signatures
gene_sets <- list(
  Hypoxia = c("VEGFA", "GLUT1", "CA9", "PGK1", "LDHA", "BNIP3"),
  Glycolysis = c("HK2", "PFKFB3", "GAPDH", "ENO1", "PKM", "LDHA"),
  OXPHOS = c("NDUFS1", "SDHA", "UQCRC1", "COX4I1", "ATP5F1A", "MT-CO1")
)
```

### 3. Calculate UCell Scores

```r
# Calculate scores
seurat_obj <- AddModuleScore_UCell(
  seurat_obj,
  features = gene_sets,
  name = "_UCell",           # Suffix for new columns
  ncores = 4,                # Parallel processing
  storeRanks = FALSE         # Save rankings for reuse?
)
```

### 4. Visualize Results

```r
# Feature plot on UMAP
FeaturePlot(seurat_obj, features = paste0(names(gene_sets), "_UCell"))

# Violin plot by cell type
VlnPlot(seurat_obj, features = "Hypoxia_UCell", group.by = "cell_type")

# Ridge plot
RidgePlot(seurat_obj, features = "Glycolysis_UCell")
```

### 5. Compare Across Conditions

```r
# Compare scores between groups
VlnPlot(seurat_obj, features = "Hypoxia_UCell", group.by = "condition")

# Statistical test
Idents(seurat_obj) <- "condition"
FindMarkers(seurat_obj, ident.1 = "tumor", ident.2 = "normal",
            features = "Hypoxia_UCell")
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `maxRank` | Number of top genes to consider | 1500 |
| `ncores` | Number of cores for parallel processing | 1 |
| `storeRanks` | Store rankings for repeated use | FALSE |
| `name` | Suffix for column names | "_UCell" |

## Scoring Matrix Directly

```r
# Work with matrix instead of Seurat
expr_matrix <- GetAssayData(seurat_obj, slot = "data")
scores <- ScoreSignatures_UCell(expr_matrix, features = gene_sets)
```

## Pre-calculated Rankings

```r
# Calculate once, reuse for multiple signatures
rankings <- StoreRankings_UCell(seurat_obj, maxRank = 1500)

# Use stored rankings
scores1 <- ScoreSignatures_UCell(rankings, features = gene_sets1)
scores2 <- ScoreSignatures_UCell(rankings, features = gene_sets2)
```

## AI Agent Test Cases

### Basic Usage
> "Calculate UCell scores for HALLMARK pathways"

> "Use UCell to score my cells for immune signatures"

> "Run UCell with 4 cores for faster computation"

### Multiple Signatures
> "Score cells with UCell for multiple metabolic pathways"

> "Add UCell scores for hypoxia and glycolysis to my Seurat object"

### Comparison
> "Compare UCell and AUCell results for the same gene sets"

> "Calculate both UCell and AddModuleScore for comparison"

## Best Practices

1. **Small gene sets** (10-100 genes) perform best
2. **maxRank** of 1500 captures most biological signals
3. **Use parallel** (`ncores > 1`) for large datasets
4. **Store rankings** when testing multiple signatures

## Comparing UCell vs AUCell

| Feature | UCell | AUCell |
|---------|-------|--------|
| Speed | Faster | Slower |
| Memory | Lower | Higher |
| Gene set size | Best 10-100 genes | Works with 20-500 |
| Thresholding | Manual | Built-in |

## References

1. Andreatta et al. (2021). UCell: Robust and scalable single-cell gene signature scoring. *Computational and Structural Biotechnology Journal*.
2. UCell documentation: https://bioconductor.org/packages/UCell/
