# scVelo Usage Guide

## Overview

scVelo infers directionality of cellular dynamics by analyzing the ratio of unspliced (pre-mRNA) to spliced (mature mRNA) reads. This enables prediction of future cell states and reconstruction of developmental trajectories.

## When to Use

- **Directional trajectory analysis**: Infer direction of cell state transitions
- **Predict future cell states**: Identify where cells are heading
- **Analyze gene expression dynamics**: Understand transcriptional kinetics
- **Identify driver genes**: Find genes driving cell state changes
- **Reconstruct latent time**: Order cells by progression through a process
- **Cell cycle analysis**: Study cell cycle dynamics

## Data Requirements

- AnnData object with:
  - `spliced` layer: Spliced (mature mRNA) counts
  - `unspliced` layer: Unspliced (pre-mRNA) counts
  - Pre-computed embedding (e.g., UMAP, t-SNE)
  - Cell type/cluster annotations (recommended)

## Quick Start

```python
import sys
sys.path.insert(0, 'scripts/python')

from core_analysis import (
    prepare_data_for_velocity,
    run_velocity_analysis,
    compute_latent_time_scvelo
)
from visualization import (
    plot_velocity_embedding_stream,
    plot_velocity_summary
)

# Load data (must have 'spliced' and 'unspliced' layers)
adata = sc.read_h5ad('your_data.h5ad')

# Complete analysis pipeline
adata = prepare_data_for_velocity(adata, n_top_genes=2000)
adata = run_velocity_analysis(adata, mode='stochastic')
compute_latent_time_scvelo(adata)

# Visualize
plot_velocity_summary(adata, basis='umap', save='velocity_summary.png')
```

## Step-by-Step Guide

### 1. Data Loading

```python
import scanpy as sc
import scvelo as scv

# Option A: From 10x Genomics + velocyto output (loom file)
adata = scv.read_loom('data.loom')

# Option B: From H5AD with existing spliced/unspliced layers
adata = sc.read_h5ad('data.h5ad')

# Option C: From 10x output folders
# adata = scv.read_10x_h5('filtered_feature_bc_matrix.h5')
# adata.layers['spliced'] = adata.X.copy()
# Add unspliced counts separately

# Check available layers
print(adata.layers.keys())
# Expected: dict_keys(['spliced', 'unspliced'])

# Check proportions
scv.pl.proportions(adata)
```

### 2. Preprocessing

```python
from core_analysis import prepare_data_for_velocity

# Comprehensive preprocessing
adata = prepare_data_for_velocity(
    adata,
    min_counts=10,          # Minimum counts per gene
    n_top_genes=2000,       # Number of highly variable genes
    n_pcs=30,               # Number of principal components
    n_neighbors=30,         # Number of neighbors for graph
    flavor='seurat'         # HVG selection flavor
)
```

**Manual preprocessing (alternative):**

```python
import scvelo as scv

# Filter and normalize
scv.pp.filter_and_normalize(adata, min_shared_counts=20)

# Compute moments (first and second-order)
scv.pp.moments(adata, n_pcs=30, n_neighbors=30)
```

### 3. Velocity Estimation

#### Deterministic Mode (Fastest)

```python
from core_analysis import compute_velocity

# Steady-state assumption
adata = compute_velocity(
    adata,
    mode='deterministic',
    min_r2=0.01             # Minimum R-squared for velocity genes
)
```

#### Stochastic Mode (Recommended)

```python
# Accounts for variability in unspliced counts
adata = compute_velocity(
    adata,
    mode='stochastic',
    min_r2=0.01
)
```

#### Dynamical Mode (Most Accurate)

```python
# Full transcriptional dynamics with EM algorithm
adata = compute_velocity(
    adata,
    mode='dynamical',
    min_r2=0.01,
    min_likelihood=0.01     # For dynamical model
)
```

### 4. Velocity Graph

```python
from core_analysis import compute_velocity_graph

# Build velocity graph representing transitions
compute_velocity_graph(
    adata,
    n_neighbors=30,
    n_jobs=-1               # Use all cores
)
```

### 5. Complete Pipeline

```python
from core_analysis import run_velocity_analysis

# One-step velocity analysis
adata = run_velocity_analysis(
    adata,
    mode='stochastic',
    min_r2=0.01,
    compute_graph=True,
    n_neighbors=30
)
```

### 6. Latent Time and Terminal States

```python
from core_analysis import (
    compute_terminal_states,
    compute_latent_time_scvelo
)

# Identify root and end points
compute_terminal_states(
    adata,
    group_key='clusters',
    root_groups=['Progenitor'],   # Known starting population
    end_groups=['Terminal_A', 'Terminal_B'],  # Known end populations
    n_jobs=-1
)

# Compute latent time (requires dynamical mode)
compute_latent_time_scvelo(
    adata,
    root_key='clusters',
    root_cells=['Progenitor'],
    n_dcs=10
)
```

### 7. Gene Analysis

```python
from core_analysis import (
    rank_velocity_genes,
    get_top_velocity_genes,
    compute_velocity_confidence
)

# Rank genes by velocity likelihood
rank_velocity_genes(
    adata,
    groupby='clusters',
    n_genes=100,
    min_r2=0.01
)

# Get top velocity genes
top_genes = get_top_velocity_genes(adata, n_genes=20)
print(top_genes)

# Compute velocity confidence per cell
compute_velocity_confidence(adata)
```

### 8. PAGA Velocity Graph

```python
from core_analysis import compute_paga_velocity
from visualization import plot_paga_velocity

# Compute PAGA with velocity transitions
compute_paga_velocity(
    adata,
    groups='clusters',
    threshold=0.1
)

# Visualize
plot_paga_velocity(adata, color='clusters')
```

### 9. Visualization

```python
from visualization import (
    plot_velocity_embedding_stream,
    plot_velocity_embedding_grid,
    plot_phase_portrait,
    plot_velocity_genes,
    plot_latent_time,
    plot_terminal_states,
    plot_velocity_confidence,
    plot_proportions
)

# Stream plot (most common)
plot_velocity_embedding_stream(
    adata,
    basis='umap',
    color='clusters',
    title='RNA Velocity',
    save='velocity_stream.png'
)

# Grid/arrows plot
plot_velocity_embedding_grid(
    adata,
    basis='umap',
    color='clusters',
    save='velocity_grid.png'
)

# Phase portrait for specific gene
plot_phase_portrait(
    adata,
    gene='Gene_Of_Interest',
    color='clusters',
    save='phase_portrait.png'
)

# Multiple velocity genes
plot_velocity_genes(
    adata,
    n_genes=9,
    min_r2=0.1,
    save='velocity_genes.png'
)

# Latent time
plot_latent_time(
    adata,
    basis='umap',
    save='latent_time.png'
)

# Terminal states
plot_terminal_states(
    adata,
    basis='umap',
    color='clusters',
    save='terminal_states.png'
)

# Velocity confidence
plot_velocity_confidence(
    adata,
    basis='umap',
    save='confidence.png'
)

# Spliced/unspliced proportions
plot_proportions(
    adata,
    groupby='clusters',
    save='proportions.png'
)

# Comprehensive summary
from visualization import plot_velocity_summary
plot_velocity_summary(
    adata,
    basis='umap',
    save='velocity_summary.png'
)
```

### 10. Utilities and Export

```python
from utils import (
    get_velocity_summary_stats,
    get_velocity_genes_summary,
    validate_velocity_consistency,
    export_velocity_to_dataframe,
    check_velocity_layers
)
from core_analysis import export_velocity_results

# Check data validity
check_velocity_layers(adata)

# Get summary statistics
stats = get_velocity_summary_stats(adata)
print(f"Velocity genes: {stats['n_velocity_genes']}")
print(f"Mean confidence: {stats['velocity_confidence']['mean']:.3f}")

# Get velocity genes table
velocity_genes_df = get_velocity_genes_summary(adata, n_top=20)
velocity_genes_df.to_csv('velocity_genes.csv', index=False)

# Validate results
validation = validate_velocity_consistency(
    adata,
    cell_type_key='clusters',
    min_confidence=0.5
)
print(f"High confidence fraction: {validation['confidence']['fraction_high_confidence']:.2%}")

# Export to DataFrame
results_df = export_velocity_to_dataframe(adata)
results_df.to_csv('velocity_results.csv', index=False)

# Comprehensive export
export_velocity_results(
    adata,
    output_prefix='analysis',
    obs_keys=['clusters', 'latent_time', 'velocity_confidence'],
    export_adata=True
)
```

## Velocity Mode Selection Guide

| Mode | Speed | Accuracy | Use Case |
|------|-------|----------|----------|
| `deterministic` | Fast | Basic | Initial exploration, steady-state populations |
| `stochastic` | Medium | Good | Most analyses, accounts for noise |
| `dynamical` | Slow | Best | Detailed dynamics, latent time, driver genes |

## Troubleshooting

### Low velocity confidence

```python
# Check R2 values
print(adata.var['fit_r2'].describe())

# Lower thresholds
compute_velocity(adata, mode='stochastic', min_r2=0.001)

# Check spliced/unspliced ratio
scv.pl.proportions(adata)
```

### No velocity genes found

```python
# Check data quality
from utils import estimate_min_counts
stats = estimate_min_counts(adata)
print(stats)

# Adjust filtering
adata = prepare_data_for_velocity(adata, min_counts=1)
```

### Inconsistent velocity directions

- Ensure correct root cells are specified
- Try stochastic or dynamical mode
- Check embedding quality
- Verify spliced/unspliced counts are correct

## AI Agent Test Cases

### Basic Usage
> "Run scVelo RNA velocity analysis on my data with stochastic mode"

> "Compute and visualize RNA velocity showing stream plot on UMAP"

### Advanced
> "Use scVelo dynamical mode to infer latent time and identify terminal states"

> "Create PAGA velocity graph and visualize trajectory branches"

> "Rank velocity genes and create phase portraits for top drivers"

### Troubleshooting
> "My scVelo analysis has low confidence - how to improve?"

> "Check if my data has proper spliced/unspliced layers"

## References

1. Bergen et al. (2020). Generalizing RNA velocity to transient cell states through dynamical modeling. *Nature Biotechnology*, 38(12), 1408-1414.
2. La Manno et al. (2018). RNA velocity of single cells. *Nature*, 560(7719), 494-498.
3. scVelo documentation: https://scvelo.readthedocs.io/
