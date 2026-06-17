---
name: bio-spatial-transcriptomics-domains-graphst
description: |
  GraphST performs spatial domain identification using graph self-supervised contrastive learning.
  Integrates spatial location and gene expression to identify tissue regions with similar
  expression profiles and spatial proximity. Supports spatial clustering, multi-section integration,
  and scRNA-seq transfer onto ST data.
tool_type: python
primary_tool: GraphST
languages: [python]
keywords: ["spatial", "domains", "clustering", "GraphST", "graph-neural-network", "self-supervised",
           "contrastive-learning", "integration", "deconvolution", "pytorch"]
code_location: scripts/python/
version_compatibility:
  python: ">=3.8"
  GraphST: ">=1.0"
  scanpy: ">=1.9.0"
  torch: ">=1.8.0"
---

## Version Compatibility + Installation

| Package | Required | Notes |
|---------|----------|-------|
| Python | >=3.8 | |
| GraphST | >=1.0 | `pip install GraphST` |
| PyTorch | >=1.8.0 | CUDA optional but recommended |
| scanpy | >=1.9.0 | |
| anndata | >=0.8.0 | |
| scikit-learn | >=1.1.0 | For silhouette scoring |
| rpy2 + R mclust | Optional | Only if using `method='mclust'` |

```bash
pip install GraphST torch scanpy
```

For mclust clustering (optional):
```r
# In R:
install.packages("mclust")
```

---

# GraphST Spatial Domain Identification

GraphST is a graph self-supervised contrastive learning framework that integrates spatial location and gene expression to identify spatial domains (tissue regions).

## Quick Selector

| Task | Approach | Best For |
|------|----------|----------|
| Domain identification | `GraphST` + `clustering()` | Standard spatial transcriptomics |
| Multi-section integration | Concatenate + `GraphST` | Multiple slices from same tissue |
| Deconvolution | `GraphST(deconvolution=True)` + `train_map()` | Map scRNA-seq to spatial |
| Optimal cluster count | `select_optimal_clusters()` (skill helper) | When n_clusters is unknown |

### When to Use GraphST

- **Spatial domain identification**: Finding tissue compartments/regions
- **Multi-slice integration**: Jointly analyzing multiple tissue sections
- **scRNA-seq transfer**: Mapping single-cell annotations to spatial spots
- **Deep learning preferred**: When GNN-based methods are desired over statistical clustering

### When NOT to Use GraphST

- **No spatial coordinates**: GraphST requires `adata.obsm['spatial']`
- **Very small datasets (<100 spots)**: May not benefit from deep learning
- **Need deterministic results**: GNN training has stochasticity
- **Quick exploration**: Leiden/Louvain on raw expression may be faster


## Core Workflow (Step-by-Step)

### Step 0: Data Requirements

**Input:** `adata` (spot × gene AnnData) with:
- `adata.X`: gene expression (counts or normalized)
- `adata.obsm['spatial']`: spatial coordinates (n_spots × 2)

```python
# Check requirements
from scripts.python.utils import validate_graphst_data
results = validate_graphst_data(adata)
print(f"Valid: {results['valid']}, Spots: {results['n_spots']}, Has spatial: {results['has_spatial']}")
```

**For Visium data:**
```python
from scripts.python.utils import prepare_visium_data
adata = prepare_visium_data(path="spaceranger/outs", count_file="filtered_feature_bc_matrix.h5")
```

---

### Step 1: Initialize GraphST Model

**Input:** Raw `adata`  
**Output:** Initialized `GraphST` model (preprocessing happens in `__init__`)

```python
from GraphST.GraphST import GraphST
import torch

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

model = GraphST(
    adata=adata,
    device=device,
    epochs=600,           # Training iterations
    dim_output=64,        # Embedding dimension
    learning_rate=0.001,
    alpha=10,             # Reconstruction loss weight
    beta=1,               # Contrastive loss weight
    datatype='10X',       # '10X', 'Stereo', or 'Slide'
    random_seed=41,
)
```

**Key Parameters:**

| Parameter | Default | When to Change |
|-----------|---------|----------------|
| `epochs` | 600 | Increase for complex tissues (1000+) |
| `dim_output` | 64 | Increase for complex tissues (128) |
| `alpha` | 10 | Decrease if overfitting (reconstruction weight) |
| `beta` | 1 | Increase for more spatial smoothing |
| `datatype` | `'10X'` | `'Stereo'` or `'Slide'` for sparse high-res data |

**What `__init__` does internally:**
- Selects highly variable genes (`preprocess()`)
- Constructs spatial interaction graph (`construct_interaction()`)
- Adds contrastive learning labels (`add_contrastive_label()`)
- Extracts features (`get_feature()`)

---

### Step 2: Train Model

**Input:** Initialized model  
**Output:** `adata` with embeddings in `adata.obsm['emb']`

```python
adata = model.train()

# Check results
print(f"Embeddings shape: {adata.obsm['emb'].shape}")
```

**Training tips:**
- GPU is 5-10× faster than CPU
- Monitor loss convergence (should decrease steadily)
- Training time: 1-10 minutes for typical datasets

---

### Step 3: Cluster Spatial Domains

**Input:** `adata` with `emb`  
**Output:** Domain labels in `adata.obs['domain']`

```python
from GraphST.utils import clustering

# Method 1: Leiden (recommended, no R dependency)
clustering(adata, n_clusters=7, method='leiden', start=0.1, end=3.0)

# Method 2: Louvain (requires 'louvain' package: pip install louvain)
clustering(adata, n_clusters=7, method='louvain', start=0.1, end=3.0)

# Method 3: Mclust (requires R + mclust package)
clustering(adata, n_clusters=7, method='mclust')

# With spatial refinement
clustering(adata, n_clusters=7, method='leiden', refinement=True, radius=50)

# Access results
print(adata.obs['domain'].value_counts())
```

**Clustering Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_clusters` | 7 | Target number of domains |
| `method` | `'mclust'` | `'leiden'`, `'louvain'`, or `'mclust'` |
| `key` | `'emb'` | Key in `obsm` for embeddings |
| `refinement` | `False` | Spatially smooth domain labels |
| `radius` | 50 | Neighborhood radius for refinement |

**Internal behavior:** `clustering()` computes PCA on `emb` → stores as `emb_pca` → searches resolution → runs clustering.

---

### Step 4: Optional Post-Processing

**Spatial refinement:**
```python
from GraphST.utils import refine_label

refined = refine_label(adata, radius=50, key='domain')
adata.obs['domain_refined'] = refined
```

**Compare clustering methods:**
```python
from scripts.python.utils import compare_clustering_methods

df_comparison = compare_clustering_methods(
    adata, methods=['leiden', 'mclust'], n_clusters=7
)
```

**Select optimal cluster count:**
```python
from scripts.python.utils import select_optimal_clusters

optimal_n, scores_df = select_optimal_clusters(
    adata, min_clusters=2, max_clusters=15, method='leiden'
)
print(f"Optimal clusters: {optimal_n}")
```

---

### Step 5: Multi-Section Integration (Optional)

```python
import anndata as ad

# Concatenate slices
adata_combined = ad.concat([adata1, adata2, adata3],
                           label='batch', index_unique='-')

# Train on combined data
model = GraphST(adata_combined, device=device, datatype='10X')
adata_combined = model.train()

# Cluster
clustering(adata_combined, n_clusters=10, method='leiden')
```

---

### Step 6: scRNA-seq Transfer / Deconvolution (Optional)

```python
# Initialize with deconvolution mode
model = GraphST(
    adata=adata,
    adata_sc=adata_sc,       # Single-cell reference
    device=device,
    deconvolution=True,
)

# Train mapping
adata, adata_sc = model.train_map()

# Project cell types to spots
from GraphST.utils import project_cell_to_spot
project_cell_to_spot(adata, adata_sc, retain_percent=0.1)

# Cell type proportions are now in adata.obs columns
```

---

## Complete Pipeline (Copy-Pasteable)

```python
from GraphST.GraphST import GraphST
from GraphST.utils import clustering
import torch

# 1. Device
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# 2. Train
model = GraphST(adata, device=device, epochs=600, random_seed=42)
adata = model.train()

# 3. Cluster
clustering(adata, n_clusters=7, method='leiden', start=0.1, end=3.0)

# 4. Export
adata.obs[['domain']].to_csv('graphst_domains.csv')
```

---

## Skill-Provided Functions

These helper functions complement the native GraphST API.

### Data Validation & Preparation
- `validate_graphst_data(adata)` → validation report dict
- `print_validation_results(results)` → formatted print
- `prepare_visium_data(path, count_file, library_id)` → load Visium data
- `create_test_data(n_spots, n_genes, n_domains, seed)` → synthetic data for testing

### Result Processing
- `summarize_graphst_results(adata)` → summary dict
- `export_graphst_results(adata, output_dir, prefix, ...)` → export domains/embeddings/adata
- `compare_clustering_methods(adata, methods, n_clusters)` → DataFrame comparing methods
- `calculate_domain_metrics(adata)` → per-domain spatial metrics
- `select_optimal_clusters(adata, min_clusters, max_clusters, method)` → (optimal_n, scores_df)

### Visualization
- `plot_domain_comparison(adata, methods, spatial_key, ncols)` → compare methods side-by-side
- `plot_embedding_umap(adata, color, use_rep)` → UMAP of embeddings
- `plot_domain_sizes(adata, method)` → bar plot of domain sizes
- `plot_spatial_heatmap(adata, features, spatial_key)` → spatial scatter of genes/features
- `plot_embedding_quality(adata, use_rep)` → 3-panel embedding diagnostics
- `plot_multi_section_domains(adatas, domain_key, ncols)` → multi-section comparison
- `create_summary_figure(adata, method, use_rep)` → comprehensive summary figure

---

## Official API — Agents Often Miss These

### 1. Correct import path for the GraphST class

```python
# CORRECT
from GraphST.GraphST import GraphST

# WRONG — 'GraphST' is the package, not the class
from GraphST import GraphST   # Imports the module, causes TypeError
```

### 2. `clustering` and `project_cell_to_spot` are imported from `GraphST` directly

```python
from GraphST import clustering, project_cell_to_spot
```

But `search_res` and `refine_label` are in `GraphST.utils`:
```python
from GraphST.utils import search_res, refine_label
```

### 3. `obsm['emb']` stores reconstruction, NOT the latent embedding

GraphST's `train()` stores the model's reconstruction output (same dim as input genes) in `obsm['emb']`, not the learned latent representation. The latent representation (`hiden_emb`, dim = `dim_output`) is kept internally as `model.hiden_feat` but is **not** exported to `obsm`.

```python
model = GraphST(adata, dim_output=64)
adata = model.train()

# adata.obsm['emb'] shape is (n_spots, n_genes), NOT (n_spots, 64)!
# The actual 64-dim embedding is at model.hiden_feat
```

### 4. `clustering()` auto-computes `emb_pca`; `search_res()` does NOT

```python
# clustering() is self-contained
clustering(adata, n_clusters=7, method='leiden')  # Works fine

# search_res() requires emb_pca to already exist
from sklearn.decomposition import PCA
pca = PCA(n_components=20, random_state=42)
adata.obsm['emb_pca'] = pca.fit_transform(adata.obsm['emb'].copy())

from GraphST.utils import search_res
res = search_res(adata, n_clusters=7, method='leiden')
```

### 5. `datatype='Stereo'` and `'Slide'` use sparse matrix encoders

These data types switch to `Encoder_sparse` and use `construct_interaction_KNN` instead of `construct_interaction`.

### 6. Louvain clustering requires extra package

```bash
pip install louvain
```

Without it, `method='louvain'` raises `ModuleNotFoundError`.

### 7. Mclust requires R + mclust

```r
install.packages("mclust")
```

If unavailable, use `method='leiden'` instead.

---

## Common Pitfalls

1. **⚠️ Wrong import path for GraphST class** — Use `from GraphST.GraphST import GraphST`, not `from GraphST import GraphST`.

2. **⚠️ Expecting `obsm['emb']` to have `dim_output` dimensions** — It has `n_genes` dimensions (reconstruction output). The latent embedding is `model.hiden_feat`.

3. **⚠️ Calling `search_res` without computing `emb_pca` first** — Always compute PCA before calling `search_res` directly.

4. **⚠️ Forgetting spatial coordinates** — `adata.obsm['spatial']` must exist before initializing `GraphST`.

5. **⚠️ Using `method='mclust'` without R/mclust installed** — Will raise `RRuntimeError`. Use `method='leiden'` as fallback.

6. **⚠️ Using `method='louvain'` without `louvain` package** — Will raise `ModuleNotFoundError`. Install with `pip install louvain`.

7. **⚠️ Passing `dim_output` but checking wrong shape** — `dim_output` controls the latent dimension, but `obsm['emb']` is reconstruction-shaped.

8. **⚠️ Not setting `random_seed`** — Results will not be reproducible across runs.

---

## Troubleshooting

### Problem: `TypeError: 'module' object is not callable`

**Cause:** `from GraphST import GraphST` imports the package module, not the class.

**Fix:**
```python
from GraphST.GraphST import GraphST
```

### Problem: `KeyError: 'spatial'`

**Cause:** Spatial coordinates missing from `adata.obsm`.

**Fix:**
```python
# For Visium
adata = sc.read_visium(path="...")

# For custom data
adata.obsm['spatial'] = adata.obs[['x_coord', 'y_coord']].values
```

### Problem: `RRuntimeError: there is no package called 'mclust'`

**Fix:** Install R mclust, or switch to Leiden:
```python
clustering(adata, n_clusters=7, method='leiden')
```

### Problem: `ModuleNotFoundError: No module named 'louvain'`

**Fix:**
```bash
pip install louvain
```

### Problem: `AssertionError: Resolution is not found`

**Cause:** `search_res` couldn't find a resolution producing exactly `n_clusters` clusters.

**Fix:** Widen the search range or use a smaller increment:
```python
search_res(adata, n_clusters=7, start=0.01, end=5.0, increment=0.005)
```

Or use `clustering()` which handles this internally.

### Problem: CUDA out of memory

**Fix:**
```python
device = torch.device('cpu')
model = GraphST(adata, device=device, dim_output=32)
```

### Problem: `obsm['emb']` shape doesn't match `dim_output`

**Fix:** This is expected behavior. `obsm['emb']` is reconstruction. Access latent embedding via `model.hiden_feat` if needed.

---

## Related Skills

- [bio-spatial-transcriptomics-domains-spagcn](../bio-spatial-transcriptomics-domains-spagcn/SKILL.md) — Graph neural network spatial domain detection
- [bio-spatial-transcriptomics-domains-stagate](../bio-spatial-transcriptomics-domains-stagate/SKILL.md) — GAT-based spatial domain detection
- [bio-spatial-transcriptomics-deconvolution-tangram](../bio-spatial-transcriptomics-deconvolution-tangram/SKILL.md) — Deep learning deconvolution

---

## References

1. Long, Y. et al. (2023). GraphST: Spatially informed clustering, integration, and deconvolution of spatial transcriptomics with graph self-supervised learning. *Nature Communications*, 14, 1155.

2. GraphST GitHub: https://github.com/JinmiaoChenLab/GraphST
