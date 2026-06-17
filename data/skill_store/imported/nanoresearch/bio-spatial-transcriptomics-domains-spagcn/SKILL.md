---
name: bio-spatial-transcriptomics-domains-spagcn
description: Spatial domain identification using SpaGCN with graph convolutional networks and histology integration
tool_type: python
primary_tool: SpaGCN
supported_tools: [scanpy, torch, numpy, pandas, matplotlib]
languages: [python]
keywords: ["spatial", "domains", "SpaGCN", "graph", "clustering", "tissue-structure", "GCN", "histology", "SVG", "spatially-variable-genes"]
code_location: scripts/python/
version_compatibility:
  python: ">=3.9"
  SpaGCN: ">=1.2.7"
  scanpy: ">=1.10.0"
  torch: ">=1.12.0"
---

# SpaGCN Spatial Domain Identification

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| Python | >= 3.9 | |
| SpaGCN | >= 1.2.7 | Core package; installs `louvain` as dependency |
| scanpy | >= 1.10.0 | Single-cell analysis |
| anndata | >= 0.10.0 | Data structures |
| torch | >= 1.12.0 | Deep learning framework |
| numpy | >= 1.24.0 | Numerical computing |
| pandas | >= 2.0.0 | Data manipulation |
| matplotlib | >= 3.7.0 | Visualization |
| seaborn | >= 0.12.0 | Statistical visualization |
| opencv-python | optional | Required only for histology integration |

## Installation

```bash
pip install SpaGCN

# With histology support
pip install SpaGCN opencv-python
```

## Skill Overview

**Use this skill when you need to:**
- Identify tissue structures / spatial domains from Visium, ST, or Slide-seq data
- Integrate H&E histology images to improve domain detection
- Find spatially variable genes (SVGs) enriched in specific domains
- Build composite meta-gene signatures from known markers
- Analyze multiple adjacent tissue sections jointly

**Do NOT use this skill when:**
- You only need cell type annotation (use `bio-single-cell-annotation-*` skills instead)
- You need cell type deconvolution (use `bio-spatial-transcriptomics-deconvolution-*` instead)
- Data lacks spatial coordinates (use standard clustering instead)

## Core Workflow

### Step 1: Data Preparation [Raw] → [Normalized]

Normalize counts, log-transform, and select highly variable genes. SpaGCN expects log-normalized data on 1,000–3,000 HVGs.

```python
from scripts.python.core_analysis import prepare_data

adata_prep = prepare_data(
    adata,
    min_cells=3,       # min cells expressing a gene
    min_genes=200,     # min genes per spot
    n_top_genes=3000,  # HVG count (1000-3000 typical)
    filter_mitochondrial=True
)
```

| Parameter | Default | When to change |
|-----------|---------|----------------|
| `n_top_genes` | 3000 | Reduce to 1000 for speed or small datasets |
| `filter_mitochondrial` | True | Set False if MT genes are biologically relevant |
| `hvg_selection` | True | Set False only if you have <1000 genes |

**Output:** `adata_prep` with `.raw` stored for later SVG detection.

### Step 2: Adjacency Matrix [Normalized] → [Neighbors]

Build the spatial graph. **Without histology** (most common):

```python
from scripts.python.core_analysis import calculate_adjacency_matrix

adj = calculate_adjacency_matrix(
    adata_prep,
    x_column="array_col",
    y_column="array_row",
    histology=False
)
```

**With H&E histology**:

```python
import cv2
img = cv2.imread("tissue_hires_image.tif")

adj = calculate_adjacency_matrix(
    adata_prep,
    x_column="array_col",
    y_column="array_row",
    x_pixel_column="x_pixel",
    y_pixel_column="y_pixel",
    histology=True,
    image=img,
    alpha=1.0,   # histology weight: 0=ignore, 1=balanced, >1=favor
    beta=49      # spot area; 49 for Visium
)
```

**Pitfall:** `calculate_adjacency_matrix` wraps `spg.calculate_adj_matrix`, which expects plain Python lists for `x` and `y`. The wrapper extracts them from `adata.obs` columns for you.

### Step 3: Parameter Search [Neighbors] → [Params]

Search two hyperparameters:

**`l`** — spatial weight controlling neighborhood influence:

```python
from scripts.python.core_analysis import search_optimal_l

l = search_optimal_l(adj, target_p=0.5)
```

| `target_p` | Spatial scale | Typical `l` | Use case |
|-----------|---------------|-------------|----------|
| 0.3 | Local | 0.1–10 | Fine structures |
| 0.5 | Balanced | 1–100 | General use (recommended start) |
| 0.7 | Global | 10–1000 | Large domains |

**`resolution`** — Louvain resolution for target cluster count:

```python
from scripts.python.core_analysis import search_optimal_resolution

res = search_optimal_resolution(
    adata_prep, adj, l=l,
    target_clusters=7,   # desired number of domains
    max_epochs=10        # low epochs for speed during search
)
```

### Step 4: Run SpaGCN [Params+Normalized] → [Domains]

```python
from scripts.python.core_analysis import run_spagcn

import random, torch, numpy as np
random.seed(100)
torch.manual_seed(100)
np.random.seed(100)

domains = run_spagcn(
    adata_prep,
    adj,
    l=l,
    resolution=res,
    max_epochs=2000,
    num_pcs=50,
    lr=0.005,
    init_spa=True,
    init="louvain"
)

adata.obs["spagcn_domain"] = domains
adata.obs["spagcn_domain"] = adata.obs["spagcn_domain"].astype("category")
```

| Parameter | Default | Notes |
|-----------|---------|-------|
| `max_epochs` | 2000 | Increase to 5000 if convergence is poor |
| `num_pcs` | 50 | Reduce to 30 if out of memory |
| `lr` | 0.005 | Keep default unless convergence issues |
| `init` | `"louvain"` | `"kmeans"` alternative; requires `n_clusters` |
| `opt` | `"admin"` | `"adam"` alternative optimizer |

### Step 5: Domain Refinement (Optional) [Domains] → [Refined]

Spatial smoothing that assigns each spot to the most common domain among its neighbors:

```python
from scripts.python.core_analysis import refine_domains

refined = refine_domains(
    adata,
    domains,
    shape="hexagon"   # "square" for ST platform
)

adata.obs["spagcn_domain_refined"] = refined
adata.obs["spagcn_domain_refined"] = adata.obs["spagcn_domain_refined"].astype("category")
```

**Pitfall:** Refinement internally rebuilds a 2D adjacency matrix (no histology) from `array_col`/`array_row`. It does NOT reuse the histology-weighted `adj` from Step 2.

### Step 6: Identify SVGs [Domains] → [SVGs]

Find spatially variable genes for a specific domain:

```python
from scripts.python.core_analysis import identify_svgs

svgs = identify_svgs(
    adata,
    target_domain=0,
    domain_column="spagcn_domain",
    min_in_group_fraction=0.8,
    min_in_out_group_ratio=1.0,
    min_fold_change=1.5
)
```

**⚠️ Critical:** `identify_svgs` hard-codes `log=True` when calling SpaGCN's `rank_genes_groups`. If your data was NOT log-transformed during preparation, SVG results will be wrong. Use `prepare_data` with default `log_transform=True`.

### Step 7: Meta Gene Discovery [Domains] → [MetaGene]

Build a composite gene signature starting from a known marker:

```python
from scripts.python.core_analysis import find_meta_gene

meta_name, meta_exp = find_meta_gene(
    adata,
    target_domain=2,
    start_gene="GFAP",
    max_iter=3
)

adata.obs["meta_gene"] = meta_exp
```

### Step 8: Visualization

```python
from scripts.python.visualization import (
    plot_spatial_domains,
    plot_domain_comparison,
    plot_gene_expression,
    plot_svg_results,
    plot_meta_gene
)

# Spatial domains
plot_spatial_domains(adata, domain_column="spagcn_domain")

# Side-by-side comparison
plot_domain_comparison(
    adata,
    domain_columns=["spagcn_domain", "spagcn_domain_refined"],
    labels=["Original", "Refined"]
)

# Gene expression
plot_gene_expression(adata, gene="GFAP")

# Top SVGs
plot_svg_results(adata, svgs, top_n=6)

# Meta gene
plot_meta_gene(adata, meta_exp=meta_exp, meta_name=meta_name)
```

## Complete Pipeline

Single copy-pasteable workflow for a Visium sample:

```python
import scanpy as sc
import random, torch, numpy as np
from scripts.python.core_analysis import (
    prepare_data, calculate_adjacency_matrix,
    search_optimal_l, search_optimal_resolution,
    run_spagcn, refine_domains, identify_svgs
)
from scripts.python.visualization import plot_spatial_domains

# Load
adata = sc.read_h5ad("visium_sample.h5ad")

# Preprocess
adata_prep = prepare_data(adata, n_top_genes=3000)

# Adjacency
adj = calculate_adjacency_matrix(adata_prep, histology=False)

# Search params
l = search_optimal_l(adj, target_p=0.5)
res = search_optimal_resolution(adata_prep, adj, l=l, target_clusters=7)

# Train
random.seed(100); torch.manual_seed(100); np.random.seed(100)
domains = run_spagcn(adata_prep, adj, l=l, resolution=res)
adata.obs["spagcn_domain"] = domains.astype("category")

# Refine
refined = refine_domains(adata, domains, shape="hexagon")
adata.obs["spagcn_domain_refined"] = refined.astype("category")

# SVGs
svgs = identify_svgs(adata, target_domain=0, domain_column="spagcn_domain")

# Plot
plot_spatial_domains(adata, domain_column="spagcn_domain")
```

## Skill-Provided Functions

### Analysis Pipeline

| Function | Purpose |
|----------|---------|
| `prepare_data(adata, ...)` | Filter, normalize, log1p, HVG selection |
| `calculate_adjacency_matrix(adata, ...)` | Build spatial graph with/without histology |
| `search_optimal_l(adj, target_p=0.5)` | Find spatial weight `l` |
| `search_optimal_resolution(adata, adj, l, target_clusters)` | Find resolution for target domain count |
| `run_spagcn(adata, adj, l, resolution, ...)` | Train SpaGCN and predict domains |
| `run_spagcn_multi_sample(adata_list, adj_list, l_list, ...)` | Joint multi-section analysis |
| `refine_domains(adata, predictions, shape="hexagon")` | Spatial smoothing of predictions |
| `identify_svgs(adata, target_domain, ...)` | Find domain-specific spatially variable genes |
| `find_meta_gene(adata, target_domain, start_gene, ...)` | Build composite meta-gene signature |

### Spatial Statistics

| Function | Purpose |
|----------|---------|
| `calculate_moran_i(adata, gene, x_column, y_column, k=5, knn=True)` | Moran's I spatial autocorrelation for one gene |
| `calculate_moran_i_genes(adata, genes, ...)` | Moran's I for multiple genes |
| `find_neighbor_clusters(adata, target_domain, ...)` | Find spatially adjacent domains |

### Visualization

| Function | Purpose |
|----------|---------|
| `plot_spatial_domains(adata, domain_column, ...)` | Scatter plot of domains on tissue |
| `plot_domain_comparison(adata, domain_columns, labels, ...)` | Side-by-side domain panels |
| `plot_gene_expression(adata, gene, ...)` | Spatial gene expression map |
| `plot_domain_heatmap(adata, genes, domain_column, ...)` | Mean expression heatmap by domain |
| `plot_svg_results(adata, svg_results, top_n=6, ...)` | Grid of top SVG expression maps |
| `plot_meta_gene(adata, meta_exp, meta_name, ...)` | Meta gene spatial map |
| `plot_multiple_genes(adata, genes, ...)` | Multi-panel gene expression grid |

## Official API — Agents Often Miss These

SpaGCN's native API has several traps that wrappers hide or that agents frequently misuse when bypassing wrappers.

### 1. `spg.SpaGCN()` requires `set_l()` before `train()`

```python
clf = spg.SpaGCN()
clf.set_l(l)          # REQUIRED — do not skip
clf.train(adata, adj, res=resolution, ...)
```

### 2. `clf.train()` uses `res=...`, not `resolution=...`

Native parameter is `res`; wrapper maps `resolution` → `res` for you.

### 3. `spg.search_res` parameter is `target_num`, not `target_clusters`

Wrapper `search_optimal_resolution` renames it to `target_clusters` for clarity. If using native API directly, use `target_num`.

### 4. `spg.calculate_adj_matrix` needs plain lists, not pandas Series

```python
# Correct native usage
x = adata.obs["array_col"].tolist()
y = adata.obs["array_row"].tolist()
adj = spg.calculate_adj_matrix(x=x, y=y, histology=False)
```

### 5. `spg.Moran_I` needs a pandas DataFrame and coordinates

⚠️ **NOT** `data_array, adjacency_matrix`.

```python
import pandas as pd
genes_exp = pd.DataFrame({"gene1": exp_values}, index=adata.obs_names)
mi = spg.Moran_I(genes_exp, x_list, y_list, k=5, knn=True)
```

Wrapper `calculate_moran_i(adata, gene="gene1")` handles this conversion.

### 6. `spg.rank_genes_groups` ≠ `scanpy.tl.rank_genes_groups`

Same name, completely different signatures. SpaGCN's version:

```python
spg.rank_genes_groups(
    input_adata=adata,
    target_cluster=0,
    nbr_list=[1, 2, 3],
    label_col="pred",
    adj_nbr=True,
    log=True
)
```

### 7. Domain refinement needs 2D adjacency without histology

```python
adj_2d = spg.calculate_adj_matrix(x=x, y=y, histology=False)
refined = spg.refine(
    sample_id=adata.obs.index.tolist(),
    pred=domains.tolist(),
    dis=adj_2d,
    shape="hexagon"
)
```

### 8. SVG detection should use raw counts

SpaGCN tutorials use `adata.raw.to_adata()` for SVG identification because differential expression should be performed on raw or normalized counts, not on the HVG-subset matrix. Wrapper `identify_svgs` operates on the passed `adata`; if you need raw counts, pass `adata.raw.to_adata()`.

### 9. `spg.multiSpaGCN()` combines samples into `clf.adata_all`

After training and prediction, the combined AnnData is available as `clf.adata_all`.

### 10. `search_l` may return `None`

If `l` cannot be found in the requested range, `spg.search_l` returns `None`. Wrapper `search_optimal_l` automatically retries with an expanded range (`start/10`, `end*10`) before returning `None`.

## Common Pitfalls

1. **⚠️ Forgetting to set seeds before `run_spagcn`** — Results are non-deterministic without `random.seed()`, `torch.manual_seed()`, `np.random.seed()`.

2. **⚠️ Using `identify_svgs` on HVG-subset data** — SVG detection needs all genes (or at least more than just HVGs). Pass `adata.raw.to_adata()` if you kept `.raw` during preparation.

3. **⚠️ Mismatching `domain_column` defaults** — `run_spagcn` returns a bare numpy array. `identify_svgs` defaults to `domain_column="pred"`. If you stored domains as `"spagcn_domain"`, pass it explicitly.

4. **⚠️ Histology image coordinate system** — `x_pixel` and `y_pixel` must match the image's pixel coordinate system. `array_row`/`array_col` are grid indices and cannot substitute for pixel coordinates when `histology=True`.

5. **⚠️ `calculate_adjacency_matrix` default coordinates** — Defaults are `x_column="array_col"`, `y_column="array_row"`. If your data uses `"x"` / `"y"` or `"array_col"` / `"array_row"` swapped, domains will be spatially scrambled.

6. **⚠️ `refine_domains` expects original `adata`, not `adata_prep`** — Refinement uses spatial coordinates from `adata.obs`, so pass the original object with coordinate columns intact.

7. **⚠️ `run_spagcn_multi_sample` requires consistent gene sets** — All samples in `adata_list` must have the same variables (genes) because `multiSpaGCN` concatenates them internally.

## Troubleshooting

### Out of Memory

```python
# Reduce HVGs
adata_prep = prepare_data(adata, n_top_genes=1000)

# Reduce PCs
domains = run_spagcn(adata_prep, adj, l=l, num_pcs=30)
```

### Poor Convergence / Unstable Domains

```python
# More epochs, lower tolerance
domains = run_spagcn(adata_prep, adj, l=l, max_epochs=5000, tol=1e-4)

# Or use local spatial weight
l = search_optimal_l(adj, target_p=0.3)
```

### Too Many or Too Few Domains

```python
# Use search_optimal_resolution with adjusted target
target = 10 if too_few else 3
res = search_optimal_resolution(adata_prep, adj, l=l, target_clusters=target)
```

### `search_optimal_l` returns None

```python
# Manually set l based on typical values
l = 1.0   # balanced
# or
l = 10.0  # global
```

### Import warnings about `louvain` vs `leidenalg`

SpaGCN depends on `louvain`. Warnings about `leidenalg` superseding `louvain` are harmless; the package still functions correctly.

## Related Skills

- [bio-spatial-transcriptomics-domains-bayesspace-r](../bio-spatial-transcriptomics-domains-bayesspace-r) — Bayesian spatial clustering
- [bio-spatial-transcriptomics-domains-stagate](../bio-spatial-transcriptomics-domains-stagate) — GCN-based domain detection
- [bio-spatial-transcriptomics-domains-graphst](../bio-spatial-transcriptomics-domains-graphst) — Graph-based clustering with deep embedding
- [bio-spatial-transcriptomics-deconvolution-cell2location](../bio-spatial-transcriptomics-deconvolution-cell2location) — Cell type deconvolution

## References

1. Hu et al. (2021). SpaGCN: Integrating gene expression, spatial location and histology to identify spatial domains and spatially variable genes by graph convolutional network. *Nature Methods*, 18(11), 1342-1351.
2. SpaGCN GitHub: https://github.com/jianhuupenn/SpaGCN
3. SpaGCN Tutorial: https://github.com/jianhuupenn/SpaGCN/tree/master/tutorial
