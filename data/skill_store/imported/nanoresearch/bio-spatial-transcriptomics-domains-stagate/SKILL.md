---
name: bio-spatial-transcriptomics-domains-stagate
description: Spatial domain identification using STAGATE graph attention autoencoder with PyTorch Geometric
tool_type: python
primary_tool: STAGATE
supported_tools: [scanpy, torch, torch-geometric, numpy, pandas, matplotlib]
languages: [python]
keywords: ["spatial", "domains", "STAGATE", "graph-attention", "clustering", "deep-learning", "pytorch-geometric", "denoising"]
code_location: scripts/python/
version_compatibility:
  python: ">=3.9"
  pytorch: ">=1.12.0"
  pytorch-geometric: ">=2.0.0"
  scanpy: ">=1.9.0"
---

# STAGATE Spatial Domain Identification

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| Python | >= 3.9 | |
| PyTorch | >= 1.12.0 | GPU recommended |
| PyTorch Geometric | >= 2.0.0 | Graph neural network backend |
| scanpy | >= 1.9.0 | Single-cell analysis |
| anndata | >= 0.8.0 | Data structures |
| scikit-learn | >= 1.0.0 | Spatial network construction |
| rpy2 | optional | Required only for `mclust_clustering` |

## Installation

```bash
# Core dependencies
pip install scanpy anndata pandas numpy matplotlib seaborn scikit-learn tqdm

# PyTorch (follow https://pytorch.org/ for your CUDA version)
pip install torch

# PyTorch Geometric
pip install torch-geometric

# Optional: for mclust clustering
pip install rpy2
```

## Skill Overview

**Use this skill when you need to:**
- Identify spatial domains using a deep graph attention autoencoder
- Obtain denoised gene expression profiles using spatial context
- Integrate multiple tissue slices into 3D domain models
- Process large datasets with batch training

**Do NOT use this skill when:**
- You lack GPU and the dataset is very large (>50k spots without batching)
- You need probabilistic clustering with uncertainty quantification (use BayesSpace)
- You only need simple spatial clustering without deep learning
- `mclust` is required but R is not available (use `leiden_clustering` instead)

## Core Workflow

### Step 1: Data Preparation [Raw] → [Normalized]

Normalize counts, log-transform, and select highly variable genes. Coordinates must be in `adata.obsm['spatial']`.

```python
from scripts.python.core_analysis import prepare_data

# Coordinates must exist before preparation
assert 'spatial' in adata.obsm, "Spatial coordinates required in adata.obsm['spatial']"

adata_prep = prepare_data(
    adata,
    min_counts=100,      # filter low-quality spots
    n_top_genes=3000,    # HVG count
    normalize=True,
    log1p=True,
)
```

| Parameter | Default | When to change |
|-----------|---------|----------------|
| `min_counts` | 100 | Lower for low-coverage platforms; raise for stricter QC |
| `n_top_genes` | 3000 | Reduce to 1000 for speed; 3000 is standard |
| `normalize` / `log1p` | True | Keep True unless data is already normalized |

**Output:** `adata_prep` with HVGs marked in `.var['highly_variable']`.

### Step 2: Build Spatial Network [Normalized] → [Network]

Construct the spatial neighbor graph. **This is mandatory before training.**

```python
from scripts.python.core_analysis import build_spatial_network

# Radius-based (recommended for Visium)
build_spatial_network(
    adata_prep,
    rad_cutoff=150,   # ~3 spot diameters for Visium (55μm)
    model='Radius',
    spatial_key='spatial'
)
```

| Platform | `rad_cutoff` | Rationale |
|----------|-------------|-----------|
| Visium (55μm) | 150–200 | ~3–4 spot diameters |
| Visium HD | 30–50 | Higher resolution |
| Xenium | 20–50 | Subcellular spots |
| MERFISH | 30–60 | Single-cell resolution |
| Slide-seq | 50–100 | 10μm beads |

**Alternative — KNN:**

```python
build_spatial_network(adata_prep, k_cutoff=10, model='KNN')
```

**Output:** `adata_prep.uns['Spatial_Net']` DataFrame with edges.

**⚠️ Critical:** `train_stagate` will raise `ValueError` if `Spatial_Net` is missing.

### Step 3: Train STAGATE [Network] → [Embeddings]

```python
from scripts.python.core_analysis import train_stagate

adata_prep = train_stagate(
    adata_prep,
    hidden_dims=[512, 30],     # [encoder_hidden, embedding_dim]
    n_epochs=1000,
    lr=0.001,
    key_added='STAGATE',
    gradient_clipping=5.0,
    weight_decay=0.0001,
    random_seed=0,
    save_reconstruction=True,  # for denoising visualization
    device=None,               # auto-detect cuda/cpu
)
```

| Parameter | Default | Notes |
|-----------|---------|-------|
| `hidden_dims` | `[512, 30]` | 30 = embedding dim; use 50 for complex tissues |
| `n_epochs` | 1000 | 500 for large datasets (>20k spots) |
| `lr` | 0.001 | Keep default |
| `gradient_clipping` | 5.0 | Prevent exploding gradients |
| `save_reconstruction` | False | Set True if you need denoised expression |
| `device` | None | `'cuda'`, `'cpu'`, or auto-detect |

**Output:** Embeddings in `adata_prep.obsm['STAGATE']` (shape: n_obs × 30).

**⚠️ Critical:** `train_stagate` operates **only on HVGs**. If `prepare_data` was skipped or HVG selection failed, training behavior is undefined.

### Step 4: Cluster Domains [Embeddings] → [Domains]

**mclust (recommended, requires R):**

```python
from scripts.python.core_analysis import mclust_clustering

adata_prep = mclust_clustering(
    adata_prep,
    n_clusters=7,
    used_obsm='STAGATE',
    model_names='EEE',
    key_added='mclust',
)
```

**Leiden (no R required):**

```python
from scripts.python.core_analysis import leiden_clustering

adata_prep = leiden_clustering(
    adata_prep,
    resolution=0.5,
    used_obsm='STAGATE',
    key_added='stagate_leiden',
    n_neighbors=15,
)
```

**Output:** Domain labels in `adata_prep.obs['mclust']` or `adata_prep.obs['stagate_leiden']`.

### Step 5: Visualization

```python
from scripts.python.visualization import (
    plot_domains,
    plot_domains_comparison,
    plot_embedding_umap,
    plot_gene_expression,
    plot_denoising_comparison,
)

# Spatial domains
plot_domains(adata_prep, domain_key='mclust')

# Compare mclust vs Leiden
plot_domains_comparison(
    adata_prep,
    domain_keys=['mclust', 'stagate_leiden'],
    n_cols=2
)

# UMAP of embeddings colored by domains
plot_embedding_umap(adata_prep, embedding_key='STAGATE', color_key='mclust')

# Gene expression
plot_gene_expression(adata_prep, gene='GFAP')

# Raw vs denoised (requires save_reconstruction=True)
plot_denoising_comparison(adata_prep, gene='GFAP')
```

### Step 6: Export

```python
from scripts.python.core_analysis import export_results

export_results(
    adata_prep,
    output_dir='./stagate_results',
    domain_key='mclust',
    embedding_key='STAGATE',
)
```

## Complete Pipeline

Single copy-pasteable workflow:

```python
import scanpy as sc
from scripts.python.core_analysis import (
    prepare_data, build_spatial_network,
    train_stagate, mclust_clustering, leiden_clustering, export_results
)
from scripts.python.visualization import plot_domains, plot_embedding_umap

# Load
adata = sc.read_h5ad("visium_sample.h5ad")
assert 'spatial' in adata.obsm

# Preprocess
adata = prepare_data(adata, n_top_genes=3000)

# Network
build_spatial_network(adata, rad_cutoff=150)

# Train
adata = train_stagate(adata, n_epochs=1000, save_reconstruction=True)

# Cluster
try:
    adata = mclust_clustering(adata, n_clusters=7)
except Exception:
    adata = leiden_clustering(adata, resolution=0.5, key_added='mclust')

# Visualize
plot_domains(adata, domain_key='mclust')
plot_embedding_umap(adata, color_key='mclust')

# Export
export_results(adata, output_dir='./results')
```

## Skill-Provided Functions

### Analysis Pipeline

| Function | Purpose |
|----------|---------|
| `prepare_data(adata, ...)` | Filter, normalize, log1p, HVG selection |
| `build_spatial_network(adata, rad_cutoff, ...)` | 2D spatial neighbor graph |
| `build_3d_spatial_network(adata, rad_cutoff_2d, rad_cutoff_z, ...)` | 3D multi-slice graph |
| `plot_network_stats(adata)` | Visualize neighbor distribution histogram |
| `train_stagate(adata, ...)` | Train graph attention autoencoder |
| `mclust_clustering(adata, n_clusters, ...)` | R-based mclust clustering |
| `leiden_clustering(adata, resolution, ...)` | Leiden clustering on embeddings |
| `louvain_clustering(adata, resolution, ...)` | Wrapper calling Leiden (scanpy deprecated louvain) |
| `create_batch_data(adata, num_batch_x, num_batch_y, ...)` | Split for batch processing |
| `export_results(adata, output_dir, ...)` | Save embeddings, domains, coordinates |
| `compute_domain_enrichment(adata, ...)` | Domain proportions by group |

### Visualization

| Function | Purpose |
|----------|---------|
| `plot_domains(adata, domain_key, ...)` | Spatial domain scatter plot |
| `plot_domains_comparison(adata, domain_keys, ...)` | Side-by-side comparison panels |
| `plot_embedding_umap(adata, embedding_key, color_key, ...)` | UMAP of STAGATE embeddings |
| `plot_embedding_pca(adata, embedding_key, ...)` | PCA of embeddings |
| `plot_domain_proportions(adata, domain_key, group_key, ...)` | Bar chart of domain composition |
| `plot_confusion_matrix(adata, key1, key2, ...)` | Cross-tabulation heatmap |
| `plot_gene_expression(adata, gene, layer, ...)` | Spatial gene expression map |
| `plot_denoising_comparison(adata, gene, ...)` | Raw vs STAGATE_ReX side-by-side |
| `plot_multi_sample_domains(adatas, ...)` | Multi-panel sample comparison |
| `plot_aligned_slices(adata, section_key, ...)` | 3D slice visualization |
| `plot_training_loss(losses, ...)` | Loss curve |

## Official API — Agents Often Miss These

### 1. `build_spatial_network` is mandatory before `train_stagate`

STAGATE does not compute spatial neighbors internally. You must run `build_spatial_network` first to populate `adata.uns['Spatial_Net']`.

### 2. `train_stagate` trains **only on HVGs**

The wrapper automatically subsets to `adata[:, adata.var['highly_variable']]` before training. If HVGs were not selected during `prepare_data`, behavior is undefined.

### 3. `save_reconstruction=True` only reconstructs HVGs

`adata.layers['STAGATE_ReX']` contains denoised expression **only for highly variable genes**. Non-HVGs are not reconstructed.

### 4. `louvain_clustering` actually calls Leiden

Due to scanpy deprecating `sc.tl.louvain`, the function `louvain_clustering` internally calls `sc.tl.leiden`. Results are stored with key `stagate_louvain` for backward compatibility.

### 5. `mclust_clustering` requires R and `rpy2`

If R is not installed, catch the exception and fall back to `leiden_clustering`:

```python
try:
    adata = mclust_clustering(adata, n_clusters=7)
except ImportError:
    adata = leiden_clustering(adata, resolution=0.5, key_added='mclust')
```

### 6. `train_stagate` copies `adata` internally

The wrapper performs `adata = adata.copy()` and converts `adata.X` to `csr_matrix`. Your original AnnData object is preserved.

### 7. 3D analysis requires concatenated AnnData

Before `build_3d_spatial_network`, slices must be concatenated with a section label:

```python
adata_concat = sc.concat(
    [adata1, adata2, adata3],
    label='section',
    keys=['1', '2', '3']
)
build_3d_spatial_network(
    adata_concat,
    rad_cutoff_2d=150,
    rad_cutoff_z=100,
    section_key='section'
)
```

### 8. Batch processing splits data physically

`create_batch_data` tiles the spatial field into non-overlapping rectangles. Each batch is trained independently — embeddings are not aligned across batches.

## Common Pitfalls

1. **⚠️ Forgetting `build_spatial_network`** — `train_stagate` raises `ValueError: Spatial_Net not found`.

2. **⚠️ Wrong `rad_cutoff` units** — `rad_cutoff` must match the coordinate units in `adata.obsm['spatial']`. For Visium, pixel coordinates may differ from microns. Check `adata.obsm['spatial'].max()` before choosing a cutoff.

3. **⚠️ Using `louvain_clustering` expecting Louvain output** — It calls Leiden under the hood. Use `leiden_clustering` directly to avoid confusion.

4. **⚠️ `n_clusters` mismatch with `mclust`** — mclust may return fewer clusters than requested if the data structure does not support the number. Check `adata.obs['mclust'].nunique()` after clustering.

5. **⚠️ Gene expression plots fail on sparse data** — `plot_gene_expression` and `plot_denoising_comparison` handle both dense and sparse matrices, but some intermediate views may not support `.flatten()`. The wrappers now use `toarray()` guards.

6. **⚠️ `hidden_dims=[512, 30]` embedding size** — The second value (30) is the embedding dimension. For complex tissues or 3D data, increase to 50.

7. **⚠️ HVG selection on integer counts** — `prepare_data` with `log1p=False` passes integer data to HVG selection. The wrapper now auto-converts to float32 before calling `sc.pp.highly_variable_genes`.

## Troubleshooting

### GPU Out of Memory

```python
# Option 1: Reduce hidden dimensions
adata = train_stagate(adata, hidden_dims=[256, 30])

# Option 2: Use CPU
adata = train_stagate(adata, device='cpu')

# Option 3: Batch processing
batch_list = create_batch_data(adata, num_batch_x=4, num_batch_y=4)
for batch in batch_list:
    build_spatial_network(batch, rad_cutoff=150)
    batch = train_stagate(batch, n_epochs=500)
```

### Poor Domain Separation

```python
# Larger neighborhood
build_spatial_network(adata, rad_cutoff=200)

# More expressive embeddings
adata = train_stagate(adata, hidden_dims=[512, 50])

# Train longer
adata = train_stagate(adata, n_epochs=2000)
```

### Too Many / Too Few Domains

```python
# mclust: adjust n_clusters
adata = mclust_clustering(adata, n_clusters=5)

# Leiden: adjust resolution
adata = leiden_clustering(adata, resolution=0.3)   # fewer domains
adata = leiden_clustering(adata, resolution=1.0)   # more domains
```

### mclust Not Available

```python
# Use Leiden as drop-in replacement
adata = leiden_clustering(adata, resolution=0.5, key_added='mclust')
```

## Related Skills

- [bio-spatial-transcriptomics-domains-spagcn](../bio-spatial-transcriptomics-domains-spagcn/SKILL.md) — GCN-based domain detection
- [bio-spatial-transcriptomics-domains-bayesspace-r](../bio-spatial-transcriptomics-domains-bayesspace-r/SKILL.md) — Bayesian spatial clustering
- [bio-spatial-transcriptomics-domains-graphst](../bio-spatial-transcriptomics-domains-graphst/SKILL.md) — Graph-based clustering with deep embedding
- [bio-spatial-transcriptomics-analysis-scanpy](../bio-spatial-transcriptomics-analysis-scanpy/SKILL.md) — General spatial analysis

## References

1. Dong, K., & Zhang, S. (2022). Deciphering spatial domains from spatially resolved transcriptomics with an adaptive graph attention auto-encoder. *Nature Communications*, 13:1736. https://doi.org/10.1038/s41467-022-29439-6
2. STAGATE PyTorch Geometric: https://github.com/QIFEIDKN/STAGATE_pyG
3. STAGATE TensorFlow: https://github.com/QIFEIDKN/STAGATE
4. PyTorch Geometric: https://pytorch-geometric.readthedocs.io/
