# Tangram Spatial Transcriptomics Deconvolution

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tangram 1.0+](https://img.shields.io/badge/tangram--sc-1.0+-green.svg)](https://github.com/broadinstitute/Tangram)

Deep learning method for mapping single-cell RNA-seq data to spatial transcriptomics using PyTorch optimization.

## Overview

Tangram maps single-cell RNA-seq data onto spatial transcriptomics by learning a probabilistic alignment between the two modalities. It uses gradient descent optimization with cosine similarity loss to find the optimal mapping matrix between cells and spatial spots.

### Key Features

- **Fast Mapping**: Clusters mode completes in minutes
- **High Resolution**: Cells mode maps individual cells
- **Gene Imputation**: Project unmeasured genes from scRNA-seq
- **Cross-Validation**: Built-in CV for quality assessment
- **Cell Counting**: Constrained mode with segmentation
- **GPU Support**: CUDA acceleration for large datasets

## Quick Start

```python
from scripts.python.core_analysis import (
    prepare_data, map_cells_to_space, project_cell_annotations
)

# Load data
adata_sc = sc.read_h5ad("single_cell.h5ad")
adata_sp = sc.read_h5ad("spatial.h5ad")

# Prepare and map
adata_sc_prep, adata_sp_prep = prepare_data(adata_sc, adata_sp)
adata_map = map_cells_to_space(
    adata_sc_prep, adata_sp_prep,
    mode='clusters',
    cluster_label='cell_type',
    num_epochs=1000,
    device='cuda:0',
)

# Project annotations
project_cell_annotations(adata_map, adata_sp_prep, 'cell_type')
```

## Installation

```bash
pip install tangram-sc torch scanpy squidpy matplotlib seaborn
```

## Usage Modes

| Mode | Speed | Resolution | Best For |
|------|-------|------------|----------|
| `clusters` | Fast (~minutes) | Cell type averages | Large datasets, exploration |
| `cells` | Slow (~hours) | Individual cells | High-resolution mapping |
| `constrained` | Medium | Cell counts | When cell counts are known |

## Workflow Example

```python
import scanpy as sc
from scripts.python.core_analysis import *
from scripts.python.visualization import *

# 1. Load data
adata_sc = sc.read_h5ad('single_cell.h5ad')
adata_sp = sc.read_h5ad('spatial.h5ad')

# 2. Prepare data
adata_sc_prep, adata_sp_prep = prepare_data(adata_sc, adata_sp)

# 3. Map cells (clusters mode)
adata_map = map_cells_to_space(
    adata_sc_prep, adata_sp_prep,
    mode='clusters',
    cluster_label='cell_type',
    device='cuda:0',
)

# 4. Project genes
adata_ge = project_genes(adata_map, adata_sc_prep)

# 5. Project cell types
project_cell_annotations(adata_map, adata_sp_prep, 'cell_type')

# 6. Visualize
plot_training_scores(adata_map)
plot_annotation_comparison(adata_sp_prep)

# 7. Cross-validate
cv_dict = cross_val(adata_sc_prep, adata_sp_prep, mode='clusters', cluster_label='cell_type')
print(f"CV score: {cv_dict['avg_test_score']:.3f}")
```

## File Structure

```
├── SKILL.md                 # Comprehensive API documentation
├── README.md               # This file
├── usage-guide.md          # Detailed usage instructions
├── examples/
│   └── example_basic.py    # Complete workflow example
├── scripts/
│   └── python/
│       ├── __init__.py     # Module exports
│       ├── core_analysis.py    # Core functions
│       └── visualization.py    # Plotting functions
└── tests/
    └── test_tangram.py     # Unit tests
```

## Core Functions

### Data Preparation

```python
from scripts.python.core_analysis import prepare_data

adata_sc_prep, adata_sp_prep = prepare_data(
    adata_sc, adata_sp,
    genes=None,              # Marker genes (optional)
    gene_to_lowercase=True,  # Convert gene names to lowercase
)
```

### Cell Mapping

```python
from scripts.python.core_analysis import map_cells_to_space

# Clusters mode (fast)
adata_map = map_cells_to_space(
    adata_sc_prep, adata_sp_prep,
    mode='clusters',
    cluster_label='cell_type',
    num_epochs=1000,
    device='cuda:0',
)

# Cells mode (high resolution)
adata_map = map_cells_to_space(
    adata_sc_prep, adata_sp_prep,
    mode='cells',
    num_epochs=1000,
    lambda_r=0.5,  # Entropy regularizer
)
```

### Gene Imputation

```python
from scripts.python.core_analysis import project_genes

adata_ge = project_genes(
    adata_map=adata_map,
    adata_sc=adata_sc_prep,
    cluster_label='cell_type',
    scale=True,
)
```

### Cell Type Projection

```python
from scripts.python.core_analysis import project_cell_annotations, extract_deconvolution_results

# Project annotations
project_cell_annotations(adata_map, adata_sp_prep, 'cell_type')

# Extract proportions
df_props = extract_deconvolution_results(adata_sp_prep)
```

### Quality Assessment

```python
from scripts.python.core_analysis import cross_val, eval_metric

# Cross-validation
cv_dict, adata_ge_cv, df_test = cross_val(
    adata_sc_prep, adata_sp_prep,
    mode='clusters',
    cluster_label='cell_type',
    cv_mode='loo',
    return_gene_pred=True,
)

# Evaluation metrics
metrics, auc_coords = eval_metric(df_compare)
print(f"AUC score: {metrics['auc_score']:.3f}")
```

## Visualization

```python
from scripts.python.visualization import *

# Training diagnostics
fig = plot_training_scores(adata_map)

# Cell type maps
fig = plot_cell_type_map(adata_sp, 'Neuron', cmap='Reds')
fig = plot_annotation_comparison(adata_sp, n_cols=4)

# Gene comparison
plot_genes_sc(['Gene1', 'Gene2'], adata_sp, adata_ge)

# AUC evaluation
fig = plot_auc(df_compare)
```

## Documentation

- **[SKILL.md](SKILL.md)**: Comprehensive API documentation with all parameters
- **[usage-guide.md](usage-guide.md)**: Detailed usage instructions and best practices
- **[examples/example_basic.py](examples/example_basic.py)**: Complete workflow example

## Algorithm Overview

Tangram learns a mapping matrix M (cells × spots) by minimizing:

```
Loss = -cosine_similarity(M · S, G) + regularization_terms
```

Where:
- S: Single-cell gene expression matrix
- G: Spatial gene expression matrix
- M: Mapping probabilities (learned)

The optimization uses PyTorch automatic differentiation with Adam optimizer.

### Loss Function Components

| Component | Description |
|-----------|-------------|
| `lambda_g1` | Gene-voxel cosine similarity (main loss) |
| `lambda_r` | Entropy regularizer (promotes peaked probabilities) |
| `lambda_d` | Density prior matching |
| `lambda_g2` | Voxel-gene similarity |

## Citation

```bibtex
@article{biancalani2021deep,
  title={Deep learning and alignment of spatially-resolved whole transcriptome profiles of cells in the mouse brain with Tangram},
  author={Biancalani, Tommaso and Scalia, Gabriele and Buffoni, Lorenzo and Avihay, Lorenzo and Lu, Chen and Svensson, Valentine and Langseth, Christopher Mosquera and Engblom, Christer and Chappell, Lauren and Lawson, Devon A and others},
  journal={Nature Methods},
  volume={18},
  number={11},
  pages={1352--1362},
  year={2021},
  publisher={Nature Publishing Group}
}
```

## Links

- [Tangram GitHub](https://github.com/broadinstitute/Tangram)
- [Tangram Documentation](https://tangram-sc.readthedocs.io/)
- [Nature Methods Paper](https://www.nature.com/articles/s41592-021-01264-7)

## License

This skill follows the same license as the Tangram package.
