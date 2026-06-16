# bio-single-cell-enrichment-progeny-r

PROGENy (Pathway RespOnsive GENes) pathway activity inference from single-cell RNA-seq data.

## Description

This skill provides PROGENy pathway activity analysis for estimating signaling pathway activities from gene expression data. PROGENy uses pathway-responsive genes derived from large-scale perturbation experiments to infer activities of 14 key pathways including MAPK, PI3K, TGFb, NFkB, and more.

## Features

- **14 signaling pathways**: MAPK, PI3K, TGFb, TNFa, NFkB, Hypoxia, JAK-STAT, EGFR, VEGF, WNT, p53, Androgen, Estrogen, Trail
- **Human and Mouse support**: Uses appropriate gene symbols and models
- **Single-cell optimized**: Designed for scRNA-seq data with Seurat integration
- **Statistical testing**: Permutation-based significance assessment
- **Differential analysis**: Compare pathway activities between conditions
- **Comprehensive visualization**: Embedding plots, heatmaps, violin plots, correlations

## Installation

```r
BiocManager::install("progeny")
```

## Quick Start

```r
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")

# Load data
seurat_obj <- readRDS("data.rds")

# Run PROGENy
seurat_obj <- run_progeny(
  seurat_obj,
  organism = "Human",
  top = 100,
  scale = FALSE,
  return_assay = TRUE
)

# Visualize
plot_pathway_embedding(seurat_obj, pathways = c("MAPK", "PI3K"), reduction = "umap")
```

## File Structure

```
.
├── SKILL.md                      # Skill metadata and detailed documentation
├── usage-guide.md               # Step-by-step usage guide
├── README.md                    # This file
├── scripts/r/
│   ├── core_analysis.R          # Core pathway analysis functions
│   ├── visualization.R          # Plotting functions
│   └── utils.R                  # Utility functions
├── examples/
│   ├── minimal_example.R        # Basic workflow
│   └── advanced_example.R       # Comprehensive analysis
└── tests/
    └── test_progeny.R           # Unit tests
```

## Requirements

- R >= 4.2.0
- progeny >= 1.20.0
- Seurat >= 4.0.0 (v4 and v5 supported)

## Input Data

Requires Seurat object or expression matrix with:
- Normalized gene expression values
- HGNC symbols (Human) or MGI symbols (Mouse) as row names
- Seurat v4 and v5 both supported

## Output

- Pathway activity scores for 14 pathways
- New "progeny" assay in Seurat object
- Optional metadata columns for easy plotting

## References

1. Schubert et al. (2018). Perturbation-response genes reveal signaling footprints in cancer gene expression. *Nature Communications*, 9:20.
2. Holland et al. (2020). Robustness of gene expression signatures towards low-input RNA-seq. *Genome Medicine*, 12:76.
3. PROGENy Bioconductor: https://bioconductor.org/packages/progeny/
