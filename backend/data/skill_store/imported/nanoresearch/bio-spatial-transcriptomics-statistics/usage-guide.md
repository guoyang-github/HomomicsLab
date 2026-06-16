# Spatial Statistics - Usage Guide

## Overview

This skill covers computing spatial statistics for spatial transcriptomics data using Squidpy, PySAL (esda, libpysal), and NetworkX. Includes Moran's I, Geary's C, Getis-Ord Gi*, bivariate correlation, co-occurrence analysis, neighborhood enrichment, Join Count statistics, network analysis, and spatial variable gene (SVG) detection.

## Prerequisites

### Core Dependencies
```bash
pip install squidpy scanpy pandas numpy scipy
```

### Advanced Statistics (PySAL)
```bash
pip install esda libpysal statsmodels
```

### Network Analysis
```bash
pip install networkx scikit-learn
```

### SVG Detection (Optional)
```bash
# FlashS (fastest, Python-only)
pip install flashs

# SPARK-X (requires R)
pip install rpy2
# In R: install.packages('SPARK')

# SpatialDE (Gaussian process)
pip install spatialDE naiveDE
```

## Quick Start

Tell your AI agent what you want to do:
- "Find spatially variable genes"
- "Calculate Moran's I for my spatial data"
- "Detect hotspots with Getis-Ord Gi*"
- "Find gene pairs with correlated spatial patterns"
- "Analyze tissue network structure"

## Analysis Selection Guide

### Which Statistic Should I Use?

| Question | Method | Tool |
|----------|--------|------|
| Which genes have spatial patterns? | Moran's I (global) | squidpy |
| Where are expression hotspots? | Getis-Ord Gi* | esda |
| Which spots are cluster outliers? | LISA (local Moran) | esda |
| Do two genes co-localize? | Bivariate Moran's I | esda |
| Are cell types randomly distributed? | Join Count | esda |
| Which cell types co-localize? | Co-occurrence | squidpy |
| Are clusters enriched near each other? | Neighborhood enrichment | squidpy |
| Which spots are structural bridges? | Betweenness centrality | networkx |
| Is tissue connectivity fragmented? | Network components | networkx |
| Find SVGs without R? | FlashS | flashs |
| Most accurate SVG detection? | SPARK-X | SPARK (R) |
| Cell type enrichment in niches? | Ro/e | Custom |

## Example Prompts

### Spatial Autocorrelation
> "Compute Moran's I for all genes"

> "Find genes with significant spatial patterns"

> "Calculate Getis-Ord Gi* for EPCAM to find hotspots"

### Local Pattern Detection
> "Run LISA analysis on CD8A to find local clusters"

> "Which spots are hot outliers for this gene?"

### Gene-Gene Relationships
> "Compute bivariate Moran's I for TGFB1-TGFBR1"

> "Find ligand-receptor pairs with spatial correlation"

### Categorical Analysis
> "Run join count analysis on cell type clusters"

> "Are tumor cells clustered or randomly distributed?"

### Network Analysis
> "Compute spatial centrality scores"

> "Find bridge spots in the tissue"

### Co-localization
> "Run co-occurrence analysis on my clusters"

> "Which cell types co-localize?"

### Cell Type Enrichment in Niches
> "Calculate Ro/e for cell types in neural zones"

> "Which cell types are enriched in the tumor niche?"

> "Find significantly depleted cell types in the peri-neural region"

### SVG Detection
> "Detect spatial variable genes using FlashS"

> "Compare SVG methods on my data"

## What the Agent Will Do

1. **Validate data quality** - Check spatial coordinates, detect NaN/Inf, verify count type
2. **Build spatial graph** - Create neighbor graph (KNN or Delaunay)
3. **Compute requested statistic** - Run appropriate method with correct parameters
4. **Apply multiple testing correction** - FDR correction for p-values
5. **Return results** - Structured output with significance values
6. **Optional: Visualize** - Create maps, plots, or summary statistics

## Parameter Tuning Tips

### Number of Neighbors (k)

```python
# Visium (hexagonal grid): k=6
sq.gr.spatial_neighbors(adata, coord_type='generic', n_neighs=6)

# Visium HD (square grid): k=4
sq.gr.spatial_neighbors(adata, coord_type='grid', n_neighs=4)

# MERFISH/Xenium (irregular): k=8-12
sq.gr.spatial_neighbors(adata, coord_type='generic', n_neighs=10)

# High-density data: Increase k
sq.gr.spatial_neighbors(adata, coord_type='generic', n_neighs=15)
```

### Permutations for Significance

```python
# Quick exploration: 99 permutations
moran = Moran(y, w, permutations=99)

# Publication quality: 999 permutations
moran = Moran(y, w, permutations=999)

# High precision: 9999 permutations (slow)
moran = Moran(y, w, permutations=9999)
```

### SVG Detection Parameters

```python
# FlashS: Adjust PCs for large datasets
flashs_results = detect_svg_flashs(adata, n_pcs=100)  # More PCs for complex patterns

# SPARK-X: Adjust filtering
sparkx_results = detect_svg_sparkx(
    adata,
    min_cells_ratio=0.05,  # Lower threshold for rare cell types
    min_total_counts=5     # Lower for sparse data
)

# SpatialDE: Default parameters work well
spatialde_results = detect_svg_spatialde(adata)
```

### Ro/e Analysis Parameters

```python
# Minimum count threshold for reliable Ro/e estimation
# Higher values = more conservative, fewer false positives
roe_results = compute_roe(adata, cell_type_key='cell_type', niche_key='zone', min_counts=10)

# For rare cell types, lower the threshold
roe_results = compute_roe(adata, cell_type_key='cell_type', niche_key='zone', min_counts=3)

# Statistical significance testing
stats = compute_niche_enrichment_stats(adata, method='chi2')  # For large samples
stats = compute_niche_enrichment_stats(adata, method='fisher')  # For small samples
```

## Data Requirements

### Raw vs Normalized Counts

| Method | Counts Required | Notes |
|--------|----------------|-------|
| Moran's I | Normalized | Log1p or Pearson residuals |
| Geary's C | Normalized | Same as Moran's I |
| Getis-Ord Gi* | Normalized | Can use raw for detection |
| LISA | Normalized | Standardized values recommended |
| Bivariate Moran | Normalized | Both genes should be normalized |
| Join Count | Categorical | Binary or category labels |
| SPARK-X | Raw counts | Integer counts required |
| SpatialDE | Raw counts | NaiveDE normalization built-in |
| FlashS | Normalized | Log1p recommended |

### Gene Filtering Best Practices

```python
# Before SVG detection, filter low-expression genes
min_cells = int(0.05 * adata.n_obs)  # 5% of cells
sc.pp.filter_genes(adata, min_cells=min_cells)

# Remove mitochondrial genes (optional)
mt_genes = adata.var_names.str.startswith('MT-')
adata = adata[:, ~mt_genes].copy()

# Remove ribosomal genes (optional)
ribo_genes = adata.var_names.str.startswith(('RPS', 'RPL'))
adata = adata[:, ~ribo_genes].copy()
```

## Performance Optimization

### Subsampling Large Datasets

```python
# For quick exploration, subsample spots
sc.pp.subsample(adata, n_obs=5000, random_state=42)

# For SVG detection on huge datasets
hvg = adata.var_names[adata.var['highly_variable']][:2000]
adata_sub = adata[:, hvg].copy()
```

### Sparse Matrix Optimization

```python
# Keep data sparse for memory efficiency
from scipy.sparse import issparse

if not issparse(adata.X):
    adata.X = scipy.sparse.csr_matrix(adata.X)

# Convert to dense only when needed
gene_expr = adata[:, gene].X.toarray().flatten()
```

### Parallel Processing

```python
# SPARK-X supports multiple cores
# In R: sparkx(..., numCores = 4)

# For batch processing in Python
from multiprocessing import Pool

def compute_for_gene(gene):
    return compute_moran(adata, gene)

with Pool(4) as p:
    results = p.map(compute_for_gene, gene_list)
```

## Troubleshooting Common Issues

### Import Errors

```python
# Error: No module named 'esda'
# Solution: pip install esda libpysal

# Error: rpy2 not found
# Solution: pip install rpy2 (also requires R installation)

# Error: FlashS not found
# Solution: pip install flashs
```

### Memory Issues

```python
# Error: MemoryError during SVG detection
# Solution 1: Process in batches
genes_batch = gene_list[:1000]
results = detect_svg_flashs(adata[:, genes_batch])

# Solution 2: Reduce n_pcs
results = detect_svg_flashs(adata, n_pcs=20)  # Default is 50

# Solution 3: Use sparse matrices
adata.X = scipy.sparse.csr_matrix(adata.X)
```

### Convergence Warnings

```python
# Warning: Moran's I p-value may not be reliable
# Solution: Increase permutations
moran = Moran(y, w, permutations=9999)

# Warning: Singular matrix in SpatialDE
# Solution: Filter more genes or reduce spots
adata_sub = adata[::2, :].copy()  # Subsample spots
```

### Data Validation Errors

```python
# Error: No spatial coordinates found
# Solution: Check adata.obsm keys
print(adata.obsm.keys())  # Should contain 'spatial'

# Error: Negative values in raw count data
# Solution: Check if data is already normalized
if adata.X.min() < 0:
    print("Data appears normalized. Use raw counts for SPARK-X/SpatialDE.")

# Error: NaN in spatial coordinates
# Solution: Remove spots with missing coordinates
mask = ~np.isnan(adata.obsm['spatial']).any(axis=1)
adata = adata[mask].copy()
```

### R Integration Issues (SPARK-X)

```python
# Error: R_HOME not set
# Solution: Set R_HOME environment variable
import os
os.environ['R_HOME'] = '/usr/lib/R'  # Adjust path for your system

# Error: SPARK package not found in R
# Solution: In R, run: install.packages('SPARK')

# Error: rpy2 initialization failed
# Solution: Ensure R and Python versions are compatible
# Check rpy2 documentation for version requirements
```

### Multiple Components Warning

```python
# Warning: Multiple connected components detected
# This means your tissue has disconnected regions

# Check which spots are in which component
print(adata.obs['network_component'].value_counts())

# Option 1: Analyze largest component only
largest = adata.obs['network_component'].value_counts().index[0]
adata_conn = adata[adata.obs['network_component'] == largest].copy()

# Option 2: Proceed with caution (some statistics still valid)
# Getis-Ord Gi*, LISA may still work per component
```

## Ro/e Interpretation Guide

Ro/e (Ratio of observed to expected) quantifies cell type enrichment in spatial niches:

| Ro/e Value | Interpretation | Biological Meaning |
|------------|----------------|-------------------|
| > 2.0 | Strongly enriched | Cell type is >2x more abundant than expected by chance |
| 1.5 - 2.0 | Enriched | Cell type is 1.5-2x more abundant |
| 0.67 - 1.5 | Neutral | Cell type present at expected frequency |
| 0.5 - 0.67 | Depleted | Cell type is less abundant than expected |
| < 0.5 | Strongly depleted | Cell type is <50% of expected abundance |

```python
# Apply interpretation categories
def categorize_roe(roe_val):
    if pd.isna(roe_val):
        return 'low_count'
    elif roe_val > 2:
        return 'strongly_enriched'
    elif roe_val > 1.5:
        return 'enriched'
    elif roe_val > 0.67:
        return 'neutral'
    elif roe_val > 0.5:
        return 'depleted'
    else:
        return 'strongly_depleted'

# Categorize entire Ro/e matrix
categories = roe_matrix.applymap(categorize_roe)
```

### Ro/e vs Neighborhood Enrichment

| Method | Use When | Output |
|--------|----------|--------|
| Ro/e | You have defined niches/zones | Enrichment ratio per cell type per niche |
| Neighborhood Enrichment | You have clusters without predefined zones | Z-score matrix between all cluster pairs |

## Tips

- **Moran's I** - Positive values indicate spatial clustering; values near 0 indicate randomness
- **Build neighbors first** - All statistics require spatial neighbor graph; call `sq.gr.spatial_neighbors()` first
- **Gene subset** - Computing for all genes can be slow; subset to HVGs for exploration
- **Multiple testing** - Always apply FDR correction for many genes (q-value < 0.05)
- **Check data type** - SPARK-X and SpatialDE need raw counts; Moran's I prefers normalized
- **Scale matters** - Ensure spatial coordinates are in consistent units (pixels or microns)
- **Visual validation** - Always plot results to check for artifacts or batch effects
- **Biological interpretation** - High Moran's I alone doesn't imply biological significance; consider effect size
- **Ro/e interpretation** - Values >1.5 or <0.67 are typically considered biologically meaningful
- **Ro/e sample size** - Use min_counts parameter to avoid unreliable ratios from low cell counts
