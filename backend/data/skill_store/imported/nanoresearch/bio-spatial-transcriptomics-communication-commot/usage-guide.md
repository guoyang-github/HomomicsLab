# COMMOT Usage Guide

## Overview

COMMOT (COMMunication analysis by Optimal Transport) performs spatially-informed cell-cell communication analysis in spatial transcriptomics data. Unlike traditional CCC methods, COMMOT incorporates physical distance constraints and can infer communication directionality.

## When to Use

Use COMMOT when you need to:

- **Analyze spatially-resolved CCC**: Account for physical distance between cells
- **Infer communication direction**: Visualize directional signaling patterns
- **Handle heteromeric complexes**: Model multi-subunit receptor complexes
- **Work with any spatial platform**: Visium, MERFISH, Xenium, Slide-seq, etc.
- **Use optimal transport**: Prefer OT-based inference over correlation

### Typical Applications

| Application | Example |
|-------------|---------|
| Tumor microenvironment | Cancer-stroma signaling patterns |
| Developmental biology | Morphogen gradient signaling |
| Immune cell infiltration | T cell migration and activation |
| Tissue organization | Epithelial-mesenchymal communication |
| Drug response | Treatment-induced signaling changes |

## Quick Start

```python
import scanpy as sc
from scripts.python.core_analysis import prepare_data, get_lr_database, run_commot
from scripts.python.visualization import plot_communication_strength

# Load data
adata = sc.read_h5ad("spatial_data.h5ad")

# Prepare
adata = prepare_data(adata, min_counts=100)

# Load LR database
df_lr = get_lr_database('CellChat', species='human')

# Run COMMOT
run_commot(adata, df_lr, distance_threshold=200.0, database_name='cellchat')

# Visualize
plot_communication_strength(adata, 'TGFB1-TGFBR1_TGFBR2', database_name='cellchat')
```

## Step-by-Step Workflow

### Step 1: Prepare Data

#### Load Spatial Data

```python
import scanpy as sc
import numpy as np

# Load Visium data
adata = sc.read_visium("path/to/visium/data")
# OR load other spatial data
adata = sc.read_h5ad("spatial_data.h5ad")

# Verify spatial coordinates
print(adata.obsm['spatial'][:5])  # Should be N x 2 array
print(f"Coordinate range: X[{adata.obsm['spatial'][:,0].min():.1f}, {adata.obsm['spatial'][:,0].max():.1f}]")
```

#### Prepare for COMMOT

```python
from scripts.python.core_analysis import prepare_data, check_spatial_units

# Prepare data
adata = prepare_data(
    adata,
    spatial_key='spatial',
    min_counts=100,
    normalize=True,
    log1p=True,
)

# Check spatial units (important!)
check_spatial_units(adata, spatial_key='spatial')
```

#### Data Requirements Checklist

- [ ] `adata.obsm['spatial']` exists with shape (N, 2) or (N, 3)
- [ ] Coordinates are in microns (not pixels or normalized)
- [ ] Gene expression is normalized and log-transformed
- [ ] Low-quality spots filtered out

### Step 2: Choose Ligand-Receptor Database

#### Option A: Built-in CellChat Database

```python
from scripts.python.core_analysis import get_lr_database, filter_lr_database

# Load database
df_lr = get_lr_database(
    database='CellChat',  # or 'CellPhoneDB_v4.0'
    species='human',      # or 'mouse'
    signaling_type='Secreted Signaling',  # or 'Cell-Cell Contact', 'ECM-Receptor'
)

# Filter to expressed pairs
df_lr_filtered = filter_lr_database(
    df_lr,
    adata,
    min_cell_pct=0.05,  # Min 5% of cells
)
```

#### Option B: Custom Database

```python
from scripts.python.core_analysis import create_custom_lr_database

# Define custom pairs
df_lr_custom = create_custom_lr_database(
    ligands=['TGFB1', 'IL6', 'CXCL12', 'WNT5A'],
    receptors=['TGFBR1_TGFBR2', 'IL6R_IL6ST', 'CXCR4', 'FZD4'],
    pathways=['TGFb', 'IL6', 'CXCL', 'WNT'],
)
```

#### Database Comparison

| Feature | CellChat | CellPhoneDB |
|---------|----------|-------------|
| Species | Human, Mouse, Zebrafish | Human, Mouse |
| Curated pathways | Yes | No |
| Multi-subunit | Yes | Yes |
| Signaling types | Secreted, Contact, ECM | Secreted, Contact |
| Size | ~2000 pairs | ~3000 pairs |

### Step 3: Run COMMOT Analysis

#### Set Distance Threshold

```python
# Platform-specific recommendations
PLATFORM_SETTINGS = {
    'Visium_55um': {'dis_thr': 250, 'description': '4-5 spot diameters'},
    'Visium_HD': {'dis_thr': 75, 'description': 'Higher resolution'},
    'Xenium': {'dis_thr': 50, 'description': 'Subcellular resolution'},
    'MERFISH': {'dis_thr': 75, 'description': 'Single-cell'},
}
```

#### Run Analysis

```python
from scripts.python.core_analysis import run_commot

# Full parameter run
run_commot(
    adata,
    df_ligrec=df_lr_filtered,
    database_name='cellchat',
    distance_threshold=200.0,      # microns - adjust for your platform!
    heteromeric=True,
    heteromeric_rule='min',        # 'min' or 'ave'
    heteromeric_delimiter='_',
    cost_type='euc',               # 'euc' or 'euc_square'
    cot_eps_p=0.1,                 # OT entropy regularization
    cot_rho=10.0,                  # OT marginal relaxation
)
```

#### Understanding Parameters

| Parameter | When to Adjust |
|-----------|----------------|
| `distance_threshold` | Increase for long-range signaling, decrease for short-range |
| `heteromeric_rule` | Use 'min' when all subunits required, 'ave' when partial complexes functional |
| `filter_lr_database(..., min_cell_pct=...)` | Increase to reduce noise, decrease to catch rare signaling |
| `cot_eps_p` | Increase for smoother solution, decrease for sharper localization |

### Step 4: Visualize Results

#### Communication Strength

```python
from scripts.python.visualization import plot_communication_strength

# Basic strength plot
plot_communication_strength(
    adata,
    lr_pair='TGFB1-TGFBR1_TGFBR2',
    database_name='cellchat',
    summary='receiver',
    cmap='coolwarm',
)

# Save figure
plot_communication_strength(
    adata,
    lr_pair='TGFB1-TGFBR1_TGFBR2',
    database_name='cellchat',
    save_path='commot_strength.png',
)
```

#### Communication Direction

```python
from scripts.python.visualization import plot_communication_direction
from scripts.python.core_analysis import infer_communication_direction

# First infer direction
infer_communication_direction(
    adata,
    database_name='cellchat',
    pathway_name='TGFb',
    k=5,
)

# Grid plot
plot_communication_direction(
    adata,
    database_name='cellchat',
    pathway_name='TGFb',
    plot_method='grid',
    grid_density=0.5,
)

# Stream plot
plot_communication_direction(
    adata,
    lr_pair='TGFB1-TGFBR1_TGFBR2',
    plot_method='stream',
    stream_density=1.5,
)

# Cell-level vectors
plot_communication_direction(
    adata,
    lr_pair='TGFB1-TGFBR1_TGFBR2',
    plot_method='cell',
    scale=0.5,
)
```

#### Ligand-Receptor Expression

```python
from scripts.python.visualization import plot_lr_expression

plot_lr_expression(
    adata,
    ligand='TGFB1',
    receptor='TGFBR1',  # First subunit if heteromeric
    figsize=(14, 6),
)
```

### Step 5: Cluster-Level Analysis

```python
from scripts.python.core_analysis import cluster_communication
from scripts.python.visualization import (
    plot_cluster_communication_network,
    plot_cluster_communication_dotplot,
)

# Ensure clusters exist
if 'leiden' not in adata.obs:
    sc.pp.neighbors(adata)
    sc.tl.leiden(adata)

# Compute cluster communication
comm_matrix = cluster_communication(
    adata,
    cluster_key='leiden',
    database_name='CellChat',
    database_name='cellchat',
)

# Visualize
plot_cluster_communication_network(
    adata, 'CellChat', cluster_key='leiden', database_name='cellchat'
)

plot_cluster_communication_dotplot(
    adata, 'CellChat', cluster_key='leiden', database_name='cellchat'
)
```

### Step 6: Explore Results

#### Get Top LR Pairs

```python
from scripts.python.core_analysis import get_top_lr_pairs

df_top = get_top_lr_pairs(adata, n=10, database_name='cellchat')
print(df_top)
```

#### Access Communication Matrices

```python
# Get specific matrix
comm_mat = adata.obsp['commot-TGFB1-TGFBR1_TGFBR2']
print(f"Communication matrix shape: {comm_mat.shape}")

# Get sender/receiver summaries
df_sender = adata.obsm['commot-sum-sender']
df_receiver = adata.obsm['commot-sum-receiver']
```

### Step 7: Export Results

```python
from scripts.python.core_analysis import export_results

export_results(
    adata,
    output_dir='./commot_output',
    database_name='cellchat',
    include_matrices=False,  # Set True to export large matrices
)

# Also save AnnData
adata.write_h5ad('adata_commot.h5ad')
```

## Advanced Usage

### Multiple Samples

```python
# Run COMMOT on multiple samples
samples = {
    'Control': adata_ctrl,
    'Treatment': adata_treat,
}

for name, ad in samples.items():
    run_commot(ad, df_lr, distance_threshold=200.0, database_name='cellchat')

# Compare
from scripts.python.visualization import plot_communication_comparison

plot_communication_comparison(
    samples,
    lr_pair='TGFB1-TGFBR1_TGFBR2',
    database_name='cellchat',
)
```

### DEG Analysis (requires tradeSeq)

```python
from scripts.python.core_analysis import detect_communication_deg

# Requires raw counts in adata.layers['counts']
df_deg, df_yhat = detect_communication_deg(
    adata,
    database_name='CellChat',
    pathway_name='TGFb',
    summary='receiver',
    n_var_genes=2000,
)
```

### Spatial Autocorrelation

```python
from scripts.python.core_analysis import communication_spatial_autocorrelation

df_autocorr = communication_spatial_autocorrelation(
    adata,
    database_name='CellChat',
    database_name='cellchat',
)
```

## Best Practices

### 1. Distance Threshold Selection

| Platform | Recommended Range | Rationale |
|----------|-------------------|-----------|
| Visium | 200-500 μm | 4-9 spot diameters |
| Visium HD | 50-100 μm | Higher resolution |
| Xenium | 30-100 μm | Subcellular spots |
| MERFISH | 50-100 μm | Single-cell |
| Slide-seq | 100-200 μm | 10μm beads |

### 2. Database Selection

- **CellChat**: Use when you want curated pathway annotations
- **CellPhoneDB**: Use when you need more comprehensive coverage
- **Custom**: Use when you have specific biological questions

### 3. Computational Considerations

- **Memory**: Large datasets may require downsampling or regional analysis
- **Speed**: Limit LR pairs to those expressed in your data
- **Parallelization**: Not natively supported; process samples separately

### 4. Biological Interpretation

- Validate top hits with known literature
- Check ligand-receptor expression patterns
- Consider alternative explanations (co-expression vs. communication)
- Use direction inference cautiously - it's model-based

## Troubleshooting

### No communication detected

```python
# Check 1: Reduce distance threshold
df_top = get_top_lr_pairs(adata, n=20, database_name='cellchat')
print(df_top)  # If empty, check below

# Check 2: Verify LR expression
print('TGFB1' in adata.var_names)
print('TGFBR1' in adata.var_names)

# Check 3: Check spatial units
check_spatial_units(adata)

# Check 4: Relax filtering to catch rare signaling
df_lr = filter_lr_database(df_lr, adata, min_cell_pct=0.01)
```

### Out of memory

```python
# Strategy 1: Filter LR pairs more strictly
df_lr_filtered = filter_lr_database(df_lr, adata, min_cell_pct=0.2)

# Strategy 2: Subsample spots
adata_sub = sc.pp.subsample(adata, n_obs=5000, copy=True)

# Strategy 3: Analyze by region
mask = adata.obsm['spatial'][:, 0] < 5000  # Subregion
adata_sub = adata[mask].copy()
```

### Visualization issues

```python
# Issue: 'spatial' not found
print(adata.obsm.keys())  # Check available keys
# Solution: Rename your coordinates
# adata.obsm['spatial'] = adata.obsm['X_spatial']

# Issue: Direction plot fails
# Solution: Run direction inference first
infer_communication_direction(adata, database_name='cellchat', pathway_name='TGFb')
```

## Common Pitfalls

1. **Wrong spatial units**: Always verify coordinates are in microns
2. **Too many LR pairs**: Filter to expressed pairs for speed
3. **Distance threshold too small**: May miss long-range signaling
4. **Ignoring heteromeric complexes**: Set `heteromeric=True` for accuracy
5. **Over-interpreting direction**: Direction inference is model-based

## References

1. **Primary Paper**
   Cang et al. (2023). Screening cell–cell communication in spatial transcriptomics via collective optimal transport. *Nature Methods* 20:218-228.

2. **Documentation**
   https://commot.readthedocs.io/

3. **GitHub**
   https://github.com/zcang/COMMOT

4. **Related Methods**
   - CellChat: Jin et al. (2021). Nature Communications.
   - CellPhoneDB: Efremova et al. (2020). Nature Protocols.
   - Optimal Transport: Peyré & Cuturi (2019). Computational Optimal Transport.

## See Also

- Full API: [SKILL.md](SKILL.md)
- Example: [examples/example_basic.py](examples/example_basic.py)
- COMMOT docs: https://commot.readthedocs.io/
