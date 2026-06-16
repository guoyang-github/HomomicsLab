# RCTD: Robust Cell Type Decomposition

R package for spatial transcriptomics deconvolution with doublet detection and platform effect normalization.

## Overview

RCTD performs cell type deconvolution for spatial transcriptomics by:

- **Platform effect normalization**: Corrects for differences between scRNA-seq and spatial platforms
- **Doublet detection**: Classifies spots as singlets, doublets, or uncertain
- **Multiple modes**: 'full' (any number of cell types), 'doublet' (1-2 cell types), or 'multi' (greedy algorithm)
- **Robust estimation**: Uses iterative reweighted least squares for stable proportions

Reference: Cable et al., "Robust decomposition of cell type mixtures in spatial transcriptomics", Nature Methods 2022

## Installation

```r
# Install spacexr from GitHub
if (!require("devtools", quietly = TRUE))
    install.packages("devtools")

devtools::install_github("dmcable/spacexr", build_vignettes = FALSE)
```

Additional dependencies:
```r
install.packages(c("ggplot2", "Matrix", "reshape2", "patchwork"))
```

## Quick Start

```r
# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Run RCTD deconvolution
results <- run_rctd(
  spatial_counts = spatial_counts,
  spatial_coords = spatial_coords,
  reference_counts = ref_counts,
  cell_types = cell_types,
  doublet_mode = "doublet",
  max_cores = 4
)

# Extract proportions
props <- extract_proportions_rctd(results)

# Visualize
plot_rctd_proportions(results, cell_types = c("T_cell", "B_cell"))
```

## Directory Structure

```
.
├── README.md                 # This file
├── SKILL.md                  # Detailed documentation for LLM agents
├── usage-guide.md            # Step-by-step usage guide
├── examples/                 # Example scripts
│   ├── minimal_example.R     # Basic workflow
│   └── advanced_example.R    # Comprehensive workflow
├── scripts/                  # Core analysis scripts
│   └── r/
│       ├── core_analysis.R   # Main analysis functions
│       ├── visualization.R   # Plotting functions
│       └── utils.R           # Utility functions
└── tests/                    # Unit tests
    └── test_rctd.R
```

## Core Modules

### core_analysis.R

Main analysis functions:

| Function | Description |
|----------|-------------|
| `check_rctd_dependencies()` | Check required packages |
| `validate_rctd_input()` | Validate input data |
| `create_rctd_objects()` | Create SpatialRNA and Reference objects |
| `run_rctd()` | Run RCTD deconvolution |
| `run_rctd_seurat()` | Run with Seurat objects |
| `extract_proportions_rctd()` | Get cell type proportions |
| `summarize_rctd_results()` | Summary statistics |
| `get_top_cell_types()` | Get top N cell types per spot |
| `get_doublet_predictions()` | Extract doublet predictions |
| `export_rctd_results()` | Export results |
| `create_rctd_report()` | Generate text report |

### visualization.R

Plotting functions:

| Function | Description |
|----------|-------------|
| `plot_rctd_proportions()` | Spatial proportion plots |
| `plot_rctd_dominant()` | Dominant cell type map |
| `plot_rctd_doublets()` | Doublet classification map |
| `plot_rctd_distribution()` | Proportion distribution |
| `plot_rctd_mean_props()` | Mean proportions bar chart |
| `plot_rctd_heatmap()` | Proportion heatmap |
| `plot_rctd_scatter()` | Scatter comparison |
| `plot_rctd_summary()` | Comprehensive summary |

### utils.R

Utility functions:

| Function | Description |
|----------|-------------|
| `create_rctd_test_data()` | Generate test data |
| `recommend_rctd_params()` | Recommend parameters |
| `filter_rctd_spots()` | Filter spots by criteria |
| `compare_rctd_results()` | Compare multiple results |
| `merge_rctd_cell_types()` | Merge cell types |
| `calculate_proportion_entropy()` | Calculate mixing entropy |
| `get_high_purity_spots()` | Get pure spots |
| `get_mixed_spots()` | Get mixed spots |
| `export_rctd_to_seurat()` | Add proportions to Seurat |

## Input Data Format

### Required

```r
# Spatial data: Counts matrix (genes x spots)
spatial_counts  # dgCMatrix or matrix

# Spatial coordinates: DataFrame with x, y
spatial_coords  # columns: "x", "y"

# Reference data: Single-cell counts (genes x cells)
reference_counts  # dgCMatrix or matrix

# Cell type labels: Named vector
# names must match colnames(reference_counts)
cell_types  # factor with cell names as names
```

### From Seurat

```r
results <- run_rctd_seurat(
  spatial_seurat = spatial_obj,
  reference_seurat = ref_obj,
  cell_type_column = "cell_type"
)
```

## Output Data

| Output | Location | Description |
|--------|----------|-------------|
| Proportions | `@results$weights` | Cell type proportions per spot (full mode) |
| Doublet weights | `@results$weights_doublet` | Proportions in doublet mode |
| Spot class | `@results$results_df$spot_class` | singlet/doublet/reject |
| First type | `@results$results_df$first_type` | Primary cell type |
| Second type | `@results$results_df$second_type` | Secondary cell type (doublets) |

## Examples

### Minimal Example

See `examples/minimal_example.R` for a basic workflow.

### Advanced Example

See `examples/advanced_example.R` for comprehensive analysis including:
- Seurat integration
- Multiple visualization types
- Result filtering and comparison
- Comprehensive reporting

## Testing

Run unit tests:

```r
cd skills/bio-spatial-transcriptomics-deconvolution-rctd-r
Rscript tests/test_rctd.R
```

Or with testthat:

```r
library(testthat)
test_file("tests/test_rctd.R")
```

## Documentation

- **SKILL.md**: Comprehensive documentation with workflow, parameters, and error handling
- **usage-guide.md**: Step-by-step guide with code examples
- **examples/**: Working example scripts

## Best Practices

1. **Reference quality**: Use high-quality annotated scRNA-seq with ≥25 cells per type
2. **Cell type selection**: Include all expected cell types
3. **Platform effects**: RCTD normalizes automatically, but check results
4. **Doublet mode**: Use 'doublet' mode for Visium, 'full' for high-resolution data
5. **Multiple cores**: Use `max_cores > 1` for faster computation

## Comparison with Other Methods

| Feature | RCTD | CARD | SPOTlight |
|---------|------|------|-----------|
| Doublet detection | ✅ Yes | ❌ No | ❌ No |
| Platform effect correction | ✅ Yes | ❌ No | ❌ No |
| Speed | 🐢 Medium | 🐢 Slow | 🚀 Fast |
| ct2loc imputation | ❌ No | ✅ Yes | ❌ No |
| Multi-sample | ✅ Yes | ✅ Yes | ❌ No |

Use RCTD when:
- You need doublet detection
- Platform effects may be significant
- You want rigorous statistical inference

## References

1. Cable et al. (2022). Robust decomposition of cell type mixtures in spatial transcriptomics. *Nature Methods*, 19, 711-718.
2. spacexr GitHub: https://github.com/dmcable/spacexr

## License

This skill wrapper follows the same license as spacexr (GPL-3).
