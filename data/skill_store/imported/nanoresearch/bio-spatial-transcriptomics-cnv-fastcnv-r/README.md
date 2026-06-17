# fastCNV Spatial Transcriptomics CNV Analysis Skill

A comprehensive R-based skill for copy number variation (CNV) analysis on spatial transcriptomics data using fastCNV.

## Features

- **Spatial Transcriptomics Support**: Optimized for 10x Visium and Visium HD
- **Fast Performance**: ~1 min for 4K cells, ~40 min for Visium HD (16 µm)
- **Pooled Reference**: Automatically builds reference across multiple samples
- **CNV Clustering**: Identify tumor subclones by CNV profile
- **CNV Classification**: Classify chromosome-arm alterations as gain/loss/no alteration
- **CNV Tree**: Build phylogenetic trees from CNV profiles
- **Spatial Visualization**: Map CNV fractions and chromosome-arm alterations on tissue

## Quick Start

```r
source("scripts/r/fastcnv_analysis.R")

# Run fastCNV on Visium data
result <- run_fastcnv(
  seuratObj = seurat_obj,
  sampleName = "Sample1",
  referenceVar = "cell_type",
  referenceLabel = "Healthy"
)

# For Visium HD
result_hd <- run_fastcnv_hd(
  seuratObj = seurat_hd,
  sampleName = "HD_Sample",
  referenceVar = "annotations",
  referenceLabel = "Healthy"
)
```

## File Structure

```
bio-spatial-transcriptomics-cnv-fastcnv-r/
├── SKILL.md                    # Skill metadata
├── README.md                   # This file
├── usage-guide.md              # Detailed usage guide
├── scripts/
│   └── r/
│       └── fastcnv_analysis.R  # Main analysis module
├── tests/
│   └── test_fastcnv.R          # Unit tests
└── examples/
    └── example_basic.R         # Basic usage example
```

## Requirements

- R >= 4.2.0
- Seurat >= 5.0.0
- fastCNV (from GitHub)
- ComplexHeatmap
- scales

## Installation

```r
remotes::install_github("must-bioinfo/fastCNV")
```

## Key Functions

| Function | Purpose |
|----------|---------|
| `run_fastcnv()` | Main analysis function for Visium/scRNA-seq |
| `run_fastcnv_hd()` | Visium HD wrapper (`fastCNV_10XHD`) |
| `run_fastcnv_multi()` | Multi-sample analysis |
| `prepare_counts_for_cnv()` | Aggregate low-count spots |
| `annotations_8um_to_16um()` | Project 8um annotations to 16um (HD) |
| `cnv_cluster()` | Hierarchical CNV clustering |
| `merge_cnv_clusters()` | Merge correlated clusters |
| `cnv_classification()` | Classify gain/loss/no alteration |
| `cnv_tree()` | Build CNV subclonality tree |
| `extract_cnv_results()` | Export results to data frame |
| `summarize_cnv_by_group()` | Summary statistics by group |
| `export_cnv_results()` | Export metadata, matrix, and RDS |
| `plot_fastcnv_heatmap()` | Generate CNV heatmap |
| `plot_cnv_fraction_spatial()` | Spatial CNV fraction visualization |
| `plot_chr_arm_spatial()` | Spatial chromosome-arm CNV plot |

## References

1. Cabrejas et al. (2025). fastCNV: Fast and accurate copy number variation prediction from High-Definition Spatial Transcriptomics and scRNA-Seq Data. bioRxiv 2025.10.22.683855.
2. fastCNV documentation: https://must-bioinfo.github.io/fastCNV/
3. fastCNV HD vignette: https://must-bioinfo.github.io/fastCNV/articles/fastCNV_HD.html
4. fastCNV ST vignette: https://must-bioinfo.github.io/fastCNV/articles/fastCNV_ST.html
