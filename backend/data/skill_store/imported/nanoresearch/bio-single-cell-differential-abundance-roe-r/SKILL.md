---
name: bio-single-cell-differential-abundance-roe-r
description: |
  Differential abundance analysis using Ro/e (Ratio of Observed to Expected) for comparing
  cell type proportions across biological conditions. Quantifies enrichment or depletion of
  each cell type in each group relative to the overall distribution. Includes bootstrap
  confidence intervals, statistical testing (Chi-square, Fisher's exact), and multiple
  visualization styles (heatmap, lollipop, dot plot, bar chart).
tool_type: r
primary_tool: Ro/e Analysis
languages: [r]
keywords: ["single-cell", "differential-abundance", "roe", "ratio", "enrichment",
           "cell-type-proportions", "bootstrap", "statistics", "R"]
---

## Version Compatibility

| Package | Required Version | Notes |
|---------|-----------------|-------|
| R | >= 4.2.0 | |
| Seurat | >= 4.0.0 | v4 and v5 both supported; only uses metadata |
| ggplot2 | >= 3.3.0 | Visualization |
| dplyr | >= 1.0.0 | Data manipulation |
| patchwork | >= 1.1.0 | Optional; multi-panel plots |

## Installation

```r
# Required
install.packages(c("ggplot2", "dplyr"))

# Optional
install.packages("patchwork")   # for plot_roe_multi() multi-panel plots
install.packages("Seurat")      # for run_roe_analysis() Seurat wrapper
```

## Skill Overview

Ro/e (Ratio of Observed to Expected) quantifies how cell type proportions differ from what would be expected if cells were randomly distributed across groups. For each cell type in each group, Ro/e = observed proportion / expected proportion.

**Core workflow**: Prepare vectors -> Calculate Ro/e -> Convert to tidy format -> Visualize -> (Optional) Bootstrap CI

**When to use:**
- Comparing cell type proportions across discrete groups (Tumor vs Normal, Treatment vs Control)
- Identifying which cell types are enriched or depleted in specific conditions
- Case-control studies with well-defined group labels
- Stratified analysis by tissue region or patient subgroup

**When NOT to use:**
- Continuous covariates (e.g., age, expression level) -> use Milo or scCODA instead
- Need neighborhood-level differential abundance -> use Milo
- Need compositional Bayesian modeling -> use scCODA
- Cytometry data with predefined clusters -> use diffcyt

**Input requirements:**
- `cell_types`: Character vector of cell type labels (one per cell)
- `groups`: Character vector of group labels (one per cell, e.g., "Tumor", "Normal")
- Optional: `samples` for paired designs (reserved), `subset_col` for stratified analysis
- NAs in cell_type or group are automatically removed

```r
# Pre-check
print(table(seurat_obj$cell_type, seurat_obj$condition))
# Ensure no critical cell types are missing annotations
```

## Core Workflow

### Step 1 -- Calculate Ro/e

**Input**: `cell_types` vector + `groups` vector
**Output**: `roe_result` list (S3 class) with Ro/e matrix, observed/expected proportions, counts, statistics

```r
source("scripts/r/roe_analysis.R")
roe_result <- calculate_roe(
  cell_types = seurat_obj$cell_type,
  groups = seurat_obj$condition,
  method = "group"
)
print(roe_result)
```

**How it works:**
1. Creates contingency table (cell_types x groups)
2. Computes observed proportions per group (column proportions)
3. Computes expected proportions:
   - `method="group"`: overall observed proportion across all groups (standard Ro/e)
   - `method="global"`: uniform distribution (1 / n_cell_types)
4. Calculates Ro/e = observed / expected for each cell type-group combination
5. Runs statistical tests: overall chi-square + per-cell-type Fisher/chi-square + BH FDR

| Parameter | Default | What It Does | When to Change |
|-----------|---------|--------------|----------------|
| `method` | `"group"` | Expected proportion baseline | `"global"` to test against equal proportions |
| `samples` | `NULL` | Sample IDs for paired analysis | Reserved for future use |

**State after Step 1:** `roe_result` contains Ro/e matrix, statistics, and raw counts.

---

### Step 2 -- Convert to Tidy Data Frame

**Input**: `roe_result` list
**Output**: Tidy data frame with columns: cell_type, group, roe, observed_prop, expected_prop, p_value, p_value_adj, significant

```r
roe_df <- roe_to_dataframe(roe_result)
head(roe_df)

# Filter significant enrichments/depletions
sig_enriched <- roe_df %>%
  filter(significant, roe > 1.5) %>%
  arrange(desc(roe))

sig_depleted <- roe_df %>%
  filter(significant, roe < 0.67) %>%
  arrange(roe)
```

**State after Step 2:** Results in tidy format for downstream analysis and custom plotting.

---

### Step 3 -- Visualize

**Input**: `roe_result` list
**Output**: ggplot objects

```r
source("scripts/r/roe_visualization.R")

# Heatmap (best for multi-group comparisons)
plot_roe_heatmap(roe_result, cluster_rows = TRUE, value_text_size = 3)

# Lollipop (best for 2-group comparisons)
plot_roe_lollipop(roe_result, compare_group = "Tumor",
                  highlight_sig = TRUE, color_by_depletion = TRUE)

# Dot plot (shows Ro/e + proportions simultaneously)
plot_roe_dotplot(roe_result, size_by = "proportion", color_scale = "roe")

# Bar chart
plot_roe_bar(roe_result, show_expected = TRUE)
```

**Visualization guide:**
- **2 groups**: Use lollipop for clearest comparison
- **>2 groups**: Use heatmap for overview
- **Show both Ro/e and abundance**: Use dot plot

**State after Step 3:** Publication-ready figures.

---

### Step 4 -- (Optional) Bootstrap Confidence Intervals

**Input**: `cell_types` vector + `groups` vector
**Output**: `roe_result` with `$bootstrap` component (ci_lower, ci_upper, roe_sd matrices)

```r
roe_boot <- calculate_roe_bootstrap(
  cell_types = seurat_obj$cell_type,
  groups = seurat_obj$condition,
  n_bootstrap = 1000,
  conf_level = 0.95,
  seed = 42
)

roe_df_boot <- roe_to_dataframe(roe_boot)
# Access: roe_df_boot$ci_lower, roe_df_boot$ci_upper
```

**How it works:**
1. Resamples cells within each group with replacement
2. Recalculates Ro/e for each bootstrap iteration
3. Computes quantile-based confidence intervals

**State after Step 4:** Results with confidence intervals for robust inference.

## Complete Pipeline

```r
library(ggplot2)
library(dplyr)
source("scripts/r/roe_analysis.R")
source("scripts/r/roe_visualization.R")

# 1. Calculate Ro/e
roe_result <- calculate_roe(
  cell_types = seurat_obj$cell_type,
  groups = seurat_obj$condition,
  method = "group"
)

# 2. Convert to tidy format
roe_df <- roe_to_dataframe(roe_result)

# 3. Visualize
plot_roe_heatmap(roe_result, value_text_size = 3)
plot_roe_lollipop(roe_result, compare_group = "Tumor", highlight_sig = TRUE)
plot_roe_dotplot(roe_result, size_by = "proportion")

# 4. (Optional) Bootstrap CI
roe_boot <- calculate_roe_bootstrap(
  cell_types = seurat_obj$cell_type,
  groups = seurat_obj$condition,
  n_bootstrap = 1000, seed = 42
)
```

Shortcut: `run_roe_analysis()` wraps metadata extraction and `calculate_roe()` for Seurat objects.

```r
# One-liner for Seurat
roe_result <- run_roe_analysis(
  seurat_obj,
  cell_type_col = "cell_type",
  group_col = "condition",
  subset_col = NULL,
  method = "group"
)
```

## Skill-Provided Functions & API Reference

> All functions are self-implemented. No external core package dependency.

### Analysis Functions

| Function | File | Purpose | Key Parameters |
|----------|------|---------|---------------|
| `calculate_roe(cell_types, groups, method="group", samples=NULL)` | roe_analysis.R | Core Ro/e | `method`: "group" or "global" |
| `calculate_roe_bootstrap(cell_types, groups, n_bootstrap=1000, conf_level=0.95, seed=NULL, ...)` | roe_analysis.R | Bootstrap CI | `n_bootstrap`, `conf_level`, `seed` |
| `run_roe_analysis(seurat_obj, cell_type_col, group_col, subset_col=NULL, ...)` | roe_analysis.R | Seurat wrapper | `subset_col` for stratified analysis |
| `roe_to_dataframe(roe_result)` | roe_analysis.R | Tidy converter | — |

### Visualization Functions

| Function | File | Purpose | Extra Dependencies |
|----------|------|---------|-------------------|
| `plot_roe_heatmap()` | roe_visualization.R | Heatmap | — |
| `plot_roe_lollipop()` | roe_visualization.R | Lollipop chart | — |
| `plot_roe_dotplot()` | roe_visualization.R | Dot plot | — |
| `plot_roe_bar()` | roe_visualization.R | Bar chart | — |
| `plot_roe_multi()` | roe_visualization.R | Multi-panel faceted plot | patchwork |
| `save_roe_plot()` | roe_visualization.R | Save to file | — |

### Result Structures

**`roe_result`** (from `calculate_roe`):

| Field | Type | Content |
|-------|------|---------|
| `$roe` | Matrix | cell_types x groups |
| `$observed` | Matrix | Observed proportions per group |
| `$expected` | Named vector | Expected proportion per cell type |
| `$counts` | Table | Raw cell counts |
| `$statistics` | List | `$chi_square`, `$per_cell_type`, `$overall_p` |
| `$method` | Character | `"group"` or `"global"` |
| `$n_cells` / `$n_groups` / `$n_cell_types` | Integer | Dimensions |

**`roe_result` with bootstrap** (from `calculate_roe_bootstrap`):

| Field | Type | Content |
|-------|------|---------|
| *(all fields above)* | | |
| `$bootstrap$n_bootstrap` | Integer | Iterations |
| `$bootstrap$conf_level` | Numeric | Confidence level |
| `$bootstrap$ci_lower` | Matrix | Lower CI bounds |
| `$bootstrap$ci_upper` | Matrix | Upper CI bounds |
| `$bootstrap$roe_sd` | Matrix | Standard deviations |

**Tidy data frame** (from `roe_to_dataframe`): `cell_type`, `group`, `roe`, `observed_prop`, `expected_prop`, `p_value`, `p_value_adj`, `significant`, `ci_lower`, `ci_upper`

### Ro/e Interpretation Reference

| Ro/e | Interpretation |
|------|----------------|
| > 2.0 | Strong enrichment |
| 1.5 - 2.0 | Moderate enrichment |
| 1.0 - 1.5 | Slight enrichment |
| 0.8 - 1.2 | Near expected |
| 0.5 - 0.8 | Slight depletion |
| < 0.5 | Strong depletion |

**Ro/e = 1**: Observed equals expected -- no enrichment or depletion.

### Underlying Computation

Ro/e is a statistical method implemented entirely in this skill's R scripts:

```r
observed = prop.table(table(cell_types, groups), margin = 2)
expected = rowSums(counts) / sum(counts)   # method="group"
roe = observed / expected
```

Statistical tests:
1. `chisq.test(count_table)` for overall association
2. `fisher.test()` per cell type (2 groups, all counts > 0)
3. `chisq.test()` per cell type (>2 groups or zeros present)
4. `p.adjust(..., method = "BH")` for FDR correction

## Common Pitfalls

1. **Warning `method = "group"` vs `method = "global"` are fundamentally different**
   - `"group"` (default): Expected = overall observed proportion of each cell type. Tests whether a group deviates from the overall baseline.
   - `"global"`: Expected = uniform distribution (1/n_cell_types). Tests whether a group deviates from equal proportions. Do NOT mix them without understanding the difference.

2. **Warning Single cell type or single group produces trivial results**
   With only 1 cell type or 1 group, Ro/e = 1.0 for all entries and the overall chi-square test is skipped (returns `NA`). There must be at least 2 cell types and 2 groups for meaningful analysis.

3. **Warning Very small counts produce unreliable statistics**
   Chi-square tests warn when expected counts are < 5. This is normal for small datasets, but consider bootstrap CIs for more robust inference. Pre-filter cell types with < 10 cells.

4. **Warning All Ro/e values close to 1 means no compositional difference**
   This is a valid biological result (groups have similar compositions), not a bug. Check that the grouping variable is meaningful and cell type annotations have sufficient resolution.

5. **Warning NAs are silently removed**
   `calculate_roe()` automatically drops cells with `NA` in cell_type or group. Verify the final counts match expectations: `print(roe_result$counts)`.

6. **Warning Per-cell-type p-values are the same across all groups**
   Statistical tests are computed per cell type (2 x k table: this type vs all others x groups), not per cell type-group pair. The p-value applies to the cell type overall, not to a specific group.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Error: x must at least have 2 elements` | Single cell type or single group | Ensure >= 2 cell types and >= 2 groups |
| `Warning: Chi-squared approximation may be incorrect` | Small expected counts in chi-square | Expected with small datasets; use bootstrap for robustness |
| Lollipop plot shows overlapping points | Multiple groups without `compare_group` | Set `compare_group` to one group, or use heatmap |
| `Error: data must be a data.frame` | Old code bug in dot plot | Fixed in current version; update scripts |
| `Error: factor level is duplicated` | Old code bug in lollipop | Fixed in current version; update scripts |
| `Warning: Using size aesthetic for lines was deprecated` | Old code using `size` in `geom_tile` | Fixed; uses `linewidth` now |

## Related Skills

- [bio-single-cell-differential-abundance-milor-r](../bio-single-cell-differential-abundance-milor-r/SKILL.md) -- DA on cell neighborhood graphs
- [bio-single-cell-differential-abundance-diffcyt-r](../bio-single-cell-differential-abundance-diffcyt-r/SKILL.md) -- Cytometry differential abundance
- [bio-spatial-transcriptomics-differential-abundance-roe-r](../bio-spatial-transcriptomics-differential-abundance-roe-r/SKILL.md) -- Spatial Ro/e with neighborhood analysis

## References

1. Wu SZ, et al. (2021). A single-cell and spatially resolved atlas of human breast cancers. *Nature Genetics*, 53:1334-1347.
2. Ianevski et al. (2022). Fully-automated and ultra-fast cell-type identification using specific marker combinations. *Nature Communications*, 13:4066.
