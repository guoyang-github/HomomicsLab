# bio-single-cell-trajectory-scvelo

RNA velocity analysis using scVelo. Infers directionality of cellular dynamics by distinguishing unspliced (pre-mRNA) and spliced (mature mRNA) counts.

## Description

This skill provides comprehensive RNA velocity analysis capabilities using scVelo. RNA velocity is a powerful computational approach that estimates the time derivative of gene expression state by comparing spliced and unspliced mRNA counts, enabling prediction of future cell states and reconstruction of developmental trajectories.

## Features

- **Three velocity estimation modes**:
  - `deterministic`: Steady-state model (fast)
  - `stochastic`: Second-order moments model (balanced)
  - `dynamical`: Full transcriptional dynamics (most accurate)

- **Comprehensive analysis**:
  - Velocity estimation and graph construction
  - Latent time inference
  - Terminal state identification
  - Driver gene ranking
  - PAGA velocity graph
  - Cell cycle scoring

- **Visualization**:
  - Stream and grid plots
  - Phase portraits
  - Latent time visualization
  - Terminal state plotting
  - Comprehensive summary plots

## Installation

```bash
pip install scvelo
```

## Quick Start

```python
import sys
sys.path.insert(0, 'scripts/python')

from core_analysis import (
    prepare_data_for_velocity,
    run_velocity_analysis,
    compute_latent_time_scvelo
)
from visualization import plot_velocity_embedding_stream

# Load data with spliced/unspliced layers
adata = sc.read_h5ad('your_data.h5ad')

# Run complete analysis
adata = prepare_data_for_velocity(adata, n_top_genes=2000)
adata = run_velocity_analysis(adata, mode='stochastic')
compute_latent_time_scvelo(adata)

# Visualize
plot_velocity_embedding_stream(adata, basis='umap', color='clusters')
```

## File Structure

```
.
├── SKILL.md                      # Skill metadata
├── usage-guide.md               # Detailed usage guide
├── README.md                    # This file
├── scripts/
│   └── python/
│       ├── core_analysis.py     # Core velocity functions
│       ├── visualization.py     # Plotting functions
│       └── utils.py             # Utility functions
├── examples/
│   ├── minimal_example.py       # Basic workflow
│   └── advanced_example.py      # Advanced features
└── tests/
    └── test_scvelo.py           # Unit tests
```

## Requirements

- Python >= 3.8
- scvelo >= 0.2.5
- scanpy >= 1.9
- anndata >= 0.8
- matplotlib >= 3.4

## Input Data

Requires an AnnData object with:
- `spliced` layer: Spliced (mature mRNA) counts
- `unspliced` layer: Unspliced (pre-mRNA) counts
- Pre-computed embedding (recommended)
- Cell type annotations (recommended)

## References

1. Bergen et al. (2020). Generalizing RNA velocity to transient cell states through dynamical modeling. *Nature Biotechnology*, 38(12), 1408-1414.
2. La Manno et al. (2018). RNA velocity of single cells. *Nature*, 560(7719), 494-498.
3. scVelo documentation: https://scvelo.readthedocs.io/
