# bio-single-cell-atac-signac-r

Single-cell ATAC-seq analysis using Signac. Quality control, normalization, dimensionality reduction (LSI), peak calling, and integration with scRNA-seq within the Seurat framework.

## Description

Signac extends Seurat to handle single-cell ATAC-seq data, providing tools for quality control (TSS enrichment, nucleosome signal), TF-IDF normalization, LSI dimensionality reduction, clustering, gene activity prediction, and integration with scRNA-seq.

## Quick Start

```r
# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Create Seurat object from 10x output
seurat_obj <- create_signac_object(
  counts_file = "filtered_peak_bc_matrix.h5",
  fragments_file = "fragments.tsv.gz",
  genome = "hg38"
)

# Compute QC metrics
seurat_obj <- compute_qc_metrics(seurat_obj)

# Filter cells
seurat_obj <- filter_cells_signac(seurat_obj)

# Run complete workflow
seurat_obj <- run_signac_workflow(seurat_obj)

# Visualize
DimPlot(seurat_obj, reduction = "umap", label = TRUE)
```

## Files

- `SKILL.md` - Comprehensive documentation with all functions and parameters
- `usage-guide.md` - Detailed step-by-step usage guide
- `scripts/r/core_analysis.R` - Core analysis functions (QC, filtering, normalization, clustering)
- `scripts/r/visualization.R` - Visualization functions (QC plots, UMAP, tracks)
- `scripts/r/utils.R` - Utility functions (installation, markers, export)
- `examples/minimal_example.R` - Minimal example workflow
- `examples/advanced_example.R` - Advanced workflow with peak calling and integration
- `tests/test_signac.R` - Unit tests

## Installation

```r
# Install Bioconductor dependencies
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("Signac")

# Optional: Install annotation packages
BiocManager::install(c("EnsDb.Hsapiens.v86", "BSgenome.Hsapiens.UCSC.hg38"))

# Optional: Install MACS2 for peak calling
# pip install MACS2
```

## Key Features

- **ChromatinAssay**: Specialized assay for ATAC-seq data
- **QC metrics**: TSS enrichment, nucleosome signal, blacklist ratio
- **TF-IDF normalization**: Standard normalization for ATAC-seq
- **LSI dimensionality reduction**: Latent Semantic Indexing
- **Gene activity**: Predict gene expression from chromatin
- **Peak calling**: MACS2 integration
- **scRNA integration**: Transfer labels from RNA to ATAC
- **Coverage tracks**: Browser-style visualization

## Workflow Overview

1. **Create object**: Load counts, fragments, and metadata
2. **QC**: Compute TSS enrichment and nucleosome signal
3. **Filter**: Remove low-quality cells
4. **Normalize**: TF-IDF normalization
5. **Features**: Select variable peaks
6. **LSI**: Dimensionality reduction
7. **Cluster**: Identify cell populations
8. **UMAP**: Visualize cells
9. **Gene activity**: Create gene activity matrix
10. **Integration**: Combine with scRNA-seq

## References

1. Stuart et al. (2021). Single-cell chromatin state analysis with Signac. *Nature Methods*, 18, 1333-1341.
2. Signac documentation: https://stuartlab.org/signac/
3. Signac GitHub: https://github.com/timoast/signac
