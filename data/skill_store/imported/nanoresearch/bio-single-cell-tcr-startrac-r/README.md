# bio-single-cell-tcr-startrac-r

STARTRAC (Single T-cell Analysis by Rna-seq and Tcr TRACking) for T cell dynamics analysis.

## Overview

This skill provides wrapper functions for the STARTRAC R package, which analyzes T cell clonal dynamics using paired single-cell RNA-seq and TCR sequencing data. STARTRAC quantifies:

- **STARTRAC-expa**: Clonal expansion within cell clusters
- **STARTRAC-migr**: Migration of T cells between tissues
- **STARTRAC-tran**: Phenotypic transitions between cell states

## Installation

```r
# Install STARTRAC from GitHub
devtools::install_github("Japrin/STARTRAC")

# Install dependencies
install.packages(c("data.table", "plyr", "doParallel", "ggplot2", "ggpubr",
                   "dplyr", "tidyr", "cowplot"))
BiocManager::install("ComplexHeatmap")
```

## Quick Start

```r
source("scripts/r/startrac_analysis.R")

# Prepare data from Seurat
input_data <- prepare_startrac_input(
    seurat_obj,
    clone_col = "tcr_clone_id",
    patient_col = "patient",
    cluster_col = "cell_type",
    loc_col = "tissue"
)

# Run analysis
result <- run_startrac(input_data, proj = "MyStudy", cores = 4)

# Visualize
plot(result, index.type = "cluster.all")
```

## Input Data Format

Required columns in input data frame:

| Column | Description |
|--------|-------------|
| `Cell_Name` | Unique cell identifier |
| `clone.id` | Clonotype ID (e.g., CDR3 sequences) |
| `patient` | Patient/sample identifier |
| `majorCluster` | Cell cluster annotation |
| `loc` | Tissue location (e.g., T, N, PB) |

## Documentation

- [SKILL.md](SKILL.md) - Complete API documentation
- [usage-guide.md](usage-guide.md) - Detailed usage guide
- [examples/example_analysis.R](examples/example_analysis.R) - Example scripts

## Reference

Zhang et al. (2018). Landscape of infiltrating T cells in liver cancer revealed by single-cell sequencing. *Cell*.

STARTRAC GitHub: https://github.com/Japrin/STARTRAC
