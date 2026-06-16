---
name: bio-single-cell-perturbation-scgen
description: scGen is a generative deep learning model for predicting single-cell perturbation responses across cell types, studies, and species. Use for perturbation prediction, batch correction, and virtual perturbations.
tool_type: python
primary_tool: scgen
supported_tools: [scanpy, scvi-tools, torch]
languages: [python]
keywords: ["perturbation", "scgen", "generative-model", "VAE", "prediction", "batch-correction", "deep-learning"]
---

## Version Compatibility

This skill provides two implementations with different dependency requirements:

### Option A: pertpy.tl.Scgen (RECOMMENDED)
- **Python**: >=3.9
- **pertpy**: >=0.9.0
- **scvi-tools**: >=1.0.0
- **scanpy**: >=1.9

### Option B: legacy scgen.SCGEN (PyTorch standalone)
- **Python**: >=3.9
- **scgen**: >=2.1.0
- **scvi-tools**: <0.20.0 (INCOMPATIBLE with >=1.0.0)
- **torch**: >=1.10
- **scanpy**: >=1.9

> ⚠️ **Important**: The standalone `scgen` PyTorch package and `scvi-tools>=1.0.0` are **mutually incompatible**. Choose ONE path and install the corresponding dependencies from `requirements.txt`.

## Installation

```bash
# Option A (recommended): pertpy Scgen
pip install pertpy

# Option B (legacy): standalone scgen
pip install "scgen>=2.1.0" "scvi-tools<0.20.0" "torch>=1.10.0"
```

## Core Analysis Workflow

scGen is a VAE-based generative model that learns to predict perturbation effects in single-cell data. Follow this step-by-step workflow for perturbation prediction and batch correction.

### Step 1: Data Validation and Preparation

Validate perturbation data before analysis.

```python
from core_analysis import validate_perturbation_data, preprocess_for_scgen

# Validate data structure
validate_perturbation_data(
    adata,
    condition_key='condition',
    cell_type_key='cell_type'
)

# Preprocess: normalize, select HVGs
adata = preprocess_for_scgen(
    adata,
    n_top_genes=7000,
    flavor='seurat'
)
```

**Key Points:**
- Requires at least 2 conditions (e.g., 'control', 'stimulated')
- Recommended: >1000 cells per condition
- scGen works best with normalized, log-transformed data

### Step 2: Setup scGen AnnData

Register AnnData with scGen's data manager.

```python
from core_analysis import setup_scgen_anndata

adata = setup_scgen_anndata(
    adata,
    batch_key='condition',
    labels_key='cell_type'
)
```

**Key Points:**
- `batch_key`: Column with condition labels (e.g., 'control', 'stimulated')
- `labels_key`: Column with cell type labels (optional but recommended)

### Step 3: Train scGen Model

Train the VAE model on your data.

```python
from core_analysis import train_scgen_model

model = train_scgen_model(
    adata,
    n_hidden=800,
    n_latent=100,
    n_layers=2,
    dropout_rate=0.2,
    max_epochs=100,
    batch_size=32,
    early_stopping=True,
    early_stopping_patience=10
)
```

**Key Parameters:**
- `n_hidden`: Number of nodes per hidden layer (default: 800)
- `n_latent`: Latent space dimensionality (default: 100)
- `n_layers`: Number of hidden layers (default: 2)
- `max_epochs`: Training epochs (default: 100)
- `early_stopping`: Stop when validation loss plateaus

### Step 4: Batch Correction (Optional)

Remove technical batch effects while preserving biological variation.

```python
from core_analysis import batch_correction

corrected = batch_correction(model)

# Use corrected data for downstream analysis
sc.pp.neighbors(corrected)
sc.tl.umap(corrected)
```

**Key Points:**
- Corrects for batch effects across conditions
- Preserves cell type-specific differences
- Results in `corrected.X` and latent representations

### Step 5: Predict Perturbation Effects

Predict how cells would respond to perturbations.

```python
from core_analysis import predict_perturbation

# Predict specific cell type
predicted, delta = predict_perturbation(
    model,
    ctrl_key='control',
    stim_key='stimulated',
    celltype_to_predict='CD4T'
)

# Or predict on specific data
predicted, delta = predict_perturbation(
    model,
    ctrl_key='control',
    stim_key='stimulated',
    adata_to_predict=test_data
)
```

**Key Points:**
- `delta`: Perturbation vector in latent space
- Can predict on unseen cell types (cross-cell-type prediction)
- Can predict on unseen conditions

### Step 6: Evaluate Predictions

Assess prediction quality using evaluation metrics and visualizations.

```python
from utils import evaluate_prediction_accuracy
from visualization import plot_regression_mean

# Quantitative evaluation
metrics = evaluate_prediction_accuracy(
    predicted,
    real_stimulated,
    condition_key='condition'
)
print(f"R² (all genes): {metrics['r2_all']:.3f}")

# Qualitative evaluation
plot_regression_mean(
    model,
    merged_adata,
    axis_keys={'x': 'control', 'y': 'predicted', 'y1': 'stimulated'},
    labels={'x': 'Control', 'y': 'Predicted'}
)
```

**Evaluation Metrics:**
- R² (coefficient of determination)
- Pearson correlation
- Spearman correlation
- Mean squared error

### Step 7: Cross-Cell-Type Analysis

Predict perturbation effects across different cell types.

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

# Compare perturbation vectors
comparison = compare_perturbation_vectors(
    deltas['CD4T'],
    deltas['CD8T'],
    label1='CD4T',
    label2='CD8T'
)
print(f"Cosine similarity: {comparison['cosine_similarity']:.3f}")
```

### Step 8: Complete Pipeline

Run the entire workflow with a single function.

```python
from core_analysis import run_complete_scgen_pipeline

results = run_complete_scgen_pipeline(
    adata,
    condition_key='condition',
    ctrl_key='control',
    stim_key='stimulated',
    cell_type_key='cell_type',
    n_top_genes=7000,
    max_epochs=100,
    run_batch_correction=True
)

model = results['model']
corrected = results['corrected']
predicted = results['predicted']
delta = results['delta']
```

## Input Requirements

### Required Data Format

```python
# AnnData object with:
adata.X  # Normalized, log-transformed gene expression
adata.obs['condition']  # Condition labels ('control', 'stimulated', etc.)
```

### Optional Columns

```python
adata.obs['cell_type']  # Cell type labels for stratified analysis
```

### Data Recommendations

| Dataset Characteristic | Recommendation |
|------------------------|----------------|
| Cells per condition | >1000 (minimum: 100) |
| Highly variable genes | 5000-7000 |
| Normalization | Total count + log1p |
| Batch effects | Can be corrected with scGen |

## Output Specifications

### Core Outputs

| Output | Type | Description |
|--------|------|-------------|
| `model` | SCGEN | Trained scGen model |
| `corrected` | AnnData | Batch-corrected expression |
| `predicted` | AnnData | Predicted stimulated cells |
| `delta` | np.ndarray | Perturbation vector (n_latent,) |
| `latent` | np.ndarray | Latent representations (n_cells x n_latent) |

### Output Locations

- Corrected expression: `corrected.X`
- Latent space (pre-correction): `corrected.obsm['latent']`
- Latent space (post-correction): `corrected.obsm['corrected_latent']`

## Key Parameters

### Model Architecture

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_hidden` | int | 800 | Nodes per hidden layer |
| `n_latent` | int | 100 | Latent dimensionality |
| `n_layers` | int | 2 | Number of hidden layers |
| `dropout_rate` | float | 0.2 | Dropout rate |

### Training

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_epochs` | int | 100 | Maximum training epochs |
| `batch_size` | int | 32 | Training batch size |
| `early_stopping` | bool | True | Enable early stopping |
| `early_stopping_patience` | int | 10 | Patience for early stopping |

### Prediction

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ctrl_key` | str | Required | Control condition label |
| `stim_key` | str | Required | Stimulated condition label |
| `celltype_to_predict` | str | None | Specific cell type to predict |

## Expected Runtime

| Dataset Size | Preprocessing | Training (100 epochs) | Prediction |
|--------------|---------------|----------------------|------------|
| 1K cells | <5s | 1-2 min | <1s |
| 10K cells | <10s | 5-10 min | <5s |
| 50K cells | <30s | 20-40 min | <10s |
| 100K+ cells | <60s | 1-2 hours | <30s |

*Runtime estimates on GPU (NVIDIA RTX 3090). CPU training is 5-10x slower.*

## Error Handling

### Common Errors and Solutions

**Missing condition column**
```
ValueError: Column 'condition' not found in adata.obs
```
→ Verify column name exists in `adata.obs.columns`

**Single condition detected**
```
ValueError: Need at least 2 conditions, found 1
```
→ Ensure data contains both control and stimulated cells

**Insufficient cells**
```
UserWarning: Conditions with fewer than 100 cells...
```
→ scGen requires minimum 100 cells per condition; recommended >1000

**GPU not available**
```
RuntimeError: CUDA out of memory
```
→ Reduce batch size or use CPU training (`use_gpu=False`)

## Visualization Functions

### Regression Plots

```python
from visualization import plot_regression_mean, plot_regression_variance

# Mean expression comparison
plot_regression_mean(model, adata, axis_keys, labels)

# Variance comparison
plot_regression_variance(model, adata, axis_keys, labels)
```

### Latent Space Analysis

```python
from visualization import plot_latent_space, plot_perturbation_vector

# Visualize latent space
plot_latent_space(model, adata, color_by='condition')

# Plot perturbation vector components
plot_perturbation_vector(delta, top_n=20)
```

### Classification

```python
from visualization import plot_binary_classifier

# Visualize perturbation classifier
plot_binary_classifier(model, adata, delta, ctrl_key, stim_key)
```

## Utility Functions

### Data Manipulation

```python
from utils import balancer, extractor, subsample_data

# Balance cell type populations
balanced = balancer(adata, cell_type_key='cell_type')

# Extract specific cell type data
extracted = extractor(adata, 'CD4T', 'condition', 'cell_type', 'ctrl', 'stim')

# Subsample data
subsampled = subsample_data(adata, target_cells=1000)
```

### Evaluation

```python
from utils import evaluate_prediction_accuracy, compare_perturbation_vectors

# Evaluate predictions
metrics = evaluate_prediction_accuracy(predicted, real, condition_key)

# Compare perturbation vectors
comparison = compare_perturbation_vectors(delta1, delta2)
```

## Related Skills

- [bio-single-cell-perturbation-pertpy](../bio-single-cell-perturbation-pertpy/SKILL.md) - General perturbation analysis toolkit
- [bio-single-cell-perturbation-mixscape](../bio-single-cell-perturbation-mixscape/SKILL.md) - CRISPR screen analysis
- [bio-single-cell-integration-scvi](../bio-single-cell-integration-scvi/SKILL.md) - Variational autoencoder integration

## References

1. Lotfollahi et al. (2019). scGen predicts single-cell perturbation responses. *Nature Methods*.
2. scGen documentation: https://scgen.readthedocs.io/
3. scGen GitHub: https://github.com/theislab/scgen
