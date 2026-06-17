# irGSEA Usage Guide

## Overview

irGSEA integrates multiple gene set enrichment analysis methods (AUCell, UCell, singscore, ssgsea, AddModuleScore) and aggregates their results for robust scoring.

## When to Use

- Robust signature scoring across methods
- Consensus-based enrichment analysis
- Large-scale gene signature screening
- Method comparison and validation

## Quick Start

```r
library(irGSEA)
library(Seurat)

# Run irGSEA with multiple methods
gene_sets <- list(
  HIF_targets = c("VEGFA", "GLUT1", "CA9"),
  MYC_targets = c("MYC", "LDHA", "ENO1")
)

seurat_obj <- irGSEA.score(
  object = seurat_obj,
  count.data = GetAssayData(seurat_obj, slot = "counts"),
  geneset = gene_sets,
  method = c("AUCell", "UCell", "singscore", "ssgsea", "AddModuleScore")
)

# Visualize
irGSEA.heatmap(seurat_obj, method = "UCell")
```

## Step-by-Step

### 1. Prepare Data

```r
library(irGSEA)
library(Seurat)

# Load Seurat object
seurat_obj <- readRDS("your_data.rds")

# Get count data
count_data <- GetAssayData(seurat_obj, slot = "counts")
```

### 2. Define Gene Sets

```r
# Custom gene sets
gene_sets <- list(
  Hypoxia = c("VEGFA", "GLUT1", "CA9", "PGK1", "LDHA"),
  Glycolysis = c("HK2", "PFKFB3", "GAPDH", "ENO1", "PKM"),
  OXPHOS = c("NDUFS1", "SDHA", "UQCRC1", "COX4I1", "ATP5F1A")
)

# Or load from MSigDB
gene_sets <- getGeneset("human", "C2", "CP:KEGG")
```

### 3. Calculate Scores with Multiple Methods

```r
seurat_obj <- irGSEA.score(
  object = seurat_obj,
  count.data = count_data,
  geneset = gene_sets,
  method = c("AUCell", "UCell", "singscore", "ssgsea", "AddModuleScore"),
  ncores = 4,
  min.cells = 10,
  min.feature = 10
)
```

### 4. Aggregate Results

```r
# Calculate consensus scores
seurat_obj <- irGSEA.integrate(
  object = seurat_obj,
  method = c("AUCell", "UCell", "singscore", "ssgsea", "AddModuleScore")
)
```

### 5. Visualize

```r
# Heatmap by cluster
irGSEA.heatmap(
  object = seurat_obj,
  method = "UCell",
  cluster.ident = "seurat_clusters"
)

# Violin plots
irGSEA.vlnplot(
  object = seurat_obj,
  method = "AUCell",
  geneset.name = "Hypoxia"
)

# UMAP
irGSEA.umap(
  object = seurat_obj,
  method = "singscore",
  geneset.name = "Glycolysis"
)
```

### 6. Differential Analysis

```r
# Compare enrichment between groups
diff_results <- irGSEA.deg(
  object = seurat_obj,
  method = "UCell",
  group.by = "condition"
)
```

## Available Methods

| Method | Description | Best For |
|--------|-------------|----------|
| AUCell | Area Under Curve | Small gene sets |
| UCell | Mann-Whitney U | Fast computation |
| singscore | Rank-based scoring | Normalized data |
| ssgsea | Single-sample GSEA | Pathway analysis |
| AddModuleScore | Seurat default | Quick assessment |

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `method` | Scoring methods to use | All 5 |
| `ncores` | Parallel cores | 1 |
| `min.cells` | Min cells per gene | 10 |
| `min.feature` | Min genes per cell | 10 |
| `seed` | Random seed | 12345 |

## Loading MSigDB Gene Sets

```r
# List available collections
listGenesets("human")

# Load specific collection
kegg_sets <- getGeneset("human", "C2", "CP:KEGG")
go_sets <- getGeneset("human", "C5", "GO:BP")

# Load Hallmark
tmp <- tempfile()
url <- "https://www.gsea-msigdb.org/gsea/msigdb/download_geneset.jsp?geneSetName=HALLMARK_HYPOXIA&fileType=txt"
download.file(url, tmp)
hypoxia_genes <- read.table(tmp, skip = 2, stringsAsFactors = FALSE)[[1]]
```

## Consensus Scoring

```r
# Get integrated results
integrated_scores <- irGSEA.integrate(
  object = seurat_obj,
  method = c("AUCell", "UCell", "singscore", "ssgsea", "AddModuleScore")
)

# Access consensus scores
consensus <- integrated_scores$Integrated.score
```

## AI Agent Test Cases

### Basic Usage
> "Run irGSEA with all methods on my scRNA-seq data"

> "Calculate enrichment scores using irGSEA for KEGG pathways"

> "Use irGSEA to score cells for multiple gene signatures"

### Method Selection
> "Run irGSEA with AUCell and UCell methods only"

> "Compare singscore and ssGSEA results using irGSEA"

### Aggregation
> "Calculate consensus scores from irGSEA multi-method output"

> "Visualize irGSEA results as heatmap"

## Best Practices

1. **Use all methods** for robust consensus
2. **Compare results** - methods should agree on top hits
3. **Focus on UCell/AUCell** for single-cell data
4. **Use AddModuleScore** only for quick exploration
5. **Validate** with known biological markers

## Troubleshooting

### Memory issues
- Reduce `ncores` or run methods separately
- Filter to highly variable genes first

### Inconsistent results
- Check gene set quality
- Ensure gene symbols are correct
- Compare with known literature

## References

1. irGSEA documentation: https://github.com/GuoBioinfoLab/irGSEA
