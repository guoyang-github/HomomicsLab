# Scrublet Usage Guide

## Overview

Scrublet detects doublets in single-cell RNA-seq data by simulating artificial doublets from random cell pairs, then using a k-nearest-neighbor classifier to score each cell's similarity to these simulated profiles.

## When to Use

- **Fast doublet detection**: Scrublet is computationally efficient
- **Python/Scanpy workflow**: Native Python implementation
- **Pre-QC filtering**: Detect doublets before downstream analysis
- **Visual inspection**: Histogram and embedding visualization available
- **Large datasets**: Can handle 100K+ cells with approximate neighbors

## When Not to Use

- **Small datasets (< 100 cells)**: Insufficient statistical power
- **Already normalized data**: Requires raw counts
- **Merged datasets**: Run per-sample separately for best results
- **Homotypic doublets**: May miss doublets from similar cell types

## Prerequisites

### Installation

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

### Dependencies

- Python >= 3.8
- scrublet >= 0.2.3
- scanpy >= 1.9.0
- scikit-learn >= 1.0
- scipy >= 1.7.0
- numpy, pandas, matplotlib

## Data Requirements

Input requirements:
- **Raw count matrix**: scipy sparse matrix or ndarray, shape (n_cells, n_genes)
- **Format**: Raw (unnormalized) UMI-based transcript counts
- **Best practice**: Run on individual samples separately (not merged datasets)

## Step-by-Step Guide

### Step 1: Calculate Expected Doublet Rate

```python
import scrublet as scr
import scanpy as sc

# Load data
adata = sc.read_10x_mtx('filtered_feature_bc_matrix/')

# Calculate expected doublet rate (~0.8% per 1000 cells)
n_cells = adata.n_obs
expected_rate = n_cells / 1000 * 0.008

print(f"Expected doublet rate: {expected_rate:.3f} ({expected_rate*100:.1f}%)")
```

**Expected Doublet Rates Reference:**

| Cells Recovered | Expected Rate | 10x Multiplet Rate |
|-----------------|---------------|-------------------|
| 500 | ~0.4% | Low |
| 1,000 | ~0.8% | Low |
| 2,000 | ~1.6% | Low |
| 5,000 | ~4.0% | Moderate |
| 10,000 | ~8.0% | High |
| 15,000 | ~12% | Very High |

### Step 2: Initialize Scrublet

```python
# Initialize with raw counts
scrub = scr.Scrublet(
    adata.X,                           # Raw count matrix
    expected_doublet_rate=expected_rate,
    sim_doublet_ratio=2.0,             # Simulated doublets per observed cell
    n_neighbors=None,                  # Auto: round(0.5 * sqrt(n_cells))
    stdev_doublet_rate=0.02,           # Uncertainty in expected rate
    random_state=42                    # For reproducibility
)
```

### Step 3: Run Doublet Detection

```python
# Run complete detection pipeline
doublet_scores, predicted_doublets = scrub.scrub_doublets(
    min_counts=2,                      # Min counts for gene filtering
    min_cells=3,                       # Min cells for gene filtering
    min_gene_variability_pctl=85,      # Keep top percentile of variable genes
    log_transform=False,               # Don't log-transform (uses raw counts)
    mean_center=True,                  # Center gene means to 0
    normalize_variance=True,           # Normalize gene variance to 1
    n_prin_comps=30,                   # Number of principal components
    synthetic_doublet_umi_subsampling=1.0,  # UMI sampling rate
    use_approx_neighbors=True,         # Use annoy for speed
    distance_metric='euclidean',       # Distance metric for NN search
    get_doublet_neighbor_parents=False,     # Don't return parent indices
    verbose=True                       # Print progress
)

print(f"Detected {sum(predicted_doublets)} doublets ({100*sum(predicted_doublets)/len(predicted_doublets):.1f}%)")
print(f"Scrublet threshold: {scrub.threshold_:.3f}")
```

### Step 4: Add Results to AnnData

```python
# Add results to AnnData
adata.obs['doublet_score'] = doublet_scores
adata.obs['predicted_doublet'] = predicted_doublets

# View results
print(adata.obs[['doublet_score', 'predicted_doublet']].head(10))

# Summary statistics
import numpy as np
print(f"\nDoublet score statistics:")
print(f"  Mean: {np.mean(doublet_scores):.3f}")
print(f"  Median: {np.median(doublet_scores):.3f}")
print(f"  Min: {np.min(doublet_scores):.3f}")
print(f"  Max: {np.max(doublet_scores):.3f}")
```

### Step 5: Visualization

#### Histogram

```python
import matplotlib.pyplot as plt

# Plot histogram of doublet scores
scrub.plot_histogram()
plt.savefig('doublet_histogram.pdf')
```

#### UMAP Visualization

```python
# Preprocess for visualization
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata)
sc.pp.pca(adata)
sc.pp.neighbors(adata)
sc.tl.umap(adata)

# Plot on UMAP
sc.pl.umap(adata, color=['doublet_score', 'predicted_doublet'])
```

#### Scrublet Embedding

```python
# Use Scrublet's internal embedding
scrub.set_embedding('UMAP', adata.obsm['X_umap'])
scrub.plot_embedding('UMAP', score='raw')
plt.savefig('doublets_umap.pdf')
```

### Step 6: Custom Threshold Selection

```python
# Automatic threshold detection (default)
scrub.call_doublets(threshold=None)
auto_predictions = scrub.predicted_doublets_

# Manual threshold
scrub.call_doublets(threshold=0.25)
manual_predictions = scrub.predicted_doublets_

# Custom threshold logic
high_confidence_doublets = doublet_scores > 0.35
adata.obs['high_conf_doublet'] = high_confidence_doublets
```

### Step 7: Filter Doublets

```python
# Before filtering
print(f"Cells before: {adata.n_obs}")

# Filter predicted doublets
adata_filtered = adata[~adata.obs['predicted_doublet']].copy()

# After filtering
print(f"Cells after: {adata_filtered.n_obs}")
print(f"Removed: {adata.n_obs - adata_filtered.n_obs} doublets")
```

### Step 8: Access Additional Attributes

```python
# Doublet scores
scrub.doublet_scores_obs_      # Observed cells
scrub.doublet_scores_sim_      # Simulated doublets

# Standard errors
scrub.doublet_errors_obs_
scrub.doublet_errors_sim_

# Z-scores for confidence
scrub.z_scores_

# Doublet parents (cell indices that created each simulated doublet)
scrub.doublet_parents_

# Manifold coordinates
scrub.manifold_obs_            # Observed cells
scrub.manifold_sim_            # Simulated doublets

# Rates
scrub.detected_doublet_rate_   # Fraction of cells called as doublets
scrub.overall_doublet_rate_    # Estimated overall doublet rate
```

## Advanced Usage

### Per-Sample Processing

```python
results = []

for sample in samples:
    # Load sample data
    adata = sc.read_10x_mtx(f'{sample}/filtered_feature_bc_matrix/')

    # Calculate expected rate for this sample
    expected_rate = adata.n_obs / 1000 * 0.008

    # Run Scrublet
    scrub = scr.Scrublet(adata.X, expected_doublet_rate=expected_rate)
    scores, pred = scrub.scrub_doublets()

    # Store results
    results.append({
        'sample': sample,
        'n_cells': adata.n_obs,
        'scores': scores,
        'predicted': pred,
        'threshold': scrub.threshold_
    })

# Combine results
all_doublets = sum([r['predicted'].sum() for r in results])
print(f"Total doublets detected: {all_doublets}")
```

### Multiple Parameter Comparison

```python
thresholds = [0.15, 0.20, 0.25, 0.30]
results = []

for thresh in thresholds:
    scrub.call_doublets(threshold=thresh, verbose=False)
    n_doublets = sum(scrub.predicted_doublets_)
    results.append({
        'threshold': thresh,
        'n_doublets': n_doublets,
        'doublet_rate': n_doublets / len(scrub.predicted_doublets_)
    })

# Compare
import pandas as pd
results_df = pd.DataFrame(results)
print(results_df)
```

## AI Agent Test Cases

### Basic Detection
> "Run Scrublet on my scRNA-seq data"

```python
scrub = scr.Scrublet(adata.X, expected_doublet_rate=0.06)
doublet_scores, predicted_doublets = scrub.scrub_doublets()
```

### With Expected Rate
> "Use Scrublet with expected doublet rate of 8%"

```python
scrub = scr.Scrublet(adata.X, expected_doublet_rate=0.08)
doublet_scores, predicted_doublets = scrub.scrub_doublets()
```

### Manual Threshold
> "Call doublets with threshold 0.3"

```python
scrub.call_doublets(threshold=0.3)
predicted_doublets = scrub.predicted_doublets_
```

### Visualization
> "Plot Scrublet histogram"

```python
scrub.plot_histogram()
```

> "Show doublets on UMAP"

```python
sc.pl.umap(adata, color=['doublet_score', 'predicted_doublet'])
```

### Filtering
> "Filter out predicted doublets"

```python
adata_filtered = adata[~adata.obs['predicted_doublet']].copy()
```

## Parameters Reference

### Scrublet Initialization

| Parameter | Default | Description |
|-----------|---------|-------------|
| `counts_matrix` | Required | Raw count matrix (sparse or dense) |
| `total_counts` | None | Total UMI counts per cell (optional) |
| `sim_doublet_ratio` | 2.0 | Simulated doublets per observed cell |
| `n_neighbors` | auto | KNN neighbors (default: 0.5*sqrt(n_cells)) |
| `expected_doublet_rate` | 0.1 | Estimated doublet rate |
| `stdev_doublet_rate` | 0.02 | Uncertainty in expected rate |
| `random_state` | 0 | Random seed |

### scrub_doublets()

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_counts` | 2 | Min counts for gene filtering |
| `min_cells` | 3 | Min cells for gene filtering |
| `min_gene_variability_pctl` | 85 | Variable gene percentile |
| `log_transform` | False | Log-transform counts |
| `mean_center` | True | Center gene means |
| `normalize_variance` | True | Normalize gene variance |
| `n_prin_comps` | 30 | Number of PCs |
| `synthetic_doublet_umi_subsampling` | 1.0 | UMI subsampling rate |
| `use_approx_neighbors` | True | Use approximate NN (annoy) |
| `distance_metric` | 'euclidean' | Distance metric |
| `get_doublet_neighbor_parents` | False | Return parent indices |
| `verbose` | True | Print progress |

## Output

| Output | Type | Description |
|--------|------|-------------|
| `doublet_scores` | ndarray | Continuous scores (0-1) |
| `predicted_doublets` | ndarray (bool) | Boolean predictions |
| `threshold_` | float | Auto-detected threshold |
| `z_scores_` | ndarray | Confidence z-scores |
| `detected_doublet_rate_` | float | Fraction called as doublets |

## Interpretation Guidelines

### Good Results
- Bimodal distribution in histogram
- Clear separation between singlets and doublets
- Predicted doublets co-localize in embedding
- Detected rate matches expected rate

### Potential Issues
- **No clear threshold**: Adjust preprocessing parameters
- **Too many doublets**: Lower threshold or check input format
- **Too few doublets**: Increase threshold
- **Doublets not co-localized**: Increase `n_prin_comps`

## Troubleshooting

### High doublet rate detected
→ Check if data was log-normalized (should use raw counts)

### Failed automatic threshold
```python
# Use manual threshold
scrub.call_doublets(threshold=0.25)
```

### Sparse matrix issues
```python
import scipy.sparse
if not scipy.sparse.issparse(counts):
    counts = scipy.sparse.csc_matrix(counts)
```

## Best Practices

1. **Run per-sample**: Don't merge samples before doublet detection
2. **Use raw counts**: Don't normalize before Scrublet
3. **Check histogram**: Verify bimodal distribution
4. **Compare rates**: Detected rate should match expected
5. **Filter after QC**: Run Scrublet before other QC filtering
6. **Save scores**: Keep continuous scores, not just binary predictions

## Comparison with Other Tools

| Feature | Scrublet | DoubletFinder | ScDblFinder |
|---------|----------|---------------|-------------|
| Speed | Fast | Moderate | Fast |
| Simulation | Yes | Yes | Yes |
| Language | Python | Python (R wrapper) | R |
| Threshold | Auto/Manual | Manual | Auto |
| Best for | Large datasets | Small datasets | R workflows |

## References

1. Wolock et al. (2019). Scrublet: Computational identification of cell doublets in single-cell transcriptomic data. *Cell Systems*, 8(4), 281-291. https://doi.org/10.1016/j.cels.2019.03.003
2. Scrublet GitHub: https://github.com/swolock/scrublet
3. Scrublet Paper: https://www.sciencedirect.com/science/article/pii/S2405471218304745

## Related Skills

- [bio-single-cell-doublet-scdblfinder-r](../bio-single-cell-doublet-scdblfinder-r/SKILL.md)
- [bio-single-cell-doublet-doubletfinder-r](../bio-single-cell-doublet-doubletfinder-r/SKILL.md)
