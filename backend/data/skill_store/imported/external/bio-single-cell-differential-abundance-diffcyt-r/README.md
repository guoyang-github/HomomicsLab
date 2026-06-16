# diffcyt: Differential Analysis in Cytometry

R package for differential abundance (DA) and differential state (DS) analysis in high-dimensional cytometry data using high-resolution clustering and empirical Bayes moderated tests.

## Overview

diffcyt performs statistical analysis for differential discovery in high-dimensional cytometry data (flow cytometry, mass cytometry/CyTOF, oligonucleotide-tagged cytometry). It combines:

- **High-resolution clustering**: FlowSOM algorithm for cell population identification
- **Differential Abundance (DA)**: Tests for differences in cell cluster proportions
- **Differential State (DS)**: Tests for differences in marker expression within clusters
- **Statistical methods**: edgeR, limma-voom, and GLMM frameworks

Reference: Weber et al., "diffcyt: Differential discovery in high-dimensional cytometry via high-resolution clustering", Communications Biology 2019

## Installation

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("diffcyt")
```

Optional packages for visualization:
```r
BiocManager::install(c("CATALYST", "ComplexHeatmap"))
install.packages(c("ggplot2", "reshape2"))
```

## Quick Start

```r
library(diffcyt)

# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/utils.R")

# Load or create data
d_input <- list(
  sample1 = matrix(rnorm(20000), nrow = 1000, ncol = 20),
  sample2 = matrix(rnorm(20000), nrow = 1000, ncol = 20)
)

experiment_info <- data.frame(
  sample_id = factor(c("sample1", "sample2")),
  group_id = factor(c("control", "treated"))
)

marker_info <- data.frame(
  marker_name = paste0("marker", 1:20),
  marker_class = factor(c(rep("type", 10), rep("state", 10)))
)

# Run complete pipeline
results <- run_diffcyt_pipeline(
  d_input = d_input,
  experiment_info = experiment_info,
  marker_info = marker_info,
  analysis_type = "DA"
)

# View results
top_results <- get_top_results(results$res, n_top = 10)
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
    └── test_diffcyt.R
```

## Core Modules

### core_analysis.R

Main analysis functions:

| Function | Description |
|----------|-------------|
| `validate_diffcyt_input()` | Validate data structure |
| `prepare_diffcyt_data()` | Prepare SummarizedExperiment |
| `generate_diffcyt_clusters()` | FlowSOM clustering |
| `test_da_edger()` | DA with edgeR |
| `run_diffcyt_pipeline()` | Complete pipeline |

### visualization.R

Plotting functions:

| Function | Description |
|----------|-------------|
| `plot_volcano()` | Volcano plot |
| `plot_ma()` | MA plot |
| `plot_cluster_abundance()` | Cluster abundance plot |
| `plot_marker_heatmap()` | Marker expression heatmap |

### utils.R

Utility functions:

| Function | Description |
|----------|-------------|
| `create_experiment_info()` | Create experiment metadata |
| `create_marker_info()` | Create marker metadata |
| `summarize_results()` | Summarize test results |
| `export_results()` | Export to CSV |
| `create_test_data()` | Generate test data |
| `filter_clusters_by_abundance()` | Filter low-abundance clusters |
| `normalize_counts()` | Normalize cluster counts |

## Input Data Format

### Required

```r
# Input data: list of matrices or flowSet
d_input <- list(
  sample1 = matrix(...),
  sample2 = matrix(...)
)

# Experiment info
experiment_info <- data.frame(
  sample_id = factor(c("s1", "s2")),
  group_id = factor(c("A", "B"))
)

# Marker info
marker_info <- data.frame(
  marker_name = c("CD3", "CD4", "CD8", "IFNg", "TNFa"),
  marker_class = factor(c("type", "type", "type", "state", "state"))
)
```

### Marker Classes

| Class | Use | Example |
|-------|-----|---------|
| `type` | Clustering | CD3, CD4, CD8, CD19 |
| `state` | DS testing | pSTAT, cytokines |
| `none` | Ignore | Time, barcodes |

## Output Data

| Output | Description |
|--------|-------------|
| `res` | Test results (p-values, logFC) |
| `d_se` | Processed data with clusters |
| `d_counts` | Cluster counts matrix |
| `d_medians` | Cluster median expression |

## Examples

### Minimal Example

See `examples/minimal_example.R` for a basic workflow.

### Advanced Example

See `examples/advanced_example.R` for comprehensive analysis including:
- Both DA and DS analysis
- Multiple testing methods
- Comprehensive visualization
- Result comparison

## Testing

Run unit tests:

```r
cd skills/bio-single-cell-differential-abundance-diffcyt-r
Rscript tests/test_diffcyt.R
```

Or with testthat:

```r
library(testthat)
test_file("tests/test_diffcyt.R")
```

## Documentation

- **SKILL.md**: Comprehensive documentation with workflow, parameters, and error handling
- **usage-guide.md**: Step-by-step guide with code examples
- **examples/**: Working example scripts

## DA vs DS Analysis

### Differential Abundance (DA)
- Tests for differences in cell cluster proportions
- Use when comparing cell population frequencies
- Methods: edgeR, voom, GLMM

### Differential State (DS)
- Tests for differences in marker expression within clusters
- Use when comparing activation states or functional markers
- Methods: limma, LMM

## References

1. Weber et al. (2019). diffcyt: Differential discovery in high-dimensional cytometry via high-resolution clustering. *Communications Biology*, 2, 183.
2. diffcyt Bioconductor: https://bioconductor.org/packages/diffcyt
3. CATALYST: Chevrier et al. (2018), *Nature Methods*, 15, 275-278.
4. FlowSOM: Van Gassen et al. (2015), *Cytometry A*, 87, 251-262.

## License

This skill wrapper follows the same license as diffcyt (GPL-3).
