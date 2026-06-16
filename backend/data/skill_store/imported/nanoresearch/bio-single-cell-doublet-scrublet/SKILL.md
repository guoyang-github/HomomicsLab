---
name: bio-single-cell-doublet-scrublet
description: |
  Scrublet detects doublets in single-cell RNA-seq data by simulating artificial doublets
  from random cell pairs and scoring each cell's similarity to these simulated profiles.
  Uses a k-nearest-neighbor classifier to calculate a continuous doublet score for each transcriptome.
tool_type: python
primary_tool: scrublet
languages: [python]
keywords: ["single-cell", "doublet-detection", "Scrublet", "QC", "simulation", "python", "scanpy"]
---

## Version Compatibility

- **Python**: >=3.8
- **scrublet**: >=0.2.3
- **scanpy**: >=1.9.0
- **scikit-learn**: >=1.0
- **scipy**: >=1.7.0

## Installation

```bash
pip install scrublet
```

Or install from source:
```bash
git clone https://github.com/swolock/scrublet.git
cd scrublet
pip install -r requirements.txt
pip install --upgrade .
```

## Data Requirements

Input requirements:
- **Raw count matrix**: scipy sparse matrix or ndarray, shape (n_cells, n_genes)
- **Format**: Raw (unnormalized) UMI-based transcript counts
- **Best practice**: Run on individual samples separately (not merged datasets)

## Core Analysis Workflow

### 1. Initialize Scrublet

**Class:** `Scrublet()`

**Purpose:** Initialize Scrublet object with counts matrix and parameters.

**Key Parameters:**
- `counts_matrix`: scipy sparse matrix or ndarray (n_cells, n_genes)
- `total_counts`: Optional array of total UMI counts per cell
- `sim_doublet_ratio`: Number of simulated doublets relative to observed cells (default: 2.0)
- `n_neighbors`: Number of neighbors for KNN graph (default: round(0.5 * sqrt(n_cells)))
- `expected_doublet_rate`: Estimated doublet rate (default: 0.1)
- `stdev_doublet_rate`: Uncertainty in expected rate (default: 0.02)
- `random_state`: Random seed (default: 0)

**Example:**
```python
import scrublet as scr
import scanpy as sc

# Load data
adata = sc.read_10x_mtx('filtered_feature_bc_matrix/')

# Calculate expected doublet rate (~0.8% per 1000 cells)
n_cells = adata.n_obs
expected_rate = n_cells / 1000 * 0.008

# Initialize Scrublet
scrub = scr.Scrublet(
    adata.X,
    expected_doublet_rate=expected_rate,
    sim_doublet_ratio=2.0,
    random_state=42
)
```

### 2. Run Doublet Detection

**Method:** `scrub_doublets()`

**Purpose:** Run the complete doublet detection pipeline.

**Key Parameters:**
- `synthetic_doublet_umi_subsampling`: Rate for sampling UMIs when creating synthetic doublets (default: 1.0)
- `use_approx_neighbors`: Use approximate NN (annoy) (default: True)
- `distance_metric`: Distance metric for NN search (default: 'euclidean')
- `get_doublet_neighbor_parents`: Return parent transcriptomes of doublet neighbors (default: False)
- `min_counts`: Gene filtering threshold (default: 3)
- `min_cells`: Gene filtering threshold (default: 3)
- `min_gene_variability_pctl`: Keep top percentile of variable genes (default: 85)
- `log_transform`: Log-transform counts (default: False)
- `mean_center`: Center data (default: True)
- `normalize_variance`: Normalize variance (default: True)
- `n_prin_comps`: Number of principal components (default: 30)
- `svd_solver`: SVD solver (default: 'arpack')
- `verbose`: Print progress (default: True)

**Returns:**
- `doublet_scores`: Continuous doublet scores (0 to 1) for each cell
- `predicted_doublets`: Boolean array of predicted doublets

**Example:**
```python
doublet_scores, predicted_doublets = scrub.scrub_doublets(
    min_counts=2,
    min_cells=3,
    min_gene_variability_pctl=85,
    n_prin_comps=30,
    synthetic_doublet_umi_subsampling=1.0
)

# Add to AnnData
adata.obs['doublet_score'] = doublet_scores
adata.obs['predicted_doublet'] = predicted_doublets

print(f"Detected {sum(predicted_doublets)} doublets ({100*sum(predicted_doublets)/len(predicted_doublets):.1f}%)")
print(f"Scrublet threshold: {scrub.threshold_:.3f}")
```

### 3. Call Doublets with Custom Threshold

**Method:** `call_doublets()`

**Purpose:** Call transcriptomes as doublets or singlets with custom threshold.

**Key Parameters:**
- `threshold`: Doublet score threshold (default: None, auto-detected)
- `verbose`: Print summary statistics (default: True)

**Sets Attributes:**
- `predicted_doublets_`: Boolean mask of predicted doublets
- `z_scores_`: Z-scores for confidence
- `threshold_`: Doublet score threshold
- `detected_doublet_rate_`: Fraction of cells called as doublets
- `detectable_doublet_fraction_`: Fraction of simulated doublets above threshold
- `overall_doublet_rate_`: Estimated overall doublet rate

**Example:**
```python
# Automatic threshold
scrub.call_doublets()

# Manual threshold
scrub.call_doublets(threshold=0.25)
predicted_doublets = scrub.predicted_doublets_
```

### 4. Visualization

**Method:** `plot_histogram()`

**Purpose:** Plot histogram of doublet scores for observed and simulated transcriptomes.

**Parameters:**
- `scale_hist_obs`: Scale for observed histogram (default: 'log')
- `scale_hist_sim`: Scale for simulated histogram (default: 'linear')
- `fig_size`: Figure size (default: (8, 3))

**Example:**
```python
import matplotlib.pyplot as plt

# Plot histogram
scrub.plot_histogram()
plt.savefig('doublet_histogram.pdf')

# Show threshold
print(f"Threshold: {scrub.threshold_:.3f}")
```

**Method:** `set_embedding()` and `plot_embedding()`

**Purpose:** Visualize doublet predictions on 2-D embedding.

**Example:**
```python
# Preprocess for visualization
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata)
sc.pp.pca(adata)
sc.pp.neighbors(adata)
sc.tl.umap(adata)

# Set embedding
scrub.set_embedding('UMAP', adata.obsm['X_umap'])

# Plot
scrub.plot_embedding('UMAP', score='raw')
plt.savefig('doublets_umap.pdf')
```

### 5. Filter Doublets

```python
# Before filtering
print(f"Cells before: {adata.n_obs}")

# Filter predicted doublets
adata_filtered = adata[~adata.obs['predicted_doublet']].copy()

# After filtering
print(f"Cells after: {adata_filtered.n_obs}")
print(f"Removed: {adata.n_obs - adata_filtered.n_obs} doublets")
```

### 6. Access Additional Attributes

```python
# Doublet scores
scrub.doublet_scores_obs_      # Observed cells
scrub.doublet_scores_sim_      # Simulated doublets

# Standard errors
scrub.doublet_errors_obs_
scrub.doublet_errors_sim_

# Z-scores
scrub.z_scores_

# Doublet parents (cell indices that created each simulated doublet)
scrub.doublet_parents_

# Manifold coordinates
scrub.manifold_obs_            # Observed cells
scrub.manifold_sim_            # Simulated doublets
```

## Input Requirements

### Required Data Format

```python
print(adata)
# AnnData object with n_obs × n_vars = 5000 × 30000

print(adata.X[:5, :5].toarray())  # Raw counts
# [[0 0 1 0 2]
#  [0 1 0 0 0]
#  [0 0 0 1 0]]

# Check format
print(type(adata.X))  # scipy.sparse.csc_matrix or ndarray
```

## Output Specifications

### Core Outputs

| Output | Type | Description |
|--------|------|-------------|
| `doublet_scores` | ndarray | Continuous scores (0-1) |
| `predicted_doublets` | ndarray (bool) | Boolean predictions |
| `threshold_` | float | Auto-detected threshold |
| `z_scores_` | ndarray | Confidence z-scores |
| `detected_doublet_rate_` | float | Fraction called as doublets |

### Additional Attributes

| Attribute | Description |
|-----------|-------------|
| `doublet_scores_obs_` | Doublet scores for observed cells |
| `doublet_scores_sim_` | Doublet scores for simulated doublets |
| `doublet_errors_obs_` | Standard errors for observed |
| `doublet_errors_sim_` | Standard errors for simulated |
| `manifold_obs_` | PCA coordinates (observed) |
| `manifold_sim_` | PCA coordinates (simulated) |
| `doublet_parents_` | Parent cell indices for simulated doublets |
| `overall_doublet_rate_` | Estimated overall doublet rate |

## Key Parameters

### Initialization

| Parameter | Default | Description |
|-----------|---------|-------------|
| `expected_doublet_rate` | 0.1 | Estimated doublet rate |
| `sim_doublet_ratio` | 2.0 | Simulated doublets per observed cell |
| `n_neighbors` | auto | KNN graph neighbors |
| `stdev_doublet_rate` | 0.02 | Uncertainty in expected rate |

### Preprocessing

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_counts` | 3 | Min counts for gene filtering |
| `min_cells` | 3 | Min cells for gene filtering |
| `min_gene_variability_pctl` | 85 | Variable gene percentile |
| `n_prin_comps` | 30 | Number of PCs |
| `mean_center` | True | Center gene means to 0 |
| `normalize_variance` | True | Normalize gene variance to 1 |

### Detection

| Parameter | Default | Description |
|-----------|---------|-------------|
| `synthetic_doublet_umi_subsampling` | 1.0 | UMI sampling rate for doublets |
| `use_approx_neighbors` | True | Use annoy for approximate NN |
| `distance_metric` | 'euclidean' | Distance metric |

## Expected Runtime

| Dataset Size | Preprocessing | Doublet Simulation | Scoring |
|--------------|---------------|-------------------|---------|
| 1K cells | <1s | <1s | 1-2s |
| 5K cells | 2-5s | 1-2s | 5-10s |
| 20K cells | 10-20s | 5-10s | 30-60s |

## Error Handling

### Wrong input format
```python
# Convert if needed
if not scipy.sparse.issparse(counts):
    counts = scipy.sparse.csc_matrix(counts)
```

### Failed automatic threshold
```python
# Manual threshold if automatic fails
scrub.call_doublets(threshold=0.25)
```

### High doublet rate detected
→ Check if data was log-normalized before input (should use raw counts)

## Common Analysis Patterns

### Pattern 1: Quick Detection
```python
scrub = scr.Scrublet(adata.X)
doublet_scores, predicted_doublets = scrub.scrub_doublets()
```

### Pattern 2: With Expected Rate
```python
expected_rate = adata.n_obs / 1000 * 0.008
scrub = scr.Scrublet(adata.X, expected_doublet_rate=expected_rate)
doublet_scores, predicted_doublets = scrub.scrub_doublets()
```

### Pattern 3: Manual Threshold
```python
scrub = scr.Scrublet(adata.X)
doublet_scores, _ = scrub.scrub_doublets()
scrub.call_doublets(threshold=0.3)  # Custom threshold
```

### Pattern 4: Per-Sample Processing
```python
results = []
for sample in samples:
    adata = sc.read_10x_mtx(f'{sample}/filtered_feature_bc_matrix/')
    scrub = scr.Scrublet(adata.X)
    scores, pred = scrub.scrub_doublets()
    results.append({'sample': sample, 'scores': scores, 'predicted': pred})
```

### Pattern 5: With Visualization
```python
scrub = scr.Scrublet(adata.X)
scores, pred = scrub.scrub_doublets()
scrub.plot_histogram()
scrub.set_embedding('UMAP', adata.obsm['X_umap'])
scrub.plot_embedding('UMAP')
```

## Expected Doublet Rates

| Cells Recovered | Expected Rate | 10x Multiplet Rate |
|-----------------|---------------|-------------------|
| 500 | ~0.4% | Low |
| 1,000 | ~0.8% | Low |
| 2,000 | ~1.6% | Low |
| 5,000 | ~4.0% | Moderate |
| 10,000 | ~8.0% | High |
| 15,000 | ~12% | Very High |

*Based on ~0.8% per 1000 cells recovered*

## Interpretation Guidelines

### Good Results
- Bimodal distribution in simulated doublet histogram
- Clear separation between singlets and doublets
- Predicted doublets co-localize in embedding
- Detected rate matches expected rate

### Potential Issues
- No clear threshold: Adjust preprocessing parameters
- Too many doublets: Lower threshold
- Too few doublets: Increase threshold
- Doublets not co-localized: Increase n_prin_comps

## Comparison with Other Tools

| Feature | Scrublet | DoubletFinder | ScDblFinder |
|---------|----------|---------------|-------------|
| Speed | Fast | Moderate | Fast |
| Simulation | Yes | Yes | Yes |
| PCA-based | Yes | Yes | Yes |
| Python | Yes | Yes (reticulate) | No (R) |
| Threshold | Auto/Manual | Manual | Auto |

## Related Skills

- [bio-single-cell-doublet-scdblfinder-r](../bio-single-cell-doublet-scdblfinder-r/SKILL.md)
- [bio-single-cell-doublet-doubletfinder-r](../bio-single-cell-doublet-doubletfinder-r/SKILL.md)

## References

1. Wolock et al. (2019). Scrublet: Computational identification of cell doublets in single-cell transcriptomic data. *Cell Systems*, 8(4), 281-291. https://doi.org/10.1016/j.cels.2019.03.003
2. Scrublet GitHub: https://github.com/swolock/scrublet
3. Scrublet Paper: https://www.sciencedirect.com/science/article/pii/S2405471218304745
