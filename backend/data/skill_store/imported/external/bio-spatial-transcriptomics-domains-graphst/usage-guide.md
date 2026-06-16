# GraphST Usage Guide

## Overview

GraphST is a graph self-supervised contrastive learning framework for spatial transcriptomics analysis. It integrates spatial location and gene expression to identify tissue regions with similar expression profiles and spatial proximity.

## When to Use

- **Spatial domain identification**: Identifying tissue compartments and regions
- **Deep learning approach**: When graph neural networks are preferred
- **Multi-slice integration**: Analyzing multiple tissue sections jointly
- **scRNA-seq transfer**: Mapping single-cell data onto spatial coordinates
- **Large-scale datasets**: Scalable to datasets with 20K+ spots

## When Not to Use

- **Small datasets (<100 spots)**: May not benefit from deep learning
- **No spatial coordinates**: GraphST requires spatial information
- **Limited compute**: Training requires GPU for best performance
- **Quick exploration**: Simpler methods like Leiden may be faster

## Prerequisites

### Installation

```bash
# Install GraphST from PyPI
pip install GraphST

# Install PyTorch (with CUDA if available)
pip install torch>=1.8.0

# Optional: for spatial scatter plots in examples below
pip install squidpy

# For mclust clustering, install R and mclust package
# In R:
# install.packages("mclust")
```

### Data Format

Input requirements:
- **AnnData object** with:
  - `adata.X`: Gene expression matrix
  - `adata.obsm['spatial']`: Spatial coordinates (n_spots × 2)
  - `adata.var_names`: Gene names
  - `adata.obs_names`: Spot barcodes

## Step-by-Step Guide

### Step 1: Prepare Data

#### Load 10X Visium Data

```python
import scanpy as sc
import torch
from GraphST.GraphST import GraphST

# Load Visium data
adata = sc.read_visium(
    path="path/to/spaceranger/outs",
    count_file="filtered_feature_bc_matrix.h5"
)

# Check spatial coordinates
print(adata.obsm['spatial'][:5])

# Basic filtering
sc.pp.filter_genes(adata, min_cells=1)
```

#### Load from H5AD

```python
# Load pre-processed data
adata = sc.read_h5ad("spatial_data.h5ad")

# Ensure spatial coordinates exist
assert 'spatial' in adata.obsm
```

### Step 2: Initialize GraphST

```python
# Check device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# Initialize model
model = GraphST(
    adata=adata,
    device=device,
    learning_rate=0.001,
    epochs=600,
    dim_output=64,
    random_seed=42,
    alpha=10,
    beta=1,
    datatype='10X'  # or 'Stereo', 'Slide'
)
```

**Parameter selection:**
- `epochs`: 600 for standard datasets, 1000+ for complex tissues
- `dim_output`: 64 for most datasets, 128 for very complex tissues
- `alpha`: 10 (reconstruction weight), decrease if overfitting
- `beta`: 1 (contrastive weight), increase for more spatial smoothing
- `datatype`: '10X' for Visium, 'Stereo' for Stereo-seq, 'Slide' for Slide-seq

### Step 3: Train Model

```python
# Train and get embeddings
adata = model.train()

# Check embeddings
print(f"Embeddings shape: {adata.obsm['emb'].shape}")
print(f"Embeddings range: [{adata.obsm['emb'].min():.3f}, {adata.obsm['emb'].max():.3f}]")
```

**Training tips:**
- GPU training is 5-10x faster than CPU
- Monitor loss convergence (should decrease steadily)
- Training time: 1-10 minutes depending on dataset size

### Step 4: Cluster Spatial Domains

```python
from GraphST.utils import clustering

# Method 1: Leiden clustering (recommended, no R required)
clustering(
    adata,
    n_clusters=7,
    method='leiden',
    start=0.1,
    end=3.0,
    refinement=False
)

# Method 2: Louvain clustering
clustering(
    adata,
    n_clusters=7,
    method='louvain',
    start=0.1,
    end=3.0
)

# Method 3: Mclust clustering (requires R and mclust package)
clustering(
    adata,
    n_clusters=7,
    method='mclust',
    refinement=False
)

# Access clusters
print(adata.obs['domain'].value_counts())
```

**Clustering method selection:**
- `leiden`: Fast, no R dependency, good for large datasets
- `louvain`: Similar to Leiden, well-established
- `mclust`: Model-based, probabilistic clusters, requires R

### Step 5: Spatial Refinement (Optional)

```python
# Refine labels using spatial neighborhood information
clustering(
    adata,
    n_clusters=7,
    method='mclust',
    refinement=True,
    radius=50
)

# Check refined vs original
if 'mclust' in adata.obs:
    print("Original:", adata.obs['mclust'].value_counts())
    print("Refined:", adata.obs['domain'].value_counts())
```

### Step 6: Visualization

```python
import matplotlib.pyplot as plt
import scanpy as sc

# Spatial domain plot
sq.pl.spatial_scatter(adata, color='domain', size=1.5,
              title='GraphST Spatial Domains')

# UMAP of embeddings
sc.pp.neighbors(adata, use_rep='emb')
sc.tl.umap(adata)
sc.pl.umap(adata, color='domain', title='UMAP of GraphST Embeddings')

# Compare with ground truth (if available)
if 'ground_truth' in adata.obs:
    sq.pl.spatial_scatter(adata, color=['ground_truth', 'domain'],
                  size=1.5, ncols=2)
```

### Step 7: Export Results

```python
import pandas as pd

# Export domain assignments
adata.obs[['domain']].to_csv('graphst_domains.csv')

# Export embeddings
embeddings_df = pd.DataFrame(
    adata.obsm['emb'],
    index=adata.obs_names
)
embeddings_df.to_csv('graphst_embeddings.csv')

# Save full AnnData
adata.write_h5ad('graphst_results.h5ad')
```

## Advanced Usage

### Multi-Section Integration

```python
import anndata as ad

# Load multiple slices
adata1 = sc.read_h5ad("slice1.h5ad")
adata2 = sc.read_h5ad("slice2.h5ad")

# Add batch information
adata1.obs['batch'] = 'slice1'
adata2.obs['batch'] = 'slice2'

# Concatenate
adata_combined = ad.concat([adata1, adata2], label='batch', index_unique='-')

# Run GraphST
model = GraphST(adata_combined, device=device, datatype='10X')
adata_combined = model.train()

# Cluster
clustering(adata_combined, n_clusters=10, method='leiden')

# Visualize by batch
sq.pl.spatial_scatter(adata_combined, color='domain', size=1.5,
              groups=['slice1', 'slice2'])
```

### scRNA-seq Transfer (Deconvolution)

```python
# Load single-cell reference
adata_sc = sc.read_h5ad("scRNA_reference.h5ad")

# Ensure cell type annotations
print(adata_sc.obs['cell_type'].value_counts())

# Initialize with deconvolution mode
model = GraphST(
    adata=adata,
    adata_sc=adata_sc,
    device=device,
    deconvolution=True,
    datatype='10X'
)

# Train mapping
adata, adata_sc = model.train_map()

# Access mapping matrix
map_matrix = adata.obsm['map_matrix']
print(f"Mapping matrix shape: {map_matrix.shape}")  # spot x cell

# Project cell types
from GraphST.utils import project_cell_to_spot
project_cell_to_spot(adata, adata_sc, retain_percent=0.1)

# Visualize projected cell types
sq.pl.spatial_scatter(adata, color=['T_cell', 'B_cell', 'Myeloid'],
              size=1.5, ncols=3)
```

### Stereo-seq / Slide-seq Data

```python
# For high-resolution data, use sparse matrix mode
model = GraphST(
    adata=adata,
    device=device,
    datatype='Stereo',  # or 'Slide' for Slide-seq
    epochs=600
)

adata = model.train()
```

### Selecting Optimal Number of Clusters

```python
from GraphST.utils import search_res

# Test different cluster numbers
cluster_range = range(3, 15)
silhouette_scores = []

for n in cluster_range:
    clustering(adata, n_clusters=n, method='leiden')
    from sklearn.metrics import silhouette_score
    score = silhouette_score(adata.obsm['emb'],
                            adata.obs['domain'].astype('category').cat.codes)
    silhouette_scores.append(score)
    print(f"n_clusters={n}, silhouette={score:.3f}")

# Select optimal
optimal_n = cluster_range[np.argmax(silhouette_scores)]
print(f"Optimal clusters: {optimal_n}")

# Final clustering
clustering(adata, n_clusters=optimal_n, method='leiden')
```

## Parameters Reference

### GraphST Model Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `learning_rate` | 0.001 | Learning rate for Adam optimizer |
| `epochs` | 600 | Number of training epochs |
| `dim_output` | 64 | Dimension of output embeddings |
| `alpha` | 10 | Weight for reconstruction loss |
| `beta` | 1 | Weight for contrastive loss |
| `random_seed` | 41 | Random seed for reproducibility |
| `datatype` | '10X' | Data type ('10X', 'Stereo', 'Slide') |

### Clustering Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_clusters` | 7 | Number of spatial domains |
| `method` | 'mclust' | Clustering algorithm |
| `refinement` | False | Apply spatial refinement |
| `radius` | 50 | Neighbor radius for refinement |
| `start` | 0.1 | Start resolution for search |
| `end` | 3.0 | End resolution for search |

## Troubleshooting

### CUDA Out of Memory

```python
# Use CPU instead
device = torch.device('cpu')

# Or reduce embedding dimension
model = GraphST(adata, device=device, dim_output=32)
```

### No Spatial Coordinates

```python
# Error: KeyError: 'spatial'
# Solution: Add spatial coordinates
adata.obsm['spatial'] = adata.obs[['array_row', 'array_col']].values
```

### Mclust Not Found

```python
# Error: RRuntimeError
# Solution 1: Install R mclust
# In R: install.packages("mclust")

# Solution 2: Use Leiden instead
clustering(adata, n_clusters=7, method='leiden')
```

### Convergence Issues

```python
# If training is unstable, adjust learning rate
model = GraphST(adata, device=device, learning_rate=0.0005)

# Or reduce alpha/beta
model = GraphST(adata, device=device, alpha=5, beta=0.5)
```

## AI Agent Test Cases

### Basic Domain Identification
> "Run GraphST on my Visium data to identify spatial domains"

```python
from GraphST.GraphST import GraphST
from GraphST.utils import clustering

model = GraphST(adata, device=device)
adata = model.train()
clustering(adata, n_clusters=7, method='leiden')
```

### With GPU Acceleration
> "Use GPU for faster GraphST training"

```python
device = torch.device('cuda')
model = GraphST(adata, device=device, epochs=600)
adata = model.train()
```

### Multi-Slice Integration
> "Integrate 3 Visium slices with GraphST"

```python
import anndata as ad
adata_combined = ad.concat([s1, s2, s3], label='batch')
model = GraphST(adata_combined, device=device)
adata_combined = model.train()
clustering(adata_combined, n_clusters=10, method='leiden')
```

### With Spatial Refinement
> "Apply spatial refinement to GraphST domains"

```python
clustering(adata, n_clusters=7, method='mclust',
           refinement=True, radius=50)
```

### Deconvolution
> "Map scRNA-seq cell types onto my Visium data"

```python
model = GraphST(adata, adata_sc=sc_reference,
                device=device, deconvolution=True)
adata, adata_sc = model.train_map()
project_cell_to_spot(adata, adata_sc)