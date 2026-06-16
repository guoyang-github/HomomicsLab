---
name: bio-single-cell-perturbation-augur-r
description: |
  Augur prioritizes cell types by their response to perturbations using machine
  learning. Trains classifiers to predict perturbation labels and ranks cell types
  by classification accuracy (AUC). Supports differential prioritization between
  conditions and comprehensive visualization. R implementation based on the
  original neurorestore/Augur package.
tool_type: r
primary_tool: Augur
language: r
dependencies:
  - Augur (>= 1.0.0)
  - Seurat (>= 4.0.0, < 5.0.0; Augur uses `GetAssayData()` without `layer` parameter, incompatible with Seurat v5)
  - dplyr
  - ggplot2
  - randomForest
  - parsnip
  - yardstick
  - pbmcapply
system_requirements:
  - R >= 4.0.0
keywords: ["perturb-seq", "augur", "cell-type-prioritization",
           "differential-analysis", "classification", "random-forest",
           "feature-importance", "R"]
---

## Version Compatibility

- **R**: >= 4.0.0
- **Augur**: >= 1.0.0 (install from GitHub: neurorestore/Augur)
- **Seurat**: >= 4.0.0, < 5.0.0 (for Seurat object input; Augur's internal `GetAssayData()` call does not support Seurat v5 `layer` parameter)
- **randomForest**: >= 4.6-14
- **parsnip**: >= 0.0.2
- **yardstick**: >= 0.0.3

## Installation

```r
# Install devtools if needed
install.packages("devtools")

# Install dependencies
install.packages(c("dplyr", "ggplot2", "randomForest", "parsnip",
                   "yardstick", "pbmcapply", "tibble", "purrr",
                   "magrittr", "rsample", "recipes", "tester",
                   "Matrix", "sparseMatrixStats", "glmnet"))

# Install Augur from GitHub
devtools::install_github("neurorestore/Augur")
```

## Data Requirements

Input requirements:
- **Single-cell expression data**: Seurat object, monocle3 cds, SingleCellExperiment, matrix, or data frame (genes x cells)
- **Perturbation labels**: Column in metadata with condition labels (e.g., 'control', 'treatment')
- **Cell type annotations**: Column in metadata with cell type labels
- **Minimum requirements**:
  - At least 2 perturbation conditions
  - Minimum 20 cells per cell type per condition (default `subsample_size`)
  - Minimum 1000 genes recommended for feature selection

## Module Structure

```
scripts/r/
└── augur_analysis.R          # Utility functions for Augur analysis
                                 # - run_augur()
                                 # - run_differential_prioritization()
                                 # - summarize_augur_results()
                                 # - get_prioritized_cell_types()
                                 # - get_top_features()
                                 # - plot_augur_lollipop()
                                 # - plot_augur_scatterplot()
                                 # - plot_augur_umap()
                                 # - plot_augur_differential()
                                 # - export_augur_results()
                                 # - validate_augur_data()

examples/
├── minimal_example.R         # Basic Augur workflow
└── advanced_example.R        # Multi-condition, differential prioritization

tests/
└── test_augur_analysis.R     # Unit tests
```

## Core Analysis Workflow

### 1. Run Augur

**Function:** `run_augur()`

**Purpose:** Train classifiers and calculate AUC for each cell type.

**Key Parameters:**
- `input`: Seurat object, matrix, or data frame (genes x cells)
- `meta`: Metadata data frame (required for matrix/df input)
- `label_col`: Column with perturbation labels. Default: `"label"`
- `cell_type_col`: Column with cell type annotations. Default: `"cell_type"`
- `classifier`: `"rf"` (random forest, default) or `"lr"` (logistic regression)
- `n_subsamples`: Number of random subsamples per cell type. Default: 50
- `subsample_size`: Cells per subsample per condition. Default: 20
- `folds`: Cross-validation folds. Default: 3
- `min_cells`: Minimum cells per cell type. Default: subsample_size
- `var_quantile`: Quantile for HVG selection. Default: 0.5
- `feature_perc`: Proportion of genes as features. Default: 0.5
- `n_threads`: Parallel threads. Default: 4
- `augur_mode`: `"default"`, `"velocity"`, or `"permute"`
- `rf_params`: Random forest parameters (trees, mtry, min_n, importance)
- `lr_params`: Logistic regression parameters (mixture, penalty)

**Returns:** List of class `"Augur"` with:
- `AUC`: Mean AUC per cell type (classification)
- `CCC`: Mean CCC per cell type (regression)
- `feature_importance`: Gene importance scores
- `results`: Detailed CV results

**Example:**
```r
source("scripts/r/augur_analysis.R")

# Default random forest classifier
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
augur$AUC
```

### 2. Score Interpretation

| Score Range | Interpretation |
|-------------|----------------|
| 0.5 | Random (no effect) |
| 0.5-0.7 | Weak effect |
| 0.7-0.9 | Moderate effect |
| 0.9-1.0 | Strong effect |

**Important:**
- AUC = 0.5 indicates the classifier cannot distinguish conditions
- Higher AUC = cell type is more affected by perturbation
- Rank cell types by AUC to prioritize for follow-up

### 3. Differential Prioritization

Compare cell type prioritization between two conditions using permutation test.

**Function:** `run_differential_prioritization()`

**Parameters:**
- `augur1`, `augur2`: Augur results for two conditions
- `permuted1`, `permuted2`: Permuted Augur results (`augur_mode = "permute"`)
- `n_permutations`: Number of permutations. Default: 1000

**Example:**
```r
# Run Augur for condition A
augur_a <- run_augur(adata_a, label_col = "condition")

# Run Augur for condition B
augur_b <- run_augur(adata_b, label_col = "condition")

# Run permuted versions for null distribution
perm_a <- run_augur(adata_a, label_col = "condition", augur_mode = "permute")
perm_b <- run_augur(adata_b, label_col = "condition", augur_mode = "permute")

# Differential prioritization
diff <- run_differential_prioritization(
  augur_a, augur_b, perm_a, perm_b,
  n_permutations = 1000
)

# View significant cell types
diff[diff$padj < 0.05, ]
```

### 4. Feature Importance

Access gene importance scores from trained classifiers.

**Function:** `get_top_features()`

**Example:**
```r
# Top genes across all cell types
top_genes <- get_top_features(augur, top_n = 10)

# Top genes for specific cell type
t_t_cell_genes <- get_top_features(augur, cell_type = "T_cell", top_n = 10)
```

### 5. Visualization

#### Lollipop Plot

```r
plot_augur_lollipop(augur)
```

#### Scatterplot Comparison

```r
plot_augur_scatterplot(augur1, augur2, top_n = 5)
```

#### UMAP Overlay

```r
plot_augur_umap(augur, seurat_obj, reduction = "umap", palette = "cividis")
```

#### Differential Prioritization Plot

```r
plot_augur_differential(diff_results, top_n = 5)
```

## Utility Functions

### Data Validation

```r
# Validate input data
validation <- validate_augur_data(
  seurat_obj,
  label_col = "condition",
  cell_type_col = "cell_type",
  min_cells = 20
)

# Print validation results
print_validation_results(validation)
```

### Result Summary

```r
# Get summary statistics
stats <- summarize_augur_results(augur)
print(sprintf("Most affected: %s (AUC = %.3f)", stats$most_affected, stats$max_auc))

# Interpret individual scores
for (i in seq_len(nrow(augur$AUC))) {
  score <- augur$AUC$auc[i]
  interpretation <- interpret_augur_score(score)
  print(sprintf("%s: %.3f - %s", augur$AUC$cell_type[i], score, interpretation))
}
```

### Prioritized Cell Types

```r
# Get top prioritized cell types
top_cell_types <- get_prioritized_cell_types(augur, min_score = 0.7, top_n = 5)
```

### Export Results

```r
export_augur_results(
  augur,
  output_dir = "augur_results",
  prefix = "sample1",
  export_summary = TRUE,
  export_importances = TRUE,
  export_detailed = FALSE
)
```

## Input Requirements

### Required Data Format

**Seurat object:**
```r
# Required meta.data columns
head(seurat_obj@meta.data)
#      condition cell_type
# 1   control   T_cell
# 2 treatment   T_cell
# 3   control   B_cell
```

**Matrix + metadata:**
```r
# Expression matrix: genes x cells
expr_matrix[1:5, 1:3]
#        Cell1 Cell2 Cell3
# Gene1   0.0   1.2   0.5
# Gene2   2.1   0.0   1.8

# Metadata data frame
meta <- data.frame(
  condition = c("control", "treatment", "control"),
  cell_type = c("T_cell", "T_cell", "B_cell"),
  row.names = c("Cell1", "Cell2", "Cell3")
)
```

### Data Validation

```r
# Check label distribution
table(seurat_obj$cell_type, seurat_obj$condition)

# Check for NA values
sum(is.na(seurat_obj$condition))
sum(is.na(seurat_obj$cell_type))
```

## Output Specifications

### Core Outputs

| Output | Type | Description |
|--------|------|-------------|
| `AUC` | Data frame | Mean AUC per cell type |
| `feature_importance` | Data frame | Gene importance per cell type |
| `results` | Data frame | Detailed CV results per fold/subsample |

### AUC Columns

| Column | Description |
|--------|-------------|
| `cell_type` | Cell type name |
| `auc` | Mean AUC across subsamples |

### Feature Importance Columns

| Column | Description |
|--------|-------------|
| `cell_type` | Cell type name |
| `subsample_idx` | Subsample index |
| `fold` | CV fold |
| `gene` | Gene symbol |
| `importance` | Importance score |

## Key Parameters

### Augur Initialization

| Parameter | Default | Description | When to Adjust |
|-----------|---------|-------------|----------------|
| `classifier` | `"rf"` | ML classifier | Use `"lr"` for faster runtime |
| `n_subsamples` | 50 | Random subsamples | Increase for stability |
| `subsample_size` | 20 | Cells per subsample | Increase if many cells available |
| `folds` | 3 | CV folds | Increase to 5 for robustness |
| `var_quantile` | 0.5 | HVG quantile | Lower for more genes |
| `feature_perc` | 0.5 | Gene proportion | Adjust based on gene count |

### Classifier Options

| Classifier | Best For | Notes |
|------------|----------|-------|
| `"rf"` | General use | Default, robust, supports feature importance |
| `"lr"` | Linear separability | Faster, L1 regularized via glmnet |

### RF Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `trees` | 100 | Number of trees |
| `mtry` | 2 | Features sampled at each split |
| `importance` | `"accuracy"` | `"accuracy"` or `"gini"` |

## Expected Runtime

| Dataset Size | N Subsamples | Runtime |
|--------------|--------------|---------|
| 1k cells, 3 cell types | 50 | 2-4 min |
| 5k cells, 5 cell types | 50 | 5-10 min |
| 10k cells, 10 cell types | 50 | 15-30 min |
| 50k cells, 15 cell types | 50 | 45-90 min |

*Runtime estimates on 4-core CPU with random forest*

## Error Handling

### Insufficient cells per type
```
Warning: skipping cell type X: minimum number of cells (N) is less than 20
```
-> Reduce `subsample_size` or filter cell types

### Only one label
```
Error: only one label provided
```
-> Check `label_col` has multiple unique values

### Missing package
```
Error: install "glmnet" R package to run Augur with logistic regression classifier
```
-> Install required package

### Dimension mismatch
```
Error: number of cells in metadata (N) does not match number of cells in expression (M)
```
-> Ensure metadata rows match expression columns

## Common Analysis Patterns

### Pattern 1: Quick Prioritization
```r
augur <- run_augur(seurat_obj, label_col = "condition", cell_type_col = "cell_type")
top_cell_types <- head(augur$AUC, 3)
```

### Pattern 2: Compare Conditions
```r
augur1 <- run_augur(subset(seurat_obj, batch == "A"), label_col = "condition")
augur2 <- run_augur(subset(seurat_obj, batch == "B"), label_col = "condition")
plot_augur_scatterplot(augur1, augur2, top_n = 5)
```

### Pattern 3: Permutation Test
```r
augur_obs <- run_augur(seurat_obj, label_col = "condition")
augur_null <- run_augur(seurat_obj, label_col = "condition", augur_mode = "permute")
# Compare observed vs null AUCs
```

### Pattern 4: Differential Prioritization
```r
# Two conditions with common control
augur_treat <- run_augur(seurat_treat, label_col = "condition")
augur_ctrl <- run_augur(seurat_ctrl, label_col = "condition")
perm_treat <- run_augur(seurat_treat, label_col = "condition", augur_mode = "permute")
perm_ctrl <- run_augur(seurat_ctrl, label_col = "condition", augur_mode = "permute")

diff <- run_differential_prioritization(
  augur_treat, augur_ctrl, perm_treat, perm_ctrl
)
plot_augur_differential(diff, top_n = 5)
```

## Best Practices

1. **Check baseline**: AUCs near 0.5 = no detectable effect
2. **Use appropriate subsample_size**: Balance statistical power and runtime
3. **Validate with permutation test**: Assess statistical significance
4. **Inspect feature importance**: Validate known marker genes are important
5. **Consider cell type abundance**: Rare cell types may have high variance
6. **Account for batch effects**: Correct batch effects before running Augur

## Related Skills

- [bio-single-cell-perturbation-mixscape](../bio-single-cell-perturbation-mixscape/SKILL.md) - Perturbation signature detection (Python)
- [bio-single-cell-perturbation-scgen](../bio-single-cell-perturbation-scgen/SKILL.md) - Perturbation modeling with VAE (Python)
- [bio-single-cell-perturbation-pertpy](../bio-single-cell-perturbation-pertpy/SKILL.md) - General perturbation analysis (Python)

## References

1. Skinnider et al. (2019). Cell type prioritization in single-cell data. *Nature Communications*, 10, 5292. https://doi.org/10.1038/s41467-019-12235-0
2. Skinnider et al. (2021). Spatial charting of single-cell transcriptomes in tissues. *Nature Biotechnology*, 39, 674-678. https://doi.org/10.1038/s41587-020-0605-1
3. Augur R Package: https://github.com/neurorestore/Augur
