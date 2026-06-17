# AUCell Usage Guide

## Overview

AUCell calculates Area Under the Curve (AUC) scores for gene set enrichment in single-cell RNA-seq data using the Area Under the recovery Curve method.

## When to Use

- Gene signature scoring per cell
- Pathway activity estimation
- Compare enrichment across cell populations
- Works well with small gene sets

## Quick Start

```r
library(AUCell)
library(Seurat)

# Get expression matrix
expr_matrix <- GetAssayData(seurat_obj, slot = "counts")

# Build rankings
cells_rankings <- AUCell_buildRankings(expr_matrix)

# Calculate AUC for gene sets
gene_sets <- list(
  HIF_targets = c("VEGFA", "GLUT1", "CA9"),
  MYC_targets = c("MYC", "LDHA", "ENO1")
)

cells_auc <- AUCell_calcAUC(gene_sets, cells_rankings)

# Add to Seurat
seurat_obj$HIF_score <- cells_auc["HIF_targets", ]
```

## Step-by-Step

### 1. Prepare Data

```r
library(AUCell)
library(Seurat)

# Load Seurat object
seurat_obj <- readRDS("your_data.rds")

# Get expression matrix (raw counts or normalized)
expr_matrix <- GetAssayData(seurat_obj, slot = "counts")
```

### 2. Build Cell Rankings

```r
# Build rankings (one-time computation per dataset)
cells_rankings <- AUCell_buildRankings(
  expr_matrix,
  plotStats = TRUE,
  verbose = TRUE
)
```

### 3. Define Gene Sets

```r
# Load from MSigDB or define custom
gene_sets <- list(
  Hypoxia = c("VEGFA", "GLUT1", "CA9", "PGK1", "LDHA"),
  Glycolysis = c("HK2", "PFKFB3", "GAPDH", "ENO1", "PKM"),
  OXPHOS = c("NDUFS1", "SDHA", "UQCRC1", "COX4I1", "ATP5F1A")
)
```

### 4. Calculate AUC Scores

```r
cells_auc <- AUCell_calcAUC(
  gene_sets,
  cells_rankings,
  aucMaxRank = ceiling(0.05 * nrow(cells_rankings)),  # Top 5% of genes
  verbose = TRUE
)

# Extract results as data frame
auc_matrix <- getAUC(cells_auc)
```

### 5. Add to Seurat and Visualize

```r
# Add scores to metadata
for (gs in rownames(auc_matrix)) {
  seurat_obj[[gs]] <- auc_matrix[gs, ]
}

# Visualize on UMAP
FeaturePlot(seurat_obj, features = "Hypoxia")
VlnPlot(seurat_obj, features = "Glycolysis")
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `aucMaxRank` | Threshold for AUC calculation (% of genes) | 0.05 (top 5%) |
| `plotStats` | Plot ranking statistics | TRUE |

## Threshold Determination

```r
# Automatic threshold for binarization
set.seed(123)
cells_assignment <- AUCell_exploreThresholds(
  cells_auc,
  plotHist = TRUE,
  nCores = 1,
  assign = TRUE
)

# Get cells with active signature
active_cells <- cells_assignment$Hypoxia$assignment
```

## AI Agent Test Cases

### Basic Usage
> "Calculate AUCell scores for hypoxia pathway in my scRNA-seq data"

> "Use AUCell to score cells for metabolic gene sets"

> "Run AUCell with my custom gene signature"

### Gene Set Analysis
> "Score cells with AUCell using KEGG pathway genes"

> "Calculate AUCell for cell cycle and apoptosis pathways"

### Threshold Determination
> "Determine optimal threshold for AUCell binarization"

> "Find cells with active hypoxia signature using AUCell"

## Best Practices

1. **Use raw counts** - AUCell ranks genes internally
2. **Small gene sets** work better (20-200 genes)
3. **Compare across samples** - Scores are comparable between cells
4. **Validate with known biology** - Check expected cell types

## Output Interpretation

| Value | Interpretation |
|-------|----------------|
| AUC = 0 | No genes in set expressed |
| AUC = 1 | All genes in set are top expressed |
| 0.5-0.7 | Moderate enrichment |
| > 0.8 | Strong enrichment |

## References

1. Aibar et al. (2017). SCENIC: single-cell regulatory network inference and clustering. *Nature Methods*.
2. AUCell documentation: https://bioconductor.org/packages/AUCell/
