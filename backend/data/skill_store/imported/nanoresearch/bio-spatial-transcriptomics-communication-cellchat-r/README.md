# SpatialCellChat Spatial Transcriptomics Communication Analysis Skill

A comprehensive R-based skill for spatially-aware cell-cell communication analysis using SpatialCellChat (CellChat v3).

## Features

- **Single-Cell Resolution**: Infer communication at individual cell level from spatial data
- **Spatial Distance Constraint**: Account for physical cell proximity in communication
- **Contact-Dependent Signaling**: Support for juxtacrine signaling analysis
- **Multi-technology Support**: Works with Visium, Visium HD, Xenium, Slide-seq, CosMx, Stereo-seq
- **Deconvolution Integration**: Support cell type proportions from RCTD/SPOTlight/cell2location for Visium
- **Spatial Visualization**: Network visualization on tissue images, hot spot detection, co-occurrence analysis
- **Hot Spot Analysis**: Getis-Ord Gi statistics for identifying communication hot/cold spots

## Quick Start

```r
source("scripts/r/cellchat_spatial.R")

# 10X Visium
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  sample_name = "Visium_Sample",
  scalefactors_json = "spatial/scalefactors_json.json",
  assay = "Spatial"
)

# Visium with deconvolution proportions
cellchat <- run_cellchat_visium(
  seurat_obj = visium_data,
  group_by = "cell_type",
  scalefactors_json = "spatial/scalefactors_json.json",
  assay = "Spatial",
  cell_type_decomposition = deconv_proportions
)

# Xenium/Visium HD
cellchat <- run_cellchat_sc_resolution(
  seurat_obj = xenium_data,
  group_by = "cell_type",
  spatial_tech = "xenium"
)
```

## File Structure

```
bio-spatial-transcriptomics-communication-cellchat-r/
├── SKILL.md                      # Skill metadata and API reference
├── README.md                     # This file
├── usage-guide.md                # Detailed usage guide
├── scripts/
│   └── r/
│       └── cellchat_spatial.R    # Main analysis module
├── tests/
│   └── test_cellchat.R           # Unit tests
└── examples/
    ├── example_visium.R          # Visium analysis example
    └── example_xenium.R          # Xenium/Visium HD example
```

## Requirements

- R >= 4.2.0
- Seurat >= 4.0.0
- SeuratObject >= 4.0.0
- SpatialCellChat (GitHub: jinworks/SpatialCellChat)
- jsonlite

## Installation

```r
# Install SpatialCellChat (CellChat v3)
remotes::install_github("jinworks/SpatialCellChat")

# Additional dependencies
install.packages("jsonlite")
BiocManager::install("BiocNeighbors")
```

## Key Functions

| Function | Purpose |
|----------|---------|
| `run_cellchat_spatial()` | Main spatial analysis function |
| `run_cellchat_visium()` | 10X Visium specific wrapper with deconvolution support |
| `run_cellchat_sc_resolution()` | Single-cell resolution data (Xenium, Visium HD, CosMx) |
| `run_cellchat_multi()` | Multiple samples (returns list for merging) |
| `plot_spatial_scoring()` | Outgoing/incoming scores merged plot |
| `extract_communication_df()` | Extract LR communications to data frame |
| `extract_enriched_lr()` | Extract enriched LR pairs for pathway |
| `summarize_communication()` | Summarize by cell group |
| `export_cellchat_results()` | Export all results to files |

**Visualization**: Call native SpatialCellChat functions directly - `netVisual_aggregate()`, `spatialDimPlot()`, `spatialFeaturePlot()`, `spatialGiPlot()`, `communicationDistPlot2()`, etc.

## Technology-Specific Settings

| Technology | ratio | tol | contact.range |
|------------|-------|-----|---------------|
| Visium | auto from JSON | 32.5 | 100 |
| Xenium | 1 | 5 | 10 |
| Visium HD | 1 | 5 | 10 |
| Slide-seq | 0.73 | 5 | 10 |
| CosMx | 0.12028 | auto | 10 |

**Note**: `spatial.factors` must be a **list** (`list(ratio = ..., tol = ...)`) for SpatialCellChat.

## References

1. Jin et al. (2024). CellChat for systematic analysis of cell-cell communication from single-cell transcriptomics. *Nature Protocols*.
2. SpatialCellChat: https://github.com/jinworks/SpatialCellChat
3. CellChat: https://github.com/jinworks/CellChat
4. Spatial tutorial: https://htmlpreview.github.io/?https://github.com/jinworks/SpatialCellChat/blob/master/tutorial/SpatialCellChat_analysis_of_spatial_transcriptomics_data.html
