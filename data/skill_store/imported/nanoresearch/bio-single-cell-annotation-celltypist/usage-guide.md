# CellTypist Usage Guide

## Overview

CellTypist is an automated cell type annotation tool using pre-trained logistic regression models. It is particularly effective for annotating human immune cells.

## When to Use

- **Human immune cell annotation**: Best-in-class for immune cells
- **PBMC/blood samples**: Optimized models available
- **Fast annotation needed**: Efficient logistic regression approach
- **High-quality reference available**: Pre-trained models from curated datasets

## Prerequisites

### Required Packages

```bash
pip install celltypist scanpy anndata
```

### Data Format

Input requirements:
- **Format**: AnnData (h5ad) or raw count matrix
- **Normalization**: Log-normalized data expected
- **Genes**: Gene symbols (not ENSEMBL IDs)
- **Features**: Include non-expressed genes if possible

## Step-by-Step Guide

### Step 1: Prepare Data

```python
import scanpy as sc
import numpy as np

# Load your data
adata = sc.read_h5ad("your_data.h5ad")

# Check if normalization is needed (same heuristic as validate_celltypist_input)
sample_size = min(1000, adata.n_obs)
x_sample = adata.X[:sample_size]
if hasattr(x_sample, 'toarray'):
    x_sample = x_sample.toarray()
max_val = float(np.max(x_sample))
if max_val > 50 and max_val.is_integer():
    print("Data appears to be raw counts - normalizing...")
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
else:
    print("Data appears to be log-normalized")
```

**Check gene symbols:**
```python
# CellTypist expects gene symbols like 'CD3D', 'CD19'
# Not ENSEMBL IDs like 'ENSG00000167286'
print(adata.var_names[:10])
```

### Step 2: Select Model

```python
import sys
sys.path.append('scripts/python')
from utils import recommend_model, get_model_catalog

# View available models
catalog = get_model_catalog()

# Get recommendation
recommended = recommend_model(
    tissue='immune',      # 'immune', 'intestine', 'lung'
    species='human',      # 'human' or 'mouse'
    resolution='low'      # 'low' (broad) or 'high' (fine-grained)
)
print(f"Recommended: {recommended}")
```

**Common models:**

| Model | Best For |
|-------|----------|
| Immune_All_Low | General immune, 28 broad categories |
| Immune_All_High | Detailed immune, 98 subtypes |
| Cells_Intestinal_Training | Intestinal epithelial |
| Cells_Lung_Airway_Training | Lung airway epithelial |
| NLP_Mouse_Immune | Mouse immune |

### Step 3: Download Model

```python
from core_analysis import download_celltypist_model

# Download (cached after first download)
download_celltypist_model('Immune_All_Low.pkl')
```

### Step 4: Run Basic Annotation

```python
from core_analysis import annotate_cells, add_predictions_to_adata

# Run annotation
predictions = annotate_cells(
    adata,
    model='Immune_All_Low.pkl',
    mode='best match',        # Single label per cell
    majority_voting=False     # No cluster refinement
)

# Add to AnnData
adata = add_predictions_to_adata(predictions)

# View results
print(adata.obs['celltypist_label'].value_counts())
```

### Step 5: Run with Majority Voting (Recommended)

```python
# First, cluster the data
sc.pp.neighbors(adata)
sc.tl.leiden(adata, resolution=0.5)

# Run annotation with majority voting
predictions = annotate_cells(
    adata,
    model='Immune_All_Low.pkl',
    majority_voting=True,
    over_clustering='leiden'  # Use Leiden clusters
)

# Add to AnnData
adata = add_predictions_to_adata(predictions)
```

**Why majority voting:**
- More robust predictions
- Reduces individual cell noise
- Uses cluster-level consensus

### Step 6: Filter by Confidence

```python
from core_analysis import filter_by_confidence

# Filter low-confidence predictions
adata = filter_by_confidence(
    adata,
    threshold=0.5,              # Confidence threshold
    unassigned_label='Unknown'  # Label for uncertain cells
)

# Compare before and after
print("Before filtering:")
print(adata.obs['celltypist_label'].value_counts())

print("\nAfter filtering:")
print(adata.obs['celltypist_label_filtered'].value_counts())
```

**Confidence thresholds:**
- `0.3`: Permissive (keep more labels)
- `0.5`: Balanced (recommended)
- `0.7`: Stringent (high confidence only)

### Step 7: Complete Pipeline (Shortcut)

```python
from core_analysis import run_celltypist_annotation

# Run complete workflow
adata = run_celltypist_annotation(
    adata,
    model='Immune_All_Low.pkl',
    majority_voting=True,
    over_clustering='leiden'
)
```

### Step 8: Visualize Results

```python
from visualization import (
    plot_confidence_distribution,
    plot_celltype_proportions,
    plot_annotation_summary
)

# Confidence distribution
plot_confidence_distribution(adata)

# Proportions by sample/group
plot_celltype_proportions(adata, groupby='sample')

# Comprehensive summary
plot_annotation_summary(adata, output_dir='./celltypist_plots')
```

### Step 9: Export Results

```python
from utils import summarize_annotations, export_annotations

# Summary statistics
summary = summarize_annotations(adata)
print(summary)

# Export to CSV
export_annotations(adata, 'annotations.csv')

# Save annotated AnnData
adata.write('annotated_data.h5ad')
```

## Advanced Usage

### Multi-Label Classification

```python
# Allow cells to have multiple labels
predictions = annotate_cells(
    adata,
    model='Immune_All_Low.pkl',
    mode='prob match',        # Multi-label mode
    p_thres=0.5               # Probability threshold
)
```

### Compare Multiple Models

```python
from core_analysis import compare_models

models = ['Immune_All_Low.pkl', 'Immune_All_High.pkl']
results_df = compare_models(adata, models, majority_voting=True)

print(results_df)
```

### Custom Over-Clustering

```python
# Use your own cluster assignments
predictions = annotate_cells(
    adata,
    model='Immune_All_Low.pkl',
    majority_voting=True,
    over_clustering='my_clusters'  # Column in adata.obs
)
```

### Train Custom Model

```python
from core_analysis import train_celltypist_model

# Train on your labeled data
model = train_celltypist_model(
    adata=training_data,
    labels='cell_type_column',
    model_file='my_model.pkl',
    use_SGD=True,
    mini_batch=True
)

# Use for prediction
predictions = annotate_cells(adata, model=model)
```

## Best Practices

1. **Always use log-normalized data**
   ```python
   sc.pp.normalize_total(adata, target_sum=1e4)
   sc.pp.log1p(adata)
   ```

2. **Use majority voting when possible**
   - More robust predictions
   - Requires clustering (Leiden recommended)

3. **Filter low-confidence predictions**
   - Threshold of 0.5 is a good balance
   - Mark uncertain cells as "Unknown"

4. **Match tissue type to model**
   - Don't use immune models for non-immune tissues
   - Use `recommend_model()` for guidance

5. **Validate with marker genes**
   ```python
   # Check known markers
   sc.pl.dotplot(adata, ['CD3D', 'CD19', 'CD14'], groupby='celltypist_label')
   ```

## Troubleshooting

### Low Confidence Scores

```python
# Check gene overlap
from utils import check_gene_overlap

stats = check_gene_overlap(adata, 'Immune_All_Low.pkl')
print(f"Gene overlap: {stats['overlap_fraction']*100:.1f}%")

# If overlap is low, check gene naming
print(adata.var_names[:10])
```

### Model Download Issues

```python
# Manual download if automatic fails
import celltypist
celltypist.models.download_models(model='Immune_All_Low.pkl', force=True)
```

### Memory Issues with Large Datasets

```python
# Process in chunks for very large datasets
# Or use GPU acceleration (requires rapids-singlecell)
predictions = annotate_cells(
    adata,
    model='Immune_All_Low.pkl',
    use_GPU=True  # Requires rapids-singlecell
)
```

## AI Agent Test Cases

### Basic Annotation
> "Run CellTypist annotation on my data"

```python
from core_analysis import run_celltypist_annotation
adata = run_celltypist_annotation(adata, model='Immune_All_Low.pkl')
```

### With Majority Voting
> "Annotate using majority voting with Leiden clusters"

```python
predictions = annotate_cells(
    adata, model='Immune_All_Low.pkl',
    majority_voting=True, over_clustering='leiden'
)
```

### Filter by Confidence
> "Filter CellTypist predictions with confidence > 0.5"

```python
adata = filter_by_confidence(adata, threshold=0.5)
```

### Recommend Model
> "What CellTypist model should I use for intestine data?"

```python
from utils import recommend_model
model = recommend_model(tissue='intestine', species='human')
```

## References

1. Domínguez Conde et al. (2022). Cross-tissue immune cell analysis reveals tissue-specific features in humans. *Science*.
2. https://www.celltypist.org/
