# scGen: Single-Cell Perturbation Prediction

Generative deep learning model for predicting single-cell perturbation responses using Variational Autoencoders (VAE).

## Overview

scGen is a deep generative model that learns to predict how cells respond to perturbations. It can:

- **Predict perturbation effects** on unseen cell types or conditions
- **Perform batch correction** while preserving biological signals
- **Extract perturbation vectors** representing the latent space direction of perturbations
- **Enable cross-study predictions** by transferring learned perturbation effects

Reference: Lotfollahi et al., "scGen predicts single-cell perturbation responses", Nature Methods 2019

## Installation

```bash
pip install scgen scvi-tools
```

## Quick Start

```python
import scanpy as sc
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join('scripts', 'python'))

from core_analysis import (
    preprocess_for_scgen,
    setup_scgen_anndata,
    train_scgen_model,
    predict_perturbation
)

# Load data
adata = sc.read_h5ad('perturbation_data.h5ad')

# Preprocess
adata = preprocess_for_scgen(adata, n_top_genes=7000)

# Setup scGen
adata = setup_scgen_anndata(adata, batch_key='condition', labels_key='cell_type')

# Train
model = train_scgen_model(adata, max_epochs=100)

# Predict
predicted, delta = predict_perturbation(
    model,
    ctrl_key='control',
    stim_key='stimulated',
    celltype_to_predict='CD4T'
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
    └── test_scgen_analysis.py
```

## Core Modules

### core_analysis.py

Main analysis functions:

| Function | Description |
|----------|-------------|
| `validate_perturbation_data()` | Validate data structure |
| `preprocess_for_scgen()` | Normalize and select HVGs |
| `setup_scgen_anndata()` | Register data with scGen |
| `train_scgen_model()` | Train VAE model |
| `predict_perturbation()` | Predict stimulated cells |
| `batch_correction()` | Remove batch effects |
| `run_complete_scgen_pipeline()` | Full workflow |

### visualization.py

Plotting functions:

| Function | Description |
|----------|-------------|
| `plot_regression_mean()` | Mean expression comparison |
| `plot_regression_variance()` | Variance comparison |
| `plot_binary_classifier()` | Perturbation classifier |
| `plot_latent_space()` | Latent space visualization |
| `plot_perturbation_vector()` | Vector components plot |

### utils.py

Utility functions:

| Function | Description |
|----------|-------------|
| `balancer()` | Balance cell type populations |
| `extractor()` | Extract cell type subsets |
| `evaluate_prediction_accuracy()` | Compute metrics |
| `compare_perturbation_vectors()` | Compare deltas |
| `create_prediction_report()` | Generate reports |

## Input Data Format

Required AnnData structure:

```python
adata.X                    # Gene expression matrix
adata.obs['condition']     # Condition labels ('control', 'stimulated')
adata.obs['cell_type']     # Cell type labels (optional)
```

## Output Data

| Output | Type | Description |
|--------|------|-------------|
| `model` | SCGEN | Trained model |
| `corrected` | AnnData | Batch-corrected data |
| `predicted` | AnnData | Predicted cells |
| `delta` | np.ndarray | Perturbation vector |

## Examples

### Minimal Example

See `examples/minimal_example.py` for a basic workflow.

### Advanced Example

See `examples/advanced_example.py` for comprehensive analysis including:
- Cross-cell-type prediction
- Multiple evaluation metrics
- Comprehensive visualization
- Batch correction

## Testing

Run unit tests:

```bash
cd skills/bio-single-cell-perturbation-scgen
python -m pytest tests/test_scgen_analysis.py -v
```

Or specific test classes:

```bash
python -m pytest tests/test_scgen_analysis.py::TestCoreAnalysis -v
python -m pytest tests/test_scgen_analysis.py::TestUtils -v
python -m pytest tests/test_scgen_analysis.py::TestVisualization -v
```

## Documentation

- **SKILL.md**: Comprehensive documentation with workflow, parameters, and error handling
- **usage-guide.md**: Step-by-step guide with code examples
- **examples/**: Working example scripts

## Key Concepts

### Perturbation Vector (Delta)

The perturbation vector represents the direction and magnitude of the perturbation effect in latent space. It is computed as:

```
delta = mean(latent_stimulated) - mean(latent_control)
```

### Cross-Cell-Type Prediction

scGen can predict how a cell type would respond to a perturbation even if that cell type was never observed in the stimulated condition during training. This is done by:

1. Learning the perturbation vector from cell types with both conditions
2. Applying the vector to the target cell type's control cells

### Batch Correction

scGen removes technical batch effects by:

1. Computing cell type-specific batch offsets in latent space
2. Adjusting latent representations to a reference batch
3. Decoding corrected latent representations

## References

1. Lotfollahi et al. (2019). scGen predicts single-cell perturbation responses. *Nature Methods*.
2. scGen documentation: https://scgen.readthedocs.io/
3. scGen GitHub: https://github.com/theislab/scgen

## License

This skill wrapper follows the same license as scGen (BSD-3-Clause).
