# bio-single-cell-enrichment-decoupler-r

decoupleR pathway and transcription factor activity inference for single-cell data

## Overview

This skill provides a comprehensive wrapper around [decoupleR](https://saezlab.github.io/decoupleR/), a Bioconductor package for inferring biological activities from omics data. decoupleR uses prior knowledge networks (pathways, transcription factor targets) to estimate pathway and TF activities from gene expression data.

**Key Capabilities:**
- Pathway activity inference using PROGENy networks
- Transcription factor activity inference using DoRothEA/CollecTRI
- Multiple statistical methods (ULM, MLM, WSum, AUCell, ORA, GSVA)
- Multi-method consensus scoring
- Seurat integration for single-cell workflows
- Comprehensive visualization tools

## Installation

### Requirements

- R >= 4.0
- Bioconductor >= 3.12

### Install Dependencies

```r
# Install BiocManager if needed
if (!requireNamespace("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

# Install decoupleR and dependencies
BiocManager::install(c("decoupleR", "OmnipathR", "SCENIC"))

# Install CRAN dependencies
install.packages(c("Seurat", "dplyr", "tidyr", "ggplot2", "pheatmap"))

# Optional: ComplexHeatmap for advanced visualizations
BiocManager::install("ComplexHeatmap")
```

## Quick Start

```r
# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Load example data
data("pbmc_small", package = "Seurat")
seurat_obj <- pbmc_small

# Get pathway network
net <- get_progeny_network(organism = "human", top = 500)

# Run pathway activity inference
acts <- run_decoupler_seurat(
  seurat_obj,
  net = net,
  method = "ulm"
)

# Add results to Seurat object
seurat_obj <- add_decoupler_to_seurat(seurat_obj, acts)

# Visualize
plot_activity_heatmap(acts, n_top = 10)
```

## Directory Structure

```
bio-single-cell-enrichment-decoupler-r/
├── README.md                 # This file
├── SKILL.md                  # Detailed skill documentation
├── usage-guide.md            # Comprehensive usage guide
├── examples/
│   ├── minimal_example.R     # Basic usage example
│   └── advanced_example.R    # Advanced workflows
├── scripts/r/
│   ├── core_analysis.R       # Core analysis functions
│   ├── visualization.R       # Plotting functions
│   └── utils.R               # Utility functions
└── tests/
    └── test_decoupler.R      # Unit tests
```

## Core Modules

### 1. Core Analysis (`scripts/r/core_analysis.R`)

**Network Retrieval:**
- `get_progeny_network()` - Get PROGENy pathway network
- `get_dorothea_network()` - Get DoRothEA TF network
- `get_collectri_network()` - Get CollecTRI TF network

**Analysis Methods:**
- `run_ulm_analysis()` - Univariate Linear Model
- `run_mlm_analysis()` - Multivariate Linear Model
- `run_wsum_analysis()` - Weighted Sum
- `run_aucell_analysis()` - AUCell enrichment
- `run_ora_analysis()` - Over-Representation Analysis
- `run_gsva_analysis()` - Gene Set Variation Analysis

**Integration:**
- `run_decoupler_seurat()` - Run with Seurat object
- `add_decoupler_to_seurat()` - Add results to Seurat metadata
- `run_decoupler_multi()` - Multi-method analysis

### 2. Visualization (`scripts/r/visualization.R`)

- `plot_activity_heatmap()` - Activity heatmap
- `plot_activity_scatter()` - Condition comparison scatter
- `plot_top_activities()` - Top activities bar plot
- `plot_activity_distribution()` - Score distribution
- `plot_activity_reduced()` - Activity on UMAP/t-SNE
- `plot_method_comparison()` - Compare multiple methods
- `plot_decoupler_summary()` - Generate summary plots

### 3. Utilities (`scripts/r/utils.R`)

- `create_decoupler_test_data()` - Generate test data
- `recommend_decoupler_params()` - Parameter recommendations
- `convert_network_format()` - Network format conversion
- `get_top_activities()` - Extract top activities
- `get_differential_activities()` - Compare conditions
- `correlate_activities()` - Correlate with metadata
- `create_consensus_score()` - Multi-method consensus

## Input/Output Specifications

### Input

**Expression Data:**
- Format: Seurat object OR matrix (genes x samples)
- Genes: Gene symbols as rownames
- Values: Normalized expression (log-transformed recommended)

**Network Data:**
- Format: Data frame with columns: source, target, weight
- source: Pathway or TF name
- target: Target gene symbol
- weight: Interaction weight (optional, default 1)

### Output

**Activity Results:**
- Format: Data frame (tibble)
- Columns: source, condition, score, statistic, pvalue (if available)
- Rows: Each source-condition combination

## Methods Overview

| Method | Type | Description | Best For |
|--------|------|-------------|----------|
| ULM | Linear Model | Univariate linear regression | General purpose, fast |
| MLM | Linear Model | Multivariate linear regression | Accounting for TF-TF interactions |
| WSum | Weighted Sum | Weighted sum of target genes | Simple, interpretable |
| AUCell | Enrichment | Area under recovery curve | Small gene sets |
| ORA | Statistical | Fisher's exact test | Binary/differential data |
| GSVA | Enrichment | Gene set variation analysis | Bulk-like behavior |

## Best Practices

1. **Data Preprocessing:**
   - Use normalized expression data
   - Log-transform counts before analysis
   - Filter low-expressed genes

2. **Network Selection:**
   - PROGENy for pathway activities
   - DoRothEA (ABC levels) for TF activities
   - CollecTRI for improved TF coverage

3. **Method Selection:**
   - Start with ULM for general analysis
   - Use MLM when TFs/pathways may interact
   - Run multiple methods for robustness

4. **Parameter Tuning:**
   - `minsize`: Minimum 5 targets per source
   - Increase for more stringent filtering
   - Adjust based on network coverage

5. **Multi-method Consensus:**
   - Run ULM + MLM + WSum
   - Use `create_consensus_score()` for combined results
   - Compare methods with `plot_method_comparison()`

## References

1. Badia-i-Mompel et al. (2022). decoupleR: Ensemble of computational methods to infer biological activities from omics data. *Bioinformatics Advances*, 2(1), vbac016.

2. Schubert et al. (2018). Perturbation-response genes reveal signaling footprints in cancer gene expression. *Nature Communications*, 9(1), 20.

3. Garcia-Alonso et al. (2019). Benchmark and integration of resources for the estimation of human transcription factor activities. *Genome Research*, 29(8), 1363-1375.

4. Müller-Dott et al. (2023). Expanding the coverage of regulatory networks with CollecTRI. *bioRxiv*.

## License

This skill follows the same license as the original decoupleR package (GPL-3).

## Support

For issues related to:
- **decoupleR package**: https://github.com/saezlab/decoupleR/issues
- **This skill**: Contact skill maintainer
