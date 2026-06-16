# spCLUE Usage Guide

## Overview

spCLUE is a deep learning method for spatial domain identification in spatial transcriptomics data. It uses cross-view contrastive learning to integrate spatial coordinates and gene expression, supporting both single-slice analysis and multi-slice integration.

## When to Use

- Identify spatial domains in a single tissue section
- Integrate multiple tissue slices with batch correction
- Combine spatial and expression information for clustering

## When NOT to Use

- Cell type annotation (use marker-based methods instead)
- Data without spatial coordinates (standard scRNA-seq clustering is more appropriate)
- Very small datasets (< 100 spots)

## Requirements

- Python >= 3.8
- PyTorch >= 1.8.0 (CUDA recommended)
- scanpy >= 1.9.0
- squidpy >= 1.3.0
- R >= 4.0.0 with mclust package
- rpy2 >= 3.4.0

## Quick Start

### Single Slice

```python
from scripts import spCLUE, preprocess, prepare_graph, clustering, fix_seed, refine_label
from sklearn.decomposition import PCA
import torch

fix_seed(42)

# Load and preprocess
adata = sc.read_h5ad("slice.h5ad")
adata = preprocess(adata, hvgNumber=2000)

# PCA
input_data = PCA(n_components=200, random_state=0).fit_transform(adata.X)

# Build graphs
graph_dict = {
    "spatial": prepare_graph(adata, key="spatial", n_neighbors=12),
    "expr": prepare_graph(adata, key="expr", n_neighbors=12, n_comps=50)
}

# Train
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
model = spCLUE(
    input_data=input_data,
    graph_dict=graph_dict,
    n_clusters=12,
    epochs=500,
    device=device,
    random_seed=42
)
pred_labels, embeddings = model.train()

# Cluster
adata.obsm['spCLUE'] = embeddings
adata.obs['pred'] = pred_labels
adata = clustering(adata, n_clusters=12, key='spCLUE', cluster_methods='mclust')

# Refine
refine_label(adata, radius=30, key='mclust', suffix='refined')

# Visualize
sq.pl.spatial_scatter(adata, color=['mclust', 'mclust_refined'])
```

### Multi-Slice Integration

```python
import anndata as ad

# Concatenate slices
adata_list = [slice1, slice2, slice3]
adata_combined = ad.concat(adata_list, label='batch', keys=['s1', 's2', 's3'])

# Preprocess combined data
adata_combined = preprocess(adata_combined, hvgNumber=2000)
input_data = PCA(n_components=200, random_state=0).fit_transform(adata_combined.X)

# Build graphs
graph_dict = {
    "spatial": prepare_graph(adata_combined, key="spatial", n_neighbors=12),
    "expr": prepare_graph(adata_combined, key="expr", n_neighbors=12, n_comps=50)
}

# Batch labels
batch_list = adata_combined.obs['batch'].astype('category').cat.codes.values

# Train with batch correction
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
model = spCLUE(
    input_data=input_data,
    graph_dict=graph_dict,
    n_clusters=12,
    batch_list=batch_list,
    epochs=500,
    device=device,
    batch_train=adata_combined.n_obs > 20000,
    random_seed=42
)

# trainBatch returns (status, embeddings) -- ignore status
_, embeddings = model.trainBatch()

# Cluster
adata_combined.obsm['spCLUE'] = embeddings
adata_combined = clustering(adata_combined, n_clusters=12, key='spCLUE', cluster_methods='mclust')

# Batch-aware refinement
batch_refine_label(adata_combined, radius=30, key='mclust', suffix='refined', batch_key='batch')

# Visualize
sq.pl.spatial_scatter(adata_combined, color=['mclust_refined', 'batch'])
```

## Step-by-Step

### 1. Data Preparation

```python
# Load spatial data
adata = sc.read_h5ad("your_data.h5ad")
# OR for 10X Visium:
# adata = sc.read_visium("path/to/visium/data")

# Ensure spatial coordinates exist
print(adata.obsm['spatial'].shape)  # Should be (n_spots, 2)

# Ensure count layer exists (required for HVG selection)
if 'count' not in adata.layers:
    adata.layers['count'] = adata.X.copy()
```

### 2. Preprocessing

```python
adata = preprocess(adata, hvgNumber=2000)
```

Performs: gene/cell filtering, HVG selection (seurat_v3 flavor on layer='count'), scaling.

### 3. PCA

```python
from sklearn.decomposition import PCA
pca = PCA(n_components=200, random_state=0)
input_data = pca.fit_transform(adata.X)
```

### 4. Graph Construction

```python
graph_dict = {
    "spatial": prepare_graph(adata, key="spatial", n_neighbors=12),
    "expr": prepare_graph(adata, key="expr", n_neighbors=12, n_comps=50)
}
```

- **Spatial graph**: KNN based on physical coordinates
- **Expression graph**: KNN based on PCA-reduced expression correlations

### 5. Model Training

Single slice:
```python
model = spCLUE(input_data, graph_dict, n_clusters=12, epochs=500, device=device)
pred_labels, embeddings = model.train()
```

Multi-slice:
```python
model = spCLUE(input_data, graph_dict, n_clusters=12, batch_list=batch_list, epochs=500, device=device)
_, embeddings = model.trainBatch()  # Ignore first return value
```

### 6. Clustering

```python
adata = clustering(adata, n_clusters=12, key='spCLUE', cluster_methods='mclust')
```

Methods:
- `mclust` (default): Requires R + mclust
- `kmeans`: Fast, no R dependency
- `leiden`: Graph-based
- `pred`: Use model predictions directly

### 7. Spatial Refinement

```python
# Single slice
refine_label(adata, radius=30, key='mclust', suffix='refined')

# Multi-slice
batch_refine_label(adata, radius=30, key='mclust', suffix='refined', batch_key='batch')
```

### 8. Visualization

```python
# Spatial plots
sq.pl.spatial_scatter(adata, color='mclust', size=1.5)
sq.pl.spatial_scatter(adata, color='mclust_refined', size=1.5)

# UMAP
sc.pp.neighbors(adata, use_rep='spCLUE')
sc.tl.umap(adata)
sc.pl.umap(adata, color='mclust')
```

## Parameters

### Model Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_clusters` | 12 | Number of spatial domains |
| `epochs` | 500 | Training epochs |
| `dim_input` | 200 | Input dimension (match PCA components) |
| `dim_hidden` | 64 | Hidden layer dimension |
| `dim_embed` | 24 | Output embedding dimension |
| `graph_corr` | 0.4 | Graph corruption probability |
| `dropout` | 0.5 | Dropout rate |
| `gamma` | 1 | Reconstruction loss weight |
| `beta` | 1 | Cluster contrastive loss weight |
| `kappa` | 0.1 | Instance contrastive loss weight |
| `batch_train` | False | Subsample 20k spots/epoch for large datasets |

### Graph Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_neighbors` | 12 | KNN neighbors |
| `n_comps` | 50 | PCA components for expression graph |
| `self_weight` | 0.3 | Self-connection weight |

## Best Practices

1. **Set random seed** with `fix_seed()` before training for reproducibility
2. **Add count layer** before preprocessing if using HVG selection
3. **Use GPU** if available; set `batch_train=True` for large datasets
4. **Choose n_clusters** based on tissue anatomy, not arbitrary numbers
5. **Try kmeans** if mclust (R) is unavailable
6. **Spatial refinement** improves domain smoothness but may over-smooth boundaries

## Troubleshooting

### mclust fails

Use kmeans fallback:
```python
adata = clustering(adata, n_clusters=12, key='spCLUE', cluster_methods='kmeans')
```

### CUDA OOM

```python
device = torch.device("cpu")
# OR for multi-slice:
model = spCLUE(..., batch_train=True)
```

### Missing count layer error

```python
adata.layers['count'] = adata.X.copy()
adata = preprocess(adata, hvgNumber=2000)
```

## References

1. Liu et al. (2023). spCLUE: A Contrastive Learning Approach to Unified Spatial Transcriptomics Analysis Across Single-Slice and Multi-Slice Data.
2. GitHub: https://github.com/liuchangyzu/spCLUE
