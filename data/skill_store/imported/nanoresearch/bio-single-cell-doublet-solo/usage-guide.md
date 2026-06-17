# SOLO Usage Guide

## Overview

SOLO (Single-cell Omics Linkage Observatory) is a semi-supervised deep learning method for doublet detection in single-cell RNA-seq data. It uses scVI's variational autoencoder to learn latent representations and trains a classifier to distinguish singlets from simulated doublets.

## Key Features

- **Deep Learning Approach**: Neural network classifier on learned representations
- **Simulated Doublets**: Creates artificial doublets by combining real cells
- **Probabilistic Output**: Calibrated doublet probabilities
- **GPU Acceleration**: Fast training on large datasets
- **Batch Handling**: Per-batch training for multi-batch experiments

## When to Use

- Large datasets (>10,000 cells)
- Deep learning-based approach preferred
- Integration with scVI workflow needed
- Scalable doublet detection required
- Probabilistic outputs desired

## Requirements

- Python >= 3.9
- scvi-tools >= 1.0
- scanpy >= 1.9
- Raw count matrix (not normalized)

## Installation

```bash
pip install scvi-tools
```

## Quick Start

```python
from scripts.python.core_analysis import run_solo_pipeline
from scripts.python.visualization import plot_doublet_summary

# Run SOLO
predictions = run_solo_pipeline(
    adata,
    batch_key=None,
    scvi_epochs=400,
    solo_epochs=100,
    doublet_threshold=0.5
)

# Visualize
plot_doublet_summary(predictions)
```

## Step-by-Step Guide

### 1. Data Preparation

```python
import scanpy as sc

# Load raw counts
adata = sc.read_h5ad("raw_counts.h5ad")

# Basic QC only (keep raw counts!)
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)

# Do NOT normalize or log-transform
# SOLO requires raw counts
```

### 2. Run Complete Pipeline

```python
from scripts.python.core_analysis import run_solo_pipeline

predictions = run_solo_pipeline(
    adata,
    batch_key=None,              # Set to batch column if applicable
    scvi_epochs=400,             # scVI training epochs
    solo_epochs=100,             # SOLO training epochs
    doublet_ratio=2,             # Simulated doublet ratio
    doublet_threshold=0.5,       # Classification threshold
    use_gpu=True,
    random_seed=42,
    inplace=True,                # Add to adata.obs
    verbose=True
)

# Results in adata.obs
print(adata.obs['solo_prediction'].value_counts())
```

### 3. Custom Training

```python
from scripts.python.core_analysis import (
    train_scvi_model, train_solo_model, predict_doublets
)

# Train scVI
vae = train_scvi_model(
    adata,
    batch_key='batch',
    n_latent=10,
    n_hidden=128,
    max_epochs=400,
    use_gpu=True
)

# Train SOLO
solo = train_solo_model(
    vae,
    doublet_ratio=2,
    max_epochs=100,
    use_gpu=True
)

# Predict
predictions = predict_doublets(solo, soft=True)
predictions['prediction'] = (predictions['doublet'] > 0.5).astype(int)
```

### 4. Multi-Batch Processing

```python
from scripts.python.core_analysis import run_solo_per_batch

# Process each batch separately
batch_results = run_solo_per_batch(
    adata,
    batch_key='lane',
    scvi_epochs=400,
    solo_epochs=100,
    use_gpu=True
)

# Combine results (skip any batch that failed)
import pandas as pd
all_predictions = pd.concat([v for v in batch_results.values() if v is not None])
```

### 5. Threshold Optimization

```python
from scripts.python.utils import (
    optimize_threshold_range, estimate_optimal_threshold
)

# Compare multiple thresholds
threshold_comparison = optimize_threshold_range(
    predictions,
    thresholds=[0.3, 0.4, 0.5, 0.6, 0.7]
)
print(threshold_comparison)

# Auto-estimate optimal threshold
optimal_thresh = estimate_optimal_threshold(
    predictions,
    method='otsu'  # or 'knee', 'quantile'
)
print(f"Optimal threshold: {optimal_thresh:.3f}")
```

### 6. Filter Doublets

```python
from scripts.python.core_analysis import filter_doublets

# Quick statistics
n_doublets = (predictions['doublet'] > 0.5).sum()
print(f"Doublet rate: {n_doublets/len(predictions)*100:.1f}%")

# Filter
adata_filtered = filter_doublets(
    adata,
    predictions,
    threshold=0.5,
    inplace=False
)

print(f"Removed {adata.n_obs - adata_filtered.n_obs} doublets")
```

### 7. Visualization

```python
from scripts.python.visualization import (
    plot_doublet_score_distribution,
    plot_doublets_on_embedding,
    plot_doublet_summary
)

# Distribution plot
plot_doublet_score_distribution(
    predictions,
    threshold=0.5,
    save_path='doublet_dist.pdf'
)

# On embedding (after computing UMAP)
sc.tl.umap(adata)
plot_doublets_on_embedding(
    adata,
    doublet_key='solo_prediction',
    basis='umap',
    save_path='doublets_umap.pdf'
)

# Comprehensive summary
plot_doublet_summary(predictions, save_path='summary.pdf')
```

### 8. Compare with Other Methods

```python
from scripts.python.utils import compare_predictions

# Run another method (e.g., Scrublet)
from scrublet import Scrublet
scrub = Scrublet(adata.X)
scores, calls = scrub.scrub_doublets()

scrublet_preds = pd.DataFrame({
    'prediction': calls
}, index=adata.obs_names)

# Compare
comparison = compare_predictions(
    predictions,
    scrublet_preds,
    other_name='scrublet'
)
print(f"Agreement: {comparison['agreement']:.2%}")
```

### 9. Export Results

```python
# Export predictions directly with pandas
predictions.to_csv('solo_results.csv')
predictions.to_excel('solo_results.xlsx')

# Save trained SOLO model
solo.save('./solo_model', overwrite=True)

# Load saved model later
from scvi.external import SOLO
solo_loaded = SOLO.load('./solo_model')
```

## AI Agent Test Cases

### Basic Usage
> "Run SOLO for doublet detection on my scRNA-seq data"

```python
predictions = run_solo_pipeline(adata, use_gpu=True)
```

### Multi-Batch
> "Run SOLO per batch for my multi-lane experiment"

```python
batch_results = run_solo_per_batch(adata, batch_key='lane')
```

### Threshold Optimization
> "Find optimal doublet threshold for my data"

```python
threshold = estimate_optimal_threshold(predictions, method='otsu')
```

### Method Comparison
> "Compare SOLO with Scrublet results"

```python
comparison = compare_predictions(solo_preds, scrublet_preds)
```

## Parameters

### scVI Training

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_latent` | 10 | Latent space dimensionality |
| `n_hidden` | 128 | Hidden layer size |
| `n_layers` | 3 | Number of hidden layers |
| `max_epochs` | 400 | Training epochs |
| `batch_key` | None | Batch column for integration |

### SOLO Training

| Parameter | Default | Description |
|-----------|---------|-------------|
| `doublet_ratio` | 2 | Ratio of simulated doublets |
| `max_epochs` | 100 | Training epochs |
| `early_stopping_patience` | 30 | Early stopping patience |
| `learning_rate` | 1e-3 | Learning rate |

### Prediction

| Parameter | Default | Description |
|-----------|---------|-------------|
| `soft` | True | Return probabilities |
| `threshold` | 0.5 | Classification threshold |

## Output Interpretation

### Doublet Score
- **Range**: 0-1
- **Interpretation**: Probability of being a doublet
- **Higher values**: More likely doublet

### Expected Doublet Rates
- 10x Genomics: ~2-8% depending on cell loading
- Drop-seq: ~1-5%
- Higher rates may indicate issues

## Best Practices

1. **Use Raw Counts**: Always input raw UMI counts
2. **Basic QC Only**: Filter cells/genes but don't normalize
3. **GPU Recommended**: Significantly faster for large datasets
4. **One Batch at a Time**: For multi-batch, use `run_solo_per_batch`
5. **Check Doublet Rate**: Should align with expected rates
6. **Compare Methods**: Cross-validate with Scrublet or DoubletFinder
7. **Save Models**: Save trained models for reproducibility

## Troubleshooting

### Training doesn't converge
- Increase `max_epochs`
- Adjust `learning_rate`
- Check data quality

### Too many/few doublets
- Adjust `threshold`
- Try threshold optimization
- Compare with expected rates

### GPU out of memory
- Reduce `batch_size`
- Use CPU (`use_gpu=False`)
- Process in smaller batches

### Multi-batch issues
- Ensure batch_key is correctly specified
- Use `restrict_to_batch` for individual batches
- Check batch balance

## References

1. Bernstein et al. (2020). Solo: Doublet identification in single-cell RNA-Seq via semi-supervised deep learning. *Cell Systems*, 11(1), 95-101.
2. Gayoso et al. (2022). A Python library for probabilistic analysis of single-cell omics data. *Nature Biotechnology*, 40, 1636-1639.
3. scvi-tools documentation: https://docs.scvi-tools.org/
