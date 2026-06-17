# scGen Usage Guide

## Overview

scGen is a generative deep learning model based on Variational Autoencoders (VAE) for predicting single-cell perturbation responses. It can predict how cells would respond to perturbations across cell types, studies, and species.

## When to Use

- **Perturbation Prediction**: Predict cellular responses to unseen perturbations
- **Cross-Cell-Type Prediction**: Apply perturbation effects from one cell type to another
- **Batch Correction**: Remove technical batch effects while preserving biology
- **Virtual Perturbations**: Simulate perturbation effects computationally
- **Perturbation Vector Analysis**: Extract and compare perturbation signatures

## Prerequisites

### Required Packages

```bash
pip install scgen scvi-tools scanpy
```

### Data Format

Your AnnData object should contain:

```python
adata.X                    # Gene expression matrix (raw or normalized)
adata.obs['condition']     # Condition labels ('control', 'stimulated', etc.)
adata.obs['cell_type']     # Cell type labels (optional but recommended)
```

## Step-by-Step Guide

### Step 1: Setup and Data Loading

```python
import scanpy as sc
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join('scripts', 'python'))

from core_analysis import validate_perturbation_data, preprocess_for_scgen

# Load your data
adata = sc.read_h5ad("perturbation_data.h5ad")

# Validate data structure
validate_perturbation_data(
    adata,
    condition_key='condition',
    cell_type_key='cell_type'
)

# Check condition distribution
print(adata.obs['condition'].value_counts())
print(adata.obs['cell_type'].value_counts())
```

### Step 2: Data Preprocessing

```python
from core_analysis import preprocess_for_scgen

# Preprocess data for scGen
adata = preprocess_for_scgen(
    adata,
    n_top_genes=7000,  # Number of highly variable genes
    flavor='seurat'    # HVG selection method
)

# The data is now normalized and HVGs are selected
print(f"Selected {sum(adata.var.highly_variable)} highly variable genes")
```

### Step 3: Setup scGen AnnData

```python
from core_analysis import setup_scgen_anndata

# Register data with scGen
adata = setup_scgen_anndata(
    adata,
    batch_key='condition',     # Column with condition labels
    labels_key='cell_type'     # Column with cell type labels (optional)
)
```

### Step 4: Train scGen Model

```python
from core_analysis import train_scgen_model

# Train the VAE model
model = train_scgen_model(
    adata,
    n_hidden=800,              # Hidden layer size
    n_latent=100,              # Latent dimensionality
    n_layers=2,                # Number of hidden layers
    dropout_rate=0.2,          # Dropout rate
    max_epochs=100,            # Maximum training epochs
    batch_size=32,             # Batch size
    early_stopping=True,       # Enable early stopping
    early_stopping_patience=10, # Patience for early stopping
    random_state=42            # For reproducibility
)
```

### Step 5: Batch Correction

```python
from core_analysis import batch_correction

# Remove batch effects
corrected = batch_correction(model)

# Visualize corrected data
sc.pp.neighbors(corrected)
sc.tl.umap(corrected)
sc.pl.umap(corrected, color=['condition', 'cell_type'])
```

### Step 6: Predict Perturbation Effects

#### Option A: Predict Specific Cell Type

```python
from core_analysis import predict_perturbation

# Predict stimulated state for CD4T cells
predicted, delta = predict_perturbation(
    model,
    ctrl_key='control',
    stim_key='stimulated',
    celltype_to_predict='CD4T'
)

print(f"Predicted {predicted.n_obs} cells")
print(f"Perturbation vector shape: {delta.shape}")
```

#### Option B: Predict on Custom Data

```python
# Load test data (control cells only)
test_data = sc.read_h5ad("test_control.h5ad")

# Predict stimulated state
predicted, delta = predict_perturbation(
    model,
    ctrl_key='control',
    stim_key='stimulated',
    adata_to_predict=test_data
)
```

### Step 7: Evaluate Predictions

```python
from utils import evaluate_prediction_accuracy
from visualization import plot_regression_mean

# Get real stimulated cells for comparison
real_stim = adata[
    (adata.obs['condition'] == 'stimulated') &
    (adata.obs['cell_type'] == 'CD4T')
]

# Evaluate accuracy
metrics = evaluate_prediction_accuracy(
    predicted,
    real_stim,
    condition_key='condition'
)

print("Prediction accuracy:")
print(f"  R² (all genes): {metrics['r2_all']:.3f}")
print(f"  Pearson (all): {metrics['pearson_all']:.3f}")
print(f"  R² (top 100 genes): {metrics['r2_top_100']:.3f}")

# Merge for visualization
from utils import merge_predictions
merged = merge_predictions(
    adata[adata.obs['condition'] == 'control'],
    real_stim,
    predicted
)

# Plot regression
plot_regression_mean(
    model,
    merged,
    axis_keys={'x': 'control', 'y': 'predicted', 'y1': 'stimulated'},
    labels={'x': 'Control', 'y': 'Predicted'},
    path_to_save='regression_mean.png'
)
```

### Step 8: Cross-Cell-Type Prediction

```python
from utils import compare_perturbation_vectors

# Predict for multiple cell types
cell_types = ['CD4T', 'CD8T', 'B', 'NK']
deltas = {}

for ct in cell_types:
    pred, delta = predict_perturbation(
        model,
        ctrl_key='control',
        stim_key='stimulated',
        celltype_to_predict=ct
    )
    deltas[ct] = delta

# Compare perturbation vectors across cell types
for i, ct1 in enumerate(cell_types):
    for ct2 in cell_types[i+1:]:
        comparison = compare_perturbation_vectors(
            deltas[ct1], deltas[ct2],
            label1=ct1, label2=ct2
        )
        print(f"{ct1} vs {ct2}:")
        print(f"  Cosine similarity: {comparison['cosine_similarity']:.3f}")
        print(f"  Pearson r: {comparison['pearson_r']:.3f}")
```

### Step 9: Visualization

```python
from visualization import (
    plot_regression_variance,
    plot_binary_classifier,
    plot_perturbation_vector,
    plot_latent_space
)

# Variance regression plot
plot_regression_variance(
    model,
    merged,
    axis_keys={'x': 'control', 'y': 'predicted', 'y1': 'stimulated'},
    labels={'x': 'Control', 'y': 'Predicted'},
    path_to_save='regression_variance.png'
)

# Binary classifier plot
plot_binary_classifier(
    model,
    adata,
    delta,
    ctrl_key='control',
    stim_key='stimulated',
    path_to_save='binary_classifier.png'
)

# Perturbation vector components
plot_perturbation_vector(
    delta,
    top_n=20,
    path_to_save='perturbation_vector.png'
)

# Latent space visualization
plot_latent_space(
    model,
    adata,
    color_by='condition',
    path_to_save='latent_space.png'
)
```

### Step 10: Complete Pipeline

```python
from core_analysis import run_complete_scgen_pipeline

# Run everything in one call
results = run_complete_scgen_pipeline(
    adata,
    condition_key='condition',
    ctrl_key='control',
    stim_key='stimulated',
    cell_type_key='cell_type',
    celltype_to_predict='CD4T',
    n_top_genes=7000,
    max_epochs=100,
    run_batch_correction=True,
    random_state=42
)

# Extract results
model = results['model']
corrected = results['corrected']
predicted = results['predicted']
delta = results['delta']
```

## Advanced Usage

### Custom Training Configuration

```python
# Train with custom architecture
model = train_scgen_model(
    adata,
    n_hidden=1200,       # Larger hidden layers
    n_latent=150,        # Higher dimensional latent space
    n_layers=3,          # Deeper network
    dropout_rate=0.3,    # Higher dropout
    max_epochs=200,
    batch_size=64
)
```

### Leave-One-Cell-Type-Out Validation

```python
from utils import extractor

# Extract data for validation cell type
train, ctrl, stim, all_ct = extractor(
    adata,
    cell_type='CD4T',
    condition_key='condition',
    cell_type_key='cell_type',
    ctrl_key='control',
    stim_key='stimulated'
)

# Train on other cell types
model = train_scgen_model(train, max_epochs=100)

# Predict held-out cell type
predicted, delta = predict_perturbation(
    model,
    ctrl_key='control',
    stim_key='stimulated',
    adata_to_predict=ctrl
)

# Evaluate
metrics = evaluate_prediction_accuracy(predicted, stim)
```

### Balancing Cell Type Populations

```python
from utils import balancer

# Balance populations before training
ctrl_balanced = balancer(
    adata[adata.obs['condition'] == 'control'],
    cell_type_key='cell_type'
)

stim_balanced = balancer(
    adata[adata.obs['condition'] == 'stimulated'],
    cell_type_key='cell_type'
)

# Concatenate and train
balanced = sc.concat([ctrl_balanced, stim_balanced])
```

### Extracting and Reusing Perturbation Vectors

```python
from core_analysis import extract_perturbation_vector

# Extract cell type-specific vectors
delta_cd4 = extract_perturbation_vector(
    model, 'control', 'stimulated',
    specific_cell_type='CD4T'
)

delta_cd8 = extract_perturbation_vector(
    model, 'control', 'stimulated',
    specific_cell_type='CD8T'
)

# Save vectors
import numpy as np
np.save('delta_cd4t.npy', delta_cd4)
np.save('delta_cd8t.npy', delta_cd8)
```

## Common Workflows

### Workflow 1: Basic Perturbation Prediction

```python
# 1. Preprocess
adata = preprocess_for_scgen(adata, n_top_genes=7000)

# 2. Setup
adata = setup_scgen_anndata(adata, batch_key='condition', labels_key='cell_type')

# 3. Train
model = train_scgen_model(adata, max_epochs=100)

# 4. Predict
predicted, delta = predict_perturbation(model, 'control', 'stimulated')
```

### Workflow 2: Cross-Study Prediction

```python
# Train on study 1
train = sc.read_h5ad('study1.h5ad')
train = preprocess_for_scgen(train)
train = setup_scgen_anndata(train, batch_key='condition')
model = train_scgen_model(train, max_epochs=100)

# Predict on study 2
test = sc.read_h5ad('study2_control.h5ad')
predicted, delta = predict_perturbation(
    model, 'control', 'stimulated',
    adata_to_predict=test
)
```

### Workflow 3: Batch Correction Only

```python
# Setup and train
adata = setup_scgen_anndata(adata, batch_key='batch', labels_key='cell_type')
model = train_scgen_model(adata, max_epochs=100)

# Batch correction only
corrected = batch_correction(model)

# Use corrected data
corrected.write('corrected_data.h5ad')
```

## Troubleshooting

### Error: "Need at least 2 conditions"

```python
# Check condition labels
print(adata.obs['condition'].value_counts())

# Ensure both control and stimulated are present
assert 'control' in adata.obs['condition'].values
assert 'stimulated' in adata.obs['condition'].values
```

### Error: "CUDA out of memory"

```python
# Use smaller batch size
model = train_scgen_model(adata, batch_size=16, use_gpu=False)

# Or use CPU
model = train_scgen_model(adata, use_gpu=False)
```

### Poor Prediction Accuracy

```python
# Check cell counts
print(adata.obs['condition'].value_counts())

# Balance cell types if needed
from utils import balancer
adata = balancer(adata, cell_type_key='cell_type')

# Try more HVGs
adata = preprocess_for_scgen(adata, n_top_genes=10000)

# Train longer
model = train_scgen_model(adata, max_epochs=200, early_stopping_patience=20)
```

## AI Agent Test Cases

### Basic Prediction
> "Train scGen and predict stimulated CD4T cells from control"
```python
adata = preprocess_for_scgen(adata, n_top_genes=7000)
adata = setup_scgen_anndata(adata, batch_key='condition', labels_key='cell_type')
model = train_scgen_model(adata, max_epochs=100)
predicted, delta = predict_perturbation(model, 'control', 'stimulated', celltype_to_predict='CD4T')
```

### Batch Correction
> "Correct batch effects in my perturbation data using scGen"
```python
adata = setup_scgen_anndata(adata, batch_key='batch', labels_key='cell_type')
model = train_scgen_model(adata, max_epochs=100)
corrected = batch_correction(model)
```

### Cross-Cell-Type Prediction
> "Predict B cell response using T cell perturbation signature"
```python
model = train_scgen_model(adata, max_epochs=100)
predicted, delta = predict_perturbation(model, 'control', 'stimulated', celltype_to_predict='B')
```

### Evaluation
> "Evaluate my scGen predictions against real stimulated cells"
```python
metrics = evaluate_prediction_accuracy(predicted, real_stim, condition_key='condition')
plot_regression_mean(model, merged, axis_keys={'x': 'control', 'y': 'predicted'}, labels={'x': 'Control', 'y': 'Predicted'})
```

## References

1. Lotfollahi et al. (2019). scGen predicts single-cell perturbation responses. *Nature Methods*.
2. scGen documentation: https://scgen.readthedocs.io/
3. scGen GitHub: https://github.com/theislab/scgen
