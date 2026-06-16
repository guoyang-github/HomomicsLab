# STAGATE Usage Guide

## Overview

STAGATE (Spatial Transcriptomics using Adaptive Graph Attention Auto-encoder) is a deep learning method for spatial domain identification in spatial transcriptomics. It combines gene expression with spatial coordinates through a graph attention mechanism.

## When to Use

Use STAGATE when you need to:

- **Identify spatial domains** with attention-based deep learning
- **Denoise gene expression** using spatial context
- **Integrate multiple slices** into 3D domains
- **Process large datasets** with batch training
- **Analyze complex spatial patterns** that traditional clustering misses

### Typical Applications

| Application | Example |
|-------------|---------|
| Brain tissue | Identify cortical layers |
| Tumor microenvironment | Distinguish tumor/stroma/border |
| Developmental biology | Segment tissue regions |
| Multi-slice integration | Build 3D tissue models |

## Quick Start

```python
import scanpy as sc
from scripts.python.core_analysis import (
    prepare_data, build_spatial_network, train_stagate, mclust_clustering
)
from scripts.python.visualization import plot_domains

# Load data
adata = sc.read_h5ad("visium_data.h5ad")

# Run complete workflow
adata = prepare_data(adata, n_top_genes=3000)
build_spatial_network(adata, rad_cutoff=150)
adata = train_stagate(adata, n_epochs=1000)
adata = mclust_clustering(adata, n_clusters=7)
plot_domains(adata, domain_key='mclust')
```

## Step-by-Step Workflow

### Step 1: Load Data

```python
import scanpy as sc

# Visium data
adata = sc.read_visium("path/to/visium/data")
# Or from h5ad
adata = sc.read_h5ad("spatial_data.h5ad")

# Check spatial coordinates
print(adata.obsm['spatial'][:5])
```

### Step 2: Prepare Data

```python
from scripts.python.core_analysis import prepare_data

adata = prepare_data(
    adata,
    min_counts=100,       # Filter low-quality spots
    n_top_genes=3000,     # Number of HVGs
    normalize=True,
    log1p=True,
)
```

#### Data Requirements Checklist

- [ ] Raw counts or normalized expression
- [ ] Spatial coordinates in `adata.obsm['spatial']`
- [ ] Minimum quality filtering
- [ ] Highly variable genes selected

### Step 3: Build Spatial Network

#### 2D Network

```python
from scripts.python.core_analysis import build_spatial_network

# For Visium (55μm spots)
build_spatial_network(adata, rad_cutoff=150, model='Radius')

# Alternative: KNN
build_spatial_network(adata, k_cutoff=10, model='KNN')

# Check network statistics
from scripts.python.core_analysis import plot_network_stats
plot_network_stats(adata)
```

#### 3D Network (Multi-slice)

```python
from scripts.python.core_analysis import build_3d_spatial_network

# Concatenate slices first
adata_concat = sc.concat(
    [adata1, adata2, adata3],
    label='section',
    keys=['1', '2', '3']
)

# Build 3D network
build_3d_spatial_network(
    adata_concat,
    rad_cutoff_2d=150,    # Within-slice radius
    rad_cutoff_z=100,     # Between-slice radius
    section_key='section',
    section_order=['1', '2', '3'],
)
```

### Step 4: Train STAGATE

```python
from scripts.python.core_analysis import train_stagate

# Basic training
adata = train_stagate(
    adata,
    hidden_dims=[512, 30],  # [hidden_dim, embedding_dim]
    n_epochs=1000,
    lr=0.001,
    key_added='STAGATE',
    device='cuda',          # Use GPU
)

# With denoising
adata = train_stagate(
    adata,
    hidden_dims=[512, 30],
    n_epochs=1000,
    save_reconstruction=True,  # Save denoised expression
)
```

#### Training Parameters Guide

| Parameter | Small Data (<5k) | Large Data (>20k) |
|-----------|------------------|-------------------|
| `hidden_dims` | [512, 30] | [256, 30] |
| `n_epochs` | 1000 | 500 |
| `lr` | 0.001 | 0.001 |
| `device` | cuda | cuda or cpu |

### Step 5: Cluster Domains

#### mclust (Recommended)

```python
from scripts.python.core_analysis import mclust_clustering

adata = mclust_clustering(
    adata,
    n_clusters=7,
    used_obsm='STAGATE',
    model_names='EEE',  # Model type (see mclust docs)
)
```

#### Leiden

```python
from scripts.python.core_analysis import leiden_clustering

adata = leiden_clustering(
    adata,
    resolution=0.5,
    used_obsm='STAGATE',
    n_neighbors=15,
)
```

#### Choosing Cluster Number

```python
# Try multiple cluster numbers
for n in range(5, 12):
    adata = mclust_clustering(adata, n_clusters=n, key_added=f'mclust_{n}')
    print(f"n={n}: {adata.obs[f'mclust_{n}'].nunique()} clusters")
```

### Step 6: Visualize

#### Spatial Domains

```python
from scripts.python.visualization import plot_domains

plot_domains(
    adata,
    domain_key='mclust',
    spot_size=1.5,
    palette='tab20',
    save_path='domains.png',
)
```

#### UMAP of Embeddings

```python
from scripts.python.visualization import plot_embedding_umap

plot_embedding_umap(
    adata,
    embedding_key='STAGATE',
    color_key='mclust',
    save_path='umap.png',
)
```

#### Compare Clusterings

```python
from scripts.python.visualization import plot_domains_comparison

plot_domains_comparison(
    adata,
    domain_keys=['mclust', 'stagate_leiden'],
    n_cols=2,
)
```

#### Domain Statistics

```python
from scripts.python.visualization import plot_domain_proportions

# Overall proportions
plot_domain_proportions(adata, domain_key='mclust')

# By group (e.g., section)
plot_domain_proportions(adata, domain_key='mclust', group_key='section')
```

### Step 7: Denoising Visualization

```python
from scripts.python.visualization import plot_denoising_comparison

# Compare raw vs denoised
plot_denoising_comparison(
    adata,
    gene='GENE_NAME',
    save_path='denoising.png',
)
```

### Step 8: Export Results

```python
from scripts.python.core_analysis import export_results

export_results(
    adata,
    output_dir='./stagate_output',
    domain_key='mclust',
    embedding_key='STAGATE',
)
```

## Advanced Usage

### Batch Processing for Large Datasets

```python
from scripts.python.core_analysis import create_batch_data, train_stagate

# Split data
batch_list = create_batch_data(
    adata,
    num_batch_x=3,
    num_batch_y=3,
    plot_stats=True,
)

# Train each batch
for i, batch in enumerate(batch_list):
    batch = prepare_data(batch, n_top_genes=3000)
    build_spatial_network(batch, rad_cutoff=150)
    batch = train_stagate(batch, n_epochs=500, key_added='STAGATE')
    batch.write_h5ad(f'batch_{i}_stagate.h5ad')
```

### Multi-sample Analysis

```python
from scripts.python.visualization import plot_multi_sample_domains

# Dictionary of samples
samples = {
    'Control': adata_ctrl,
    'Treatment': adata_treat,
}

# Process each
for name, ad in samples.items():
    ad = prepare_data(ad)
    build_spatial_network(ad, rad_cutoff=150)
    ad = train_stagate(ad, n_epochs=1000)
    ad = mclust_clustering(ad, n_clusters=7)
    samples[name] = ad

# Compare
plot_multi_sample_domains(samples, domain_key='mclust')
```

### 3D Domain Visualization

```python
from scripts.python.visualization import plot_aligned_slices

plot_aligned_slices(
    adata_concat,
    section_key='section',
    domain_key='mclust',
    save_path='3d_domains.png',
)
```

## Best Practices

### 1. Radius Selection

| Platform | Recommended | Rationale |
|----------|-------------|-----------|
| Visium | 150-200 μm | ~3-4 spot diameters |
| Visium HD | 30-50 μm | Higher resolution |
| Xenium | 20-50 μm | Subcellular |
| MERFISH | 30-60 μm | Single-cell |

### 2. Embedding Dimension

- Standard (2D): 30 dimensions
- High complexity: 50 dimensions
- Simple tissues: 20 dimensions

### 3. Training Epochs

- Small data (<5k spots): 1000 epochs
- Medium data (5-20k): 500-1000 epochs
- Large data (>20k): 500 epochs

### 4. GPU vs CPU

```python
# Auto-detect
adata = train_stagate(adata, device=None)

# Force GPU
adata = train_stagate(adata, device='cuda')

# Force CPU (if GPU OOM)
adata = train_stagate(adata, device='cpu')
```

## Troubleshooting

### GPU Out of Memory

```python
# Solution 1: Reduce batch size (use batch processing)
batch_list = create_batch_data(adata, num_batch_x=4, num_batch_y=4)

# Solution 2: Reduce hidden dimensions
adata = train_stagate(adata, hidden_dims=[256, 30])

# Solution 3: Use CPU
adata = train_stagate(adata, device='cpu')
```

### Poor Domain Separation

```python
# Solution 1: Adjust network radius
build_spatial_network(adata, rad_cutoff=200)  # Larger neighborhood

# Solution 2: Increase embedding dimension
adata = train_stagate(adata, hidden_dims=[512, 50])

# Solution 3: Train longer
adata = train_stagate(adata, n_epochs=2000)
```

### Too Many Small Domains

```python
# Solution 1: Reduce n_clusters
adata = mclust_clustering(adata, n_clusters=5)

# Solution 2: Lower Leiden resolution
adata = leiden_clustering(adata, resolution=0.3)

# Solution 3: Increase spatial radius
build_spatial_network(adata, rad_cutoff=250)
```

### mclust Not Available

```python
# Use Leiden instead
adata = leiden_clustering(adata, resolution=0.5, used_obsm='STAGATE')

# Or install rpy2
# pip install rpy2
```

## Performance Tips

1. **Use GPU**: 10x faster than CPU
2. **Start Small**: Test with fewer epochs first
3. **Batch Processing**: For datasets >50k spots
4. **Monitor Loss**: Stop early if converged
5. **Cache Networks**: Save Spatial_Net for reuse

## Common Pitfalls

1. **Wrong radius**: Too small = noisy domains, too large = over-smoothing
2. **Wrong n_clusters**: Too many = fragmentation, too few = merging
3. **Not using HVGs**: Slow training with all genes
4. **Ignoring spatial units**: Ensure coordinates are in microns

## References

1. Dong & Zhang (2022). Deciphering spatial domains from spatially resolved transcriptomics with an adaptive graph attention auto-encoder. *Nature Communications*.

2. STAGATE Documentation: https://stagate.readthedocs.io/

3. PyTorch Geometric: https://pytorch-geometric.readthedocs.io/

## See Also

- Full API: [SKILL.md](SKILL.md)
- Example: [examples/example_basic.py](examples/example_basic.py)
- STAGATE GitHub: https://github.com/QIFEIDKN/STAGATE
