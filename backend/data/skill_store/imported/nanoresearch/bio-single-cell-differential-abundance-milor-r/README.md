# miloR: Differential Abundance Analysis for Single-Cell Data

R package for differential abundance (DA) analysis on single-cell data using graph-based neighborhoods. Tests for changes in cell population abundance between conditions without requiring discrete clustering.

## Overview

miloR performs statistical testing for differential abundance in single-cell data by:

- **Building KNN graph**: Represents cell-cell similarity structure
- **Defining neighborhoods**: Samples representative cells and defines local neighborhoods
- **Counting cells**: Counts cells per neighborhood per sample
- **DA testing**: Tests for differential abundance using edgeR/limma
- **Spatial FDR**: Adjusts for multiple testing using neighborhood structure

Reference: Dann et al., "Milo detects differentially abundant cell populations in single-cell data", Nature Biotechnology 2021

## Installation

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("miloR")
```

Optional packages for visualization:
```r
BiocManager::install("ComplexHeatmap")
install.packages("ggplot2")
```

## Quick Start

```r
library(miloR)
library(SingleCellExperiment)

# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Run complete pipeline
results <- run_milo_pipeline(
  x = sce,                    # SingleCellExperiment object
  sample_col = "sample_id",
  condition_col = "condition",
  design = ~ condition,
  k = 30,                     # k for kNN graph
  d = 30,                     # PCA dimensions
  prop = 0.1,                 # Sampling proportion
  refined = TRUE              # Refined sampling
)

# View results
top_da <- get_top_da_nhoods(results$da_results, n_top = 10)
summary <- summarize_milo_results(results$da_results)
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
    └── test_milor.R
```

## Core Modules

### core_analysis.R

Main analysis functions:

| Function | Description |
|----------|-------------|
| `validate_milor_input()` | Validate input data |
| `create_milo_object()` | Create Milo object from SCE |
| `build_milo_graph()` | Build kNN graph |
| `make_milo_neighborhoods()` | Define neighborhoods |
| `calc_milo_distances()` | Calculate neighborhood distances |
| `count_milo_cells()` | Count cells per neighborhood |
| `test_milo_da()` | Test differential abundance |
| `run_milo_pipeline()` | Complete pipeline |
| `group_milo_neighborhoods()` | Group overlapping DA neighborhoods |
| `find_milo_markers()` | Find marker genes for DA neighborhoods |
| `annotate_milo_neighborhoods()` | Annotate with cell types |

### visualization.R

Plotting functions:

| Function | Description |
|----------|-------------|
| `plot_milo_beeswarm()` | DA beeswarm plot |
| `plot_milo_graph_da()` | Neighborhood graph with DA |
| `plot_milo_umap_da()` | DA on UMAP embedding |
| `plot_milo_volcano()` | Volcano plot |
| `plot_milo_counts()` | Cell counts per neighborhood |
| `plot_milo_size_distribution()` | Neighborhood size distribution |
| `plot_milo_summary()` | Multi-panel summary |

### utils.R

Utility functions:

| Function | Description |
|----------|-------------|
| `create_milo_test_data()` | Generate test data |
| `seurat_to_sce()` | Convert Seurat to SCE |
| `create_milo_design()` | Create design data frame |
| `get_top_da_nhoods()` | Get top DA neighborhoods |
| `get_significant_nhoods()` | Get significant neighborhoods |
| `summarize_milo_results()` | Summarize DA results |
| `export_milo_results()` | Export to CSV |
| `recommend_milo_k()` | Recommend k parameter |
| `recommend_milo_prop()` | Recommend prop parameter |

## Input Data Format

### Required

```r
# SingleCellExperiment with:
# - logcounts or counts assay
# - Reduced dimensions (PCA, UMAP, etc.)
# - Sample metadata in colData

sce <- SingleCellExperiment(
  assays = list(logcounts = logcounts_matrix),
  colData = data.frame(
    sample_id = factor(sample_ids),
    condition = factor(conditions)
  ),
  reducedDims = SimpleList(PCA = pca_matrix)
)
```

### From Seurat

```r
sce <- seurat_to_sce(seurat_obj, assay = "RNA")
```

## Output Data

| Output | Description |
|--------|-------------|
| `da_results` | Data frame with logFC, PValue, SpatialFDR |
| `milo` | Milo object with neighborhoods |
| `nhoodCounts` | Cell counts per neighborhood per sample |

## Examples

### Minimal Example

See `examples/minimal_example.R` for a basic workflow.

### Advanced Example

See `examples/advanced_example.R` for comprehensive analysis including:
- Batch correction in design formula
- Neighborhood grouping
- Marker gene identification
- Cell type annotation
- Multiple parameter comparisons

## Testing

Run unit tests:

```r
cd skills/bio-single-cell-differential-abundance-milor-r
Rscript tests/test_milor.R
```

Or with testthat:

```r
library(testthat)
test_file("tests/test_milor.R")
```

## Documentation

- **SKILL.md**: Comprehensive documentation with workflow, parameters, and error handling
- **usage-guide.md**: Step-by-step guide with code examples
- **examples/**: Working example scripts

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `k` | 30 | k for kNN graph |
| `d` | 30 | Number of PCA dimensions |
| `prop` | 0.1 | Proportion of cells to sample |
| `refined` | TRUE | Use refined neighborhood sampling |
| `fdr.weighting` | "k-distance" | Method for spatial FDR |
| `norm.method` | "TMM" | Normalization method |

## Best Practices

1. **k parameter**: 30-50 for most datasets, larger for dense datasets
2. **Refined sampling**: Use TRUE for better neighborhood coverage
3. **Replicates**: Need biological replicates per condition (minimum 2-3)
4. **Batch correction**: Include batch in design formula
5. **Cell type annotation**: Annotate DA neighborhoods post-hoc

## References

1. Dann et al. (2022). Milo detects differentially abundant cell populations in single-cell data. *Nature Biotechnology*, 40, 245-253.
2. miloR Bioconductor: https://bioconductor.org/packages/miloR
3. miloR GitHub: https://github.com/MarioniLab/miloR

## License

This skill wrapper follows the same license as miloR (GPL-3).
