---
name: bio-single-cell-doublet-solo
description: Deep learning-based doublet detection using SOLO from scvi-tools. Trains a semi-supervised classifier on scVI latent space to distinguish singlets from simulated doublets.
tool_type: python
primary_tool: scvi
supported_tools: [scanpy, anndata]
languages: [python]
keywords: ["single-cell", "doublet-detection", "SOLO", "scVI", "deep-learning", "quality-control"]
code_location: scripts/python/
version_compatibility:
  python: ">=3.9"
  scvi-tools: ">=1.0"
  scanpy: ">=1.9"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| Python | >= 3.9 | |
| scvi-tools | >= 1.0 | Core framework |
| scanpy | >= 1.9 | Single-cell analysis |
| anndata | >= 0.8 | Data structure |
| torch | >= 2.0 | Deep learning backend |
| matplotlib | >= 3.7 | Visualization |
| seaborn | >= 0.12 | Visualization |
| scikit-image | optional | For Otsu threshold estimation |
| kneed | optional | For knee-based threshold estimation |

## Installation

```bash
pip install scvi-tools scanpy anndata matplotlib seaborn

# Optional: threshold estimation dependencies
pip install scikit-image kneed

# Optional: GPU support
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

## Skill Overview

SOLO (Single-cell Omics Linkage Observatory) detects doublets by training a neural network classifier on scVI's latent representations. It simulates artificial doublets by combining real cell profiles and learns to distinguish them from singlets.

**Core workflow**: Validate raw counts → QC filter → Train scVI → Train SOLO → Predict → Filter → Visualize

**When to use**:
- Large datasets (>5,000 cells) where deep learning-based detection is preferred
- Existing scVI integration workflow — SOLO reuses the trained scVI model
- Need calibrated doublet probabilities (not just binary calls)
- Multi-batch experiments requiring per-batch doublet detection

**When NOT to use**:
- Very small datasets (<500 cells) — SOLO needs sufficient data for meaningful latent spaces. Use Scrublet or DoubletFinder instead.
- Non-UMI data (e.g., Smart-seq2 without UMIs) — doublet simulation assumes Poisson-sampled UMIs.
- Raw counts are unavailable — SOLO cannot simulate valid doublets from normalized data.
- scVI integration is already failing — SOLO inherits scVI's latent space quality.

## Quick Reference

| Goal | Entry Point | Key Difference |
|------|-------------|---------------|
| Single dataset | `run_solo_pipeline(adata)` | One-shot: scVI → SOLO → predictions |
| Multi-batch | `run_solo_per_batch(adata, batch_key=...)` | Shared scVI + per-batch SOLO |
| Full control | `train_scvi_model()` → `train_solo_model()` → `predict_doublets()` | Custom hyperparameters |

## Core Workflow (Step-by-Step)

### Step 1: Validate and Prepare Raw Counts

**Goal**: Ensure data is suitable for SOLO and apply QC filtering only.

**Input requirements**:
- `adata.X`: **Raw UMI counts** (integers, not normalized) — **required**
- `adata.obs`: Cell metadata (optional: batch key for multi-batch)

```python
from scripts.python.utils import validate_adata_for_solo, preprocess_for_solo

# Verify raw counts
validate_adata_for_solo(adata, require_raw=True)
# Warns if max value < 20 or non-integer — strong signal data is normalized.

# QC only — never normalize
adata = preprocess_for_solo(
    adata,
    min_genes=200,
    min_cells=3,
    max_genes=8000,      # optional
    max_counts=50000,    # optional
    mt_threshold=20      # optional
)
```

**CRITICAL**: `preprocess_for_solo()` **never normalizes**. It only filters cells/genes and computes QC metrics. Normalization must happen **after** doublet removal.

**MT-gene detection**: Detects both human (`MT-`) and mouse (`mt-`) mitochondrial gene names automatically.

---

### Step 2: Run Complete Pipeline

**Goal**: Train scVI, train SOLO, and get doublet predictions in one call.

```python
from scripts.python.core_analysis import run_solo_pipeline

predictions = run_solo_pipeline(
    adata,
    batch_key=None,              # set if multi-batch
    scvi_epochs=400,
    solo_epochs=100,
    doublet_ratio=2,
    doublet_threshold=0.5,
    use_gpu=True,
    inplace=True,                # writes to adata.obs AND returns predictions
    verbose=True
)

# adata.obs now contains:
#   solo_doublet_score   (probability)
#   solo_singlet_score   (probability)
#   solo_prediction      ('singlet' or 'doublet')
#   uns['solo_threshold'] = 0.5
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `batch_key` | None | Batch column for multi-batch experiments |
| `scvi_epochs` | 400 | scVI training epochs |
| `solo_epochs` | 100 | SOLO classifier training epochs |
| `doublet_ratio` | 2 | Simulated doublets per real cell |
| `doublet_threshold` | 0.5 | Probability cutoff for calling doublets |
| `use_gpu` | True | Auto-detects CUDA; falls back to CPU |
| `inplace` | True | Writes `solo_*` columns to `adata.obs` |

**What this adds over raw scvi-tools**: Sets random seed, orchestrates the full chain (`setup_anndata` → scVI train → SOLO train → predict → threshold → write to `.obs`), and handles GPU/CPU fallback automatically.

**CRITICAL**: `scvi.model.SCVI.setup_anndata()` stores registration in `adata.uns['_scvi']` and **can only be called once**. Calling `run_solo_pipeline` twice on the same `adata` (e.g., with different `batch_key`) will fail. Use `adata.copy()` if re-training.

---

### Step 3: Custom Training (Optional)

**Goal**: Full control over scVI and SOLO hyperparameters.

```python
from scripts.python.core_analysis import train_scvi_model, train_solo_model, predict_doublets

vae = train_scvi_model(
    adata,
    batch_key='batch',
    n_latent=20,
    n_hidden=256,
    n_layers=2,
    max_epochs=400,
    use_gpu=True
)

solo = train_solo_model(
    vae,
    restrict_to_batch=None,   # restrict to one batch if needed
    doublet_ratio=2,
    max_epochs=100,
    use_gpu=True
)

predictions = predict_doublets(solo, soft=True)
# soft=True  → DataFrame with 'doublet' and 'singlet' probability columns
# soft=False → DataFrame with 'prediction' column containing STRINGS
```

| Parameter | Default | Small (<5k) | Medium (5k–30k) | Large (>30k) |
|-----------|---------|-------------|-----------------|--------------|
| `n_latent` | 10 | 10 | 10–20 | 20–30 |
| `n_hidden` | 128 | 128 | 128–256 | 256–512 |
| `n_layers` | 3 | 2 | 2–3 | 3 |
| `max_epochs` (scVI) | 400 | 200 | 400 | 400–500 |
| `max_epochs` (SOLO) | 100 | 100 | 100–150 | 100–150 |
| `doublet_ratio` | 2 | 2 | 2–3 | 2–3 |

---

### Step 4: Threshold Inspection and Adjustment

**Goal**: Verify predicted doublet rate aligns with biology and pick an optimal threshold.

```python
from scripts.python.utils import (
    estimate_expected_doublet_rate,
    optimize_threshold_range,
    estimate_optimal_threshold
)

# Expected rate from 10x documentation
expected = estimate_expected_doublet_rate(adata.n_obs, method='10x')

# Compare multiple thresholds
threshold_comparison = optimize_threshold_range(
    predictions,
    thresholds=[0.3, 0.4, 0.5, 0.6, 0.7]
)

# Auto-estimate (Otsu requires skimage; falls back to 90th percentile)
optimal = estimate_optimal_threshold(predictions, method='otsu')
```

| Threshold | Use Case |
|-----------|----------|
| 0.3 | Aggressive; risk of losing real singlets |
| 0.5 | Balanced default |
| 0.7 | Conservative; may miss doublets |
| Auto (Otsu) | Bimodal score distributions |
| Expected rate | Known 10x loading density |

---

### Step 5: Filter Doublets

**Goal**: Remove predicted doublets from the dataset.

```python
from scripts.python.core_analysis import filter_doublets

adata_clean = filter_doublets(adata, predictions, threshold=0.5, inplace=False)
```

**What this adds**: Handles multiple prediction formats (`prediction_label` strings, `prediction` 0/1, or raw `doublet` scores). Auto-retrieves threshold from `adata.uns['solo_threshold']` if `threshold=None`.

---

### Step 6: Multi-Batch Workflow (If Applicable)

**Goal**: Detect doublets separately for each batch while sharing a single scVI encoder.

```python
from scripts.python.core_analysis import run_solo_per_batch
import pandas as pd

batch_results = run_solo_per_batch(
    adata,
    batch_key='lane',
    scvi_epochs=400,
    solo_epochs=100
)
# If a batch fails (too few cells), warns and sets results[batch] = None

all_preds = pd.concat([v for v in batch_results.values() if v is not None])
```

**Caveat**: Assumes batch effects are handled by scVI. If batches are extremely different (different tissues), consider separate scVI models per batch instead.

---

### Step 7: Visualize

**Goal**: Inspect doublet predictions on embedding and score distributions.

```python
from scripts.python.visualization import (
    plot_doublet_summary,
    plot_doublets_on_embedding,
    plot_doublet_score_distribution
)

# Requires UMAP/t-SNE precomputed
plot_doublets_on_embedding(adata, basis='umap')
# Validates X_umap exists before plotting. Dual panel: binary + continuous scores.

plot_doublet_score_distribution(predictions, threshold=0.5)
# Histogram with threshold line, mean, and annotated rate.

plot_doublet_summary(predictions)
# 5-panel dashboard: hist, pie, box, CDF, stats table.
```

---

### Step 8: Cross-Method Comparison (Optional)

**Goal**: Validate SOLO results against another detector.

```python
from scripts.python.utils import compare_predictions, ensemble_doublet_calls

# Compare with Scrublet/DoubletFinder
comparison = compare_predictions(solo_preds, scrublet_preds, other_name='scrublet')
# Returns: agreement, confusion matrix, both_doublet, both_singlet, solo_only, scrublet_only

# Weighted ensemble
ensemble = ensemble_doublet_calls(
    {'solo': solo_preds, 'scrublet': scrublet_preds},
    weights={'solo': 0.6, 'scrublet': 0.4}
)
```

**What `compare_predictions` adds**: Automatically handles boolean, string, and numeric prediction columns from different tools.

---

## Complete Pipeline

```python
from scripts.python.utils import validate_adata_for_solo, preprocess_for_solo
from scripts.python.core_analysis import run_solo_pipeline, filter_doublets
from scripts.python.visualization import plot_doublet_summary, plot_doublets_on_embedding
import scanpy as sc

# 1. Load and validate raw counts
adata = sc.read_h5ad("raw_counts.h5ad")
validate_adata_for_solo(adata, require_raw=True)
adata = preprocess_for_solo(adata, min_genes=200, min_cells=3)

# 2. Run SOLO
predictions = run_solo_pipeline(
    adata, batch_key=None, scvi_epochs=400, solo_epochs=100,
    doublet_threshold=0.5, use_gpu=True, inplace=True
)

# 3. Filter
adata_clean = filter_doublets(adata, predictions, threshold=0.5, inplace=False)

# 4. Normalize AFTER removing doublets
sc.pp.normalize_total(adata_clean, target_sum=1e4)
sc.pp.log1p(adata_clean)

# 5. Visualize (requires UMAP)
sc.pp.highly_variable_genes(adata_clean, n_top_genes=2000)
sc.pp.scale(adata_clean)
sc.tl.pca(adata_clean)
sc.pp.neighbors(adata_clean)
sc.tl.umap(adata_clean)

plot_doublets_on_embedding(adata_clean, basis='umap')
plot_doublet_summary(predictions)

# 6. Save
adata_clean.write_h5ad("clean_data.h5ad")
predictions.to_csv("solo_predictions.csv")
```

## Skill-Provided Functions

Source: `scripts/python/` directory

### Core Analysis

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `run_solo_pipeline(adata, ...)` | `batch_key`, `scvi_epochs`, `solo_epochs`, `doublet_threshold` | End-to-end: scVI → SOLO → predictions → `adata.obs` |
| `run_solo_per_batch(adata, batch_key, ...)` | `batch_key` | Shared scVI + per-batch SOLO; error-tolerant |
| `train_scvi_model(adata, ...)` | `n_latent`, `n_hidden`, `n_layers`, `max_epochs` | Wraps scVI with seed, GPU auto-detect, hyperparameter passthrough |
| `train_solo_model(vae, ...)` | `restrict_to_batch`, `doublet_ratio`, `max_epochs` | Wraps SOLO.from_scvi_model + train |
| `predict_doublets(solo, soft=True)` | `soft`, `return_logits` | Normalizes output to DataFrame; `soft=False` returns **string labels** |
| `filter_doublets(adata, predictions, ...)` | `threshold`, `inplace` | Multi-format prediction handling; auto-retrieves stored threshold |
| `add_predictions_to_adata(adata, predictions, ...)` | `doublet_threshold` | Adds `solo_*` columns to `.obs`; stores threshold in `.uns` |

### Utilities

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `validate_adata_for_solo(adata, ...)` | `require_raw`, `min_cells`, `min_genes` | Type/size check + **raw-count heuristic** (integer detection) |
| `preprocess_for_solo(adata, ...)` | `min_genes`, `max_genes`, `mt_threshold` | QC filtering only; **never normalizes** |
| `estimate_optimal_threshold(predictions, ...)` | `method` ('otsu', 'knee', 'quantile') | Auto threshold with fallback if deps missing |
| `optimize_threshold_range(predictions, ...)` | `thresholds` | Grid comparison across thresholds |
| `estimate_expected_doublet_rate(n_cells, ...)` | `method` ('10x', 'dropseq', 'general') | Platform-specific formula (~0.8% per 1k cells for 10x) |
| `compare_predictions(solo_preds, other_preds, ...)` | `other_name`, `solo_threshold` | Confusion matrix; handles bool/str/num predictions |
| `ensemble_doublet_calls(predictions_dict, ...)` | `weights` | Weighted ensemble across multiple detectors |
| `merge_predictions_with_adata(adata, predictions, ...)` | `prefix` | **Index-alignment safe** merge; supports custom prefix |
| `create_summary_report(predictions, ...)` | `threshold`, `output_path` | Text report with statistics and interpretation |

### Visualization

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `plot_doublets_on_embedding(adata, ...)` | `basis`, `doublet_key`, `score_key` | **Validates embedding exists**; dual panel (binary + scores) |
| `plot_doublet_score_distribution(predictions, ...)` | `threshold`, `bins` | Histogram with threshold line, mean, rate annotation |
| `plot_doublet_summary(predictions, ...)` | `threshold` | 5-panel dashboard: hist, pie, box, CDF, stats table |
| `plot_batch_comparison(batch_results, ...)` | | Bar chart of rates + overlaid score distributions |
| `plot_training_history(model, ...)` | | Loss curves; handles DataFrame/array history formats |

## Official API — Agents Often Miss These

| Pattern | Key Point |
|---------|-----------|
| `scvi.model.SCVI.setup_anndata(adata, ...)` | Stores registration in `adata.uns['_scvi']`. **Can only be called once per adata**. Re-training requires `adata.copy()`. |
| `SOLO.from_scvi_model(vae, adata=..., restrict_to_batch=...)` | Creates SOLO using scVI encoder; simulates doublets internally. If `adata` omitted, uses scVI's registered AnnData. |
| `solo.predict(soft=True)` | Returns DataFrame with `singlet` and `doublet` probability columns (sum to 1 per cell). |
| `solo.predict(soft=False)` | Returns **pandas Series** of string labels (`'singlet'` / `'doublet'`). Our wrapper converts to DataFrame. |
| `model.save(dir_path, overwrite=..., save_anndata=...)` | Prefer `save_anndata=False` to avoid storing large AnnData copy. |
| `SOLO.load(dir_path)` | Returns model ready for prediction. Original AnnData NOT required if `save_anndata=False`. |
| `scvi.settings.seed` | Our wrappers set this automatically via `random_seed` parameter. |

## Common Pitfalls

1. **Normalizing before SOLO**  
   `sc.pp.normalize_total()` or `sc.pp.log1p()` before `run_solo_pipeline()` produces **invalid simulated doublets**. QC-filter only, then run SOLO, then normalize the filtered data.

2. **`setup_anndata` can only be called once**  
   Calling `train_scvi_model()` twice on the same `adata` will fail. Use `adata.copy()` if re-training.

3. **`run_solo_pipeline(inplace=True)` modifies input `adata`**  
   Unlike scanpy functions that return `None` when `inplace=True`, this returns predictions AND modifies `adata.obs`.

4. **GPU memory on large datasets**  
   scVI allocates the full count matrix on GPU. For >50k cells, reduce `batch_size` or use `use_gpu=False`.

5. **Predictions index may not match `adata.obs_names`**  
   `predict_doublets()` returns a DataFrame indexed by SOLO's internal cell names. If cells were reordered, use `merge_predictions_with_adata()` which checks alignment.

6. **`predict_doublets(soft=False)` returns strings**  
   If downstream code expects numeric labels, use `soft=True` and threshold manually.

7. **Per-batch SOLO reuses the same scVI encoder**  
   If batches are extremely different, consider separate scVI models per batch.

8. **Mt-gene detection supports human and mouse**  
   `preprocess_for_solo()` detects both `MT-` (human) and `mt-` (mouse) prefixes. For other naming conventions (e.g. `Mt-`), pre-compute `pct_counts_mt` manually.

## Troubleshooting

### `ValueError: AnnData has already been setup`

`setup_anndata` was called twice on the same object. scvi-tools stores registration in `adata.uns['_scvi']`.

```python
# Fix: use a copy
predictions = run_solo_pipeline(adata.copy(), batch_key='batch')
```

### `RuntimeError: CUDA out of memory`

```python
# Fix: switch to CPU or reduce batch size
predictions = run_solo_pipeline(adata, use_gpu=False, batch_size=64)
```

### Predicted doublet rate >> 10%

Likely caused by feeding normalized data to SOLO. The simulated doublets are mathematically invalid.

```python
# Fix: restart with raw counts
# Verify: adata.X.max() should be > 20 and integer-like
print(adata.X.max())   # should be a large integer
```

### `ImportError: skimage` when using Otsu threshold

```python
# Fix: install scikit-image, or use quantile method
optimal = estimate_optimal_threshold(predictions, method='quantile')
```

### Batch fails silently in `run_solo_per_batch`

One batch has too few cells for SOLO training.

```python
# Fix: check which batches failed and filter small ones beforehand
for batch, result in batch_results.items():
    if result is None:
        print(f"Batch {batch} failed — too few cells")
```

### Loss curves flat / not converging

```python
# Fix: increase epochs or adjust learning rate
vae = train_scvi_model(adata, max_epochs=600, learning_rate=5e-4)
```

## Related Skills

- [bio-single-cell-doublet-scrublet](../bio-single-cell-doublet-scrublet/SKILL.md) — Faster, non-deep-learning alternative; better for small datasets
- [bio-single-cell-preprocessing](../bio-single-cell-preprocessing/SKILL.md) — QC and filtering workflows
- [bio-single-cell-batch-integration](../bio-single-cell-batch-integration/SKILL.md) — If you need scVI integration beyond doublet detection

## References

1. Bernstein et al. (2020). Solo: Doublet identification in single-cell RNA-Seq via semi-supervised deep learning. *Cell Systems*, 11(1), 95-101.
2. Gayoso et al. (2022). A Python library for probabilistic analysis of single-cell omics data. *Nature Biotechnology*, 40, 1636-1639.
3. scvi-tools documentation: https://docs.scvi-tools.org/
