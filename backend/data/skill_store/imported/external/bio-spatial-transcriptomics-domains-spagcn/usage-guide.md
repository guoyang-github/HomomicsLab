# SpaGCN Usage Guide

## Overview

SpaGCN (Spatial Graph Convolutional Network) is a deep learning method that identifies spatial domains by integrating gene expression, spatial location, and optionally histology information using graph convolutional networks.

## Key Features

- **Graph Convolutional Networks**: Captures spatial dependencies through graph structure
- **Multi-modal Integration**: Combines expression, location, and histology
- **Deep Iterative Clustering**: Refines clusters using network structure
- **Spatially Variable Genes**: Identifies domain-specific markers
- **Meta Gene Discovery**: Builds composite gene signatures

## When to Use

- Identify tissue structures with spatial coherence
- Analyze data where tissue morphology correlates with expression
- Find spatially variable genes across domains
- Integrate histology for improved domain detection
- Process both single-sample and multi-sample datasets

## Requirements

- Python >= 3.9
- SpaGCN >= 1.2.7
- PyTorch >= 1.12.0
- scanpy >= 1.10.0
- OpenCV (for histology integration)

## Installation

```bash
# Standard installation
pip install SpaGCN

# With histology support
pip install SpaGCN opencv-python

# Development version
pip install git+https://github.com/jianhuupenn/SpaGCN.git
```

## Quick Start

### Basic Usage

```python
import SpaGCN as spg
import scanpy as sc

# Load data
adata = sc.read_h5ad("visium_data.h5ad")

# Preprocess
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# Calculate adjacency matrix
x_pixel = adata.obs["x_pixel"].tolist()
y_pixel = adata.obs["y_pixel"].tolist()
x_array = adata.obs["array_row"].tolist()
y_array = adata.obs["array_col"].tolist()

adj = spg.calculate_adj_matrix(
    x=x_array, y=y_array,
    histology=False
)

# Search for optimal l
l = spg.search_l(p=0.5, adj=adj, start=0.01, end=1000)

# Search for optimal resolution
res = spg.search_res(adata, adj, l, target_num=7, start=0.7, step=0.1)

# Run SpaGCN
clf = spg.SpaGCN()
clf.set_l(l)
clf.train(adata, adj, init_spa=True, init="louvain", res=res)
y_pred, prob = clf.predict()

adata.obs["pred"] = y_pred
```

## Step-by-Step

### 1. Data Preparation

```python
import SpaGCN as spg
import scanpy as sc
import numpy as np

# Load spatial data
adata = sc.read_h5ad("visium_data.h5ad")

# Basic QC
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)

# Filter special genes
spg.prefilter_genes(adata, min_cells=3)
spg.prefilter_specialgenes(adata)

# Normalization
adata.raw = adata
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
```

### 2. Adjacency Matrix Calculation

#### Without Histology

```python
x_array = adata.obs["array_row"].tolist()
y_array = adata.obs["array_col"].tolist()

adj = spg.calculate_adj_matrix(
    x=x_array,
    y=y_array,
    histology=False
)
```

#### With Histology

```python
import cv2

# Load H&E image
img = cv2.imread("tissue_hires_image.tif")

x_pixel = adata.obs["x_pixel"].tolist()
y_pixel = adata.obs["y_pixel"].tolist()
x_array = adata.obs["array_row"].tolist()
y_array = adata.obs["array_col"].tolist()

# Parameters:
# - beta: area of each spot (default=49 for Visium)
# - alpha: weight for histology (default=1)
adj = spg.calculate_adj_matrix(
    x=x_array, y=y_array,
    x_pixel=x_pixel, y_pixel=y_pixel,
    image=img,
    beta=49,
    alpha=1,
    histology=True
)
```

### 3. Parameter Search

#### Find l (spatial weight)

```python
# p = percentage of total expression contributed by neighborhoods
# Typical values: 0.3 (local), 0.5 (balanced), 0.7 (global)
p = 0.5
l = spg.search_l(p, adj, start=0.01, end=1000, tol=0.01, max_run=100)
```

#### Find resolution (for target cluster count)

```python
# If you know the number of clusters you want
n_clusters = 7
res = spg.search_res(
    adata, adj, l, n_clusters,
    start=0.7, step=0.1,
    tol=5e-3, lr=0.05, max_epochs=20
)
```

### 4. Run SpaGCN

```python
import random
import torch

# Set seeds for reproducibility
r_seed = t_seed = n_seed = 100
random.seed(r_seed)
torch.manual_seed(t_seed)
np.random.seed(n_seed)

# Initialize model
clf = spg.SpaGCN()
clf.set_l(l)

# Train
clf.train(
    adata=adata,
    adj=adj,
    num_pcs=50,           # Number of principal components
    lr=0.005,             # Learning rate
    max_epochs=2000,      # Training epochs
    weight_decay=0,       # L2 regularization
    opt="admin",          # Optimizer
    init_spa=True,        # Initialize with spatial
    init="louvain",       # Initialization method
    n_neighbors=10,       # For Louvain
    res=res,              # Resolution
    tol=1e-3              # Convergence tolerance
)

# Predict
y_pred, prob = clf.predict()
adata.obs["pred"] = y_pred
adata.obs["pred"] = adata.obs["pred"].astype('category')
```

### 5. Domain Refinement (Optional)

```python
# Calculate 2D adjacency for refinement
adj_2d = spg.calculate_adj_matrix(x=x_array, y=y_array, histology=False)

# Refine predictions
refined_pred = spg.refine(
    sample_id=adata.obs.index.tolist(),
    pred=adata.obs["pred"].tolist(),
    dis=adj_2d,
    shape="hexagon"  # "hexagon" for Visium, "square" for ST
)

adata.obs["refined_pred"] = refined_pred
adata.obs["refined_pred"] = adata.obs["refined_pred"].astype('category')
```

### 6. Visualization

```python
import matplotlib.pyplot as plt

# Plot spatial domains
plot_color = ["#F56867", "#FEB915", "#C798EE", "#59BE86", "#7495D3",
              "#D1D1D1", "#6D1A9C", "#15821E", "#3A84E6", "#997273"]

num_celltype = len(adata.obs["pred"].unique())
adata.uns["pred_colors"] = list(plot_color[:num_celltype])

ax = sc.pl.scatter(
    adata, alpha=1,
    x="y_pixel", y="x_pixel",
    color="pred",
    size=100000/adata.shape[0],
    show=False
)
ax.set_aspect('equal', 'box')
ax.axes.invert_yaxis()
plt.savefig("domains.png", dpi=600)
plt.close()
```

### 7. Identify SVGs (Spatially Variable Genes)

```python
# Read raw data for SVG detection
raw = adata.raw.to_adata()
raw.obs["pred"] = adata.obs["pred"].astype('category')
raw.obs["x_array"] = x_array
raw.obs["y_array"] = y_array

# Use domain 0 as example
target = 0

# Set filtering criteria
min_in_group_fraction = 0.8
min_in_out_group_ratio = 1
min_fold_change = 1.5

# Search radius
adj_2d = spg.calculate_adj_matrix(x=x_array, y=y_array, histology=False)
start = np.quantile(adj_2d[adj_2d != 0], q=0.001)
end = np.quantile(adj_2d[adj_2d != 0], q=0.1)

r = spg.search_radius(
    target_cluster=target,
    cell_id=raw.obs.index.tolist(),
    x=x_array, y=y_array,
    pred=raw.obs["pred"].tolist(),
    start=start, end=end,
    num_min=10, num_max=14
)

# Find neighboring domains
nbr_domains = spg.find_neighbor_clusters(
    target_cluster=target,
    cell_id=raw.obs.index.tolist(),
    x=raw.obs["x_array"].tolist(),
    y=raw.obs["y_array"].tolist(),
    pred=raw.obs["pred"].tolist(),
    radius=r,
    ratio=1/2
)

nbr_domains = nbr_domains[0:3]

# Rank genes
de_genes_info = spg.rank_genes_groups(
    input_adata=raw,
    target_cluster=target,
    nbr_list=nbr_domains,
    label_col="pred",
    adj_nbr=True,
    log=True
)

# Filter
de_genes_info = de_genes_info[de_genes_info["pvals_adj"] < 0.05]
filtered_info = de_genes_info[
    (de_genes_info["in_out_group_ratio"] > min_in_out_group_ratio) &
    (de_genes_info["in_group_fraction"] > min_in_group_fraction) &
    (de_genes_info["fold_change"] > min_fold_change)
]

print(f"SVGs for domain {target}:", filtered_info["genes"].tolist())
```

### 8. Meta Gene Identification

```python
# Use domain 2 as example
target = 2
start_gene = "GFAP"  # Start with a known marker

meta_name, meta_exp = spg.find_meta_gene(
    input_adata=raw,
    pred=raw.obs["pred"].tolist(),
    target_domain=target,
    start_gene=start_gene,
    mean_diff=0,
    early_stop=True,
    max_iter=3
)

print(f"Meta gene: {meta_name}")
raw.obs["meta"] = meta_exp
```

## Hyperparameter Selection

### l Parameter

Controls the spatial weight in the adjacency matrix:

| p value | Spatial scale | Typical l range |
|---------|---------------|-----------------|
| 0.3 | Local | 0.1 - 10 |
| 0.5 | Balanced | 1 - 100 |
| 0.7 | Global | 10 - 1000 |

**Guidance:**
- Smaller l = more local neighborhoods
- Larger l = more global structure
- Start with p=0.5 and adjust based on results

### Resolution

Controls the number of clusters:

| Resolution | Expected clusters |
|------------|-------------------|
| 0.2 - 0.4 | 3 - 5 |
| 0.4 - 0.8 | 6 - 10 |
| 0.8 - 1.5 | 10+ |

### Histology Parameters

- **alpha**: Weight for histology
  - 0 = ignore histology
  - 1 = balanced (default)
  - >1 = favor histology
  
- **beta**: Spot area for color extraction
  - 49 for Visium (default)
  - Adjust based on spot size

## Multi-Sample Analysis

### Multiple Adjacent Sections

```python
# Load multiple samples
adata1 = sc.read("sample1.h5ad")
adata2 = sc.read("sample2.h5ad")

# Process each
for adata in [adata1, adata2]:
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)

# Search l for each
adj1 = spg.calculate_adj_matrix(x=x1, y=y1, histology=False)
adj2 = spg.calculate_adj_matrix(x=x2, y=y2, histology=False)

l1 = spg.search_l(p=0.5, adj=adj1)
l2 = spg.search_l(p=0.5, adj=adj2)

l_list = [l1, l2]

# Multi-section SpaGCN
from anndata import AnnData

adata_list = [adata1, adata2]
adj_list = [adj1, adj2]
res = 0.2

clf = spg.multiSpaGCN()
clf.train(
    adata_list, adj_list, l_list,
    init_spa=True, init="louvain",
    res=res, max_epochs=200
)

y_pred, prob = clf.predict()
adata_all = clf.adata_all
adata_all.obs["pred"] = y_pred
```

## AI Agent Test Cases

### Basic Usage
> "Run SpaGCN on my Visium data"

```python
domains = run_spagcn(adata_prep, adj, l=l, resolution=0.4)
```

### With Known Cluster Count
> "Identify 7 spatial domains using SpaGCN"

```python
res = search_optimal_resolution(adata_prep, adj, l=l, target_clusters=7)
domains = run_spagcn(adata_prep, adj, l=l, resolution=res)
```

### With Histology
> "Integrate H&E image with SpaGCN"

```python
adj = calculate_adjacency_matrix(
    adata_prep, x_pixel_column="x_pixel",
    y_pixel_column="y_pixel", histology=True, image=he_img
)
```

### SVG Identification
> "Find spatially variable genes for domain 0"

```python
svgs = identify_svgs(adata, target_domain=0, min_fold_change=1.5)
```

### Meta Gene Discovery
> "Build a meta gene signature starting from GFAP"

```python
meta_name, meta_exp = find_meta_gene(
    adata, target_domain=2, start_gene="GFAP"
)
```

## Best Practices

1. **Gene Selection**: Use 1000-3000 highly variable genes
2. **l Parameter**: Search with p=0.5 as starting point
3. **Resolution**: Use search_res if target cluster count known
4. **Histology**: Include when tissue morphology is informative
5. **Refinement**: Apply for cleaner domain boundaries
6. **Seeds**: Set for reproducibility
7. **Convergence**: Monitor delta_label in training output

## Troubleshooting

### Out of Memory

```python
# Reduce number of genes
sc.pp.highly_variable_genes(adata, n_top_genes=1000)
adata = adata[:, adata.var.highly_variable]

# Reduce PCs
clf.train(adata, adj, num_pcs=30)
```

### Poor Convergence

```python
# Increase epochs
clf.train(adata, adj, max_epochs=5000)

# Decrease tolerance
clf.train(adata, adj, tol=5e-4)
```

### Unrealistic Domains

```python
# Adjust l parameter
l = search_optimal_l(adj, target_p=0.3)  # More local

# Or adjust resolution
res = 0.3  # Fewer clusters
```

## References

1. Hu et al. (2021). SpaGCN: Integrating gene expression, spatial location and histology to identify spatial domains and spatially variable genes by graph convolutional network. *Nature Methods*, 18(11), 1342-1351.
2. SpaGCN GitHub: https://github.com/jianhuupenn/SpaGCN
3. Tutorial: https://github.com/jianhuupenn/SpaGCN/tree/master/tutorial
