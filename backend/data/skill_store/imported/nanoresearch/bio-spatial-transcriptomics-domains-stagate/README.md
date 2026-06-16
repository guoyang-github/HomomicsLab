# STAGATE Spatial Domain Identification

[![Python >=3.9](https://img.shields.io/badge/python->=3.9-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch->=1.12-orange.svg)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive skill for spatial domain identification in spatial transcriptomics using [STAGATE](https://github.com/QIFEIDKN/STAGATE) - a graph attention autoencoder framework.

## Overview

STAGATE learns low-dimensional latent embeddings by integrating gene expression with spatial information through a graph attention autoencoder. It adaptively learns edge weights of spatial neighbor networks and uses them to update spot representations by aggregating information from neighbors.

### Key Features

- **Graph Attention Autoencoder**: Deep learning-based dimensionality reduction
- **Spatial-Aware**: Integrates spatial coordinates with gene expression
- **Adaptive Attention**: Learns edge weights dynamically
- **Denoising**: Reconstructs denoised expression profiles
- **3D Support**: Multi-slice integration and 3D domain identification
- **Fast PyG Implementation**: 10x faster than TensorFlow version

## Quick Start

```python
import scanpy as sc
from scripts.python.core_analysis import (
    prepare_data, build_spatial_network, train_stagate, mclust_clustering
)
from scripts.python.visualization import plot_domains

# Load data
adata = sc.read_h5ad("visium_data.h5ad")

# Prepare
adata = prepare_data(adata, n_top_genes=3000)

# Build network
build_spatial_network(adata, rad_cutoff=150)

# Train
adata = train_stagate(adata, n_epochs=1000)

# Cluster
adata = mclust_clustering(adata, n_clusters=7)

# Visualize
plot_domains(adata, domain_key='mclust')
```

## Installation

### Prerequisites

```bash
# Core dependencies
pip install scanpy anndata pandas numpy matplotlib seaborn scikit-learn

# PyTorch (follow https://pytorch.org/ for your system)
pip install torch

# PyTorch Geometric
pip install torch-geometric

# Optional: for mclust clustering
pip install rpy2
```

### System Requirements

- Python >= 3.9
- PyTorch >= 1.12.0
- PyTorch Geometric >= 2.0.0
- scanpy >= 1.9.0
- GPU recommended for faster training

## File Structure

```
bio-spatial-transcriptomics-domains-stagate/
├── README.md                    # This file
├── SKILL.md                     # Detailed API documentation
├── usage-guide.md               # Step-by-step usage guide
├── scripts/
│   └── python/
│       ├── core_analysis.py     # Core analysis functions
│       ├── stagate_model.py     # STAGATE model implementation
│       └── visualization.py     # Visualization functions
├── examples/
│   └── example_basic.py         # Complete workflow example
└── tests/
    └── test_stagate.py          # Unit tests
```

## Core Functions

### Analysis Functions (`core_analysis.py`)

| Function | Description |
|----------|-------------|
| `prepare_data()` | Data preprocessing and HVG selection |
| `build_spatial_network()` | Build 2D spatial neighbor network |
| `build_3d_spatial_network()` | Build 3D network for multi-slice data |
| `train_stagate()` | Train STAGATE model |
| `mclust_clustering()` | Cluster with mclust (R-based) |
| `leiden_clustering()` | Cluster with Leiden algorithm |
| `create_batch_data()` | Split data for batch processing |
| `export_results()` | Export results to files |

### Visualization Functions (`visualization.py`)

| Function | Description |
|----------|-------------|
| `plot_domains()` | Spatial domain visualization |
| `plot_domains_comparison()` | Compare multiple clusterings |
| `plot_embedding_umap()` | UMAP of STAGATE embeddings |
| `plot_domain_proportions()` | Domain composition plots |
| `plot_multi_sample_domains()` | Multiple sample comparison |
| `plot_aligned_slices()` | 3D slice visualization |
| `plot_denoising_comparison()` | Raw vs denoised expression |

## Algorithm Overview

### Graph Attention Autoencoder

```
Input (Gene Expression) → Encoder → Embedding → Decoder → Reconstruction
                ↑__________Attention___________↑
```

**Encoder:**
1. Conv1: Apply graph attention to aggregate neighbor information
2. Conv2: Generate low-dimensional embeddings

**Decoder:**
1. Conv3: Reconstruct with tied weights and attention
2. Conv4: Output denoised expression

### Attention Mechanism

STAGATE uses a sigmoid-activated attention mechanism:

```
α_ij = sigmoid(a^T [Wh_i || Wh_j])
```

Where:
- α_ij: Attention weight between spots i and j
- W: Learnable weight matrix
- h_i, h_j: Feature vectors
- ||: Concatenation

## Platform-Specific Settings

| Platform | rad_cutoff | Notes |
|----------|------------|-------|
| Visium (55μm) | 150-200 | ~3-4 spot diameters |
| Visium HD | 30-50 | Higher resolution |
| Xenium | 20-50 | Subcellular spots |
| MERFISH | 30-60 | Single-cell |
| Slide-seq | 50-100 | 10μm beads |

## Example Workflow

See `examples/example_basic.py` for a complete workflow including:

1. Data loading and preparation
2. Spatial network construction
3. STAGATE model training
4. Domain clustering
5. Visualization and export

Run the example:

```bash
cd examples
python example_basic.py
```

## Performance Tips

1. **Use GPU**: Set `device='cuda'` for 10x speedup
2. **Batch Processing**: Use `create_batch_data()` for large datasets
3. **Early Stopping**: Monitor loss and reduce epochs if converged
4. **Memory**: Process large datasets in batches

## Troubleshooting

### GPU out of memory
```python
# Use CPU
adata = train_stagate(adata, device='cpu')

# Or reduce hidden dimensions
adata = train_stagate(adata, hidden_dims=[256, 30])
```

### Poor clustering
```python
# Adjust network radius
build_spatial_network(adata, rad_cutoff=200)  # Larger neighborhood

# Or increase embedding dimension
adata = train_stagate(adata, hidden_dims=[512, 50])
```

### mclust not available
```python
# Use Leiden instead
adata = leiden_clustering(adata, resolution=0.5)
```

## Citation

If you use STAGATE in your research, please cite:

```
Dong, K., & Zhang, S. (2022). Deciphering spatial domains from spatially 
resolved transcriptomics with an adaptive graph attention auto-encoder. 
Nature Communications, 13(1), 1-12.
```

## References

1. **Primary Paper**
   Dong & Zhang (2022). Nature Communications 13:1736.
   https://doi.org/10.1038/s41467-022-29439-6

2. **GitHub (TensorFlow)**
   https://github.com/QIFEIDKN/STAGATE

3. **GitHub (PyTorch Geometric)**
   https://github.com/QIFEIDKN/STAGATE_pyG

4. **Documentation**
   https://stagate.readthedocs.io/

## Related Skills

- [bio-spatial-transcriptomics-domains-spagcn](../bio-spatial-transcriptomics-domains-spagcn/) - SpaGCN for spatial domains
- [bio-spatial-transcriptomics-domains-bayesspace-r](../bio-spatial-transcriptomics-domains-bayesspace-r/) - BayesSpace R package
- [bio-spatial-transcriptomics-domains-graphst](../bio-spatial-transcriptomics-domains-graphst/) - GraphST method
- [bio-spatial-transcriptomics-analysis-scanpy](../bio-spatial-transcriptomics-analysis-scanpy/) - General spatial analysis

## License

This skill is provided under the MIT License. The underlying STAGATE package is under BSD-3-Clause.

## Contact

For questions about this skill, please open an issue in the repository.
For questions about STAGATE package, visit: https://github.com/QIFEIDKN/STAGATE
