# bio-single-cell-enrichment-clusterprofiler-r

Comprehensive enrichment analysis for single-cell RNA-seq data using clusterProfiler.

## Features

- **ORA (Over-Representation Analysis)**: GO, KEGG, MSigDB, custom gene sets
- **GSEA (Gene Set Enrichment Analysis)**: Rank-based enrichment analysis
- **Multi-cluster Comparison**: Compare enrichment across cell clusters
- **Rich Visualization**: Dot plots, networks, GSEA plots, upset plots
- **Seurat Integration**: Direct support for Seurat objects and marker analysis

## Quick Start

```r
# Source scripts
source("scripts/r/ora_analysis.R")
source("scripts/r/visualization.R")

# GO enrichment
result <- run_enrichGO(
    gene_list = marker_genes,
    org_db = org.Hs.eg.db,
    ont = "BP"
)

# Visualize
dotplot(result, showCategory = 15)
```

## Installation

```r
BiocManager::install(c("clusterProfiler", "org.Hs.eg.db", "enrichplot"))
install.packages("msigdbr")
```

## Structure

```
scripts/r/
├── ora_analysis.R       # ORA functions (GO, KEGG, enricher)
├── gsea_analysis.R      # GSEA functions
├── compare_cluster.R    # Multi-cluster comparison
├── visualization.R      # Plotting functions
└── utils.R              # Utility functions

examples/
├── example_basic.R      # Basic workflow
├── example_seurat.R     # Seurat integration
└── example_comparison.R # Cluster comparison
```

## Documentation

- [SKILL.md](SKILL.md) - Complete skill documentation
- [usage-guide.md](usage-guide.md) - Detailed usage guide

## References

- Yu et al. (2012). clusterProfiler: an R package for comparing biological themes among gene clusters. *OMICS*.
- Wu et al. (2021). clusterProfiler 4.0: A universal enrichment tool for interpreting omics data. *The Innovation*.
