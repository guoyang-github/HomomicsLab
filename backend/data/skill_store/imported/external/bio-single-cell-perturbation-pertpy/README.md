# pertpy: Single-Cell Perturbation Analysis

Python toolkit for analyzing single-cell perturbation data including CRISPR screens, drug perturbations, and genetic knockouts.

## Overview

pertpy is a Python package in the scverse ecosystem designed specifically for perturbation analysis of single-cell data. It provides tools for:

- **Perturbation Space Analysis**: Aggregate cells by perturbation for downstream analysis
- **Distance Metrics**: Compare perturbations using various statistical distances
- **Differential Expression**: Identify genes affected by perturbations
- **Augur Classification**: Machine learning-based perturbation effect quantification
- **Mixscape**: CRISPR screen analysis to identify perturbed cells
- **Guide RNA Assignment**: Assign gRNAs to cells in CRISPR screens

## Installation

```bash
pip install pertpy
```

## Quick Start

```python
import scanpy as sc
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join('scripts', 'python'))

from core_analysis import (
    check_perturbation_data,
    compute_pseudobulk_space,
    run_augur_classification,
    run_complete_perturbation_analysis
)

# Load your perturbation data
adata = sc.read_h5ad('perturbation_data.h5ad')

# Validate data
check_perturbation_data(adata, perturbation_col='perturbation', control='control')

# Run complete analysis pipeline
adata = run_complete_perturbation_analysis(
    adata,
    perturbation_col='perturbation',
    control='control'
)
```

## Directory Structure

```
.
├── README.md                 # This file
├── SKILL.md                  # Detailed documentation for LLM agents
├── usage-guide.md            # Step-by-step usage guide
├── examples/                 # Example scripts
│   ├── minimal_example.py    # Basic workflow
│   └── advanced_example.py   # Comprehensive workflow
├── scripts/                  # Core analysis scripts
│   └── python/
│       ├── core_analysis.py  # Main analysis functions
│       ├── visualization.py  # Plotting functions
│       └── utils.py          # Utility functions
└── tests/                    # Unit tests
    └── test_pertpy.py
```

## Usage Examples

### Minimal Example

See `examples/minimal_example.py` for a basic workflow:

```python
from core_analysis import check_perturbation_data, run_augur_classification

# Validate and run Augur
check_perturbation_data(adata, perturbation_col='perturbation')
adata = run_augur_classification(adata, labels_col='perturbation')
```

### Advanced Example

See `examples/advanced_example.py` for a comprehensive workflow including:
- Pseudobulk and centroid space computation
- Distance calculations between perturbations
- Mixscape analysis for CRISPR screens
- Differential expression analysis
- Comprehensive visualization

## Core Modules

### core_analysis.py

Main analysis functions:

| Function | Description |
|----------|-------------|
| `check_perturbation_data()` | Validate AnnData for perturbation analysis |
| `compute_pseudobulk_space()` | Aggregate cells by perturbation |
| `compute_centroid_space()` | Compute centroids in embedding space |
| `calculate_perturbation_distances()` | Calculate distances between perturbations |
| `compute_perturbation_signature()` | Compute expression change vs control |
| `run_mixscape_classification()` | Classify cells as perturbed/NP |
| `assign_guide_rna()` | Assign gRNAs to cells |
| `compare_perturbations()` | Differential expression analysis |
| `run_augur_classification()` | ML-based perturbation classification |
| `run_complete_perturbation_analysis()` | Full pipeline |

### visualization.py

Plotting functions:

| Function | Description |
|----------|-------------|
| `plot_augur_results()` | Plot Augur prioritization |
| `plot_perturbation_distance_heatmap()` | Distance matrix heatmap |
| `plot_mixscape_results()` | Mixscape classification |
| `plot_de_volcano()` | DE volcano plots |
| `plot_distance_dendrogram()` | Hierarchical clustering |
| `plot_perturbation_summary()` | Comprehensive summary |

### utils.py

Utility functions:

| Function | Description |
|----------|-------------|
| `get_perturbation_summary()` | Summary statistics per perturbation |
| `find_high_confidence_perturbations()` | Identify strong effects |
| `export_de_results()` | Export DE results to CSV |
| `create_perturbation_report()` | Generate analysis report |
| `check_dependencies()` | Verify required packages |

## Input Data Format

Required AnnData structure:

```python
adata.X                    # Expression matrix (raw or normalized)
adata.obs['perturbation']  # Perturbation labels
adata.obs['replicate']     # Replicate information (for DE)
adata.obs['guide_identity'] # gRNA labels (for CRISPR)
```

## Output Data

| Output | Location |
|--------|----------|
| Pseudobulk profiles | Returned AnnData |
| Distance matrix | pd.DataFrame |
| DE results | Dict[str, pd.DataFrame] |
| Perturbation signature | `adata.layers['X_pert']` |
| Mixscape class | `adata.obs['mixscape_class']` |
| Augur results | `adata.uns['augur_results']` |

## Testing

Run unit tests:

```bash
cd skills/bio-single-cell-perturbation-pertpy
python -m pytest tests/test_pertpy.py -v
```

Or run specific test classes:

```bash
python -m pytest tests/test_pertpy.py::TestCoreAnalysis -v
python -m pytest tests/test_pertpy.py::TestUtils -v
python -m pytest tests/test_pertpy.py::TestVisualization -v
```

## Documentation

- **SKILL.md**: Comprehensive documentation with workflow, parameters, and error handling
- **usage-guide.md**: Step-by-step guide with code examples
- **examples/**: Working example scripts

## References

1. Schaer et al. (2023). pertpy: A Python toolkit for perturbation analysis. *bioRxiv*.
2. Papathanasiou et al. (2023). Augur: Cell type prioritization in single-cell data. *Nature Methods*.
3. Replogle et al. (2022). Mapping information-rich genotype-phenotype landscapes with genome-scale Perturb-seq. *Cell*.
4. [pertpy Documentation](https://pertpy.readthedocs.io/)
5. [pertpy GitHub](https://github.com/scverse/pertpy)

## License

This skill wrapper is provided under the same license as pertpy (BSD-3-Clause).
