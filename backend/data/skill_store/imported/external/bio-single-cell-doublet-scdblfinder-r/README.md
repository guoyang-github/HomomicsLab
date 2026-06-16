# scDblFinder: Doublet Detection for Single-Cell RNA-seq

Fast and accurate doublet detection using gradient-boosted classification of artificial doublets.

## Overview

scDblFinder is a Bioconductor package for detecting doublets (multiple cells captured within the same droplet) in single-cell RNA-seq data. It uses:

- **Artificial doublet generation**: Creates simulated doublets from real cells
- **Gradient-boosted classification**: Trains classifier to distinguish real cells from doublets
- **Multi-sample support**: Handles batch effects across different captures
- **Cluster-aware**: Can use cluster information for more efficient doublet generation

Reference: Germain et al., PipeComp framework, Genome Biology 2021

## Installation

```r
# Install from Bioconductor
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("scDblFinder")

# Or install latest version from GitHub
BiocManager::install("plger/scDblFinder")
```

Additional dependencies:
```r
install.packages(c("ggplot2", "SingleCellExperiment", "BiocParallel"))
```

## Quick Start

```r
# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# From SingleCellExperiment
library(SingleCellExperiment)
sce <- SingleCellExperiment(assays = list(counts = counts_matrix))
sce <- run_scdblfinder(sce)
table(sce$scDblFinder.class)

# From Seurat
seurat_obj <- run_scdblfinder_seurat(seurat_obj)
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
    └── test_scdblfinder.R
```

## Core Modules

### core_analysis.R

Main analysis functions:

| Function | Description |
|----------|-------------|
| `check_scdblfinder_dependencies()` | Check required packages |
| `validate_scdblfinder_input()` | Validate input data |
| `run_scdblfinder()` | Run scDblFinder analysis |
| `run_scdblfinder_seurat()` | Run with Seurat objects |
| `extract_doublet_scores()` | Get doublet scores |
| `get_doublet_cells()` | Get doublet cell names |
| `get_singlet_cells()` | Get singlet cell names |
| `summarize_scdblfinder_results()` | Summary statistics |
| `filter_scdblfinder()` | Filter doublets |
| `export_scdblfinder_results()` | Export results |
| `add_scdblfinder_to_seurat()` | Add results to Seurat |

### visualization.R

Plotting functions:

| Function | Description |
|----------|-------------|
| `plot_doublet_score_distribution()` | Score histogram |
| `plot_doublet_scores_by_class()` | Boxplot by class |
| `plot_doublet_map()` | Observed vs expected heatmap |
| `plot_doublet_thresholds()` | Threshold optimization |
| `plot_doublets_reduced()` | Plot on UMAP/t-SNE |
| `plot_doublet_rate_by_sample()` | Multi-sample rates |
| `plot_scdblfinder_summary()` | Comprehensive summary |

### utils.R

Utility functions:

| Function | Description |
|----------|-------------|
| `create_scdblfinder_test_data()` | Generate test data |
| `recommend_scdblfinder_params()` | Recommend parameters |
| `estimate_doublet_rate()` | Estimate expected doublet rate |
| `filter_doublets()` | Filter doublets from SCE |
| `compare_scdblfinder_results()` | Compare multiple samples |
| `check_doublet_enrichment()` | Check cluster enrichment |
| `create_scdblfinder_qc_report()` | QC report |

## Input Data Format

### Required

```r
# SingleCellExperiment with counts assay
library(SingleCellExperiment)
sce <- SingleCellExperiment(assays = list(counts = counts_matrix))

# Or raw count matrix
counts_matrix  # matrix or dgCMatrix (genes x cells)
```

### From Seurat

```r
seurat_obj <- run_scdblfinder_seurat(
  seurat_obj,
  samples = "sample_id",  # Optional for multi-sample
  clusters = "seurat_clusters"  # Optional for cluster-aware
)
```

## Output Data

| Output | Location | Description |
|--------|----------|-------------|
| Score | `$scDblFinder.score` | Doublet score (0-1, higher = more likely doublet) |
| Class | `$scDblFinder.class` | "singlet" or "doublet" |
| Origin | `$scDblFinder.mostLikelyOrigin` | Most likely origin clusters (if cluster-based) |

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `clusters` | FALSE | TRUE (auto), FALSE (random), or vector |
| `samples` | NULL | Sample IDs for multi-sample |
| `nfeatures` | 1500 | Number of features to use |
| `dims` | 20 | Number of PCA dimensions |
| `k` | NULL | k for kNN (auto if NULL) |
| `dbr` | NULL | Expected doublet rate (auto if NULL) |
| `dbr.sd` | NULL | Uncertainty in doublet rate |
| `dbr.per1k` | 0.008 | Doublet rate per 1000 cells |

## Examples

### Minimal Example

See `examples/minimal_example.R` for a basic workflow.

### Advanced Example

See `examples/advanced_example.R` for comprehensive analysis including:
- Multi-sample processing
- Cluster-aware detection
- Visualization
- QC reporting

## Testing

Run unit tests:

```r
cd skills/bio-single-cell-doublet-scdblfinder-r
Rscript tests/test_scdblfinder.R
```

Or with testthat:

```r
library(testthat)
test_file("tests/test_scdblfinder.R")
```

## Documentation

- **SKILL.md**: Comprehensive documentation with workflow, parameters, and error handling
- **usage-guide.md**: Step-by-step guide with code examples
- **examples/**: Working example scripts

## Best Practices

1. **Multi-sample**: Use `samples` parameter for batch handling
2. **Expected rate**: Set `dbr.per1k` based on 10X chip type
3. **Clusters**: Use `clusters=TRUE` for better performance on clustered data
4. **Features**: Use HVGs for better performance
5. **Parallel**: Use `BPPARAM` for multi-sample processing

## Comparison with Other Tools

| Feature | scDblFinder | DoubletFinder | Scrublet |
|---------|-------------|---------------|----------|
| Speed | 🚀 Fast | 🐢 Slow | 🚀 Fast |
| Accuracy | ⭐⭐⭐ Excellent | ⭐⭐⭐ Excellent | ⭐⭐ Good |
| Multi-sample | ✅ Yes | ⚠️ Manual | ❌ No |
| Bioconductor | ✅ Yes | ❌ No | ❌ No |
| Native R | ✅ Yes | ✅ Yes | ❌ Python |

scDblFinder was independently evaluated by Xi & Li (2021) and achieved the highest mean AUPRC and AUROC values among doublet detection methods.

## References

1. Germain et al. (2021). PipeComp, a general framework for the evaluation of computational pipelines, reveals performant single cell RNA-seq preprocessing tools. *Genome Biology*.
2. Xi & Li (2021). Benchmarking Computational Doublet-Detection Methods for Single-Cell RNA Sequencing Data. *Cell Systems*.
3. scDblFinder documentation: https://github.com/plger/scDblFinder

## License

This skill wrapper follows the same license as scDblFinder (GPL-3).
