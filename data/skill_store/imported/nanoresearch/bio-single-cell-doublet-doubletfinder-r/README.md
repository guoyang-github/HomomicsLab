# bio-single-cell-doublet-doubletfinder-r

DoubletFinder doublet detection for single-cell RNA sequencing data using artificial nearest neighbor (pANN) classification.

## Description

This skill provides DoubletFinder doublet detection capabilities for identifying doublets (two cells captured in the same droplet) in single-cell RNA-seq data. DoubletFinder generates artificial doublets from real data, computes the proportion of artificial nearest neighbors (pANN) for each cell, and classifies cells based on pANN thresholding.

## Features

- **pANN-based classification**: Uses proportion of artificial nearest neighbors
- **Parameter sweep**: Automatic optimization of pK parameter using BCmvn
- **Homotypic adjustment**: Adjust for transcriptionally-similar doublets using cell annotations
- **SCTransform support**: Compatible with SCTransform normalization
- **Parallel processing**: Speed up parameter sweep with multiple cores
- **Platform-specific rates**: Built-in doublet rates for major platforms (10x, Parse, Drop-seq)
- **Comprehensive visualization**: pK optimization, doublet embedding, pANN distributions

## Installation

```r
remotes::install_github('chris-mcginnis-ucsf/DoubletFinder')
```

## Quick Start

```r
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")

# Load pre-processed Seurat object (after NormalizeData, ScaleData, RunPCA)
seurat_obj <- readRDS("processed_data.rds")

# Run complete workflow
seurat_obj <- run_doubletfinder_workflow(
  seurat_obj,
  PCs = 1:20,
  adjust_homotypic = TRUE,
  cluster_col = "seurat_clusters",
  filter = TRUE
)

# Visualize
plot_doublet_summary(seurat_obj)
```

## File Structure

```
.
├── SKILL.md                      # Skill metadata and detailed documentation
├── usage-guide.md               # Step-by-step usage guide
├── README.md                    # This file
├── scripts/r/
│   ├── core_analysis.R          # Core doublet detection functions
│   ├── visualization.R          # Plotting functions
│   └── utils.R                  # Utility functions
├── examples/
│   ├── minimal_example.R        # Basic workflow
│   └── advanced_example.R       # Advanced features
└── tests/
    └── test_doubletfinder.R     # Unit tests
```

## Requirements

- R >= 4.2.0
- DoubletFinder >= 2.0.4
- Seurat >= 4.3.0 or >= 5.0

## Input Data

Requires fully pre-processed Seurat object with:
- Normalized data (NormalizeData or SCTransform)
- Variable features identified
- Scaled data (unless using SCTransform)
- PCA computed
- Clustering (optional but recommended for homotypic adjustment)

## Output

- `pANN_*` columns: pANN scores for each cell
- `DF.classifications_*` columns: "Singlet" or "Doublet" classification
- `doublet` column: Simplified classification

## Key Steps

1. **Preprocessing**: Normalize, find variable features, scale, PCA
2. **Parameter sweep**: Find optimal pK using BCmvn
3. **Estimate doublets**: Based on platform and loading density
4. **Run DoubletFinder**: Classify cells using pANN
5. **Homotypic adjustment**: Adjust for same-type doublets (optional)
6. **Filter**: Remove predicted doublets

## Platform-Specific Doublet Rates

| Platform | Rate per 1000 cells |
|----------|---------------------|
| 10x v2/v3 | ~0.8% |
| 10x v3.1 | ~0.4% |
| 10x HT | ~1.6% |
| Parse | ~0.6% |
| Drop-seq | ~0.5% |

## Important Notes

- Do NOT run on aggregated data from multiple distinct samples
- Do NOT run on integrated/batch-corrected data
- Pre-filter low-quality cells before DoubletFinder
- Homotypic adjustment requires clustering information

## References

1. McGinnis et al. (2019). DoubletFinder: Doublet Detection in Single-Cell RNA Sequencing Data Using Artificial Nearest Neighbors. *Cell Systems*, 8(4):329-337.
2. DoubletFinder GitHub: https://github.com/chris-mcginnis-ucsf/DoubletFinder
