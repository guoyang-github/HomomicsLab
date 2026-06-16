# SpaGCN Spatial Domain Identification Skill

A comprehensive Python-based skill for spatial transcriptomics domain identification using SpaGCN with graph convolutional networks.

## Features

- **Graph Convolutional Networks**: Leverage spatial graph structure for domain detection
- **Histology Integration**: Optional integration of H&E image information
- **Parameter Auto-Search**: Automated search for optimal l and resolution parameters
- **Domain Refinement**: Post-processing spatial smoothing for cleaner domains
- **SVG Identification**: Find spatially variable genes for each domain
- **Meta Gene Discovery**: Construct composite gene signatures for domains
- **Multi-Sample Support**: Process multiple slides jointly or separately

## Quick Start

```python
from scripts.python.core_analysis import (
    prepare_data,
    calculate_adjacency_matrix,
    search_optimal_l,
    run_spagcn
)

# Prepare data
adata_prep = prepare_data(adata, n_top_genes=3000)

# Calculate adjacency matrix
adj = calculate_adjacency_matrix(adata_prep, histology=False)

# Search for optimal l parameter
l = search_optimal_l(adj, target_p=0.5)

# Run SpaGCN
domains = run_spagcn(adata_prep, adj, l=l, resolution=0.4)
adata.obs['spagcn_domain'] = domains
```

## File Structure

```
bio-spatial-transcriptomics-domains-spagcn/
├── SKILL.md                      # Skill metadata
├── README.md                     # This file
├── usage-guide.md                # Detailed usage guide
├── scripts/
│   └── python/
│       ├── __init__.py
│       ├── core_analysis.py      # Main analysis functions
│       ├── visualization.py      # Visualization utilities
│       └── utils.py              # Helper functions
├── tests/
│   └── test_spagcn.py           # Unit tests
└── examples/
    ├── minimal_example.py        # Basic workflow
    └── multi_sample_analysis.py  # Multi-sample analysis
```

## Requirements

- Python >= 3.9
- SpaGCN >= 1.2.7
- scanpy >= 1.10.0
- anndata >= 0.10.0
- torch >= 1.12.0
- numpy, pandas, matplotlib, seaborn

## Installation

```bash
pip install SpaGCN
```

Or with conda:
```bash
conda install -c conda-forge SpaGCN
```

## Key Functions

| Function | Purpose |
|----------|---------|
| `prepare_data()` | Preprocess spatial data |
| `calculate_adjacency_matrix()` | Build spatial adjacency matrix |
| `search_optimal_l()` | Find optimal spatial weight parameter |
| `search_optimal_resolution()` | Find resolution for target cluster count |
| `run_spagcn()` | Run SpaGCN clustering |
| `refine_domains()` | Spatial smoothing of domains |
| `identify_svgs()` | Find spatially variable genes |
| `find_meta_gene()` | Discover composite gene signatures |

## Hyperparameters

### l (Spatial Weight)
Controls the distance decay in adjacency matrix. Higher values give more weight to distant neighbors.

| p target | Typical l range | Use case |
|----------|-----------------|----------|
| 0.3 | 0.1 - 10 | Local neighborhoods only |
| 0.5 | 1 - 100 | Balanced (default) |
| 0.7 | 10 - 1000 | Large neighborhoods |

### resolution (Louvain)
Controls the number of clusters. Higher values produce more clusters.

| Target clusters | Typical resolution |
|-----------------|-------------------|
| 3-5 | 0.2 - 0.5 |
| 6-10 | 0.4 - 0.8 |
| 10+ | 0.8 - 1.5 |

### Histology Parameters (when using H&E)

| Parameter | Default | Description |
|-----------|---------|-------------|
| alpha | 1.0 | Weight for histology in adjacency |
| beta | 49 | Spot area for color extraction |

## Output

| Output | Description | Location |
|--------|-------------|----------|
| Domain labels | Spatial domain assignments | `adata.obs['pred']` |
| Refined domains | Post-processed domains | `adata.obs['refined_pred']` |
| Probabilities | Cluster assignment probabilities | Returned by `run_spagcn()` |
| SVGs | Spatially variable genes | DataFrame from `identify_svgs()` |
| Meta genes | Composite gene signatures | String + expression values |

## References

1. Hu et al. (2021). SpaGCN: Integrating gene expression, spatial location and histology to identify spatial domains and spatially variable genes by graph convolutional network. *Nature Methods*, 18(11), 1342-1351.
2. GitHub: https://github.com/jianhuupenn/SpaGCN
3. Tutorial: https://github.com/jianhuupenn/SpaGCN/tree/master/tutorial
