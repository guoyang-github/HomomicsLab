---
name: bio-spatial-transcriptomics-deconvolution-cell2location
description: Spatial transcriptomics deconvolution using cell2location. Estimates cell type proportions per spot with Bayesian uncertainty quantification (q05/q50/q95) from an annotated scRNA-seq reference.
tool_type: python
primary_tool: cell2location
supported_tools: [scvi-tools, scanpy, torch]
languages: [python]
keywords: ["spatial", "deconvolution", "cell2location", "cell-type-proportions", "visium", "uncertainty", "bayesian"]
code_location: scripts/python/
version_compatibility:
  python: ">=3.9"
  cell2location: ">=0.1.3"
  scanpy: ">=1.10.0"
  scvi-tools: ">=1.0.0, <1.2.0"
  torch: ">=2.0"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| Python | >= 3.9 | |
| cell2location | >= 0.1.3 | Core deconvolution |
| scanpy | >= 1.10 | AnnData I/O |
| scvi-tools | 1.0.x–1.1.x | **Pin to `<1.2.0`** — cell2location fails with ≥1.2.0 due to `parse_use_gpu_arg` removal |
| torch | >= 2.0 | Backend; CUDA 11.8+ recommended |
| anndata | >= 0.10 | Data structure |

## Installation

```bash
pip install "scvi-tools<1.2.0" cell2location scanpy
```

Verify GPU before long runs:
```python
import torch
print(torch.cuda.is_available())  # Should be True for GPU training
```

## Skill Overview

Cell2location is a Bayesian model that deconvolves spatial transcriptomics spots into cell type proportions using a reference scRNA-seq atlas. It runs in two stages: (1) estimate cell type signatures from the reference, (2) fit spatial abundances with uncertainty.

**Core workflow**: Prepare data → Estimate reference signatures → Fit spatial model → Extract proportions → Visualize

**When to use**:
- You have a well-annotated scRNA-seq reference from the same tissue/condition
- Need per-spot cell type proportions with uncertainty bounds
- Analyzing Visium (55 μm) or similar spot-based spatial data
- Have GPU access for hours-long training

**When NOT to use**:
- No scRNA-seq reference available — cell2location is reference-based
- Very few cells per cell type (< 10) — signature estimation is unreliable
- Gene overlap < 100 between reference and spatial — insufficient shared features
- Need real-time results — training takes 30 min to 4+ hours even on GPU
- Single-cell resolution data (e.g., MERFISH with 1 cell/spot) — deconvolution is unnecessary

## Core Workflow (Step-by-Step)

### Step 1: Prepare Data

**Goal**: Harmonize spatial and reference data to shared genes and ensure raw counts.

```python
from scripts.python.core_analysis import prepare_data

spatial_prep, ref_prep = prepare_data(
    spatial_adata=spatial_adata,      # Visium / spatial data
    reference_adata=reference_adata,  # scRNA-seq with cell type labels
    cell_type_key='cell_type',        # Column in reference.obs
    min_common_genes=100,             # Raise error if fewer shared genes
    require_int_dtype=True,           # Warn + convert if not integer counts
)
```

**What this wrapper adds**:
- Extracts raw counts from `.layers['raw']` or `.raw.to_adata()` if present
- Warns and converts non-integer data to integer counts (does not raise)
- Subsets both datasets to intersection of gene names
- Raises `ValueError` if `cell_type_key` missing or common genes < `min_common_genes`
- Always returns copies; original objects are not modified

**After this step**: Both AnnData objects share the same genes, contain raw integer counts.

---

### Step 2: Validate Inputs (Optional)

**Goal**: Catch common problems before the long training step.

```python
from scripts.python.utils import validate_inputs

validate_inputs(spatial_prep, ref_prep, cell_type_key='cell_type')
# Raises ValueError if:
#   - cell_type_key missing from reference
#   - Any cell type has < 10 cells (signatures unreliable)
#   - Spatial coordinates missing (no 'spatial' in obsm or 'array_row' in obs)
```

**After this step**: Confident that data meets minimum requirements.

---

### Step 3: Run Deconvolution

**Goal**: Train reference signature model, then fit spatial abundances.

```python
from scripts.python.core_analysis import run_cell2location

results = run_cell2location(
    spatial_adata=spatial_prep,
    reference_adata=ref_prep,
    cell_type_key='cell_type',
    max_epochs=30000,
    batch_size=None,               # Auto: min(2500, n_spots)
    gpu=True,                      # Auto-falls back to CPU if CUDA unavailable
    batch_key=None,                # Set to "sample" for multi-sample correction
    detection_alpha=200,           # 20 for high within-slide variability
    N_cells_per_location=None,     # Auto: from obs['n_cells'] or default 10
)
```

**What this wrapper adds**:
- **Two-stage pipeline**: `RegressionModel.setup_anndata` → train (250 epochs) → export signatures → `Cell2location.setup_anndata` → train (`max_epochs`) → export posteriors
- **Version compatibility**: Tries `accelerator='gpu'` (scvi-tools ≥ 0.20), falls back to `use_gpu=True` (older versions)
- **Auto batch size**: `min(2500, n_spots)` if not specified
- **Auto `N_cells_per_location`**: Infers from `spatial_adata.obs['n_cells']` if present; defaults to 10. Validates that the column is numeric.
- **Input protection**: Operates on copies of both inputs; safe to call multiple times with the same objects
- **New hyperparameters exposed**: `batch_key`, `detection_alpha`, `N_cells_per_location`

**Returns**: `spatial_adata` with results stored in `.obsm`:
- `q05_cell_abundance_w_sf` — 5% quantile (conservative)
- `q50_cell_abundance_w_sf` — median (best point estimate)
- `q95_cell_abundance_w_sf` — 95% quantile (liberal)
- `means_cell_abundance_w_sf` — mean abundance
- `stds_cell_abundance_w_sf` — standard deviation

**Training time**:
- ~1,000 spots: 30–60 min (GPU)
- ~5,000 spots: 2–4 hours (GPU)
- CPU: 5–10× slower

**After this step**: `results` AnnData contains deconvolution posteriors in `.obsm`.

---

### Step 4: Extract Proportions

**Goal**: Convert posterior abundances to interpretable proportions.

```python
from scripts.python.core_analysis import estimate_cell_type_proportions

# Normalized proportions (sum to 1 per spot)
props = estimate_cell_type_proportions(
    results,
    q_threshold=0.05,   # Use 5% quantile (conservative)
    normalize=True      # Divide by row sum; fill NaN with 0
)
# Returns DataFrame: spots × cell_types

# Or extract raw abundances without normalization
abundances = estimate_cell_type_proportions(results, q_threshold=0.50, normalize=False)
```

**Quantile selection guide**:

| Quantile | Use When |
|----------|----------|
| `q05` (0.05) | Conservative; minimizes false positives |
| `q50` (0.50) | Best point estimate; default for visualization |
| `q95` (0.95) | Liberal; captures potential low-abundance signal |

**After this step**: `props` DataFrame ready for downstream analysis.

---

### Step 5: Visualize

**Goal**: Plot cell type proportions on spatial coordinates.

```python
from scripts.python.visualization import (
    plot_proportions_spatial,
    plot_cell_type_maps,
    plot_dominant_cell_type,
)

# Multi-panel spatial maps for selected cell types
fig = plot_proportions_spatial(
    results,
    cell_types=['T_cell', 'B_cell', 'Macrophage'],
    ncols=3,
    cmap='viridis',
    save_path='proportions.pdf'
)

# Uncertainty comparison (q05 / q50 / q95) for one cell type
fig = plot_cell_type_maps(results, cell_type='T_cell', save_path='uncertainty.pdf')

# Dominant cell type per spot
fig = plot_dominant_cell_type(results, save_path='dominant.pdf')
```

**Coordinate detection**: All plotting functions check `'spatial' in adata.obsm` first, then fall back to `adata.obs[['array_row', 'array_col']]`.

**After this step**: Publication-ready spatial proportion maps.

---

## Complete Pipeline

```python
from scripts.python.core_analysis import (
    prepare_data, run_cell2location, estimate_cell_type_proportions
)
from scripts.python.utils import validate_inputs
from scripts.python.visualization import (
    plot_proportions_spatial, plot_dominant_cell_type
)
import scanpy as sc

# 1. Load data
spatial = sc.read_h5ad("visium_data.h5ad")
reference = sc.read_h5ad("scrnaseq_reference.h5ad")

# 2. Prepare and validate
spatial_prep, ref_prep = prepare_data(
    spatial, reference, cell_type_key='cell_type', min_common_genes=100
)
validate_inputs(spatial_prep, ref_prep, cell_type_key='cell_type')

# 3. Run deconvolution (~30 min – 4 hr depending on size)
results = run_cell2location(
    spatial_prep, ref_prep,
    cell_type_key='cell_type',
    max_epochs=30000, gpu=True
)

# 4. Extract proportions
props = estimate_cell_type_proportions(results, q_threshold=0.05, normalize=True)

# 5. Visualize
plot_proportions_spatial(results, cell_types=props.columns[:6].tolist(), ncols=3)
plot_dominant_cell_type(results)

# 6. Save
results.write_h5ad("cell2location_results.h5ad")
props.to_csv("cell_type_proportions.csv")
```

## Skill-Provided Functions

Source: `scripts/python/` directory

### Core Analysis

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `prepare_data(spatial, reference, ...)` | `cell_type_key`, `min_common_genes`, `require_int_dtype` | Raw count extraction, common gene intersection, warns + converts non-integer data. Returns **copies** `(spatial_prep, ref_prep)` |
| `run_cell2location(spatial, reference, ...)` | `max_epochs`, `batch_size`, `gpu`, `batch_key`, `detection_alpha`, `N_cells_per_location` | Two-stage pipeline on **copies** of inputs. Handles scvi-tools version compatibility (`accelerator` vs `use_gpu`). Auto-infers `N_cells_per_location` from `obs['n_cells']` with numeric validation. **Returns new AnnData** with `.obsm` posteriors |
| `estimate_cell_type_proportions(results, ...)` | `q_threshold` (0.05/0.50/0.95), `normalize` | Extracts quantile from `.obsm`, cleans column names, optionally normalizes rows to sum 1. Handles all-zero rows (remain all zeros) |
| `extract_proportions(results, key=...)` | `key` (e.g. `'q05_cell_abundance_w_sf'`) | Lower-level extractor; returns `(DataFrame, cell_type_names_list)` |

### Utilities

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `validate_inputs(spatial, reference, ...)` | `cell_type_key` | Pre-flight check: cell type key exists, ≥10 cells per type, spatial coordinates present and 2D |
| `filter_low_quality_spots(spatial, ...)` | `min_counts`, `min_genes` | QC filter; auto-computes `total_counts` and `n_genes_by_counts` if missing. Returns **copy**; input not modified |
| `estimate_optimal_epochs(spatial)` | — | Recommends epochs based on spot count: <1k→10k, <5k→20k, <20k→30k, else 50k |

### Visualization

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `plot_proportions_spatial(adata, ...)` | `cell_types`, `ncols`, `cmap`, `save_path` | Multi-panel spatial scatter. Auto-detects `obsm['spatial']` or `obs[['array_row', 'array_col']]` |
| `plot_cell_type_maps(adata, cell_type, ...)` | `cell_type`, `figsize`, `save_path` | Three-panel q05/q50/q95 comparison for uncertainty visualization |
| `plot_proportion_distribution(adata, ...)` | `cell_types`, `figsize`, `save_path` | Box plot of proportion distributions; defaults to top 8 cell types |
| `plot_dominant_cell_type(adata, ...)` | `figsize`, `save_path` | Spatial map colored by dominant cell type per spot |
| `normalize_proportions(props_df)` | — | Row-normalize DataFrame to sum 1; fills NaN with 0 |

## Official API — Agents Often Miss These

| Pattern | Key Point |
|---------|-----------|
| `RegressionModel.setup_anndata(ref, labels_key=...)` | Must be called **before** creating `RegressionModel(ref)`. Stores registration in `ref.uns['_scvi']`. Cannot be called twice on same object. |
| `Cell2location.setup_anndata(spatial)` | Same one-time registration rule. If processing multiple slides, call on each separately. |
| `ref_model.export_posterior(ref, sample_kwargs={...})` | Populates `ref.varm['means_per_cluster_mu_fg']`. This matrix is the **cell_state_df** passed to `Cell2location()`. |
| `mod.export_posterior(spatial, sample_kwargs={...})` | Populates `spatial.obsm['q05_cell_abundance_w_sf']`, `q50`, `q95`, `means`, `stds`. **All are raw abundances, not proportions.** |
| `N_cells_per_location` | Critical hyperparameter. Visium (55 μm): 3–10; Visium HD: 1–3; Slide-seq: 1–3. Our wrapper defaults to 10 (reads from `obs['n_cells']` if present). |
| `detection_alpha` | Prior on detection sensitivity. Default 200 (low within-slide variability). Try 20 if strong batch effects within a slide. |
| `accelerator='gpu'` vs `use_gpu=True` | scvi-tools ≥ 0.20 uses `accelerator` (PyTorch Lightning). Older versions use `use_gpu`. Our wrapper tries both. |
| `batch_size=None` | Full-batch training. For large datasets, set explicitly (e.g., 2500) to avoid OOM. |
| scvi-tools version pin | **`<1.2.0`** is required. ≥1.2.0 removes `parse_use_gpu_arg`, breaking cell2location imports. |

## Common Pitfalls

1. **Using normalized data as input**  
   Cell2location expects **raw integer counts** for both spatial and reference. Our `prepare_data()` warns and converts, but this can mask upstream data issues. Verify: `adata.X.dtype` should be integer and `adata.X.max()` should be > 20.

2. **Calling `setup_anndata` twice on the same object**  
   Like scvi-tools, cell2location stores registration in `adata.uns['_scvi']`. Re-calling raises `ValueError: AnnData has already been setup`. Our `run_cell2location()` wrapper automatically works on copies, so this is only a concern when using the raw cell2location API directly.

3. **Incorrect spatial coordinate detection**  
   Cell2location itself does not need spatial coordinates, but visualization does. Our plotting functions check `'spatial' in adata.obsm` (not `hasattr(adata.obsm, 'spatial')`, which is a common agent mistake — `AxisArrays` does not have a `spatial` attribute).

4. **Expecting proportions from `.obsm` directly**  
   `obsm['q05_cell_abundance_w_sf']` contains **raw cell abundances**, not proportions. Use `estimate_cell_type_proportions(normalize=True)` to get per-spot fractions summing to 1.

5. **Underestimating training time**  
   30,000 epochs × 5,000 spots ≈ 2–4 hours on GPU. CPU is 5–10× slower. Plan compute budget accordingly.

6. **Forgetting that reference and spatial need gene symbol overlap**  
   If reference uses Ensembl IDs and spatial uses gene symbols (or vice versa), common gene count will be near zero. Convert before `prepare_data()`.

7. **`N_cells_per_location` mismatch with tissue density**  
   Dense tissue (tumor, liver) may need 8–10; sparse tissue (brain cortex) may need 3–5. Default 10 is reasonable for Visium but can bias results in low-density tissues.

## Troubleshooting

### `ValueError: AnnData has already been setup`

`setup_anndata` was called twice. Cell2location (via scvi-tools) stores registration in `adata.uns['_scvi']`.

```python
# Our wrapper handles copies automatically — no action needed:
results = run_cell2location(spatial_prep, ref_prep, ...)

# If using raw cell2location API directly, pass copies:
RegressionModel.setup_anndata(spatial_prep.copy())
```

### `ImportError: cannot import name 'parse_use_gpu_arg' from 'scvi-tools'`

scvi-tools ≥ 1.2.0 is installed. Cell2location is incompatible.

```bash
# Fix: downgrade scvi-tools
pip install "scvi-tools<1.2.0"
```

### `RuntimeError: CUDA out of memory`

```python
# Fix: reduce batch size or use CPU
results = run_cell2location(
    spatial_prep, ref_prep,
    batch_size=1000,   # default is min(2500, n_spots)
    gpu=False
)
```

### Empty or near-zero proportions for all cell types

Likely causes: insufficient gene overlap, mismatched gene naming, or reference cell types not represented in spatial data.

```python
# Debug: check overlap
spatial_genes = set(spatial.var_names)
ref_genes = set(reference.var_names)
print(f"Common genes: {len(spatial_genes & ref_genes)}")
print(f"Reference cell types: {reference.obs['cell_type'].value_counts().to_dict()}")
```

### Unrealistic abundances (e.g., >100 cells per spot)

`N_cells_per_location` is too high for your tissue density.

```python
# Fix: manually set based on histology
results = run_cell2location(
    spatial_prep, ref_prep,
    # N_cells_per_location is auto-inferred; for manual control,
    # use cell2location API directly or modify spatial_prep.obs['n_cells']
)
```

### Convergence issues (ELBO not plateauing)

```python
# Fix: increase epochs or check data quality
from scripts.python.utils import estimate_optimal_epochs
recommended = estimate_optimal_epochs(spatial_prep)
results = run_cell2location(spatial_prep, ref_prep, max_epochs=recommended)
```

## Related Skills

- [bio-spatial-transcriptomics-deconvolution-rctd-r](../bio-spatial-transcriptomics-deconvolution-rctd-r/SKILL.md) — Faster R-based alternative; good for quick screening
- [bio-spatial-transcriptomics-deconvolution-spotlight-r](../bio-spatial-transcriptomics-deconvolution-spotlight-r/SKILL.md) — R-based NMF deconvolution
- [bio-single-cell-annotation-celltypist](../bio-single-cell-annotation-celltypist/SKILL.md) — Automated cell-type annotation for building the reference

## References

1. Kleshchevnikov et al. (2022). Cell2location maps fine-grained cell types in spatial transcriptomics. *Nature Biotechnology*, 40, 661–671.
2. Cell2location documentation: https://cell2location.readthedocs.io/
