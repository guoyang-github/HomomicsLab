# bio-single-cell-atac-archr-r

Single-cell ATAC-seq analysis using ArchR. Fast and scalable analysis of chromatin accessibility data including dimensionality reduction, clustering, peak calling, and motif enrichment.

## Description

ArchR is a comprehensive R package for analyzing single-cell ATAC-seq (Assay for Transposase-Accessible Chromatin using sequencing) data. This skill provides wrapper functions and comprehensive documentation for running ArchR analysis from fragment files to biological insights.

## Quick Start

```r
# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Setup ArchR
setup_archr(threads = 16, genome = "hg38")

# Run complete workflow
proj <- run_archr_workflow(
  input_files = c("sample1_fragments.tsv.gz", "sample2_fragments.tsv.gz"),
  sample_names = c("Sample1", "Sample2"),
  output_directory = "ArchR-Project",
  genome = "hg38",
  run_peak_calling = TRUE
)

# Visualize
plot_embedding(proj, color_by = "cellColData", name = "Clusters")
```

## Files

- `SKILL.md` - Comprehensive documentation with all functions and parameters
- `usage-guide.md` - Detailed step-by-step usage guide
- `scripts/r/core_analysis.R` - Core analysis functions (setup, Arrow files, clustering, peaks)
- `scripts/r/visualization.R` - Visualization functions (embeddings, gene scores, tracks)
- `scripts/r/utils.R` - Utility functions (installation, markers, export)
- `examples/minimal_example.R` - Minimal example workflow
- `examples/advanced_example.R` - Advanced workflow with peak calling and integration
- `tests/test_archr.R` - Unit tests

## Installation

```r
# Install Bioconductor dependencies
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install(c("magick", "ComplexHeatmap", "SummarizedExperiment"))

# Install ArchR from GitHub
devtools::install_github("GreenleafLab/ArchR", ref="master",
                         repos = BiocManager::repositories())

# Optional: Install MACS2 for peak calling
# pip install MACS2
```

## Key Features

- **Arrow files**: Efficient storage format for scATAC-seq data
- **Doublet detection**: Identify and remove doublets
- **Iterative LSI**: Dimensionality reduction optimized for ATAC data
- **Clustering**: Seurat-style clustering with resolution control
- **Peak calling**: Reproducible peak set with MACS2
- **Motif analysis**: TF motif enrichment with chromVAR
- **Gene scores**: Predict gene activity from chromatin accessibility
- **scRNA integration**: Integrate with scRNA-seq data
- **Visualization**: UMAP, browser tracks, heatmaps, and more

## Workflow Overview

1. **Setup**: Configure threads and genome
2. **Arrow files**: Create efficient storage from fragment files
3. **Project**: Create ArchR project
4. **Doublets**: Detect and filter doublets
5. **LSI**: Iterative dimensionality reduction
6. **Clustering**: Identify cell populations
7. **UMAP**: Visualize cells in 2D
8. **Peaks**: Call reproducible peak set (requires MACS2)
9. **Motifs**: Analyze TF binding motifs
10. **Integration**: Combine with scRNA-seq data

## References

1. Granja et al. (2021). ArchR is a scalable software package for integrative single-cell chromatin accessibility analysis. *Nature Genetics*, 53, 403-411.
2. ArchR documentation: https://www.archrproject.com/
3. ArchR GitHub: https://github.com/GreenleafLab/ArchR
