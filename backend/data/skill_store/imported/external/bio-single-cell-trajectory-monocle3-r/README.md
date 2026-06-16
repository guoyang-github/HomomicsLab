# Monocle3 Trajectory Inference Skill

A comprehensive R-based skill for single-cell trajectory inference and pseudotime analysis using Monocle3 with reversed graph embedding.

## Features

- **Data Loading**: Direct loading of Cell Ranger, MTX, and MatrixMarket data
- **QC & Preprocessing**: Gene detection, size factor estimation, normalization, PCA
- **Trajectory Inference**: Order cells along developmental trajectories using reversed graph embedding
- **Pseudotime Analysis**: Assign pseudotime values based on position in the trajectory
- **Branch Detection**: Identify branching points where cells diverge into different fates
- **Gene Dynamics**: Analyze gene expression changes along pseudotime (Moran's I test)
- **Gene Modules**: Find co-expressed gene modules across trajectories
- **Model Evaluation**: Evaluate fit quality (AIC, BIC, deviance), compare nested models
- **Batch Correction**: Align datasets from different batches or conditions via `align_cds()`
- **3D Visualization**: Interactive 3D trajectory visualization
- **Cell Classification**: Automated cell type annotation via Garnett
- **BPCells Support**: On-disk matrix storage for large datasets
- **Save/Load**: Save and restore complete Monocle3 objects including BPCells matrices

## Quick Start

```r
library(monocle3)
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")

# Create CDS
cds <- create_cds(counts_matrix, cell_metadata, gene_metadata)

# Run complete analysis via skill helper
cds <- run_trajectory_analysis(cds,
                               num_dim = 50,
                               reduction_method = "UMAP",
                               root_cells = root_cell_ids)

# Plot results
plot_cells(cds, color_cells_by = "pseudotime", show_trajectory_graph = TRUE)
plot_cells(cds, label_cell_groups = FALSE, label_leaves = TRUE,
           label_branch_points = TRUE, show_trajectory_graph = TRUE, cell_size = 0.5)
```

Or step-by-step with official functions:

```r
library(monocle3)
cds <- new_cell_data_set(expression_data = counts,
                         cell_metadata = cell_meta,
                         gene_metadata = gene_meta)
cds <- preprocess_cds(cds, num_dim = 50)
cds <- reduce_dimension(cds, reduction_method = "UMAP")
cds <- cluster_cells(cds)
cds <- learn_graph(cds)
cds <- order_cells(cds, root_cells = root_ids)
plot_cells(cds, color_cells_by = "pseudotime", show_trajectory_graph = TRUE)
```

## File Structure

```
bio-single-cell-trajectory-monocle3-r/
├── SKILL.md                      # Skill metadata + official API reference
├── README.md                     # This file
├── usage-guide.md                # Detailed usage guide
├── DESCRIPTION                   # R package metadata
├── scripts/
│   └── r/
│       ├── core_analysis.R       # High-value helpers (conversion, pipeline, loaders)
│       ├── visualization.R       # Convenience plots with added logic
│       └── utils.R               # Trajectory/branch/export utilities
├── tests/
│   └── test_monocle3.R           # Unit tests
└── examples/
    ├── minimal_example.R         # Basic workflow with official functions
    └── advanced_example.R        # Advanced features
```

## Requirements

- R >= 4.2.0
- monocle3 >= 1.4.25
- Bioconductor >= 3.17
- ggplot2, dplyr, igraph

Optional:
- Seurat >= 4.3.0 (for Seurat object conversion; **supports v4 and v5**)
- plotly >= 4.9.0 (for 3D visualization)

## Installation

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")
BiocManager::install("monocle3")
```

## Skill-Provided Helper Functions

These are **not** thin wrappers — they add real logic.

| Function | File | What it does |
|----------|------|-------------|
| `create_cds()` | core_analysis.R | Create CDS with NULL-metadata defaults |
| `cds_from_seurat()` | core_analysis.R | Convert Seurat v4/v5 with auto layer/slot detection |
| `cds_from_sce()` | core_analysis.R | Convert SCE with gene_short_name fix |
| `run_trajectory_analysis()` | core_analysis.R | End-to-end pipeline |
| `get_earliest_principal_node()` | core_analysis.R | Programmatic root selection |
| `find_trajectory_variable_genes()` | core_analysis.R | graph_test + q-value + Moran's I filter |
| `get_root_nodes()` | utils.R | Extract root node indices |
| `get_branch_nodes()` | utils.R | Extract branch nodes (degree > 2, non-root) |
| `get_leaf_nodes()` | utils.R | Extract leaf nodes (degree == 1, non-root) |
| `get_clusters()` | utils.R | Extract cluster vector from S4 structure |
| `get_partitions()` | utils.R | Extract partition assignments |
| `get_top_markers()` | utils.R | top_markers + fraction + pseudo_R2 filter |
| `annotate_clusters()` | utils.R | Map cluster IDs to annotations |
| `export_pseudotime_data()` | utils.R | Export pseudotime + metadata to CSV |
| `check_cds_completeness()` | utils.R | Check which analysis steps have run |
| `plot_trajectory_3d()` | visualization.R | Validate 3D reduction before plotting |
| `plot_trajectory_features()` | visualization.R | Multi-panel plot for multiple features |
| `plot_pseudotime_distribution()` | visualization.R | Custom ggplot histogram |

## Workflow Stages

| Stage | Official Function | Skill Helper | Output |
|-------|-------------------|--------------|--------|
| 1. Data Loading | `new_cell_data_set()` / `load_cellranger_data()` (official) | `create_cds()`, `cds_from_seurat()` | cell_data_set |
| 2. QC | `detect_genes()`, `estimate_size_factors()` | — | Filtered CDS |
| 3. Preprocessing | `preprocess_cds()` | — | Normalized data, PCA |
| 4. Dimension Reduction | `reduce_dimension()` | — | UMAP/tSNE |
| 5. Clustering | `cluster_cells()` | — | Cluster assignments |
| 6. Graph Learning | `learn_graph()` | — | Principal graph |
| 7. Ordering | `order_cells()` | `get_earliest_principal_node()` | Pseudotime values |
| 8. DE Analysis | `graph_test()` | `find_trajectory_variable_genes()` | Significant genes |
| 9. Module Analysis | `find_gene_modules()` | — | Gene modules |
| 10. Modeling | `fit_models()`, `evaluate_fits()` | — | Model fits |
| 11. Export | — | `export_pseudotime_data()` | CSV outputs |

## Output

| Output | Description | Access |
|--------|-------------|--------|
| Pseudotime | Cell ordering values | `pseudotime(cds)` |
| Principal Graph | Trajectory structure | `principal_graph(cds)` |
| Clusters | Cell clusters | `clusters(cds)` |
| Partitions | Cell partitions | `partitions(cds)` |
| DE Results | Differential expression | `graph_test()` output |
| Gene Modules | Co-expressed modules | `find_gene_modules()` output |
| Model Fits | GLM fits | `fit_models()` output |

## References

1. Trapnell et al. (2014). The dynamics and regulators of cell fate decisions are revealed by pseudotemporal ordering of single cells. *Nature Biotechnology*.
2. Cao et al. (2019). The single-cell transcriptional landscape of mammalian organogenesis. *Nature*.
3. Monocle3 documentation: https://cole-trapnell-lab.github.io/monocle3/
