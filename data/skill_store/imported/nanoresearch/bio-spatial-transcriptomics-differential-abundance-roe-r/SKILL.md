---
name: bio-spatial-transcriptomics-differential-abundance-roe-r
description: |
  Spatial Ro/e (Ratio of Observed to Expected) analysis for quantifying cell type
  co-occurrence patterns and regional enrichment in spatial transcriptomics data.
  Two complementary analyses: (1) Co-occurrence -- which cell types are spatial neighbors;
  (2) Regional Abundance -- which cell types are enriched in anatomical regions.
tool_type: r
primary_tool: Spatial Ro/e Analysis
languages: [r]
keywords: ["spatial-transcriptomics", "differential-abundance", "roe", "co-occurrence",
           "colocalization", "neighborhood", "network", "regional-enrichment", "anatomical-regions"]
---

## Version Compatibility

| Package | Required Version | Notes |
|---------|-----------------|-------|
| R | >= 4.2.0 | |
| dplyr | >= 1.0.0 | Core analysis |
| ggplot2 | >= 3.3.0 | Visualization |
| reshape2 | >= 1.4.0 | Visualization |
| Seurat | >= 4.3.0 | Optional; v4 and v5 both supported |
| igraph | >= 1.2.0 | Optional; network plots only |
| ggraph | >= 2.0.0 | Optional; network plots only |
| circlize | >= 0.4.0 | Optional; chord diagrams only |

## Installation

```r
# Required
install.packages(c("dplyr", "ggplot2", "reshape2"))

# Optional -- only if you use the corresponding features
install.packages(c("igraph", "ggraph"))   # for network plots
install.packages("circlize")              # for chord diagrams
install.packages("Seurat")                # for Seurat wrappers
```

## Skill Overview

Spatial Ro/e quantifies cell type co-occurrence patterns and regional enrichment in spatial transcriptomics using the Ratio of Observed to Expected statistic.

**Core workflow**: Define neighborhoods/regions -> Calculate observed co-occurrence/abundance -> Compute expected under random -> Ro/e = Observed/Expected -> Permutation test + FDR

**Two complementary analyses:**

| Analysis | Question | Core Function |
|----------|----------|---------------|
| **Co-occurrence** | Which cell types are spatial neighbors? | `calculate_spatial_roe()` |
| **Regional Abundance** | Which cell types prefer which regions? | `calculate_regional_roe()` |

**When to use:**
- Identifying cellular niches and co-localization patterns in spatial data
- Detecting cell type exclusion patterns (e.g., immune cells excluded from tumor core)
- Comparing spatial organization between conditions (High vs Low NI)
- Post-deconvolution spatial analysis (cell2location, RCTD, Tangram proportions)
- Validating deconvolution results against known anatomy

**When NOT to use:**
- Non-spatial scRNA-seq without coordinates -> use `bio-single-cell-differential-abundance-roe-r`
- Need continuous interaction scores (ligand-receptor) -> use CellChat or LIANA
- Need 3D tissue modeling -> use MISTy
- Very small datasets (< 20 spots) -> statistical power insufficient

**Input requirements:**

**Co-occurrence analysis:**
- `cell_types`: Vector of labels (one per spot) OR proportion matrix (spots x cell_types)
- `coords`: Data frame with x, y coordinates (one row per spot)

**Regional abundance analysis:**
- `proportions`: Matrix of deconvolution proportions (spots x cell_types, 0-1)
- `regions`: Vector of anatomical region labels (one per spot)

```r
# Pre-check: ensure coordinates align with cell type labels
stopifnot(nrow(coords) == length(cell_types))
stopifnot(nrow(coords) == length(regions))
```

## Core Workflow

### Analysis 1: Spatial Co-occurrence

**Question**: Which cell types spatially co-localize or exclude each other?

#### Step 1 -- Define Neighborhoods

**Input**: Spatial coordinates + cell type data
**Output**: Spot-level neighborhood index list

```r
result <- calculate_spatial_roe(
  cell_types = cell_labels,
  coords = coords,
  method = "radius",
  radius = 150,
  min_neighbors = 3
)
```

**How it works:**
1. For each spot, finds all neighbors within `radius` (or `k` nearest for `method="knn"`)
2. Filters spots with fewer than `min_neighbors`

| Parameter | Default | What It Does | Platform Recommendation |
|-----------|---------|--------------|------------------------|
| `method` | `"radius"` | Neighborhood definition | `"knn"` for irregular spacing |
| `radius` | `NULL` | Search radius (auto if NULL) | Visium 100-150μm, Slide-seq 20-30μm, MERFISH 5-10μm |
| `k` | `10` | Nearest neighbors | Increase for sparse data |
| `min_neighbors` | `3` | Min neighbors for valid spot | Lower for sparse platforms |

**State after Step 1:** Valid neighborhoods computed for each spot.

#### Step 2 -- Calculate Ro/e

**Input**: Neighborhoods + cell type data
**Output**: Symmetric Ro/e matrix (cell_types x cell_types)

**Calculation:**
- **Observed** = mean proportion of cell type B in neighborhoods of cell type A
- **Expected** = global_freq(A) x global_freq(B)
- **Ro/e** = Observed / Expected

**State after Step 2:** Ro/e matrix computed. Values > 1 = co-localization; < 1 = exclusion.

#### Step 3 -- Statistical Testing

**Input**: Ro/e matrix
**Output**: Significance flags (BH-adjusted p-values)

**How it works:**
1. Permutation test: randomize spot locations (100 iterations, seed=42)
2. Compare observed vs null distribution
3. Benjamini-Hochberg FDR correction

**State after Step 3:** `$statistics$significant` matrix available.

#### Step 4 -- Visualize

**Input**: `spatial_roe_result`
**Output**: ggplot/igraph/circlize objects

```r
plot_spatial_roe_heatmap(result, show_values = TRUE)
plot_spatial_roe_network(result, min_roe = 1.5)
plot_spatial_roe_chord(result, min_roe = 1.5)
plot_spatial_roe_lollipop(result, n_top = 20)
```

**State after Step 4:** Figures generated.

---

### Analysis 2: Regional Abundance

**Question**: Which cell types are enriched or depleted in specific anatomical regions?

#### Step 1 -- Aggregate by Region

**Input**: Deconvolution proportions + region labels
**Output**: Region-aggregated proportion matrix

```r
result <- calculate_regional_roe(
  proportions = deconv_matrix,
  regions = region_labels,
  aggr_method = "mean",
  min_spots = 5
)
```

**How it works:**
1. Aggregates proportions per region (mean or median)
2. Filters regions with < `min_spots` and cell types with mean proportion < `min_proportion`

| Parameter | Default | What It Does |
|-----------|---------|--------------|
| `aggr_method` | `"mean"` | Regional aggregation | `"median"` for robustness |
| `min_spots` | `5` | Min spots per region | Lower for small datasets |
| `min_proportion` | `0.01` | Min mean proportion for cell type | |

**State after Step 1:** Valid region-cell_type combinations computed.

#### Step 2 -- Calculate Ro/e

**Input**: Aggregated proportions
**Output**: Ro/e matrix (cell_types x regions)

**Calculation:**
- **Observed** = aggregated proportion within region
- **Expected** = global mean proportion across all spots
- **Ro/e** = Observed / Expected

**State after Step 2:** Ro/e matrix computed.

#### Step 3 -- Statistical Testing

Same as co-occurrence: permutation test + BH FDR.

**State after Step 3:** Significance flags available.

#### Step 4 -- Visualize

```r
plot_regional_roe_heatmap(result, show_values = TRUE)
plot_regional_roe_lollipop(result, region = "Tumor_Core")
plot_regional_composition(result, normalize = TRUE)
plot_regional_comparison(result)
```

**State after Step 4:** Figures generated.

## Advanced Scenarios

### Bootstrap Confidence Intervals (Regional)

**When to use**: When permutation p-values are insufficient and you need confidence intervals for Ro/e estimates. Slower than standard analysis.

**Input**: Same as `calculate_regional_roe()`
**Output**: `regional_roe_result` with `$bootstrap` component

```r
result_boot <- calculate_regional_roe_bootstrap(
  proportions = deconv_matrix,
  regions = region_labels,
  n_bootstrap = 500,
  conf_level = 0.95
)

# Access CI
result_boot$bootstrap$ci_lower
result_boot$bootstrap$ci_upper
result_boot$bootstrap$roe_sd
```

**How it works:**
1. Resamples spots within each region with replacement
2. Recalculates Ro/e for each iteration
3. Computes quantile-based confidence intervals

### Condition Comparison (Regional)

**When to use**: Comparing regional enrichment between two conditions (e.g., High NI vs Low NI).

**Input**: Two proportion matrices + two region vectors
**Output**: Differential Ro/e and fold change

```r
comparison <- compare_regional_roe(
  proportions_list = list(
    High_NI = props_high,
    Low_NI = props_low
  ),
  regions_list = list(
    High_NI = regions_high,
    Low_NI = regions_low
  )
)

# Differential results
comparison$differential$diff_roe
comparison$differential$fold_change

# Individual condition results
comparison$High_NI
comparison$Low_NI
```

**Important:** Only supports **exactly 2 conditions**. Requires common regions and cell types across conditions.

## Complete Pipeline

### Scenario A: Basic Co-occurrence + Regional

```r
library(ggplot2)
source("scripts/r/spatial_roe_analysis.R")
source("scripts/r/spatial_roe_visualization.R")
source("scripts/r/regional_roe_analysis.R")
source("scripts/r/regional_roe_visualization.R")

# Co-occurrence
result_spatial <- calculate_spatial_roe(
  cell_types = cell_labels, coords = spatial_coords,
  method = "radius", radius = 150
)
plot_spatial_roe_heatmap(result_spatial)
plot_spatial_roe_network(result_spatial, min_roe = 1.5)

# Regional abundance
result_regional <- calculate_regional_roe(
  proportions = deconv_matrix, regions = region_labels
)
plot_regional_roe_heatmap(result_regional)
```

### Scenario B: With Bootstrap CI

```r
result_boot <- calculate_regional_roe_bootstrap(
  proportions = deconv_matrix, regions = region_labels,
  n_bootstrap = 500, conf_level = 0.95
)

# Plot with CI
library(ggplot2)
roe_df <- regional_roe_to_dataframe(result_boot)
ggplot(roe_df, aes(x = cell_type, y = roe)) +
  geom_pointrange(aes(ymin = ci_lower, ymax = ci_upper)) +
  geom_hline(yintercept = 1, linetype = "dashed") +
  coord_flip() + theme_minimal()
```

### Scenario C: Compare Conditions

```r
comparison <- compare_regional_roe(
  proportions_list = list(High_NI = props_high, Low_NI = props_low),
  regions_list = list(High_NI = regions_high, Low_NI = regions_low)
)

plot_regional_condition_comparison(comparison, plot_type = "heatmap")
```

## Skill-Provided Functions & API Reference

> All functions are self-implemented. No external core package dependency.

### Analysis Functions

| Function | File | Purpose | Key Parameters |
|----------|------|---------|---------------|
| `calculate_spatial_roe(cell_types, coords, method="radius", radius=NULL, k=10, min_neighbors=3)` | spatial_roe_analysis.R | Core co-occurrence | `radius`, `k`, `min_neighbors` |
| `run_spatial_roe(seurat_obj, cell_type_col, coord_slot="spatial", ...)` | spatial_roe_analysis.R | Seurat wrapper | `cell_type_col`, `coord_slot` |
| `spatial_roe_to_dataframe(x)` | spatial_roe_analysis.R | Tidy converter | — |
| `calculate_regional_roe(proportions, regions, aggr_method="mean", min_spots=5, min_proportion=0.01)` | regional_roe_analysis.R | Core regional abundance | `aggr_method`, `min_spots` |
| `calculate_regional_roe_bootstrap(proportions, regions, n_bootstrap=500, conf_level=0.95, ...)` | regional_roe_analysis.R | Bootstrap CI | `n_bootstrap`, `conf_level` |
| `compare_regional_roe(proportions_list, regions_list, ...)` | regional_roe_analysis.R | Condition comparison | — (exactly 2 conditions) |
| `run_regional_roe(seurat_obj, deconv_assay="predictions", region_col="region", ...)` | regional_roe_analysis.R | Seurat wrapper | `deconv_assay`, `region_col` |
| `calculate_regional_specificity(x)` | regional_roe_analysis.R | Specificity scores | — |
| `regional_roe_to_dataframe(x)` | regional_roe_analysis.R | Tidy converter | — |

### Visualization Functions

| Function | File | Purpose | Extra Dependencies |
|----------|------|---------|-------------------|
| `plot_spatial_roe_heatmap()` | spatial_roe_viz.R | Co-occurrence heatmap | — |
| `plot_spatial_roe_network()` | spatial_roe_viz.R | Co-localization network | igraph, ggraph |
| `plot_spatial_roe_chord()` | spatial_roe_viz.R | Circular co-localization | circlize |
| `plot_spatial_roe_lollipop()` | spatial_roe_viz.R | Top interactions ranking | — |
| `plot_neighborhood_map()` | spatial_roe_viz.R | Neighborhood size map | — |
| `plot_regional_roe_heatmap()` | regional_roe_viz.R | Regional enrichment heatmap | — |
| `plot_regional_roe_lollipop()` | regional_roe_viz.R | Region-specific enrichment | — |
| `plot_regional_composition()` | regional_roe_viz.R | Stacked composition bar | — |
| `plot_regional_comparison()` | regional_roe_viz.R | Multi-region faceted plot | — |
| `plot_regional_condition_comparison()` | regional_roe_viz.R | Differential heatmap/scatter | — |
| `plot_spatial_regions()` | regional_roe_viz.R | Region boundary map | — |

### Result Structures

**`spatial_roe_result`** (from `calculate_spatial_roe`):

| Field | Type | Content |
|-------|------|---------|
| `$roe` | Matrix | cell_types x cell_types, symmetric |
| `$observed` | Matrix | Observed co-occurrence proportions |
| `$expected` | Matrix | Expected under random |
| `$statistics` | List | `$p_values`, `$p_values_adj`, `$significant` |
| `$neighbors` | List | Spot-level neighborhood indices |

**`regional_roe_result`** (from `calculate_regional_roe`):

| Field | Type | Content |
|-------|------|---------|
| `$roe` | Matrix | cell_types x regions |
| `$observed` | Matrix | Aggregated proportions per region |
| `$expected` | Vector | Global mean per cell type |
| `$statistics` | List | `$p_values`, `$p_values_adj`, `$significant` |
| `$regions` | Character | Region names |
| `$bootstrap` | List | Only from `bootstrap`: `$ci_lower`, `$ci_upper`, `$roe_sd` |

**`regional_roe_comparison`** (from `compare_regional_roe`):

| Field | Type | Content |
|-------|------|---------|
| `[[cond_name]]` | List | Each condition's `regional_roe_result` |
| `$differential$diff_roe` | Matrix | cond1 - cond2 |
| `$differential$fold_change` | Matrix | cond1 / cond2 |
| `$differential$common_regions` | Character | Shared regions |
| `$differential$common_celltypes` | Character | Shared cell types |

**Tidy data frame** (from `*_to_dataframe`): `cell_type`, `region`, `roe`, `observed_prop`, `expected_prop`, `p_value`, `p_value_adj`, `significant`, `interpretation`

## Ro/e Interpretation Reference

| Ro/e | Co-occurrence | Regional Abundance |
|------|--------------|-------------------|
| > 2.0 | Strong co-localization | Strongly enriched |
| 1.5 - 2.0 | Moderate co-localization | Moderately enriched |
| 1.0 - 1.5 | Slight co-localization | Slightly enriched |
| 0.8 - 1.2 | Random distribution | Proportionate to region |
| 0.5 - 0.8 | Moderate exclusion | Moderately depleted |
| < 0.5 | Strong exclusion | Strongly depleted |

**Ro/e = 1**: No enrichment or depletion -- observed equals expected.

## Common Pitfalls

1. **Warning Ro/e = 1 does NOT mean "no interaction" in co-occurrence**
   Ro/e = 1 means random spatial distribution. For co-occurrence, this is the baseline. For regional abundance, it means the cell type is at the global average proportion.

2. **Warning `radius` must match platform spot size**
   Visium ~55μm apart; use 100-150μm. Slide-seq ~10μm; use 20-30μm. MERFISH ~5μm; use 5-10μm. Wrong radius produces meaningless neighborhoods.

3. **Warning Proportion matrix must be spots x cell_types**
   `calculate_spatial_roe()` accepts deconvolution proportion matrices. Ensure rows = spots, columns = cell types. Transpose with `t()` if needed.

4. **Warning `compare_regional_roe()` only supports exactly 2 conditions**
   Requires named lists of exactly 2 elements. Will warn if no common regions or cell types exist.

5. **Warning Permutation test uses fixed seed = 42**
   Results are deterministic. For publication, use `calculate_regional_roe_bootstrap()` which provides confidence intervals.

6. **Warning Diagonal values in co-occurrence are self-co-occurrence**
   Represents how much a cell type clusters with itself. Usually high but less interesting than off-diagonal cross-interactions.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| All Ro/e values ≈ 1 | Groups have similar compositions | Check grouping; increase cell type resolution |
| Many NA Ro/e values | Zero counts or insufficient neighbors | Lower `min_neighbors` or increase `radius` |
| `nrow(coords) != length(cell_types)` | Mismatched dimensions | Ensure same length and order |
| Network plot too cluttered | Too many cell types or low threshold | Increase `min_roe` or filter to top N |
| Chord diagram fails | `circlize` not installed | `install.packages("circlize")` |
| Bootstrap extremely slow | Large dataset + many iterations | Reduce `n_bootstrap` to 200-500 |
| `LayerData/GetAssayData not found` | Seurat version mismatch | Update SeuratObject to >= 4.9.9 |

## Related Skills

- [bio-single-cell-differential-abundance-roe-r](../bio-single-cell-differential-abundance-roe-r/SKILL.md) -- Non-spatial Ro/e for bulk/scRNA-seq
- [bio-spatial-transcriptomics-deconvolution-cell2location](../bio-spatial-transcriptomics-deconvolution-cell2location/SKILL.md) -- Pre-processing: cell type deconvolution
- [bio-spatial-transcriptomics-communication-cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/SKILL.md) -- Ligand-receptor analysis

## References

1. Ianevski et al. (2022). Fully-automated and ultra-fast cell-type identification using specific marker combinations. *Nature Communications*, 13:4066.
2. Arnold et al. (2020). Modeling cell-cell interactions from spatial molecular data.
