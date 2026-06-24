---
name: bio-single-cell-perturbation-augur-r
description: |
  Augur prioritizes cell types by their response to perturbations using machine
  learning. Trains classifiers to predict perturbation labels and ranks cell
  types by classification accuracy (AUC). Supports differential prioritization
  between conditions and visualization. R implementation based on
  neurorestore/Augur.
version: "1.1"
tool_type: r
primary_tool: Augur
supported_tools: [Seurat, dplyr, ggplot2, randomForest, parsnip, yardstick, pbmcapply]
languages: [r]
dependencies:
  - Augur (>= 1.0.0)
  - Seurat (>= 4.0.0, < 5.0.0)
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

## Version Compatibility & Installation

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.0.0 | |
| Augur | >= 1.0.0 | Install from GitHub `neurorestore/Augur` |
| Seurat | >= 4.0.0, < 5.0.0 | Seurat v4 only; Augur uses `slot` not `layer` |
| randomForest | >= 4.6-14 | For RF classifier |
| parsnip | >= 0.0.2 | Model interface |
| yardstick | >= 0.0.3 | Metrics |
| pbmcapply | | Parallel processing |

```r
install.packages("devtools")
install.packages(c("dplyr", "ggplot2", "randomForest", "parsnip",
                   "yardstick", "pbmcapply", "tibble", "purrr",
                   "magrittr", "rsample", "recipes", "tester",
                   "Matrix", "sparseMatrixStats", "glmnet"))
devtools::install_github("neurorestore/Augur")
```

> **Agent warning:** This skill requires **Seurat v4** (`SeuratObject < 5.0.0`). Passing a Seurat v5 object raises an explicit error. To use with v5 data, extract the matrix and metadata manually and pass them to `run_augur()`.

## Skill Overview

Augur trains machine-learning classifiers to predict perturbation labels within each cell type and ranks cell types by classification accuracy (AUC). A higher AUC means the cell type's transcriptome is more distinguishable between conditions, indicating a stronger perturbation response.

**Key characteristics:** AUC = 0.5 means no effect; AUC near 1.0 means strong effect; supports binary/class labels (AUC) and continuous labels (CCC regression mode); requires cell type annotations.

**When to use:**
- You want to prioritize which cell types are most affected by a perturbation.
- You have at least two perturbation conditions and pre-defined cell type labels.
- You want to compare perturbation sensitivity across batches or backgrounds.
- You want feature-importance scores for marker discovery (with random forest).

**When NOT to use:**
- You do not have cell type annotations → annotate first.
- You have only one condition → Augur needs >= 2 labels.
- Cell types have very few cells (<20 per condition) → results will be unreliable.
- You have strong batch confounding → correct batch effects first.
- You need perturbation effect magnitude per gene → use [bio-single-cell-perturbation-pertpy](../bio-single-cell-perturbation-pertpy/SKILL.md) or [bio-single-cell-perturbation-mixscape](../bio-single-cell-perturbation-mixscape/SKILL.md).

## Core Workflow

### Step 1: Validate Input

```r
source("scripts/r/augur_analysis.R")

validation <- validate_augur_data(
  seurat_obj,
  label_col = "condition",
  cell_type_col = "cell_type",
  min_cells = 20
)
print_validation_results(validation)
```

**Requirements:** Seurat v4 object, matrix, or data frame with genes as rows; metadata columns for labels and cell types; at least 2 labels; >= `subsample_size` cells per cell type per condition.

### Step 2: Run Augur

```r
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

augur$AUC
```

**Output:** list of class `Augur` containing `AUC`, `feature_importance`, `results`, etc.

### Step 3: Interpret and Visualize

```r
summarize_augur_results(augur)
plot_augur_lollipop(augur)
plot_augur_umap(augur, seurat_obj, reduction = "umap", top_n = 5)
```

### Step 4: Differential Prioritization (Optional)

```r
augur1 <- run_augur(batch1, label_col = "condition")
augur2 <- run_augur(batch2, label_col = "condition")
perm1 <- run_augur(batch1, label_col = "condition", augur_mode = "permute")
perm2 <- run_augur(batch2, label_col = "condition", augur_mode = "permute")

diff <- run_differential_prioritization(augur1, augur2, perm1, perm2)
plot_augur_differential(diff, top_n = 5)
```

### Input Format Examples

Seurat v4 object:
```r
seurat_obj <- readRDS("data.rds")
table(seurat_obj$condition, seurat_obj$cell_type)  # must have >= 2 labels
```

Matrix + metadata:
```r
expr <- as.matrix(GetAssayData(seurat_obj, slot = "data"))
meta <- seurat_obj@meta.data
augur <- run_augur(expr, meta = meta, label_col = "condition", cell_type_col = "cell_type")
```

Check for missing labels:
```r
any(is.na(meta$condition)) | any(is.na(meta$cell_type))
```

## Complete Pipeline (Copy-Pasteable)

```r
library(Seurat)
source("scripts/r/augur_analysis.R")

seurat_obj <- readRDS("your_data.rds")

validation <- validate_augur_data(
  seurat_obj,
  label_col = "condition",
  cell_type_col = "cell_type",
  min_cells = 20
)
print_validation_results(validation)

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

print(augur$AUC)
print(summarize_augur_results(augur))
plot_augur_lollipop(augur)
plot_augur_umap(augur, seurat_obj, reduction = "umap", top_n = 5)

top_genes <- get_top_features(augur, top_n = 10)
```

## Skill-Provided Functions

### Core analysis
- `run_augur(...)` — main Augur wrapper.
- `run_differential_prioritization(...)` — permutation-based comparison.
- `summarize_augur_results(augur)` — summary statistics.

### Result extraction
- `get_prioritized_cell_types(augur, min_score, top_n)` — rank cell types by AUC.
- `get_top_features(augur, cell_type, top_n)` — top genes by feature importance.

### Visualization
- `plot_augur_lollipop(augur, ...)` — lollipop plot of AUCs.
- `plot_augur_umap(augur, sc, reduction, palette, top_n, ...)` — overlay AUC on UMAP.
- `plot_augur_differential(diff_results, top_n, ...)` — differential prioritization plot.

### Utilities
- `validate_augur_data(...)` — input validation.
- `print_validation_results(validation)` — pretty-print validation.
- `export_augur_results(...)` — export CSVs.

## Official API — Agents Often Miss These

**1. This skill requires Seurat v4**

`run_augur()` checks `SeuratObject` version and errors on v5. To use with v5:
```r
expr_matrix <- Seurat::GetAssayData(seurat_obj, layer = "data")
meta_df <- seurat_obj@meta.data
augur <- run_augur(expr_matrix, meta = meta_df, label_col = "condition")
```

**2. `augur_mode = "permute"` generates a null distribution**

Permutation mode shuffles labels and is used for differential prioritization. Augur internally uses 500 subsamples in permute mode.

**3. Differential prioritization requires four Augur runs**

You need observed Augur results for both conditions **and** permuted Augur results for both conditions:
```r
diff <- run_differential_prioritization(augur1, augur2, perm1, perm2)
```

**4. Feature importance is only available with `classifier = "rf"`**

Logistic regression (`"lr"`) does not return feature importance. `get_top_features()` will error if you use `"lr"`.

**5. `subsample_size` cells are required per cell type per condition**

Cell types with fewer cells are skipped. Either filter cell types or reduce `subsample_size`.

## Common Pitfalls

1. **Seurat v5 incompatibility** — use Seurat v4 or extract matrix + metadata.
2. **Only one unique label** — `run_augur()` needs at least two conditions.
3. **Cell types skipped due to low cell count** — default `subsample_size = 20` requires 20 cells per cell type per condition.
4. **Feature importance missing with logistic regression** — use `classifier = "rf"` for `get_top_features()`.
5. **Strong batch effects** — correct batch effects before Augur.
6. **Forgetting permuted runs for differential prioritization** — you need four Augur objects.

## Scenarios

### Scenario 1: Basic Cell-Type Prioritization

```r
source("scripts/r/augur_analysis.R")

augur <- run_augur(
  seurat_obj,
  label_col = "condition",
  cell_type_col = "cell_type",
  classifier = "rf",
  n_subsamples = 50,
  n_threads = 4
)

head(augur$AUC)
plot_augur_lollipop(augur)
```

### Scenario 2: Compare Two Batches

```r
augur1 <- run_augur(subset(seurat_obj, batch == "A"), label_col = "condition")
augur2 <- run_augur(subset(seurat_obj, batch == "B"), label_col = "condition")
plot_augur_scatterplot(augur1, augur2, top_n = 5)
```

### Scenario 3: Differential Prioritization

```r
augur1 <- run_augur(batch1, label_col = "condition")
augur2 <- run_augur(batch2, label_col = "condition")
perm1 <- run_augur(batch1, label_col = "condition", augur_mode = "permute")
perm2 <- run_augur(batch2, label_col = "condition", augur_mode = "permute")

diff <- run_differential_prioritization(augur1, augur2, perm1, perm2)
sig <- diff[diff$padj < 0.05, ]
plot_augur_differential(diff, top_n = 5)
```

## Parameters

### `run_augur()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input` | Seurat/matrix/df | required | Expression data (genes x cells) |
| `meta` | data.frame | NULL | Metadata (required for matrix/df) |
| `label_col` | char | "label" | Perturbation label column |
| `cell_type_col` | char | "cell_type" | Cell type column |
| `classifier` | char | "rf" | "rf" or "lr" |
| `n_subsamples` | int | 50 | Random subsamples per cell type |
| `subsample_size` | int | 20 | Cells per subsample per condition |
| `folds` | int | 3 | CV folds |
| `min_cells` | int | subsample_size | Minimum cells per cell type per condition |
| `var_quantile` | numeric | 0.5 | HVG selection quantile |
| `feature_perc` | numeric | 0.5 | Proportion of genes as features |
| `n_threads` | int | 4 | Parallel threads |
| `augur_mode` | char | "default" | "default", "velocity", or "permute" |
| `rf_params` | list | list(...) | RF parameters: trees, mtry, min_n, importance |
| `lr_params` | list | list(...) | LR parameters: mixture, penalty |

### `run_differential_prioritization()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `augur1`, `augur2` | Augur | required | Observed Augur results |
| `permuted1`, `permuted2` | Augur | required | Permuted Augur results |
| `n_subsamples` | int | 50 | Subsamples to pool per permutation |
| `n_permutations` | int | 1000 | Number of permutations |

## Output Interpretation

| AUC | Interpretation |
|-----|----------------|
| 0.5 | No effect (random) |
| 0.5–0.7 | Weak effect |
| 0.7–0.9 | Moderate effect |
| 0.9–1.0 | Strong effect |

`run_augur()` returns a list of class `Augur` with `AUC` (or `CCC` in regression mode), `feature_importance`, `results`, and `parameters`.

`run_differential_prioritization()` returns a data frame with `cell_type`, `auc.x`, `auc.y`, `delta_auc`, `b`, `m`, `z`, `pval`, `padj`.

## Best Practices & Runtime Notes

- Genes must be rows; metadata must contain `label_col` and `cell_type_col` with no NAs.
- Each cell type × condition needs ≥ `subsample_size` cells; filter or reduce `subsample_size` for rare groups.
- Use `n_subsamples >= 50` and `folds = 3` for stable AUC estimates.
- Increase `n_subsamples` if AUCs are noisy; decrease if runtime is limiting.
- Decrease `subsample_size` for rare cell types; increase `var_quantile` to remove low-variance noise genes.
- Use `classifier = "rf"` for feature importance; `"lr"` is faster but provides no importance.
- Correct batch effects before comparing AUCs across batches.
- Approximate runtime: ~1–5 min per 1,000 cells with default RF on a few threads.

## API Reference

| Function | Location | Description |
|----------|----------|-------------|
| `run_augur()` | [augur_analysis.R:76](scripts/r/augur_analysis.R#L76) | Main Augur runner |
| `run_differential_prioritization()` | [augur_analysis.R:199](scripts/r/augur_analysis.R#L199) | Differential prioritization |
| `summarize_augur_results()` | [augur_analysis.R:241](scripts/r/augur_analysis.R#L241) | Summary statistics |
| `get_prioritized_cell_types()` | [augur_analysis.R:305](scripts/r/augur_analysis.R#L305) | Rank cell types |
| `get_top_features()` | [augur_analysis.R:331](scripts/r/augur_analysis.R#L331) | Top feature genes |
| `plot_augur_lollipop()` | [augur_analysis.R:371](scripts/r/augur_analysis.R#L371) | Lollipop plot |
| `plot_augur_scatterplot()` | [augur_analysis.R:391](scripts/r/augur_analysis.R#L391) | Scatterplot comparison |
| `plot_augur_umap()` | [augur_analysis.R:415](scripts/r/augur_analysis.R#L415) | UMAP overlay |
| `plot_augur_differential()` | [augur_analysis.R:446](scripts/r/augur_analysis.R#L446) | Differential plot |
| `export_augur_results()` | [augur_analysis.R:467](scripts/r/augur_analysis.R#L467) | Export CSVs |
| `validate_augur_data()` | [augur_analysis.R:522](scripts/r/augur_analysis.R#L522) | Input validation |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Seurat v5 detected...` | SeuratObject >= 5.0.0 | Use Seurat v4 or extract matrix + metadata |
| `only one label provided` | `label_col` has one unique value | Check metadata column |
| `skipping cell type X...` | Insufficient cells per condition | Reduce `subsample_size` or filter cell types |
| `No feature importance found` | Used `classifier = "lr"` | Use `"rf"` for feature importance |
| `install "glmnet" ...` | glmnet missing | `install.packages("glmnet")` |
| Metadata/expression mismatch | Row/column order mismatch | Ensure metadata rows match expression columns |

## Related Skills

- [bio-single-cell-perturbation-mixscape](../bio-single-cell-perturbation-mixscape/SKILL.md) — Perturbation signature detection (Python)
- [bio-single-cell-perturbation-scgen](../bio-single-cell-perturbation-scgen/SKILL.md) — Perturbation modeling with VAE (Python)
- [bio-single-cell-perturbation-pertpy](../bio-single-cell-perturbation-pertpy/SKILL.md) — General perturbation analysis (Python)

## References

1. Skinnider et al. (2019). Cell type prioritization in single-cell data. *Nature Communications*, 10, 5292. https://doi.org/10.1038/s41467-019-12235-0
2. Augur R Package: https://github.com/neurorestore/Augur
