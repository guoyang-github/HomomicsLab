# CARD: Spatial Correlation-Aware Deconvolution

R package for spatial transcriptomics deconvolution using Conditional Autoregressive (CAR) model. CARD models spatial correlations between spots, making it ideal for analyzing tissue architecture.

## Overview

CARD performs cell type deconvolution for spatial transcriptomics by:

- **Spatial correlation modeling**: Accounts for spatial dependencies between spots
- **Conditional autoregressive prior**: Encourages similar cell type composition in neighboring spots
- **ct2loc imputation**: Cell type-informed gene expression imputation
- **Multi-sample support**: Joint analysis of multiple tissue slices

Reference: Ma et al., "CARD: Deconvolution of spatial transcriptomics with conditional autoregressive model", Nature Communications 2022

## Installation

```r
if (!require("devtools", quietly = TRUE))
    install.packages("devtools")

devtools::install_github("YingMa0107/CARD")
```

Additional dependencies:
```r
install.packages(c("ggplot2", "reshape2", "cowplot", "patchwork"))
```

## Quick Start

```r
# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Run CARD deconvolution
results <- run_card(
  spatial_counts = spatial_counts,
  spatial_coords = spatial_coords,
  reference_counts = ref_counts,
  cell_types = cell_types,
  spatial_mode = "single"
)

# Extract proportions
props <- extract_proportions_card(results)

# Visualize
plot_card_proportions(results, cell_types = c("T_cell", "B_cell"))
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
    └── test_card.R
```

## Core Modules

### core_analysis.R

Main analysis functions:

| Function | Description |
|----------|-------------|
| `check_card_dependencies()` | Check required packages |
| `validate_card_input()` | Validate input data |
| `create_card_object()` | Create CARD data object |
| `run_card()` | Run CARD deconvolution |
| `run_card_seurat()` | Run with Seurat objects |
| `extract_proportions_card()` | Get cell type proportions |
| `extract_refined_expression()` | Get ct2loc expression |
| `summarize_card_results()` | Summary statistics |

### visualization.R

Plotting functions:

| Function | Description |
|----------|-------------|
| `plot_card_proportions()` | Spatial proportion plots |
| `plot_card_pie()` | Pie chart visualization |
| `plot_card_ct2loc()` | Cell type to location plots |
| `plot_card_comparison()` | Compare across conditions |
| `plot_card_heatmap()` | Proportion heatmap |
| `plot_card_domains()` | Spatial domains (multi-mode) |
| `plot_card_summary()` | Comprehensive summary |

### utils.R

Utility functions:

| Function | Description |
|----------|-------------|
| `create_card_test_data()` | Generate test data |
| `prepare_card_seurat()` | Prepare Seurat objects |
| `export_card_results()` | Export results |
| `create_card_report()` | Generate text report |
| `filter_card_spots()` | Filter spots by criteria |
| `compare_card_results()` | Compare multiple results |
| `get_dominant_celltype()` | Get dominant cell type per spot |
| `recommend_card_params()` | Recommend parameters |

## Input Data Format

### Required

```r
# Spatial data: Counts matrix (genes x spots)
spatial_counts  # dgCMatrix or matrix

# Spatial coordinates: DataFrame with x, y
spatial_coords  # columns: "x", "y"

# Reference data: Single-cell counts (genes x cells)
reference_counts  # dgCMatrix or matrix

# Cell type labels: Named factor
cell_types  # names match colnames(reference_counts)
```

### From Seurat

```r
results <- run_card_seurat(
  spatial_seurat = spatial_obj,
  reference_seurat = ref_obj,
  cell_type_column = "cell_type"
)
```

## Output Data

| Output | Location | Description |
|--------|----------|-------------|
| Proportions | `@Proportion_CARD` | Cell type proportions per spot |
| Coordinates | `@spatial_location` | Spatial coordinates |
| Refined expression | `@refined_expression` | ct2loc imputed expression |
| Spatial domains | `@spatial_domain` | Domain labels (multi-mode) |

## Examples

### Minimal Example

See `examples/minimal_example.R` for a basic workflow.

### Advanced Example

See `examples/advanced_example.R` for comprehensive analysis including:
- Seurat integration
- Multiple visualization types
- Region-based comparison
- Comprehensive reporting

## Testing

Run unit tests:

```r
cd skills/bio-spatial-transcriptomics-deconvolution-card-r
Rscript tests/test_card.R
```

Or with testthat:

```r
library(testthat)
test_file("tests/test_card.R")
```

## Documentation

- **SKILL.md**: Comprehensive documentation with workflow, parameters, and error handling
- **usage-guide.md**: Step-by-step guide with code examples
- **examples/**: Working example scripts

## Best Practices

1. **Reference quality**: Use high-quality annotated scRNA-seq
2. **Cell type selection**: Include all expected cell types
3. **Spatial coordinates**: Ensure accurate coordinate alignment
4. **Filtering**: Remove low-UMI spots before analysis
5. **Multiple samples**: Use "multi" mode for joint analysis

## Comparison with Other Methods

| Feature | CARD | RCTD | SPOTlight |
|---------|------|------|-----------|
| Spatial correlation | ✅ Yes | ✅ Yes | ❌ No |
| Speed | 🐢 Slow | 🐢 Slow | 🚀 Fast |
| ct2loc imputation | ✅ Yes | ❌ No | ❌ No |
| Multi-sample | ✅ Yes | ✅ Yes | ❌ No |

## References

1. Ma et al. (2022). CARD: Computational deconvolution of spatial transcriptomics with conditional autoregressive model. *Nature Communications*, 13, 1-17.
2. CARD GitHub: https://github.com/YingMa0107/CARD

## License

This skill wrapper follows the same license as CARD (GPL-3).
