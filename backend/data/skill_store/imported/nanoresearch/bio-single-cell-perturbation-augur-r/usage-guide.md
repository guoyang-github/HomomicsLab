# Augur Single-Cell Usage Guide (R)

## Overview

Augur identifies which cell types are most affected by perturbations by training machine learning classifiers to predict sample labels. Cell types with higher classification accuracy (AUC) are more affected by the perturbation.

This is the R implementation based on the original [neurorestore/Augur](https://github.com/neurorestore/Augur) package.

## When to Use

- **Prioritize cell types**: Find which cell types respond most strongly to perturbations
- **Compare conditions**: Compare sensitivity across different experimental conditions
- **Validate perturbations**: Confirm expected cell types are affected
- **Feature discovery**: Identify marker genes that distinguish perturbed states

## When Not to Use

- **No cell type labels**: Augur requires pre-defined cell types
- **Single condition**: Need at least 2 perturbation conditions
- **Very rare cell types**: Cell types with <20 cells per condition may be unreliable
- **Batch effects**: Strong batch confounding may bias results (correct first)

## Prerequisites

### Installation

```r
install.packages("devtools")

# Install Augur from GitHub
devtools::install_github("neurorestore/Augur")

# Install suggested packages
install.packages(c("Seurat", "dplyr", "ggplot2"))
```

### Data Requirements

Input requirements:
- Seurat object, matrix, or data frame with genes in rows and cells in columns
- Metadata with perturbation labels and cell type annotations
- Minimum 20 cells per cell type per condition

## Step-by-Step Guide

### Step 1: Prepare Data

```r
library(Seurat)

# Load your data
seurat_obj <- readRDS("perturb_seq_data.rds")

# Check required columns
cat("Obs columns:", colnames(seurat_obj@meta.data), "\n")
cat("\nPerturbation distribution:\n")
print(table(seurat_obj$condition))
cat("\nCell type distribution:\n")
print(table(seurat_obj$cell_type))
```

### Step 2: Data Validation

```r
source("scripts/r/augur_analysis.R")

# Check cell type counts per condition
crosstab <- table(seurat_obj$cell_type, seurat_obj$condition)
print(crosstab)

# Validate data
validation <- validate_augur_data(
  seurat_obj,
  label_col = "condition",
  cell_type_col = "cell_type",
  min_cells = 20
)
print_validation_results(validation)

# Filter to cell types with sufficient cells
min_cells <- 20
valid_cell_types <- rownames(crosstab)[apply(crosstab, 1, function(x) all(x >= min_cells))]
seurat_obj <- subset(seurat_obj, cell_type %in% valid_cell_types)
cat(sprintf("Retained %d cell types with >= %d cells\n", length(valid_cell_types), min_cells))
```

### Step 3: Run Augur

```r
# Run with default random forest
augur <- run_augur(
  seurat_obj,
  label_col = "condition",
  cell_type_col = "cell_type",
  classifier = "rf",
  n_subsamples = 50,
  subsample_size = 20,
  folds = 3,
  n_threads = 4
)

# View results
print(augur$AUC)
```

### Step 4: Interpret Results

```r
# Sort by AUC
auc_sorted <- augur$AUC[order(augur$AUC$auc, decreasing = TRUE), ]

cat("\nCell Type Prioritization (most to least affected):\n")
for (i in seq_len(nrow(auc_sorted))) {
  score <- auc_sorted$auc[i]
  interpretation <- interpret_augur_score(score)
  cat(sprintf("  %s: %.3f (%s)\n", auc_sorted$cell_type[i], score, interpretation))
}
```

### Step 5: Visualization

#### Lollipop Plot

```r
p <- plot_augur_lollipop(augur)
print(p)
ggsave("augur_lollipop.pdf", p, width = 6, height = 4)
```

#### UMAP Overlay

```r
p <- plot_augur_umap(
  augur, seurat_obj,
  reduction = "umap",
  palette = "cividis",
  top_n = 5
)
print(p)
```

### Step 6: Feature Importance Analysis

```r
# Get top genes per cell type
top_genes <- get_top_features(augur, top_n = 10)
print(top_genes)

# Top genes for specific cell type
t_cell_genes <- get_top_features(augur, cell_type = "T_cell", top_n = 10)
print(t_cell_genes)
```

### Step 7: Differential Prioritization

Compare Augur scores between two experimental conditions:

```r
# Split data by batch and run Augur for each
batch1 <- subset(seurat_obj, batch == "Batch1")
batch2 <- subset(seurat_obj, batch == "Batch2")

augur1 <- run_augur(batch1, label_col = "condition", n_threads = 4)
augur2 <- run_augur(batch2, label_col = "condition", n_threads = 4)

# Run permuted versions for null distribution
perm1 <- run_augur(batch1, label_col = "condition", augur_mode = "permute")
perm2 <- run_augur(batch2, label_col = "condition", augur_mode = "permute")

# Differential prioritization
diff <- run_differential_prioritization(
  augur1, augur2, perm1, perm2,
  n_permutations = 1000
)

# View significant results
print(diff[diff$padj < 0.05, c("cell_type", "auc.x", "auc.y", "delta_auc", "padj")])

# Plot
p <- plot_augur_differential(diff, top_n = 5)
print(p)
ggsave("augur_differential.pdf", p, width = 5, height = 5)
```

## Parameters Reference

### run_augur()

| Parameter | Default | Description |
|-----------|---------|-------------|
| `input` | - | Seurat, matrix, or data frame (genes x cells) |
| `meta` | NULL | Metadata data frame (required for matrix input) |
| `label_col` | `"label"` | Condition label column |
| `cell_type_col` | `"cell_type"` | Cell type column |
| `classifier` | `"rf"` | `"rf"` or `"lr"` |
| `n_subsamples` | 50 | Random subsamples per cell type |
| `subsample_size` | 20 | Cells per subsample per condition |
| `folds` | 3 | CV folds |
| `min_cells` | subsample_size | Minimum cells per cell type |
| `var_quantile` | 0.5 | HVG selection quantile |
| `feature_perc` | 0.5 | Gene proportion for features |
| `n_threads` | 4 | Parallel threads |
| `augur_mode` | `"default"` | `"default"`, `"velocity"`, `"permute"` |
| `show_progress` | TRUE | Show progress bar |

### RF Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `trees` | 100 | Number of trees |
| `mtry` | 2 | Features at each split |
| `importance` | `"accuracy"` | `"accuracy"` or `"gini"` |

## AI Agent Test Cases

### Basic Prioritization
> "Run Augur to prioritize cell types by perturbation response"

```r
augur <- run_augur(seurat_obj, label_col = "condition", cell_type_col = "cell_type")
```

### With Custom Parameters
> "Run Augur with 100 subsamples and logistic regression"

```r
augur <- run_augur(
  seurat_obj,
  label_col = "condition",
  classifier = "lr",
  n_subsamples = 100,
  subsample_size = 30
)
```

### Compare Conditions
> "Compare Augur scores between two batches"

```r
augur1 <- run_augur(subset(seurat_obj, batch == "A"), label_col = "condition")
augur2 <- run_augur(subset(seurat_obj, batch == "B"), label_col = "condition")
plot_augur_scatterplot(augur1, augur2, top_n = 5)
```

### Plot Results
> "Plot Augur prioritization as a lollipop chart"

```r
plot_augur_lollipop(augur)
```

## Troubleshooting

### Low AUCs for all cell types
- Check perturbation labels are correct
- Verify cell type annotations are accurate
- Consider if perturbation is subtle

### High variance in scores
- Increase `n_subsamples` (e.g., to 100)
- Increase `subsample_size` if many cells available
- Check for batch effects

### Cell types being skipped
- Reduce `subsample_size` or `min_cells`
- Filter to cell types present in all conditions
- Check crosstab of cell types vs conditions

### Package installation issues
- Ensure R >= 4.0.0
- Install MatrixGenerics and sparseMatrixStats from Bioconductor
- For Seurat input, ensure Seurat is installed

## Best Practices

1. **Validate cell type labels**: Incorrect annotations will give misleading results
2. **Check for batch effects**: Correct batch effects before running Augur
3. **Use permutation test**: Establish statistical significance
4. **Inspect feature importance**: Known markers should be important
5. **Consider cell abundance**: Results for rare cell types may be noisy
6. **Run differential prioritization**: Compare across conditions rigorously

## References

1. Skinnider et al. (2019). Cell type prioritization in single-cell data. *Nature Communications*.
2. https://github.com/neurorestore/Augur
