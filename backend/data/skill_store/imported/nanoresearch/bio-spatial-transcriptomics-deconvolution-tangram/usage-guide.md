# Tangram Usage Guide

## Overview

Tangram is a deep learning method that maps single-cell RNA-seq data onto spatial transcriptomics by learning a probabilistic alignment between the two modalities. It uses PyTorch-based gradient descent optimization with cosine similarity loss to find the optimal mapping matrix.

## When to Use

- **Fast deconvolution needed**: Clusters mode completes in minutes
- **Gene imputation**: Project unmeasured genes from scRNA-seq to spatial
- **High-resolution mapping**: Cells mode maps individual cells
- **Cross-validation**: Built-in CV for quality assessment
- **Cell counting**: Constrained mode with segmentation data

## Installation

```bash
pip install tangram-sc torch scanpy squidpy matplotlib seaborn
```

## Quick Start

```python
from scripts.python.core_analysis import (
    prepare_data, map_cells_to_space, project_cell_annotations
)

# Load data
adata_sc = sc.read_h5ad("single_cell.h5ad")
adata_sp = sc.read_h5ad("spatial.h5ad")

# 1. Prepare data
adata_sc_prep, adata_sp_prep = prepare_data(adata_sc, adata_sp)

# 2. Map cells
adata_map = map_cells_to_space(
    adata_sc_prep, adata_sp_prep,
    mode='clusters',
    cluster_label='cell_type',
    num_epochs=1000,
    device='cuda:0',
)

# 3. Project annotations
project_cell_annotations(adata_map, adata_sp_prep, annotation='cell_type')

# Results are in adata_sp_prep.obsm['tangram_ct_pred']
```

---

## Step-by-Step Workflows

### 1. Basic Deconvolution (Clusters Mode)

Best for: Initial exploration, large datasets

```python
from scripts.python.core_analysis import *

# Prepare data
adata_sc_prep, adata_sp_prep = prepare_data(
    adata_sc, adata_sp,
    genes=None,  # Use all shared genes
)

# Map using cluster averages (fast)
adata_map = map_cells_to_space(
    adata_sc_prep,
    adata_sp_prep,
    mode='clusters',
    cluster_label='cell_type',
    num_epochs=1000,
    device='cuda:0',
    density_prior='rna_count_based',
)

# Check training scores
df_scores = adata_map.uns['train_genes_df']
print(f"Mean training score: {df_scores['train_score'].mean():.3f}")

# Project cell types
project_cell_annotations(adata_map, adata_sp_prep, 'cell_type')

# Extract proportions
df_props = extract_deconvolution_results(adata_sp_prep)
```

### 2. High-Resolution Mapping (Cells Mode)

Best for: Detailed spatial mapping when runtime is acceptable

```python
# Map individual cells (slower but higher resolution)
adata_map = map_cells_to_space(
    adata_sc_prep,
    adata_sp_prep,
    mode='cells',
    num_epochs=1000,
    device='cuda:0',
    # Add entropy regularizer for sharper mappings
    lambda_r=0.5,
)

# Project annotations
project_cell_annotations(adata_map, adata_sp_prep, 'cell_type')
```

### 3. Gene Imputation

Project gene expression from scRNA-seq to spatial data:

```python
# Project genes using the mapping
adata_ge = project_genes(
    adata_map=adata_map,
    adata_sc=adata_sc_prep,
    cluster_label='cell_type' if adata_map.n_obs < adata_sc_prep.n_obs else None,
    scale=True,
)

# Compare with measured expression
df_compare = compare_spatial_geneexp(
    adata_ge=adata_ge,
    adata_sp=adata_sp_prep,
    adata_sc=adata_sc_prep,
)

print(f"Mean gene score: {df_compare['score'].mean():.3f}")
```

### 4. Cross-Validation for Quality Assessment

Assess prediction accuracy using held-out genes:

```python
# Run leave-one-out cross-validation
cv_dict, adata_ge_cv, df_test = cross_val(
    adata_sc=adata_sc_prep,
    adata_sp=adata_sp_prep,
    mode='clusters',
    cluster_label='cell_type',
    num_epochs=500,  # Fewer epochs for CV
    device='cuda:0',
    cv_mode='loo',  # 'loo' or '10fold'
    return_gene_pred=True,
)

print(f"CV test score: {cv_dict['avg_test_score']:.3f}")
print(f"CV train score: {cv_dict['avg_train_score']:.3f}")

# Get evaluation metrics
metrics, auc_coords = eval_metric(df_test)
print(f"AUC score: {metrics['auc_score']:.3f}")
```

### 5. Constrained Mapping (Cell Counting)

Use when cell counts per spot are known (requires segmentation):

```python
import squidpy as sq

# Calculate segmentation features
sq.im.calculate_image_features(
    adata_sp,
    img,
    features=['segmentation'],
    key_added='image_features',
)

# Create segmentation dataframe
create_segment_cell_df(adata_sp)

# Map with constraints
adata_map = map_cells_to_space(
    adata_sc_prep,
    adata_sp_prep,
    mode='constrained',
    target_count=5,  # Expected cells per spot
    lambda_count=1.0,
    lambda_f_reg=1.0,
)

# Count cells per spot
count_cell_annotations(
    adata_map, adata_sc_prep, adata_sp,
    annotation='cell_type'
)

# Get individual cell assignments
adata_cells = deconvolve_cell_annotations(adata_sp)
```

---

## Modes Comparison

| Mode | Speed | Resolution | Memory | Best For |
|------|-------|------------|--------|----------|
| `clusters` | Fast (~minutes) | Cell type averages | Low | Large datasets, exploration |
| `cells` | Slow (~hours) | Individual cells | High | High-resolution mapping |
| `constrained` | Medium | Cell counts | Medium | When counts known |

---

## Parameters

### Data Preparation

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `genes` | list | None | Marker genes to use. If None, uses all shared genes. |
| `gene_to_lowercase` | bool | True | Convert gene names to lowercase for matching |

### Mapping

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | str | 'cells' | 'clusters', 'cells', or 'constrained' |
| `cluster_label` | str | None | Column in adata_sc.obs for cluster aggregation |
| `num_epochs` | int | 1000 | Training iterations |
| `device` | str | 'cpu' | 'cpu', 'cuda:0', etc. |
| `density_prior` | str/array | 'rna_count_based' | 'rna_count_based', 'uniform', or custom array |
| `learning_rate` | float | 0.1 | Optimizer learning rate |
| `random_state` | int | None | Random seed for reproducibility |

### Loss Function Weights

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lambda_g1` | float | 1.0 | Gene-voxel cosine similarity (main loss) |
| `lambda_r` | float | 0.0 | Entropy regularizer (higher = more peaked) |
| `lambda_d` | float | 0 | Density regularizer (auto-set if density_prior) |
| `lambda_g2` | float | 0 | Voxel-gene similarity |


### Constrained Mode

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_count` | int | None | Expected cells per spot |
| `lambda_count` | float | 1.0 | Count regularizer |
| `lambda_f_reg` | float | 1.0 | Filter regularizer (promotes Boolean values) |

---

## Best Practices

### 1. Gene Selection

```python
# Use marker genes for better alignment
marker_genes = ['EPCAM', 'PTPRC', 'VWF', 'COL1A1']  # Epithelial, immune, endothelial, fibroblast

adata_sc_prep, adata_sp_prep = prepare_data(
    adata_sc, adata_sp,
    genes=marker_genes,
)
```

### 2. Monitor Training

```python
# Check training scores
df_scores = adata_map.uns['train_genes_df']
print(f"Mean: {df_scores['train_score'].mean():.3f}")
print(f"Median: {df_scores['train_score'].median():.3f}")

# Low scores may indicate poor alignment
if df_scores['train_score'].mean() < 0.5:
    print("Warning: Low training scores. Check gene overlap.")
```

### 3. GPU Acceleration

```python
# Use GPU for large datasets
adata_map = map_cells_to_space(
    adata_sc_prep, adata_sp_prep,
    device='cuda:0',  # or 'cuda:1', etc.
)
```

### 4. Cross-Validation

Always run CV to assess prediction quality:

```python
cv_dict = cross_val(adata_sc_prep, adata_sp_prep, mode='clusters', cluster_label='cell_type')

if cv_dict['avg_test_score'] < 0.5:
    print("Warning: Low CV score. Consider using more/different marker genes.")
```

### 5. Sparsity Considerations

```python
# Check gene sparsity
df_compare = compare_spatial_geneexp(adata_ge, adata_sp, adata_sc)

# Genes with very different sparsity between modalities may be poorly predicted
high_sparsity_diff = df_compare[df_compare['sparsity_diff'].abs() > 0.5]
print(f"Genes with high sparsity diff: {len(high_sparsity_diff)}")
```

---

## Troubleshooting

### Low Training Scores

**Symptom:** Mean training score < 0.5

**Solutions:**
- Use marker genes instead of all genes
- Check gene name matching (case sensitivity)
- Ensure proper normalization
- Increase `num_epochs`

### Out of Memory

**Symptom:** CUDA out of memory error

**Solutions:**
- Use `clusters` mode instead of `cells` mode
- Use CPU: `device='cpu'`
- Reduce batch size or number of cells
- Use fewer genes

### Poor Cross-Validation Performance

**Symptom:** CV test score << training score

**Solutions:**
- Overfitting: Reduce `num_epochs` or add regularization (`lambda_r`)
- Gene mismatch: Check `training_genes` overlap
- Use different marker genes

### Constrained Mode Fails

**Symptom:** Error about missing segmentation

**Solutions:**
- Run `sq.im.calculate_image_features()` first
- Run `create_segment_cell_df()` before counting

---

## Performance Tips

1. **Start with clusters mode** for initial exploration
2. **Use marker genes** (~50-200) rather than all genes
3. **Enable GPU** for datasets > 10k cells
4. **Cache preprocessed data** to avoid repeated preparation
5. **Use fewer epochs** for CV (500 vs 1000)

---

## Visualization

```python
from scripts.python.visualization import *

# Training diagnostics
fig = plot_training_scores(adata_map)

# Cell type maps
fig = plot_cell_type_map(adata_sp, 'Neuron', cmap='Reds')

# Multi-cell comparison
fig = plot_annotation_comparison(adata_sp, n_cols=4)

# Gene comparison
plot_genes_sc(['Gene1', 'Gene2'], adata_sp, adata_ge)

# AUC evaluation
fig = plot_auc(df_compare)
```

---

## AI Agent Test Cases

### Basic Usage
> "Run Tangram to map scRNA-seq cells to my spatial data"
> "Use Tangram cluster mode for deconvolution"

### Gene Projection
> "Project unmeasured genes from scRNA-seq to spatial using Tangram"
> "Impute gene expression in spatial data with Tangram"

### Quality Assessment
> "Run cross-validation on my Tangram mapping"
> "Check the quality of Tangram predictions"

### Cell Counting
> "Count cells per spot using Tangram constrained mode"
> "Deconvolve cell types with segmentation"

---

## References

1. Biancalani, T. et al. (2021). Deep learning and alignment of spatially-resolved whole transcriptome profiles of cells in the mouse brain with Tangram. *Nature Methods*, 18(11), 1352-1362.

2. Tangram GitHub: https://github.com/broadinstitute/Tangram

3. Tangram Documentation: https://tangram-sc.readthedocs.io/
