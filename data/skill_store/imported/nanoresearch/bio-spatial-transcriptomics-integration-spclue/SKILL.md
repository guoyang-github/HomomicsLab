---
name: bio-spatial-transcriptomics-integration-spclue
description: |
  spCLUE performs spatial domain identification and multi-slice integration using
  cross-view contrastive learning. Constructs multi-view graphs (spatial and expression)
  and employs graph neural networks with instance-level and cluster-level contrastive
  learning. Supports batch correction for integrating multiple tissue slices.
tool_type: python
primary_tool: spCLUE
supported_tools: [PyTorch, scanpy, squidpy, rpy2, mclust]
languages: [python, r]
keywords: ["spatial", "domains", "clustering", "integration", "contrastive-learning",
           "graph-neural-network", "multi-slice", "batch-correction", "pytorch", "spCLUE"]
code_location: scripts/
version_compatibility:
  python: ">=3.8"
  pytorch: ">=1.8.0"
  scanpy: ">=1.9.0"
  r: ">=4.0.0"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| Python | >= 3.8 | |
| PyTorch | >= 1.8.0 | CUDA optional but strongly recommended |
| scanpy | >= 1.9.0 | |
| squidpy | >= 1.3.0 | For spatial visualization |
| scikit-learn | >= 1.1.0 | PCA, KMeans |
| rpy2 | >= 3.4.0 | Python-R bridge |
| R | >= 4.0.0 | Required for mclust clustering |
| R mclust | -- | `install.packages("mclust")` in R |

## Installation

```bash
# PyTorch (adjust for your CUDA version)
pip install torch>=1.8.0

# Python dependencies
pip install scanpy>=1.9.0 anndata>=0.8.0 squidpy>=1.3.0
pip install scikit-learn>=1.1.0 scipy>=1.8.0 tqdm
pip install rpy2>=3.4.0

# R dependency (in R console)
install.packages("mclust")
```

## Skill Overview

spCLUE identifies spatial domains in tissue sections by combining spatial coordinates and gene expression through graph contrastive learning. It supports both single-slice domain detection and multi-slice integration with batch correction.

**Core workflow**: Preprocess -> Build multi-view graphs -> Train spCLUE -> Cluster -> (Optional) Spatial refinement

**When to use**:
- Identify anatomically meaningful regions in a tissue section (e.g. cortical layers, tumor microenvironment zones)
- Integrate multiple adjacent tissue slices while preserving spatial structure
- Batch correction across slices from the same sample

**When NOT to use**:
- Cell type annotation (use marker-based methods or CellTypist instead)
- Analysis without spatial coordinates (use standard scRNA-seq clustering)
- Very small datasets (< 100 spots; GNNs need sufficient graph structure)

## Quick Reference: Single-Slice vs Multi-Slice

| Goal | Entry Point | Key Difference |
|------|-------------|---------------|
| Single slice domains | `model.train()` | No batch correction |
| Multi-slice integration | `model.trainBatch()` | Requires `batch_list`, enables `batch_train` |

## Core Workflow (Step-by-Step)

Import skill modules:

```python
from scripts import spCLUE, preprocess, prepare_graph, clustering, fix_seed
from scripts import refine_label, batch_refine_label
from sklearn.decomposition import PCA
import torch
```

### Step 1: Load and Preprocess Data

**Goal**: Prepare AnnData with spatial coordinates and normalized expression.

**Input requirements**:
- `adata.X`: Gene expression (counts or normalized)
- `adata.obsm['spatial']`: Spatial coordinates (n_spots x 2) -- **required**
- `adata.layers['count']`: Raw counts -- **required if using HVG selection** (seurat_v3 flavor)

```python
# Load data
adata = sc.read_h5ad("spatial_data.h5ad")
# OR: adata = sc.read_visium("path/to/visium/dir")

# Verify spatial coordinates exist
assert "spatial" in adata.obsm, "spatial coordinates required in adata.obsm['spatial']"

# Preprocess
adata = preprocess(adata, hvgNumber=2000)
```

**CRITICAL**: `preprocess()` with `hvgNumber` uses `flavor="seurat_v3"` which requires `adata.layers['count']`. If this layer is missing, either:
- Add it: `adata.layers['count'] = adata.X.copy()` (before preprocessing)
- Or use `hvgNumber=None` to skip HVG selection

---

### Step 2: PCA Dimensionality Reduction

**Goal**: Reduce gene expression to 200 features for model input.

```python
pca = PCA(n_components=200, random_state=0)
input_data = pca.fit_transform(adata.X)
```

---

### Step 3: Build Multi-View Graphs

**Goal**: Construct spatial adjacency graph and expression similarity graph.

```python
graph_dict = {
    "spatial": prepare_graph(adata, key="spatial", n_neighbors=12),
    "expr": prepare_graph(adata, key="expr", n_neighbors=12, n_comps=50)
}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `key` | "spatial" | "spatial" (from coordinates) or "expr" (from PCA correlations) |
| `n_neighbors` | 12 | KNN neighbors. Higher = more global structure |
| `n_comps` | 50 | PCA components for expression graph (expr only) |
| `self_weight` | 0.3 | Self-connection weight in symmetric normalization |

---

### Step 4: Train spCLUE

#### Option A: Single Slice

```python
fix_seed(42)
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

model = spCLUE(
    input_data=input_data,
    graph_dict=graph_dict,
    n_clusters=12,       # Number of spatial domains
    epochs=500,
    device=device,
    random_seed=42
)

pred_labels, embeddings = model.train()

# Store results
adata.obsm['spCLUE'] = embeddings
adata.obs['pred'] = pred_labels
```

#### Option B: Multi-Slice Integration

```python
import anndata as ad

# Concatenate slices
adata_list = [slice1, slice2, slice3]
adata_combined = ad.concat(adata_list, label='batch', keys=['s1', 's2', 's3'])

# Preprocess and PCA on combined data
adata_combined = preprocess(adata_combined, hvgNumber=2000)
input_data = PCA(n_components=200, random_state=0).fit_transform(adata_combined.X)

# Build graphs
graph_dict = {
    "spatial": prepare_graph(adata_combined, key="spatial", n_neighbors=12),
    "expr": prepare_graph(adata_combined, key="expr", n_neighbors=12, n_comps=50)
}

# Batch labels (integer codes)
batch_list = adata_combined.obs['batch'].astype('category').cat.codes.values

# Train with batch correction
model = spCLUE(
    input_data=input_data,
    graph_dict=graph_dict,
    n_clusters=12,
    batch_list=batch_list,
    epochs=500,
    device=device,
    batch_train=adata_combined.n_obs > 20000,  # Enable for large datasets
    random_seed=42
)

# trainBatch returns (status_string, embeddings)
# The first return value is a status string ("success"), ignore it
_, embeddings = model.trainBatch()

adata_combined.obsm['spCLUE'] = embeddings
```

**Key model parameters**:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_clusters` | 12 | Target number of spatial domains |
| `epochs` | 500 | Training epochs. Early stopping at ARI >= 0.3 (single) or 0.5 (batch) |
| `dim_input` | 200 | Must match PCA n_components |
| `dim_hidden` | 64 | GCN hidden dimension |
| `dim_embed` | 24 | Output embedding dimension |
| `graph_corr` | 0.4 | Edge dropout probability for graph corruption |
| `dropout` | 0.5 | Node feature dropout |
| `gamma` | 1 | Weight for reconstruction loss |
| `beta` | 1 | Weight for cluster-level contrastive loss |
| `kappa` | 0.1 | Weight for instance-level contrastive loss |
| `learning_rate` | 0.001 | Adam learning rate |

---

### Step 5: Cluster Embeddings

**Goal**: Convert embeddings to discrete spatial domain labels.

```python
adata = clustering(
    adata,
    n_clusters=12,
    key='spCLUE',
    cluster_methods='mclust',   # Options: 'mclust', 'kmeans', 'leiden', 'pred'
    refinement=False
)
```

| Method | Requirement | Best For |
|--------|------------|----------|
| `mclust` | R + rpy2 + mclust | Default; probabilistic model-based clustering |
| `kmeans` | sklearn only | Fast; no R dependency |
| `leiden` | leidenalg | Graph-based; good for irregular domain shapes |
| `pred` | -- | Use model's internal predictions directly |

**R/mclust troubleshooting**: If mclust fails, fall back to kmeans:
```python
adata = clustering(adata, n_clusters=12, key='spCLUE', cluster_methods='kmeans')
```

---

### Step 6: Spatial Refinement (Optional)

**Goal**: Smooth labels using spatial neighborhood majority voting.

```python
# Single slice
refine_label(adata, radius=30, key='mclust', suffix='refined')
# Creates: adata.obs['mclust_refined']

# Multi-slice (batch-aware)
batch_refine_label(adata, radius=30, key='mclust',
                   suffix='refined', batch_key='batch')
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `radius` | 30 | Number of nearest neighbors to vote |
| `key` | "mclust" | Column in adata.obs to refine |
| `batch_key` | "batchID" | For batch_refine_label: column with batch info |

---

### Step 7: Visualize

```python
import squidpy as sq

# Spatial domain plot
sq.pl.spatial_scatter(adata, color='mclust', size=1.5)

# Refined domains
sq.pl.spatial_scatter(adata, color='mclust_refined', size=1.5)

# UMAP of embeddings
sc.pp.neighbors(adata, use_rep='spCLUE')
sc.tl.umap(adata)
sc.pl.umap(adata, color=['mclust', 'batch'])
```

---

## Complete Pipeline: Single Slice

```python
from scripts import spCLUE, preprocess, prepare_graph, clustering, fix_seed, refine_label
from sklearn.decomposition import PCA
import torch
import scanpy as sc
import squidpy as sq

fix_seed(42)

# 1. Load and preprocess
adata = sc.read_h5ad("slice.h5ad")
adata = preprocess(adata, hvgNumber=2000)

# 2. PCA
input_data = PCA(n_components=200, random_state=0).fit_transform(adata.X)

# 3. Graphs
graph_dict = {
    "spatial": prepare_graph(adata, key="spatial", n_neighbors=12),
    "expr": prepare_graph(adata, key="expr", n_neighbors=12, n_comps=50)
}

# 4. Train
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
model = spCLUE(input_data=input_data, graph_dict=graph_dict,
               n_clusters=12, epochs=500, device=device, random_seed=42)
pred_labels, embeddings = model.train()

# 5. Store and cluster
adata.obsm['spCLUE'] = embeddings
adata.obs['pred'] = pred_labels
adata = clustering(adata, n_clusters=12, key='spCLUE', cluster_methods='mclust')

# 6. Refine
refine_label(adata, radius=30, key='mclust', suffix='refined')

# 7. Plot
sq.pl.spatial_scatter(adata, color=['mclust', 'mclust_refined'])
```

---

## Skill-Provided Functions

Source: `scripts/` directory

### Data Processing

| Function | Parameters | Description |
|----------|-----------|-------------|
| `preprocess(adata, hvgNumber=None)` | `hvgNumber`: number of HVGs | Filters, normalizes, selects HVGs. **Requires `adata.layers['count']` if hvgNumber is set** |
| `prepare_graph(adata, key, n_neighbors=12, ...)` | `key`: "spatial" or "expr" | Builds KNN adjacency matrix with symmetric normalization |
| `fix_seed(seed)` | | Sets random seeds for PyTorch, numpy, CUDA |

### Model

| Class | Key Parameters | Description |
|-------|---------------|-------------|
| `spCLUE(input_data, graph_dict, n_clusters=12, ...)` | `batch_list`, `batch_train` | Main model class. Use `train()` for single-slice, `trainBatch()` for multi-slice |

### Clustering & Refinement

| Function | Parameters | Description |
|----------|-----------|-------------|
| `clustering(adata, n_clusters=12, key='embed', cluster_methods='mclust', refinement=False)` | | Clusters embeddings. Methods: mclust/kmeans/leiden/pred |
| `refine_label(adata, radius=30, key='label')` | | Single-slice spatial majority voting |
| `batch_refine_label(adata, radius=30, key='label', batch_key='batchID')` | | Multi-slice spatial majority voting |
| `calculateMetrics(true, pred, embedding)` | | Computes ARI, NMI, Silhouette, CH index |

---

## Official API -- Agents Often Miss These

| Pattern | Key Point |
|---------|-----------|
| `model.train()` | Returns `(pred_labels, embeddings)`. Early stops when ARI >= 0.3 (for n_spot <= 10000) or 1.1 (larger datasets). |
| `model.trainBatch()` | Returns `(status_string, embeddings)`. **First value is a status string ("success")** -- ignore it and use the second value. |
| `batch_train=True` | For datasets > 20k spots. Randomly subsamples 20k spots per epoch to prevent OOM. Only relevant for `trainBatch()`. |
| `mclust` clustering | Requires R + `install.packages("mclust")` + rpy2. If unavailable, fall back to `cluster_methods='kmeans'`. |
| `adata.layers['count']` | Required by `preprocess(adata, hvgNumber=...)` due to `flavor="seurat_v3"`. Add manually if missing. |
| `n_clusters` | This is the **target** number of domains. The model uses it to initialize cluster centers, but final count may vary slightly with mclust/leiden. |

---

## Common Pitfalls

1. **Missing spatial coordinates**: spCLUE requires `adata.obsm['spatial']`. Standard scRNA-seq without spatial info cannot be used.
2. **Missing `layers['count']`**: Calling `preprocess(adata, hvgNumber=2000)` without `adata.layers['count']` throws an error. Fix: `adata.layers['count'] = adata.X.copy()` before preprocessing.
3. **R/mclust not installed**: `clustering(..., cluster_methods='mclust')` fails with obscure rpy2 errors if R or mclust is missing. Use `'kmeans'` as fallback.
4. **CUDA OOM**: Large datasets (>30k spots) on GPU may OOM. Use `batch_train=True` for multi-slice, or switch to CPU.
5. **Wrong n_clusters**: Too few clusters merges distinct anatomical regions; too many splits coherent domains. Start with anatomical knowledge (e.g. 6-7 for cortex, 10-15 for tumor).
6. **trainBatch first return value**: `status, embeddings = model.trainBatch()` -- `status` is "success" (not an error code). Use `embeddings`.
7. **Graph construction on integrated data**: For multi-slice, build graphs AFTER concatenation so neighbors can cross slice boundaries (if spatially aligned) or stay within slices.

---

## Hyperparameter Guide

| Parameter | Default | Small data (<1k spots) | Medium (1k-10k) | Large (>10k) |
|-----------|---------|------------------------|-----------------|--------------|
| `n_clusters` | 12 | 5-8 | 8-15 | 10-20 |
| `n_neighbors` | 12 | 6-10 | 10-15 | 15-20 |
| `epochs` | 500 | 200-300 | 500 | 500-800 |
| `dim_embed` | 24 | 16 | 24 | 32-64 |
| `batch_train` | False | False | False | **True** (multi-slice) |

---

## Troubleshooting

### mclust clustering fails

```python
# Fallback to kmeans (no R required)
adata = clustering(adata, n_clusters=12, key='spCLUE', cluster_methods='kmeans')
```

### CUDA out of memory

```python
# Use CPU
device = torch.device("cpu")

# Or enable batch training for multi-slice
model = spCLUE(..., batch_train=True)
```

### All spots assigned to one cluster

Increase `n_clusters` or try `cluster_methods='leiden'`:
```python
adata = clustering(adata, n_clusters=20, key='spCLUE', cluster_methods='leiden')
```

### Results not reproducible

```python
from scripts import fix_seed
fix_seed(42)  # Before any model initialization
```

---

## Related Skills

- [bio-spatial-transcriptomics-clustering-spagcn](../bio-spatial-transcriptomics-clustering-spagcn/SKILL.md) - GCN-based spatial domain detection
- [bio-spatial-transcriptomics-clustering-stagate](../bio-spatial-transcriptomics-clustering-stagate/SKILL.md) - Graph attention for spatial domains
- [bio-spatial-transcriptomics-deconvolution-card-r](../bio-spatial-transcriptomics-deconvolution-card-r/SKILL.md) - Cell type deconvolution

## References

1. Liu et al. (2023). spCLUE: A Contrastive Learning Approach to Unified Spatial Transcriptomics Analysis Across Single-Slice and Multi-Slice Data.
2. spCLUE GitHub: https://github.com/liuchangyzu/spCLUE
