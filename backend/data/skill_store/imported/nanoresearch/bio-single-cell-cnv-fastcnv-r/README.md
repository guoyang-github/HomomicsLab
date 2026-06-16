# fastCNV Single-Cell CNV Analysis Skill

A comprehensive R-based skill for copy number variation (CNV) analysis on single-cell RNA-seq data using fastCNV.

## Features

- **Fast Performance**: ~1 minute for 4,000 cells
- **Genome-wide CNV**: Sliding window approach across chromosomes
- **Subclone Detection**: Built-in CNV clustering for tumor subclones
- **Flexible Reference**: Run with or without reference cells
- **Multi-sample**: Pooled reference across samples automatically
- **CNV Tree**: Build phylogenetic trees from CNV profiles

## Quick Start

```r
source("scripts/r/run_fastcnv.R")

# Run with immune cells as reference
result <- run_fastcnv_sc(
  seurat_obj = seurat_obj,
  sample_name = "Tumor1",
  reference_var = "annot",
  reference_label = c("TNKILC", "Myeloid", "B", "Mast", "Plasma")
)

# Visualize
FeaturePlot(result, features = "cnv_fraction")
DimPlot(result, group.by = "cnv_clusters", label = TRUE)
```

## File Structure

```
bio-single-cell-cnv-fastcnv-r/
├── SKILL.md                 # Skill metadata
├── README.md                # This file
├── usage-guide.md           # Detailed usage guide
├── scripts/
│   └── r/
│       └── run_fastcnv.R    # Main analysis module
├── tests/
│   └── test_fastcnv.R       # Unit tests
└── examples/
    └── example_basic.R      # Basic usage example
```

## Requirements

- R >= 4.2.0
- Seurat >= 5.0.0
- fastCNV (from GitHub)
- scales

## Installation

```r
remotes::install_github("must-bioinfo/fastCNV")
```

## Key Functions

| Function | Purpose |
|----------|---------|
| `run_fastcnv_sc()` | Main analysis for single-cell data |
| `run_fastcnv_multi_sc()` | Multi-sample analysis |
| `cnv_cluster()` | Hierarchical CNV clustering |
| `merge_cnv_clusters()` | Merge correlated clusters |
| `cnv_classification()` | Classify gain/loss/no alteration |
| `cnv_tree()` | Build CNV subclonality tree |
| `extract_cnv_metadata()` | Extract CNV metadata from Seurat object |
| `plot_cnv_heatmap()` | CNV heatmap generation |
| `plot_chr_arm_umap()` | UMAP chromosome-arm CNV plot |
| `summarize_cnv_by_cluster()` | Summarize by group |
| `export_cnv_results()` | Export results to CSV/RDS |

## Output Description

| Column | Description |
|--------|-------------|
| `cnv_fraction` | Overall CNV burden per cell |
| `cnv_clusters` | CNV-based subclonal clusters |
| `*_CNV` (e.g., `20.p_CNV`) | Per chromosome arm CNV scores |
| `*_CNV_classification` | Gain/loss/no_alteration calls |

## References

1. Cabrejas et al. (2025). fastCNV: Fast and accurate copy number variation prediction from High-Definition Spatial Transcriptomics and scRNA-Seq Data. bioRxiv 2025.10.22.683855.
2. fastCNV documentation: https://must-bioinfo.github.io/fastCNV/
3. fastCNV scRNA-seq vignette: https://must-bioinfo.github.io/fastCNV/articles/fastCNV_sc.html
