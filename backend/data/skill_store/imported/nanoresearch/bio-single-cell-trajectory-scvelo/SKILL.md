---
name: bio-single-cell-trajectory-scvelo
description: |
  RNA velocity analysis using scVelo. Infers cellular dynamics directionality by distinguishing 
  unspliced (pre-mRNA) from spliced (mature mRNA) counts. Three estimation modes available:
  deterministic (steady-state assumption, fastest), stochastic (second-order moments, balanced),
  dynamical (full transcriptional dynamics with EM, most accurate). Core capabilities include
  velocity vector computation, velocity graph construction, latent time inference, terminal state
  identification, driver gene ranking, and PAGA velocity graph integration.
tool_type: python
primary_tool: scvelo
languages: [python]
keywords: ["single-cell", "trajectory", "RNA-velocity", "scvelo", "dynamics", "velocity", 
           "pseudotime", "spliced", "unspliced", "latent-time", "cell-development", "python"]
---

## Version Compatibility

- **Python**: >=3.8
- **scvelo**: >=0.2.5
- **scanpy**: >=1.9
- **anndata**: >=0.8
- **numpy**: >=1.20
- **pandas**: >=1.3

## Installation

```bash
pip install scvelo
```

## Data Requirements

Input AnnData must contain:
- `layers['spliced']`: Spliced (mature mRNA) count matrix
- `layers['unspliced']`: Unspliced (pre-mRNA) count matrix
- `obsm['X_umap']` or other embedding: For velocity visualization
- `obs['clusters']` or cell type annotation: For grouping analysis (recommended)

**Data Validation:**
```python
from utils import check_velocity_layers
check_velocity_layers(adata)  # Raises ValueError if layers missing
```

## Core Analysis Workflow

### 1. Data Loading

**Data Sources:**
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
```

**Data Validation:**
```python
from utils import check_velocity_layers
check_velocity_layers(adata)  # Raises ValueError if 'spliced'/'unspliced' missing
print(adata.layers.keys())  # Expected: dict_keys(['spliced', 'unspliced'])
```

### 2. Preprocessing

Function: `prepare_data_for_velocity(adata, **kwargs)`

**Purpose:** Filter genes, normalize, compute moments for velocity estimation.

**Key Steps:**
1. Filter genes by min_counts (default: 10) in both spliced and unspliced
2. Normalize and log-transform
3. Select highly variable genes (default: 2000)
4. Compute PCA (default: 30 components)
5. Compute neighbors graph (default: 30 neighbors)
6. Calculate first and second-order moments (Ms, Mu layers)

```python
from core_analysis import prepare_data_for_velocity

adata = prepare_data_for_velocity(
    adata,
    min_counts=10,          # Lower for sparse data (5-10), higher for dense
    n_top_genes=2000,       # 2000 standard; increase for complex tissues
    n_pcs=30,               # PCA components
    n_neighbors=30,         # Balance local vs global (20-50 typical)
    flavor='seurat'         # HVG selection flavor
)
```

**Manual preprocessing (alternative):**
```python
import scvelo as scv
scv.pp.filter_and_normalize(adata, min_shared_counts=20)
scv.pp.moments(adata, n_pcs=30, n_neighbors=30)
```

### 3. Velocity Estimation

#### Mode Selection Decision Tree:
```
Data quality good (high unspliced counts)?
├── Yes → Use 'dynamical' for best accuracy
│         → Enables latent time, driver genes, reaction rates
├── No/Unsure → Use 'stochastic' (recommended default)
│               → Better than deterministic for transient states
└── Quick exploration only → Use 'deterministic'
                            → Fastest, steady-state assumption
```

**Mode Characteristics:**

| Mode | Speed | Accuracy | Best For |
|------|-------|----------|----------|
| `deterministic` | ~seconds | Basic | Initial exploration, steady-state |
| `stochastic` | ~10-30s | Good | Most analyses, default choice |
| `dynamical` | Minutes-hours | Best | High-quality data, detailed dynamics |

Function: `compute_velocity(adata, mode='stochastic', **kwargs)`

**Process:**
1. Estimate gamma (splicing/degradation ratio) per gene
2. Fit regression: unspliced vs spliced
3. Calculate R² to select velocity genes
4. Compute velocity vectors: v = (unspliced - gamma * spliced)

**Examples:**
```python
from core_analysis import compute_velocity

# Deterministic (fastest)
adata = compute_velocity(adata, mode='deterministic', min_r2=0.01)

# Stochastic (recommended default)
adata = compute_velocity(adata, mode='stochastic', min_r2=0.01)

# Dynamical (most accurate)
adata = compute_velocity(adata, mode='dynamical', min_r2=0.01, min_likelihood=0.01)
```

**Key Parameters:**
- `min_r2`: R² threshold for velocity gene selection (default: 0.01)
  - Increase (0.05-0.1) for fewer, higher-confidence genes
  - Decrease (0.001) if too few velocity genes found

**Output:**
- `layers['velocity']`: Velocity vectors
- `var['velocity_genes']`: Boolean mask for velocity genes
- `var['fit_r2']`: R² values per gene
- `var['fit_gamma']`: Estimated gamma values

### 4. Velocity Graph

Function: `compute_velocity_graph(adata, n_neighbors=30, n_jobs=-1)`

**Purpose:** Build directed graph representing likely cell transitions based on velocity directions.

**Process:**
1. Find neighbors for each cell in embedding space
2. Compute cosine similarity between velocity and neighbor positions
3. Positive similarity = likely transition

```python
from core_analysis import compute_velocity_graph

compute_velocity_graph(adata, n_neighbors=30, n_jobs=-1)
```

**Output:**
- `uns['velocity_graph']`: Directed transition probabilities
- `obs['velocity_self_transition']`: Self-loop probabilities

### 5. Complete Pipeline

Function: `run_velocity_analysis(adata, **kwargs)`

One-step analysis combining preprocessing, velocity estimation, and graph construction.

```python
from core_analysis import run_velocity_analysis

adata = run_velocity_analysis(
    adata,
    mode='stochastic',
    min_r2=0.01,
    compute_graph=True,
    n_neighbors=30
)
```

Runs: preprocessing → velocity → graph

### 6. Latent Time and Terminal States

#### Terminal State Identification

Function: `compute_terminal_states(adata, group_key=None, root_groups=None, end_groups=None, **kwargs)`

**Purpose:** Identify root (start) and terminal (end) cell populations.

```python
from core_analysis import compute_terminal_states

# Annotation-guided
compute_terminal_states(
    adata,
    group_key='clusters',
    root_groups=['Progenitor'],           # Known starting population
    end_groups=['Terminal_A', 'Terminal_B']  # Known end populations
)

# Data-driven (automatic)
compute_terminal_states(adata, n_jobs=-1)
```

#### Latent Time Inference (Dynamical Mode Only)

Function: `compute_latent_time_scvelo(adata, root_key=None, root_cells=None, **kwargs)`

**Requirements:** Must use dynamical mode for velocity + specify root cells

```python
from core_analysis import compute_latent_time_scvelo

# By cluster/group
compute_latent_time_scvelo(adata, root_key='clusters', root_cells=['Progenitor'])

# By cell indices
root_idx = np.where(adata.obs['clusters'] == 'Progenitor')[0]
adata.obs['root_cells'] = False
adata.obs.iloc[root_idx, adata.obs.columns.get_loc('root_cells')] = True
compute_latent_time_scvelo(adata, n_dcs=10)
```

**Output:**
- `obs['latent_time']`: Continuous time (0 to ~1)
- `obs['root_cells']`, `obs['end_points']`: Boolean assignments

### 7. Gene Analysis

Function: `rank_velocity_genes(adata, groupby='clusters', n_genes=100, **kwargs)`

**Purpose:** Identify genes driving cell state transitions.

```python
from core_analysis import (
    rank_velocity_genes,
    get_top_velocity_genes,
    compute_velocity_confidence
)

# Rank genes by velocity likelihood
rank_velocity_genes(adata, groupby='clusters', n_genes=100, min_r2=0.01)

# Get top velocity genes
top_genes = get_top_velocity_genes(adata, n_genes=20)

# Compute per-cell velocity confidence
compute_velocity_confidence(adata)
```

**Metrics:**
- Likelihood contribution to velocity model
- R² of velocity fit
- Phase portrait trajectory alignment

**Output:** `uns['rank_velocity_genes']` - Ranked gene lists per group

### 8. PAGA Velocity Graph

Function: `compute_paga_velocity(adata, groups='clusters', **kwargs)`

**Purpose:** Combine PAGA (partition-based graph abstraction) with velocity for cluster-level trajectory inference.

**Use when:** Multiple lineage branches, discrete cell types with clear transitions.

```python
from core_analysis import compute_paga_velocity
from visualization import plot_paga_velocity

# Requires PAGA to be computed first
# cellcycle.tl.paga(adata, groups='clusters')  # if cellcycle available

compute_paga_velocity(adata, groups='clusters', threshold=0.1)
plot_paga_velocity(adata, color='clusters')
```

### 9. Visualization

```python
from visualization import (
    plot_velocity_embedding_stream,    # Most common - flow lines
    plot_velocity_embedding_grid,      # Arrow grid
    plot_phase_portrait,               # Gene spliced vs unspliced
    plot_velocity_genes,               # Multiple phase portraits
    plot_latent_time,                  # Time coloring (dynamical only)
    plot_terminal_states,              # Root/end highlights
    plot_velocity_confidence,          # Confidence coloring
    plot_velocity_summary,             # Multi-panel comprehensive
    plot_proportions                   # Spliced/unspliced ratios
)

# Primary visualizations
plot_velocity_embedding_stream(adata, basis='umap', color='clusters', save='stream.png')
plot_velocity_embedding_grid(adata, basis='umap', color='clusters', save='grid.png')
plot_phase_portrait(adata, gene='GeneName', color='clusters', save='phase.png')
plot_velocity_genes(adata, n_genes=9, min_r2=0.1, save='genes.png')
plot_latent_time(adata, basis='umap', save='time.png')
plot_terminal_states(adata, basis='umap', color='clusters', save='states.png')
plot_velocity_confidence(adata, basis='umap', save='confidence.png')
plot_velocity_summary(adata, basis='umap', save='summary.png')
plot_proportions(adata, groupby='clusters', save='proportions.png')
```

### 10. Utilities and Export

```python
from utils import (
    check_velocity_layers,           # Verify data validity
    check_velocity_computed,         # Check velocity computed
    estimate_min_counts,             # Parameter guidance
    get_velocity_summary_stats,      # Summary statistics
    get_velocity_genes_summary,      # Gene ranking table
    validate_velocity_consistency,   # Quality check
    export_velocity_to_dataframe,    # Export to pandas
    merge_velocity_results           # Merge results
)
from core_analysis import export_velocity_results

# Validation
check_velocity_layers(adata)

# Parameter guidance
stats = estimate_min_counts(adata)  # Returns recommended_min_counts

# Summary statistics
stats = get_velocity_summary_stats(adata)
print(f"Velocity genes: {stats['n_velocity_genes']}")

# Gene table
velocity_genes_df = get_velocity_genes_summary(adata, n_top=20)
velocity_genes_df.to_csv('velocity_genes.csv', index=False)

# Quality validation
validation = validate_velocity_consistency(adata, cell_type_key='clusters')
print(f"High confidence: {validation['confidence']['fraction_high_confidence']:.2%}")

# Export
results_df = export_velocity_to_dataframe(adata)
results_df.to_csv('velocity_results.csv', index=False)

# Comprehensive export
export_velocity_results(adata, output_prefix='analysis/', export_adata=True)
```

## Complete Pipeline Functions

### Full Analysis Pipeline
```python
from core_analysis import run_velocity_analysis

adata = run_velocity_analysis(
    adata,
    mode='stochastic',
    min_r2=0.01,
    compute_graph=True,
    n_neighbors=30
)
```

This runs: preprocessing → velocity estimation → velocity graph construction

## Visualization Functions

### Primary Visualizations

1. **Velocity Stream Plot** (most common)
   ```python
   from visualization import plot_velocity_embedding_stream
   plot_velocity_embedding_stream(adata, basis='umap', color='clusters')
   ```
   Shows velocity as continuous flow lines on embedding.

2. **Velocity Grid/Arrows**
   ```python
   from visualization import plot_velocity_embedding_grid
   plot_velocity_embedding_grid(adata, basis='umap', color='clusters')
   ```
   Shows velocity as arrows averaged in grid cells.

3. **Phase Portrait**
   ```python
   from visualization import plot_phase_portrait
   plot_phase_portrait(adata, gene='GeneName', color='clusters')
   ```
   Scatter plot of spliced vs unspliced counts for a specific gene.

4. **Latent Time**
   ```python
   from visualization import plot_latent_time
   plot_latent_time(adata, basis='umap')
   ```
   Color cells by inferred latent time (requires dynamical mode).

5. **Velocity Genes Grid**
   ```python
   from visualization import plot_velocity_genes
   plot_velocity_genes(adata, n_genes=9, min_r2=0.1)
   ```
   Phase portraits for top velocity genes.

6. **Comprehensive Summary**
   ```python
   from visualization import plot_velocity_summary
   plot_velocity_summary(adata, basis='umap')
   ```
   Multi-panel figure with stream, grid, clusters, latent time, confidence.

## Utility Functions

### Data Validation
```python
from utils import (
    check_velocity_layers,        # Verify spliced/unspliced exist
    check_velocity_computed,       # Verify velocity is computed
    validate_velocity_consistency  # Check results quality
)
```

### Parameter Guidance
```python
from utils import estimate_min_counts

stats = estimate_min_counts(adata)
# Returns: recommended_min_counts, distribution percentiles
```

### Results Export
```python
from utils import (
    get_velocity_summary_stats,    # Dict with n_velocity_genes, confidence, etc.
    get_velocity_genes_summary,    # DataFrame of top velocity genes
    export_velocity_to_dataframe,  # Export to pandas DataFrame
    merge_velocity_results         # Merge results into original adata
)

from core_analysis import export_velocity_results
export_velocity_results(adata, output_prefix='results/')
# Exports: CSV files, H5AD, plots
```

## Common Analysis Patterns

### Pattern 1: Quick Exploration
```python
adata = prepare_data_for_velocity(adata, n_top_genes=2000)
adata = run_velocity_analysis(adata, mode='deterministic')
plot_velocity_embedding_stream(adata, basis='umap', color='clusters')
```

### Pattern 2: Standard Analysis (Recommended)
```python
adata = prepare_data_for_velocity(adata, n_top_genes=2000)
adata = run_velocity_analysis(adata, mode='stochastic')
compute_terminal_states(adata, group_key='clusters')
rank_velocity_genes(adata, groupby='clusters')
plot_velocity_summary(adata, basis='umap')
```

### Pattern 3: Deep Dynamics Analysis
```python
adata = prepare_data_for_velocity(adata, n_top_genes=3000)
adata = compute_velocity(adata, mode='dynamical', min_r2=0.01)
compute_velocity_graph(adata)
compute_terminal_states(adata, root_groups=['Progenitor'])
compute_latent_time_scvelo(adata, root_cells=['Progenitor'])
rank_velocity_genes(adata, groupby='clusters')
export_velocity_results(adata, output_prefix='deep_analysis/')
```

### Pattern 4: Multi-lineage with PAGA
```python
# Standard velocity
adata = prepare_data_for_velocity(adata)
adata = run_velocity_analysis(adata, mode='stochastic')

# Add PAGA trajectory
cellcycle.tl.paga(adata, groups='clusters')  # If cellcycle available
compute_paga_velocity(adata, groups='clusters')
plot_paga_velocity(adata, color='clusters')
```

## Troubleshooting Common Issues

### Issue: "No velocity genes found"
**Diagnosis:**
```python
from utils import estimate_min_counts
print(estimate_min_counts(adata))
```

**Solutions:**
1. Lower min_r2 threshold: `compute_velocity(adata, min_r2=0.001)`
2. Lower min_counts: `prepare_data_for_velocity(adata, min_counts=1)`
3. Check spliced/unspliced ratio: `scv.pl.proportions(adata)`

### Issue: "Low velocity confidence"
**Solutions:**
1. Use stochastic or dynamical mode instead of deterministic
2. Increase n_neighbors: `prepare_data_for_velocity(adata, n_neighbors=50)`
3. Check data quality - ensure sufficient unspliced counts

### Issue: "Inconsistent velocity directions"
**Diagnosis:** Check embedding quality and root cell specification

**Solutions:**
1. Specify correct root cells explicitly
2. Recompute embedding with different parameters
3. Use dynamical mode for better accuracy

### Issue: "Dynamical mode too slow"
**Solutions:**
1. Subsample cells: `adata_subset = adata[::2].copy()`
2. Reduce n_top_genes: `prepare_data_for_velocity(adata, n_top_genes=1500)`
3. Use stochastic mode for initial analysis, dynamical for final

## Output Description

### AnnData Modifications

**Layers:**
- `spliced`, `unspliced`: Input count matrices
- `Ms`, `Mu`: First-order moments (smoothed)
- `velocity`: Computed velocity vectors
- `velocity_u`: Velocity for unspliced (dynamical mode)

**obs (cell-level):**
- `velocity_self_transition`: Probability of self-loop
- `velocity_confidence`: Confidence in velocity assignment
- `latent_time`: Inferred developmental time (dynamical)
- `root_cells`, `end_points`: Terminal state assignments
- `fit_likelihood`: Likelihood of cell fit (dynamical)

**var (gene-level):**
- `velocity_genes`: Boolean for genes used in velocity
- `fit_r2`: R² of velocity fit
- `fit_gamma`: Estimated degradation/splicing ratio
- `fit_beta`: Estimated splicing rate (dynamical)
- `fit_likelihood`: Gene fit likelihood (dynamical)

**uns:**
- `velocyto_params`: Parameters used for velocity computation
- `velocity_graph`: Directed transition graph (sparse matrix)
- `rank_velocity_genes`: Ranked gene lists
- `paga`: PAGA graph with velocity transitions

## Module Structure

```
scripts/python/
├── core_analysis.py      # prepare_data_for_velocity, compute_velocity,
│                         # compute_velocity_graph, run_velocity_analysis,
│                         # compute_latent_time_scvelo, compute_terminal_states,
│                         # rank_velocity_genes, compute_paga_velocity,
│                         # score_cell_cycle, export_velocity_results
├── visualization.py      # plot_velocity_embedding_stream, plot_velocity_embedding_grid,
│                         # plot_phase_portrait, plot_velocity_genes, plot_latent_time,
│                         # plot_paga_velocity, plot_velocity_confidence,
│                         # plot_terminal_states, plot_velocity_summary, plot_proportions
└── utils.py              # check_velocity_layers, check_velocity_computed,
                          # estimate_min_counts, optimize_velocity_params,
                          # get_velocity_genes_summary, get_velocity_summary_stats,
                          validate_velocity_consistency, export_velocity_to_dataframe,
                          merge_velocity_results, split_by_trajectory_branch
```

## Related Skills

- [bio-single-cell-trajectory-monocle3-r](../bio-single-cell-trajectory-monocle3-r/SKILL.md) - Alternative trajectory inference with pseudotime
- [bio-single-cell-trajectory-cytotrace-r](../bio-single-cell-trajectory-cytotrace-r/SKILL.md) - Stemness scoring and developmental potential
- [bio-single-cell-clustering](../bio-single-cell-clustering/SKILL.md) - Cell clustering for velocity groups
- [bio-single-cell-pseudotime-dpt](../bio-single-cell-pseudotime-dpt/SKILL.md) - Diffusion pseudotime analysis

## References

1. Bergen et al. (2020). Generalizing RNA velocity to transient cell states through dynamical modeling. *Nature Biotechnology*, 38(12), 1408-1414. https://doi.org/10.1038/s41587-020-0591-3
2. La Manno et al. (2018). RNA velocity of single cells. *Nature*, 560(7719), 494-498. https://doi.org/10.1038/s41586-018-0414-6
3. scVelo documentation: https://scvelo.readthedocs.io/
4. scVelo GitHub: https://github.com/theislab/scvelo
