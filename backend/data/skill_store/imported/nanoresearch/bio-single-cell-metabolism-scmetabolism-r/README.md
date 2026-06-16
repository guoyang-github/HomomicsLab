# scMetabolism Single-Cell Metabolic Analysis

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![R >= 4.2.0](https://img.shields.io/badge/R-%3E%3D%204.2.0-blue.svg)](https://cran.r-project.org/)

A comprehensive skill for quantifying metabolic pathway activities in single-cell RNA-seq data using the [scMetabolism](https://github.com/wu-yc/scMetabolism) R package.

## Overview

scMetabolism enables pathway-level metabolic analysis of single-cell data using multiple gene set scoring algorithms. This skill provides a complete workflow from data preparation to visualization.

### Key Features

- **4 Scoring Algorithms**: VISION (default), AUCell, ssGSEA, GSVA
- **2 Pathway Databases**: KEGG (85 pathways), REACTOME (82 pathways)
- **Comprehensive Visualizations**: UMAP/tSNE overlay, dot plots, box plots, heatmaps, violin plots, ridge plots
- **Flexible Input**: Supports Seurat objects or raw count matrices
- **Group Comparisons**: Compare metabolic activities across cell types or conditions

## Quick Start

```r
library(Seurat)

# Source the scMetabolism wrapper functions
source("scripts/r/run_scmetabolism.R")
source("scripts/r/visualize_scmetabolism.R")

# Load your Seurat object
seurat_obj <- readRDS("your_data.rds")

# Run scMetabolism analysis
result <- run_scmetabolism(
  seurat_obj,
  method = "VISION",
  metabolism.type = "KEGG",
  ncores = 4
)

seurat_obj <- result$seurat_obj

# Visualize pathway activity on UMAP
dimplot_metabolism(
  seurat_obj,
  pathway = "Glycolysis / Gluconeogenesis",
  reduction = "umap"
)

# Compare pathways across cell types
dotplot_metabolism(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis", "Oxidative phosphorylation"),
  group.by = "cell_type"
)
```

## Installation

### Prerequisites

```r
# Required packages
install.packages(c("Seurat", "ggplot2", "pheatmap", "ggridges", "viridis"))

# Install scMetabolism from GitHub
if (!requireNamespace("devtools", quietly = TRUE)) {
  install.packages("devtools")
}
devtools::install_github("wu-yc/scMetabolism")

# Optional but recommended
install.packages("wesanderson")  # For color palettes
```

### System Requirements

- R >= 4.2.0
- Seurat >= 4.3.0
- Sufficient memory for single-cell analysis (recommend 8GB+ for large datasets)

## File Structure

```
bio-single-cell-metabolism-scmetabolism-r/
├── SKILL.md                    # Detailed documentation
├── README.md                   # This file
├── usage-guide.md              # Step-by-step usage guide
├── scripts/
│   └── r/
│       ├── run_scmetabolism.R         # Core analysis functions
│       └── visualize_scmetabolism.R   # Visualization functions
├── examples/
│   └── example_basic.R               # Complete workflow example
└── tests/
    └── test_scmetabolism.R           # Unit tests
```

## Core Functions

### Analysis Functions (`run_scmetabolism.R`)

| Function | Description |
|----------|-------------|
| `run_scmetabolism()` | Main function to run analysis on Seurat object |
| `run_scmetabolism_matrix()` | Run analysis on raw count matrix |
| `get_metabolic_pathways()` | List available metabolic pathways |
| `extract_metabolism_scores()` | Extract scores as data frame |
| `compare_metabolism()` | Compare pathways between groups |
| `get_top_variable_pathways()` | Identify most variable pathways |
| `export_scmetabolism_results()` | Export results to files |

### Visualization Functions (`visualize_scmetabolism.R`)

| Function | Description |
|----------|-------------|
| `dimplot_metabolism()` | Overlay pathway scores on UMAP/tSNE |
| `dotplot_metabolism()` | Dot plot of pathways by group |
| `boxplot_metabolism()` | Box plot comparison |
| `violinplot_metabolism()` | Violin plot distribution |
| `ridgeplot_metabolism()` | Ridge/joy plot |
| `heatmap_metabolism()` | Heatmap of pathway activities |

## Algorithm Selection Guide

| Method | Speed | Memory | Best For |
|--------|-------|--------|----------|
| **VISION** | Medium | Medium | General use, balanced performance |
| **AUCell** | Fast | Low | Large datasets, fast screening |
| **ssGSEA** | Slow | High | High-resolution analysis |
| **GSVA** | Medium | Medium | Standard pathway analysis |

## Scoring Methods Explained

### VISION (Default)
- Uses random walk with restarts on cell-cell similarity graph
- Accounts for expression similarity between cells
- Good balance of speed and accuracy

### AUCell
- Area Under the Curve calculation
- Fast and memory efficient
- Good for large datasets

### ssGSEA
- Single-sample Gene Set Enrichment Analysis
- Most sensitive but computationally intensive
- Good for detecting subtle pathway differences

### GSVA
- Gene Set Variation Analysis
- Non-parametric, unsupervised
- Standard for pathway enrichment

## Pathway Databases

### KEGG (85 Pathways)
- Glycolysis / Gluconeogenesis
- Citrate cycle (TCA cycle)
- Oxidative phosphorylation
- Fatty acid metabolism
- Amino acid metabolism
- And more...

### REACTOME (82 Pathways)
- More detailed pathway annotations
- Alternative pathway definitions
- Additional metabolic processes

## Example Workflow

See `examples/example_basic.R` for a complete workflow including:

1. Data loading and preparation
2. Running scMetabolism with different algorithms
3. Extracting and exploring results
4. Creating visualizations (DimPlot, DotPlot, BoxPlot, Heatmap)
5. Exporting results

Run the example:

```r
source("examples/example_basic.R")
```

## Troubleshooting

### Common Issues

**Error: "Pathway not found in metabolism assay"**
- Check exact pathway name with `get_metabolic_pathways()`
- Pathway names are case-sensitive

**Error: "Assay 'METABOLISM' not found"**
- Run `run_scmetabolism()` first to create the assay
- Check the `output_assay` parameter name

**Low pathway scores across all cells**
- Try using normalized data (`slot = "data"`)
- Consider imputation for sparse data (`imputation = TRUE`)
- Check if metabolic genes are present in your data

**Out of memory errors**
- Reduce `ncores` or use `method = "AUCell"`
- Subsample cells for initial exploration
- Process data in batches

### Performance Tips

- Use `method = "AUCell"` for large datasets (>10,000 cells)
- Start with `ncores = 2` and increase based on available memory
- For very large datasets, consider subsetting by cell type

## Citation

If you use scMetabolism in your research, please cite:

```
Yingcheng Wu, Shuaixi Yang, Jiaqiang Ma, et al.
Spatiotemporal Immune Landscape of Colorectal Cancer Liver Metastasis at Single-Cell Level.
Cancer Discovery. 2021.
https://pubmed.ncbi.nlm.nih.gov/34417225/
```

## Related Skills

- [bio-single-cell-annotation-sctype-r](../bio-single-cell-annotation-sctype-r/) - Cell type annotation
- [bio-single-cell-cnv-infercnv-r](../bio-single-cell-cnv-infercnv-r/) - CNV analysis
- [bio-single-cell-communication-nichenet-r](../bio-single-cell-communication-nichenet-r/) - Cell-cell communication

## References

1. Wu et al. (2021). scMetabolism: a computational framework for single-cell metabolic analysis. *Bioinformatics*.
2. DeTomaso et al. (2019). Functional interpretation of single cell similarity maps. *Nature Communications*.
3. Aibar et al. (2017). SCENIC: single-cell regulatory network inference and clustering. *Nature Methods*.
4. Hänzelmann et al. (2013). GSVA: gene set variation analysis for microarray and RNA-seq data. *BMC Bioinformatics*.

## License

This skill is provided under the MIT License. The underlying scMetabolism package is under GPL-3.

## Contact

For questions about this skill, please open an issue in the repository.
For questions about scMetabolism package, visit: https://github.com/wu-yc/scMetabolism
