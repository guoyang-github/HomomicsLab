---
name: bio-spatial-transcriptomics-deconvolution-tangram
description: Deep learning method for mapping single-cell RNA-seq to spatial transcriptomics using PyTorch optimization
tool_type: python
primary_tool: tangram-sc
supported_tools: [scanpy, torch, squidpy]
languages: [python]
keywords: ["spatial", "deconvolution", "Tangram", "deep-learning", "mapping", "gene-imputation"]
code_location: scripts/python/
version_compatibility:
  python: ">=3.9"
  tangram-sc: ">=1.0.0"
  scanpy: ">=1.10.0"
---

## Version Compatibility + Installation

| Package | Required | Notes |
|---------|----------|-------|
| Python | >=3.9 | |
| tangram-sc | >=1.0.0 | `pip install tangram-sc` |
| scanpy | >=1.10.0 | |
| anndata | >=0.10.0 | |
| torch | >=1.9.0 | CUDA optional but recommended for large datasets |
| squidpy | >=1.2.0 | Only for constrained mode (segmentation) |

```bash
pip install tangram-sc torch scanpy squidpy matplotlib seaborn
```

**GPU Support:** Optional but recommended for datasets > 10k cells. Use `device='cuda:0'`.

---

# Tangram Spatial Deconvolution

Tangram is a deep learning method that maps single-cell RNA-seq data to spatial transcriptomics by solving a convex optimization problem. It learns a probabilistic mapping between single cells and spatial spots using gradient descent with cosine similarity loss.

## Quick Selector

| Mode | Speed | Resolution | Memory | Best For |
|------|-------|------------|--------|----------|
| `clusters` | Fast (~minutes) | Cell type averages | Low | Initial exploration, large datasets |
| `cells` | Slow (~hours) | Individual cells | High | High-resolution mapping |
| `constrained` | Medium | Cell counts | Medium | When cell counts per spot are known |

### When to Use Tangram

- **Fast deconvolution needed**: Clusters mode completes in minutes
- **Gene imputation**: Project unmeasured genes from scRNA-seq to spatial
- **High-resolution mapping**: Cells mode maps individual cells
- **Cross-validation**: Built-in CV for quality assessment
- **Cell counting**: Constrained mode with segmentation data

### When NOT to Use Tangram

- **No single-cell reference available**: Tangram requires scRNA-seq reference
- **Very small gene overlap** (<50 shared genes between sc and spatial): Use marker gene selection
- **Need probabilistic uncertainty estimates**: Use Cell2location or DestVI instead


## Core Workflow (Step-by-Step)

### Step 1: Prepare Data

**Input:** Raw `adata_sc` (cell×gene) and `adata_sp` (spot×gene)  
**Output:** Preprocessed AnnDatas ready for Tangram

```python
from scripts.python.core_analysis import prepare_data

adata_sc_prep, adata_sp_prep = prepare_data(
    adata_sc=adata_sc,
    adata_sp=adata_sp,
    genes=None,              # Marker genes (optional); None = all shared genes
    gene_to_lowercase=True,  # Convert gene names to lowercase for matching
    copy=True,               # Return copies (recommended)
)
```

**State changes:**
- `adata_sc_prep.uns['training_genes']` — genes used for training
- `adata_sc_prep.uns['overlap_genes']` — all shared genes between datasets
- `adata_sp_prep.obs['uniform_density']` — uniform density prior
- `adata_sp_prep.obs['rna_count_based_density']` — RNA count-based density

**Key parameter:**

| Parameter | Default | When to Change |
|-----------|---------|----------------|
| `genes` | `None` | Provide marker genes (~50-200) for better alignment |
| `gene_to_lowercase` | `True` | Set `False` if gene names are case-sensitive (e.g., mouse vs human) |
| `copy` | `True` | Set `False` only if memory is constrained and you don't need originals |

---

### Step 2: Map Cells to Space

**Input:** Preprocessed `adata_sc_prep`, `adata_sp_prep`  
**Output:** `adata_map` — cell×spot mapping matrix

#### Clusters Mode (Fast — Recommended First)

```python
from scripts.python.core_analysis import map_cells_to_space

adata_map = map_cells_to_space(
    adata_sc=adata_sc_prep,
    adata_sp=adata_sp_prep,
    mode='clusters',
    cluster_label='cell_type',       # REQUIRED for clusters mode
    num_epochs=1000,
    device='cuda:0',
    density_prior='rna_count_based',
    lambda_g1=1.0,                   # Gene-voxel similarity weight (main loss)
    lambda_r=0.0,                    # Entropy regularizer (0 = none)
)
```

#### Cells Mode (High Resolution)

```python
adata_map = map_cells_to_space(
    adata_sc=adata_sc_prep,
    adata_sp=adata_sp_prep,
    mode='cells',                    # Map individual cells
    num_epochs=1000,
    device='cuda:0',
    lambda_r=0.5,                    # Entropy for sharper, peaked mappings
)
```

#### Constrained Mode (Cell Counts — Requires Segmentation)

```python
adata_map = map_cells_to_space(
    adata_sc=adata_sc_prep,
    adata_sp=adata_sp_prep,
    mode='constrained',
    target_count=5,                  # Expected cells per spot
    lambda_count=1.0,
    lambda_f_reg=1.0,
)
```

**Key Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | str | `'cells'` | `'cells'`, `'clusters'`, or `'constrained'` |
| `cluster_label` | str | `None` | **Required** for `clusters` mode: column in `adata_sc.obs` |
| `num_epochs` | int | `1000` | Training iterations |
| `device` | str | `'cpu'` | `'cpu'`, `'cuda:0'`, etc. |
| `density_prior` | str/array | `'rna_count_based'` | `'rna_count_based'`, `'uniform'`, custom array, or `None` |
| `lambda_g1` | float | `1.0` | Gene-voxel similarity weight (main loss) |
| `lambda_g2` | float | `0` | Voxel-gene similarity (reverse direction) |
| `lambda_r` | float | `0` | Entropy regularizer (higher = more peaked probabilities) |
| `lambda_d` | float | `0` | Density regularizer (auto-set if `density_prior` provided) |
| `target_count` | int | `None` | For `constrained` mode: expected cells per spot |

**Output (`adata_map`):**
- `adata_map.X` — mapping matrix (cells × spots) with probabilities
- `adata_map.uns['train_genes_df']` — training gene scores:
  - `train_score`: cosine similarity per gene
  - `sparsity_sc`: sparsity in single-cell data
  - `sparsity_sp`: sparsity in spatial data
  - `sparsity_diff`: difference in sparsity
- `adata_map.uns['training_history']` — loss curves during training

---

### Step 3: Project Cell Type Annotations

**Input:** `adata_map` (from Step 2), `adata_sp_prep`  
**Output:** Cell type proportions in `adata_sp_prep.obsm['tangram_ct_pred']`

```python
from scripts.python.core_analysis import project_cell_annotations, extract_deconvolution_results

# Project annotations (modifies adata_sp_prep in-place)
project_cell_annotations(
    adata_map=adata_map,
    adata_sp=adata_sp_prep,
    annotation='cell_type',
    threshold=0.5,                   # For constrained mode only
)

# Extract proportions as DataFrame
df_props = extract_deconvolution_results(
    adata_sp=adata_sp_prep,
    annotation_key='tangram_ct_pred',
    normalize=True,                  # Normalize to sum to 1 per spot
)
```

**State changes:**
- `adata_sp_prep.obsm['tangram_ct_pred']` — DataFrame of cell type proportions (spots × cell_types)

---

### Step 4: Gene Imputation (Optional)

**Input:** `adata_map`, `adata_sc_prep`, `adata_sp_prep`  
**Output:** `adata_ge` — spatial data with projected gene expression

```python
from scripts.python.core_analysis import project_genes, compare_spatial_geneexp

# Project genes from scRNA-seq to spatial
adata_ge = project_genes(
    adata_map=adata_map,
    adata_sc=adata_sc_prep,
    cluster_label='cell_type',       # Must match cluster_label used in map_cells_to_space
    scale=True,
)

# Compare projected vs measured expression
df_compare = compare_spatial_geneexp(
    adata_ge=adata_ge,
    adata_sp=adata_sp_prep,
    adata_sc=adata_sc_prep,          # Optional: adds sparsity comparison columns
)
```

**Output (`adata_ge`):**
- Spot-by-gene AnnData with projected expression
- `adata_ge.var['is_training']` — boolean indicating training genes

---

### Step 5: Quality Assessment (Recommended)

**Input:** `adata_sc_prep`, `adata_sp_prep`  
**Output:** CV scores and evaluation metrics

```python
from scripts.python.core_analysis import cross_val, eval_metric, check_mapping_quality

# Check training quality on existing mapping
report = check_mapping_quality(adata_map, min_score=0.5)
print(f"Avg score: {report['avg_score']:.3f}, Passes: {report['passes_threshold']}")

# Cross-validation (leave-one-out or 10-fold)
cv_dict, adata_ge_cv, df_test = cross_val(
    adata_sc=adata_sc_prep,
    adata_sp=adata_sp_prep,
    mode='clusters',
    cluster_label='cell_type',
    cv_mode='loo',                   # 'loo' or '10fold'
    return_gene_pred=True,
    num_epochs=500,                  # Fewer epochs for CV
)

print(f"CV test score: {cv_dict['avg_test_score']:.3f}")

# Evaluation metrics on test genes
metrics, auc_coords = eval_metric(df_test)
print(f"AUC score: {metrics['auc_score']:.3f}")
```

**Cross-Validation Output:**
- `cv_dict['avg_test_score']` — mean score on held-out genes
- `cv_dict['avg_train_score']` — mean score on training genes
- `adata_ge_cv` — predicted expression for test genes (if `return_gene_pred=True`)
- `df_test` — per-gene test scores (if `return_gene_pred=True`)

---

### Step 6: Deconvolution with Segmentation (Optional)

Requires segmentation data from squidpy.

```python
import squidpy as sq
from scripts.python.core_analysis import (
    create_segment_cell_df,
    count_cell_annotations,
    deconvolve_cell_annotations
)

# Calculate image features with segmentation
sq.im.calculate_image_features(
    adata_sp,
    img,
    features=['segmentation'],
    key_added='image_features',
)

# Create segmentation dataframe
create_segment_cell_df(adata_sp)

# Count cells per spot
count_cell_annotations(
    adata_map=adata_map,
    adata_sc=adata_sc_prep,
    adata_sp=adata_sp,
    annotation='cell_type',
    threshold=0.5,
)

# Extract individual cell assignments
adata_cells = deconvolve_cell_annotations(adata_sp)
```

**Output:**
- `adata_sp.obsm['tangram_ct_count']` — cell counts per spot
- `adata_cells` — AnnData with individual cell assignments

---

## Complete Pipeline (Copy-Pasteable)

```python
import scanpy as sc
from scripts.python.core_analysis import (
    prepare_data, map_cells_to_space, project_genes,
    project_cell_annotations, compare_spatial_geneexp,
    cross_val, eval_metric, check_mapping_quality,
    extract_deconvolution_results, export_results
)
from scripts.python.visualization import (
    plot_training_scores, plot_annotation_comparison, plot_auc
)

# 1. Load data
adata_sc = sc.read_h5ad('single_cell.h5ad')
adata_sp = sc.read_h5ad('spatial.h5ad')

# 2. Prepare
adata_sc_prep, adata_sp_prep = prepare_data(adata_sc, adata_sp, copy=True)

# 3. Map (clusters mode — fast, good starting point)
adata_map = map_cells_to_space(
    adata_sc_prep, adata_sp_prep,
    mode='clusters', cluster_label='cell_type',
    num_epochs=1000, device='cuda:0'
)

# 4. Check quality
report = check_mapping_quality(adata_map, min_score=0.5)
print(f"Training score: {report['avg_score']:.3f}")

# 5. Project cell types
project_cell_annotations(adata_map, adata_sp_prep, annotation='cell_type')
df_props = extract_deconvolution_results(adata_sp_prep, normalize=True)

# 6. Project genes (optional)
adata_ge = project_genes(adata_map, adata_sc_prep, cluster_label='cell_type', scale=True)
df_compare = compare_spatial_geneexp(adata_ge, adata_sp_prep, adata_sc_prep)

# 7. Cross-validation (optional)
cv_dict, _, df_test = cross_val(
    adata_sc_prep, adata_sp_prep,
    mode='clusters', cluster_label='cell_type',
    cv_mode='loo', return_gene_pred=True, num_epochs=500
)
metrics, _ = eval_metric(df_test)
print(f"CV test: {cv_dict['avg_test_score']:.3f}, AUC: {metrics['auc_score']:.3f}")

# 8. Export
export_results(adata_map, adata_sp_prep, output_dir='./tangram_output', annotation_key='cell_type')
```

---

## Skill-Provided Functions

### Data Preparation
- `prepare_data(adata_sc, adata_sp, genes=None, gene_to_lowercase=True, copy=True)` — preprocess both AnnDatas for Tangram

### Core Mapping
- `map_cells_to_space(adata_sc, adata_sp, mode='cells', cluster_label=None, ...)` — main training function

### Gene Projection
- `project_genes(adata_map, adata_sc, cluster_label=None, scale=True)` — impute gene expression
- `compare_spatial_geneexp(adata_ge, adata_sp, adata_sc=None, genes=None)` — compare projected vs measured

### Cell Annotation Projection
- `project_cell_annotations(adata_map, adata_sp, annotation='cell_type', threshold=0.5)` — project cell types (in-place)
- `extract_deconvolution_results(adata_sp, annotation_key='tangram_ct_pred', normalize=True)` — extract proportions as DataFrame

### Quality Assessment
- `cross_val(adata_sc, adata_sp, mode='clusters', ...)` — cross-validation
- `eval_metric(df_all_genes, test_genes=None)` — compute AUC and sparsity metrics
- `check_mapping_quality(adata_map, min_score=0.5)` — check training score quality, returns report dict
- `get_training_scores(adata_map)` — extract `train_genes_df` as DataFrame

### Segmentation / Constrained Mode
- `create_segment_cell_df(adata_sp)` — prepare segmentation data
- `count_cell_annotations(adata_map, adata_sc, adata_sp, annotation, threshold=0.5)` — count cells per spot
- `deconvolve_cell_annotations(adata_sp, filter_cell_annotation=None)` — get individual cell assignments

### Utilities
- `export_results(adata_map, adata_sp, output_dir, annotation_key=None, prefix='tangram')` — export to CSV
- `annotate_gene_sparsity(adata)` — add sparsity column to `adata.var`

### Visualization
- `plot_training_scores(adata_map, ...)` — 4-panel training diagnosis
- `plot_cell_type_map(adata_sp, cell_type, ...)` — single cell type spatial map
- `plot_annotation_comparison(adata_sp, ...)` — multi-cell type side-by-side maps
- `plot_cell_annotation_sc(adata_sp, annotation_list, ...)` — scanpy-style spatial plots
- `plot_genes_sc(genes, adata_measured, adata_predicted, ...)` — measured vs predicted gene comparison
- `plot_auc(df_all_genes, ...)` — AUC evaluation curve
- `plot_deconvolution_results(adata_sp, ...)` — cell count maps

---

## Official API — Agents Often Miss These

### 1. `map_cells_to_space` has NO `lambda_l1`, `lambda_l2`, `lambda_neighborhood_g1`, etc.

Tangram 1.0.4 only accepts these regularization parameters:
- `lambda_d`, `lambda_g1`, `lambda_g2`, `lambda_r`
- `lambda_count`, `lambda_f_reg` (constrained mode only)

Any other `lambda_*` parameters will cause `TypeError: unexpected keyword argument`.

### 2. `cluster_label` must match between `map_cells_to_space` and `project_genes`

If you use `mode='clusters'` with `cluster_label='cell_type'`, you must pass the same `cluster_label` to `project_genes`:

```python
# CORRECT
adata_map = map_cells_to_space(..., mode='clusters', cluster_label='cell_type')
adata_ge = project_genes(adata_map, adata_sc, cluster_label='cell_type', scale=True)

# WRONG — will give wrong projections
adata_ge = project_genes(adata_map, adata_sc, cluster_label=None, scale=True)
```

### 3. `cross_val` return type depends on `return_gene_pred`

```python
# return_gene_pred=False (default) → returns cv_dict only
cv_dict = cross_val(..., return_gene_pred=False)

# return_gene_pred=True → returns tuple (cv_dict, adata_ge_cv, df_test)
cv_dict, adata_ge_cv, df_test = cross_val(..., return_gene_pred=True)
```

### 4. `density_prior=None` disables density regularization

The default in `map_cells_to_space` is `'rna_count_based'`, but in `cross_val` it is `None`. If you want CV to match your mapping, explicitly pass the same `density_prior`.

### 5. `project_cell_annotations` modifies `adata_sp` in-place

There is no return value. The result is written to `adata_sp.obsm['tangram_ct_pred']`:

```python
project_cell_annotations(adata_map, adata_sp, annotation='cell_type')
# NOW adata_sp.obsm['tangram_ct_pred'] exists
```

### 6. `prepare_data` modifies in-place (unless `copy=True`)

Always use `copy=True` (the default) to avoid mutating your original data:

```python
adata_sc_prep, adata_sp_prep = prepare_data(adata_sc, adata_sp, copy=True)
```

### 7. `device='cuda:0'` requires CUDA + compatible torch

If CUDA is not available, Tangram will silently fall back to CPU. Check with:

```python
import torch
print(torch.cuda.is_available())  # Should be True for GPU
```

---

## Common Pitfalls

1. **⚠️ Calling `map_cells_to_space` with non-existent `lambda_l1`, `lambda_l2`, etc.** — These parameters were removed in Tangram 1.0.4. Only use `lambda_d`, `lambda_g1`, `lambda_g2`, `lambda_r`, `lambda_count`, `lambda_f_reg`.

2. **⚠️ Forgetting `cluster_label` in `clusters` mode** — `map_cells_to_space(mode='clusters')` will raise `ValueError` without `cluster_label`.

3. **⚠️ Passing `cluster_label=None` to `project_genes` after `clusters` mapping** — Gene projections will be incorrect. Always match the `cluster_label` parameter.

4. **⚠️ Assuming `cross_val` always returns a tuple** — Check `return_gene_pred`. Default returns a dict only.

5. **⚠️ Using `cells` mode on very large datasets** — Memory scales with `n_cells × n_spots`. For >50k cells, use `clusters` mode or subset cells.

6. **⚠️ Missing `tangram_ct_pred` before visualization** — Run `project_cell_annotations()` before any plotting function that reads `obsm['tangram_ct_pred']`.

7. **⚠️ Case-sensitive gene names** — If your datasets use different cases (e.g., `Gene1` vs `gene1`), set `gene_to_lowercase=True` in `prepare_data` (default).

8. **⚠️ Low training scores (<0.5)** — Usually indicates poor gene overlap or mismatched normalization. Use marker genes and check `adata_sc_prep.uns['overlap_genes']`.

---

## Troubleshooting

### Problem: `TypeError: map_cells_to_space() got an unexpected keyword argument 'lambda_l1'`

**Fix:** Remove `lambda_l1`, `lambda_l2`, `lambda_neighborhood_g1`, `lambda_ct_islands`, `lambda_getis_ord`, `lambda_moran`, `lambda_geary` from your call. Only these are valid: `lambda_d`, `lambda_g1`, `lambda_g2`, `lambda_r`, `lambda_count`, `lambda_f_reg`.

```python
# WRONG
map_cells_to_space(..., lambda_l1=0.1, lambda_l2=0.1)

# CORRECT
map_cells_to_space(..., lambda_g1=1.0, lambda_r=0.5)
```

### Problem: `ValueError: cluster_label must be provided for 'clusters' mode`

**Fix:** Pass the column name from `adata_sc.obs` that contains cell type labels:

```python
map_cells_to_space(..., mode='clusters', cluster_label='cell_type')
```

### Problem: `KeyError: 'tangram_ct_pred' not found`

**Fix:** Run `project_cell_annotations()` before extracting or visualizing results:

```python
project_cell_annotations(adata_map, adata_sp, annotation='cell_type')
df_props = extract_deconvolution_results(adata_sp)
```

### Problem: Low training scores (mean < 0.5)

**Fix:**
- Use marker genes: `prepare_data(..., genes=marker_genes)`
- Check gene overlap: `print(len(adata_sc_prep.uns['overlap_genes']))`
- Ensure both datasets are properly normalized
- Increase `num_epochs` (try 2000-5000)

### Problem: CUDA out of memory

**Fix:**
- Use `clusters` mode instead of `cells` mode
- Use CPU: `device='cpu'`
- Reduce `num_epochs`
- Subset cells: `adata_sc = adata_sc[adata_sc.obs['cell_type'].isin(['TypeA', 'TypeB'])]`

### Problem: CV test score much lower than training score

**Fix:**
- Overfitting: reduce `num_epochs` or increase `lambda_r`
- Poor gene overlap: check `training_genes` and `overlap_genes`
- Use different marker genes with better spatial coverage

### Problem: `AttributeError: module 'tangram' has no attribute 'cell_type_mapping'`

**Fix:** This function was removed. Use `project_cell_annotations()` instead, which writes results to `adata_sp.obsm['tangram_ct_pred']`.

---

## Related Skills

- [bio-spatial-transcriptomics-deconvolution-cell2location](../bio-spatial-transcriptomics-deconvolution-cell2location/SKILL.md) — Bayesian deconvolution with uncertainty
- [bio-spatial-transcriptomics-deconvolution-destvi](../bio-spatial-transcriptomics-deconvolution-destvi/SKILL.md) — Variational inference deconvolution
- [bio-spatial-transcriptomics-deconvolution-spotlight](../bio-spatial-transcriptomics-deconvolution-spotlight/SKILL.md) — NMF-based deconvolution

---

## References

1. Biancalani, T. et al. (2021). Deep learning and alignment of spatially-resolved whole transcriptome profiles of cells in the mouse brain with Tangram. *Nature Methods*, 18(11), 1352-1362.

2. Tangram GitHub: https://github.com/broadinstitute/Tangram

3. Tangram Documentation: https://tangram-sc.readthedocs.io/
