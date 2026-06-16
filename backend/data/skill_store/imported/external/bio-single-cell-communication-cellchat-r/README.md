# CellChat Single-Cell Communication Analysis Skill

A comprehensive R-based skill for cell-cell communication analysis from single-cell RNA-seq data using CellChat.

## Features

- **Comprehensive Database**: ~3,300 validated ligand-receptor interactions
- **Multiple Signaling Types**: Secreted, ECM-Receptor, Cell-Cell Contact, Non-protein
- **Systems Analysis**: Network centrality, pattern recognition, manifold learning
- **Multi-condition Comparison**: Identify altered signaling across conditions

## Quick Start

```r
source("scripts/r/cellchat_analysis.R")

# Run complete analysis
cellchat <- run_cellchat(
  seurat_obj,
  group_by = "cell_type"
)

# Visualize
plot_cellchat_circle(cellchat)
plot_cellchat_bubble(cellchat, signaling = c("CXCL", "CCL"))
```

## File Structure

```
bio-single-cell-communication-cellchat-r/
├── SKILL.md                      # Skill metadata
├── README.md                     # This file
├── usage-guide.md                # Detailed usage guide
├── scripts/
│   └── r/
│       └── cellchat_analysis.R   # Main analysis module
├── tests/
│   └── test_cellchat.R           # Unit tests
└── examples/
    └── example_basic.R           # Basic usage example
```

## Requirements

- R >= 4.2.0
- Seurat >= 4.3.0
- CellChat (from GitHub)
- NMF, ggalluvial, patchwork

## Installation

```r
remotes::install_github("jinworks/CellChat")
install.packages(c("NMF", "ggalluvial", "patchwork"))
```

## Key Functions

| Function | Purpose |
|----------|---------|
| `run_cellchat()` | Main analysis pipeline |
| `plot_cellchat_circle()` | Circle network visualization |
| `plot_cellchat_bubble()` | Bubble plot of L-R pairs |
| `plot_cellchat_pathway()` | Pathway-specific visualization |
| `compute_cellchat_centrality()` | Network centrality analysis |
| `identify_cellchat_patterns()` | Communication pattern identification |
| `compare_cellchat_conditions()` | Multi-condition comparison |

## Output Description

| Slot | Description |
|------|-------------|
| `@net$prob` | Communication probabilities |
| `@net$count` | Number of interactions |
| `@net$weight` | Interaction strength |
| `@netP$prob` | Pathway-level probabilities |

## References

1. Jin et al. (2024). CellChat for systematic analysis of cell-cell communication from single-cell transcriptomics. Nature Protocols.
2. Jin et al. (2021). Inference and analysis of cell-cell communication using CellChat. Nature Communications.
3. CellChat documentation: https://github.com/jinworks/CellChat
