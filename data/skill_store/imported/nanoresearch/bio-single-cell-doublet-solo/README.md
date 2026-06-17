# SOLO Doublet Detection Skill

A comprehensive Python-based skill for deep learning doublet detection using SOLO from scvi-tools. SOLO uses a semi-supervised VAE approach to classify cells as singlets or doublets in the latent space.

## Features

- **Deep Learning Classification**: Neural network classifier on scVI latent representations
- **Simulated Doublets**: Creates artificial doublets by combining real cell profiles
- **Probabilistic Output**: Calibrated doublet probabilities (not just binary calls)
- **Multi-Batch Support**: Handles multi-batch datasets with per-batch training
- **Threshold Optimization**: Automatic threshold estimation methods
- **Comprehensive Visualization**: Distribution plots, embedding plots, training curves
- **Method Comparison**: Compare with Scrublet and other doublet detectors

## Quick Start

```python
from scripts.python.core_analysis import run_solo_pipeline
from scripts.python.visualization import plot_doublet_summary

# Run SOLO
predictions = run_solo_pipeline(
    adata,
    batch_key=None,              # Set to batch column if applicable
    scvi_epochs=400,
    solo_epochs=100,
    doublet_threshold=0.5,
    use_gpu=True
)

# Visualize results
plot_doublet_summary(predictions)
```

## File Structure

```
bio-single-cell-doublet-solo/
├── SKILL.md                      # Skill metadata
├── README.md                     # This file
├── usage-guide.md                # Detailed usage guide
├── scripts/
│   └── python/
│       ├── core_analysis.py      # Main analysis functions
│       ├── visualization.py      # Visualization utilities
│       └── utils.py              # Helper functions
├── tests/
│   └── test_solo.py              # Unit tests
└── examples/
    ├── minimal_example.py        # Basic workflow
    └── advanced_example.py       # Advanced features
```

## Requirements

- Python >= 3.9
- scvi-tools >= 1.0
- scanpy >= 1.9
- anndata >= 0.8
- torch >= 2.0
- matplotlib >= 3.7
- seaborn >= 0.12

## Installation

```bash
# Install scvi-tools
pip install scvi-tools

# Install additional dependencies
pip install matplotlib seaborn scikit-image

# Optional: for GPU support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Core Functions

### Analysis

| Function | Purpose |
|----------|---------|
| `run_solo_pipeline()` | Complete SOLO workflow |
| `train_scvi_model()` | Train scVI VAE |
| `train_solo_model()` | Train SOLO classifier |
| `predict_doublets()` | Get doublet predictions |
| `run_solo_per_batch()` | Per-batch analysis |

### Result Processing

| Function | Purpose |
|----------|---------|
| `filter_doublets()` | Remove predicted doublets |

| `add_predictions_to_adata()` | Add to AnnData |


### Visualization

| Function | Purpose |
|----------|---------|
| `plot_doublet_score_distribution()` | Score histogram |
| `plot_doublets_on_embedding()` | UMAP/t-SNE visualization |
| `plot_doublet_summary()` | Comprehensive summary |
| `plot_training_history()` | Training curves |
| `plot_batch_comparison()` | Multi-batch comparison |

### Utilities

| Function | Purpose |
|----------|---------|
| `validate_adata_for_solo()` | Validate input |
| `preprocess_for_solo()` | Preprocess data |
| `estimate_optimal_threshold()` | Auto threshold |
| `compare_predictions()` | Compare methods |
| `estimate_expected_doublet_rate()` | Expected rate |

## Workflow Examples

### Basic

```python
# Load data
adata = sc.read_h5ad("raw_counts.h5ad")

# Run SOLO
predictions = run_solo_pipeline(adata)

# Filter
adata_filtered = filter_doublets(adata, predictions)
```

### Multi-Batch

```python
# Process each batch separately
batch_results = run_solo_per_batch(adata, batch_key='lane')

# Combine
all_preds = pd.concat(batch_results.values())
```

### Custom Training

```python
# Custom scVI
vae = train_scvi_model(adata, n_latent=20, max_epochs=400)

# Custom SOLO
solo = train_solo_model(vae, doublet_ratio=3, max_epochs=150)

# Predict
predictions = predict_doublets(solo)
```

## Algorithm Overview

1. **scVI Training**: Learns latent representations of cells
2. **Doublet Simulation**: Creates artificial doublets by combining real cells
3. **Classifier Training**: Trains neural network to distinguish singlets from doublets
4. **Prediction**: Outputs doublet probabilities for each cell

## Output

| Column | Description |
|--------|-------------|
| `solo_doublet_score` | Probability of being doublet |
| `solo_singlet_score` | Probability of being singlet |
| `solo_prediction` | Binary call (singlet/doublet) |

## References

1. Bernstein et al. (2020). Solo: Doublet identification in single-cell RNA-Seq via semi-supervised deep learning. *Cell Systems*.
2. Gayoso et al. (2022). A Python library for probabilistic analysis of single-cell omics data. *Nature Biotechnology*.
3. scvi-tools documentation: https://docs.scvi-tools.org/
