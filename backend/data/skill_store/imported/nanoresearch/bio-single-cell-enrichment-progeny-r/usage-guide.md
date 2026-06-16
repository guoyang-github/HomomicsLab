# PROGENy Usage Guide

## Overview

PROGENy (Pathway RespOnsive GENes) estimates signaling pathway activity from gene expression using footprint-based analysis. It uses pathway-responsive genes derived from large-scale perturbation experiments to infer activities of 14 key signaling pathways.

## When to Use

- **Pathway activity inference**: Estimate signaling pathway activities when you have gene expression data
- **Single-cell pathway analysis**: Map pathway activities onto cell types and states
- **Condition comparison**: Compare pathway activities between treatments, time points, or disease states
- **Cell type characterization**: Identify which pathways drive specific cell populations
- **Cross-talk analysis**: Study correlations between different signaling pathways

## Data Requirements

- **Gene expression**: Normalized counts (log-transformed recommended)
- **Gene symbols**: HGNC symbols for Human, MGI symbols for Mouse
- **Recommended input**: Seurat object with normalized data in the `data` layer (v5) or `data` slot (v4)

## Quick Start

```r
library(Seurat)
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")

# Load data
seurat_obj <- readRDS("data.rds")

# Run PROGENy
seurat_obj <- run_progeny(
  seurat_obj,
  organism = "Human",
  top = 100,
  scale = FALSE,
  return_assay = TRUE
)

# Visualize
plot_pathway_embedding(seurat_obj, pathways = c("MAPK", "PI3K"), reduction = "umap")
```

## Step-by-Step Guide

### 1. Data Preparation

```r
# Load Seurat object
seurat_obj <- readRDS("your_data.rds")

# Check gene naming (should be HGNC symbols for Human)
head(rownames(seurat_obj))

# Validate gene overlap with PROGENy model
source("scripts/r/utils.R")
overlap <- validate_gene_overlap(rownames(seurat_obj), organism = "Human")
print_overlap_stats(overlap)
# Expect >50% overlap for reliable results
```

### 2. Run PROGENy Analysis

```r
source("scripts/r/core_analysis.R")

# Basic run
seurat_obj <- run_progeny(
  seurat_obj,
  organism = "Human",    # or "Mouse"
  top = 100,             # Top responsive genes per pathway
  scale = FALSE,         # Don't scale for single-cell
  return_assay = TRUE,   # Return as Seurat assay
  verbose = TRUE
)

# Check results
names(seurat_obj@assays)
rownames(seurat_obj[["progeny"]])  # 14 pathways
```

**Parameter selection:**

| Parameter | Recommended | Description |
|-----------|-------------|-------------|
| `top` | 100 (50-500) | More genes = more coverage but potentially more noise |
| `scale` | FALSE | Use FALSE for single-cell, TRUE for bulk comparison |
| `organism` | "Human" | "Human" or "Mouse" |

### 3. Add to Metadata

```r
# Add pathway scores as metadata columns
seurat_obj <- add_progeny_to_metadata(seurat_obj, prefix = "PROGENy_")

# Access individual pathway scores
head(seurat_obj$PROGENy_MAPK)
head(seurat_obj$PROGENy_PI3K)
```

### 4. Visualization

#### Feature plots on embedding
```r
source("scripts/r/visualization.R")

# Plot specific pathways
plot_pathway_embedding(
  seurat_obj,
  pathways = c("MAPK", "PI3K", "TGFb", "TNFa", "NFkB", "Hypoxia"),
  reduction = "umap",
  ncol = 3
)
```

#### Heatmap by cluster
```r
plot_pathway_heatmap(
  seurat_obj,
  group.by = "seurat_clusters",
  scale = "row",
  cluster_cols = TRUE
)
```

#### Violin plots
```r
plot_pathway_violin(
  seurat_obj,
  pathways = c("MAPK", "PI3K", "TGFb"),
  group.by = "cell_type",
  ncol = 3
)
```

#### Dot plot
```r
plot_pathway_dotplot(
  seurat_obj,
  group.by = "condition"
)
```

#### Pathway correlation
```r
plot_pathway_correlation(
  seurat_obj,
  method = "pearson",
  title = "Pathway Activity Correlation"
)
```

### 5. Differential Pathway Analysis

```r
# Find markers between clusters
pathway_markers <- find_pathway_markers(
  seurat_obj,
  group.by = "seurat_clusters",
  assay = "progeny",
  min.pct = 0,
  logfc.threshold = 0
)

# Top markers per cluster
library(dplyr)
top_markers <- pathway_markers %>%
  group_by(cluster) %>%
  top_n(3, avg_log2FC)

print(top_markers)
```

### 6. Condition Comparison

```r
# Extract pathway scores
scores <- t(as.matrix(seurat_obj[["progeny"]]@data))

# Compare conditions
comparison <- compare_pathway_conditions(
  scores,
  metadata = seurat_obj@meta.data,
  condition_col = "treatment",
  condition1 = "control",
  condition2 = "treated",
  method = "wilcox"
)

# View significant results
comparison %>%
  filter(adj_p_value < 0.05) %>%
  arrange(adj_p_value)
```

### 7. Average Activity by Group

```r
# Calculate average activity
avg_activity <- average_pathway_activity(
  seurat_obj,
  group.by = "condition",
  use_metadata = FALSE
)

print(avg_activity)

# Bar plot
plot_pathway_bar(avg_activity, group_col = "condition")
```

### 8. Permutation Analysis (for significance)

```r
# Extract expression matrix
expr_matrix <- as.matrix(GetAssayData(seurat_obj, layer = "data"))  # Seurat v5
# expr_matrix <- as.matrix(GetAssayData(seurat_obj, slot = "data"))  # Seurat v4

# Run with permutations (computationally intensive)
perm_results <- run_progeny_permutation(
  expr_matrix,
  organism = "Human",
  top = 100,
  perm = 10000,
  z_scores = TRUE,
  get_nulldist = FALSE
)

# Results is a list: [[1]] scores, [[2]] null distributions (if requested)
zscore_matrix <- perm_results
```

### 9. Export Results

```r
# Export all results
export_progeny_results(
  seurat_obj,
  output_dir = "progeny_results",
  prefix = "analysis",
  export_scores = TRUE,
  export_metadata = TRUE
)

# Save updated Seurat object
saveRDS(seurat_obj, "seurat_with_progeny.rds")
```

## Available Pathways

| Pathway | Description |
|---------|-------------|
| Androgen | Androgen receptor signaling |
| EGFR | EGFR signaling |
| Estrogen | Estrogen receptor signaling |
| Hypoxia | Hypoxia response |
| JAK-STAT | JAK-STAT signaling |
| MAPK | MAPK/ERK signaling |
| NFkB | NF-κB signaling |
| PI3K | PI3K-AKT signaling |
| TGFb | TGF-β signaling |
| TNFa | TNF-α signaling |
| Trail | TRAIL signaling |
| VEGF | VEGF signaling |
| WNT | WNT/β-catenin signaling |
| p53 | p53 pathway |

## Best Practices

1. **Gene naming**: Ensure HGNC symbols (Human) or MGI symbols (Mouse)
2. **Normalization**: Use normalized expression values (log-transformed)
3. **top parameter**: 100 is standard; use 200-500 for noisy data, 50 for clean data
4. **Scaling**: FALSE for single-cell (preserves cell-to-cell variation), TRUE for bulk comparison
5. **Validation**: Always check gene overlap (>50% recommended)

## AI Agent Test Cases

### Basic Usage
> "Run PROGENy pathway analysis on my Seurat object"

> "Calculate MAPK and PI3K pathway activities"

### Analysis
> "Find differentially active pathways between clusters"

> "Compare pathway activities between control and treatment"

### Visualization
> "Plot pathway scores on UMAP"

> "Create heatmap of all PROGENy pathways by cell type"

### Advanced
> "Run PROGENy with permutation testing for significance"

> "Identify cells with extreme NFkB activity"

## References

1. Schubert et al. (2018). Perturbation-response genes reveal signaling footprints in cancer gene expression. *Nature Communications*.
2. PROGENy documentation: https://github.com/saezlab/progeny
