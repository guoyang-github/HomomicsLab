---
name: bio-single-cell-annotation-celltypist
description: Automated cell type annotation using CellTypist pre-trained logistic regression models
version: 1.1
tool_type: python
primary_tool: CellTypist
supported_tools: [scanpy, anndata, sklearn]
keywords: ["single-cell", "annotation", "celltypist", "immune", "classification", "logistic-regression"]
---

## Version Compatibility & Installation

| Package | Required | Notes |
|---------|----------|-------|
| Python | >= 3.8 | |
| celltypist | >= 1.6 | Pre-trained models pickled with sklearn ~0.24; newer sklearn emits a warning but works |
| scanpy | >= 1.9 | |
| anndata | >= 0.8 | |
| scikit-learn | >= 1.0 | |
| scipy | >= 1.7 | Used in `merge_predictions` |

```bash
pip install celltypist scanpy anndata scikit-learn scipy
```

## Skill Overview

CellTypist annotates single-cell RNA-seq data using pre-trained logistic regression models. It is **fast**, **deterministic**, and works well when your data matches the model's tissue and species.

**When to use:**
- Human immune cell annotation (PBMC, blood, lymphoid tissue) — CellTypist's strongest domain
- Fast, automated annotation on large datasets
- Benchmarking against manual annotation or other tools
- Training custom logistic-regression models on labeled reference data

**When NOT to use:**
- Non-immune tissues without an appropriate model (models are tissue-specific)
- Mouse data (only one model available: `NLP_Mouse_Immune.pkl`)
- Cases requiring probabilistic uncertainty quantification beyond a single confidence score
- When you need annotation without any log-normalized data (CellTypist strictly requires it)

## Core Workflow

### Step 1: Data Preparation

**Input:** Raw or normalized AnnData  
**Output:** Log-normalized AnnData ready for CellTypist

```python
import scanpy as sc
import numpy as np

# If starting from raw counts
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# Requirements checklist:
# - Gene symbols (CD3D, CD19), NOT ENSEMBL IDs (ENSG...)
# - Log-normalized expression in adata.X
# - Include all genes (do NOT subset to HVGs before annotation)
```

| Parameter | Why it matters |
|-----------|----------------|
| `target_sum=1e4` | CellTypist models trained with this normalization. Using different scales degrades accuracy. |
| Gene symbols | Models use gene symbols. ENSEMBL IDs cause "No features overlap" error. |
| Keep all genes | Subsetting to HVGs before annotation removes model genes and crashes or silently yields poor predictions. |

### Step 2: Select & Download Model

**Input:** Tissue/species info  
**Output:** Model loaded into memory

```python
import celltypist

# List all official models
models_df = celltypist.models.models_description()

# Download a specific model (cached in ~/.celltypist/data/models/)
celltypist.models.download_models(model='Immune_All_Low.pkl')

# Load model object for inspection
model = celltypist.models.Model.load('Immune_All_Low.pkl')
print(f"Cell types: {len(model.cell_types)}")
print(f"Features: {len(model.features)}")
```

**Common pre-trained models:**

| Model | Cell Types | Best For |
|-------|-----------|----------|
| `Immune_All_Low.pkl` | 28 broad | General human immune (default) |
| `Immune_All_High.pkl` | 98 fine-grained | Detailed immune subtypes |
| `Cells_Intestinal_Training.pkl` | 56 | Intestinal epithelial |
| `Cells_Lung_Airway_Training.pkl` | 38 | Lung airway epithelial |
| `COVID19_Immune_Landscape.pkl` | — | COVID-specific immune states |
| `NLP_Mouse_Immune.pkl` | 22 | Mouse immune |

> **Agent note:** Model names **must include the `.pkl` suffix**. `Model.load('Immune_All_Low')` fails.

### Step 3: Run Annotation

**Input:** Log-normalized AnnData + model  
**Output:** `AnnotationResult` object

```python
import celltypist

predictions = celltypist.annotate(
    adata,
    model='Immune_All_Low.pkl',
    mode='best match',           # 'best match' or 'prob match'
    majority_voting=True,        # Refine via cluster consensus (recommended)
    over_clustering='leiden',    # Use existing clusters; omit to auto-cluster
    p_thres=0.5,                 # Probability threshold for multi-label mode
    use_GPU=False,               # GPU only used for over-clustering Leiden
    min_prop=0                   # Min proportion for subcluster assignment
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | str | `'best match'` | `'best match'` = one label per cell; `'prob match'` = multi-label (0, 1, or ≥2 labels per cell) |
| `majority_voting` | bool | `False` | Refine predictions by cluster-level consensus. Dramatically improves robustness. |
| `over_clustering` | str / array / `None` | `None` | Cluster labels for majority voting. If `None` and `majority_voting=True`, CellTypist auto-over-clusters. |
| `p_thres` | float | `0.5` | Probability threshold for `'prob match'` mode only. Ignored in `'best match'`. |
| `use_GPU` | bool | `False` | Accelerates Leiden over-clustering only (requires rapids). Does NOT speed up prediction. |

### Step 4: Add Predictions to AnnData

**Input:** `AnnotationResult`  
**Output:** AnnData with new `.obs` columns

```python
# Native CellTypist API
adata = predictions.to_adata(prefix='celltypist_')

# Or use the wrapper which adds a convenience 'celltypist_label' column
from core_analysis import add_predictions_to_adata
adata = add_predictions_to_adata(predictions, prefix='celltypist_')
```

**Columns added by `to_adata()`:**

| Column | Description |
|--------|-------------|
| `celltypist_predicted_labels` | Individual cell prediction |
| `celltypist_majority_voting` | Cluster-consensus label (if `majority_voting=True`) |
| `celltypist_conf_score` | Confidence score (0–1) |
| `celltypist_over_clustering` | Cluster assignments used for majority voting |
| `celltypist_label` | **Wrapper-only**: convenience column = majority_voting if available, else predicted_labels |

> **Agent note:** `predictions` object also exposes `predictions.probability_matrix` and `predictions.decision_matrix` as pandas DataFrames. Access these **before** calling `to_adata()` if you need them.

### Step 5: Filter by Confidence

**Input:** Annotated AnnData  
**Output:** AnnData with `_filtered` label column

```python
from core_analysis import filter_by_confidence

adata = filter_by_confidence(
    adata,
    conf_col='celltypist_conf_score',
    label_col='celltypist_label',
    threshold=0.5,
    unassigned_label='Unassigned'
)
# New column: adata.obs['celltypist_label_filtered']
```

| Threshold | Behavior |
|-----------|----------|
| `0.3` | Permissive — more cells labeled, lower accuracy |
| `0.5` | Balanced — recommended default |
| `0.7` | Stringent — high confidence only |

### Step 6: Summarize & Export

```python
from utils import summarize_annotations, export_annotations

# Summary table: cell type, n_cells, proportion, mean/median confidence
summary = summarize_annotations(adata)

# Export to CSV (includes cell_barcode, label, confidence)
export_annotations(adata, output_file='annotations.csv')

# Save annotated h5ad
adata.write('annotated_data.h5ad')
```

## Complete Pipeline (Copy-Pasteable)

```python
import scanpy as sc
import celltypist

# 1. Load and normalize
adata = sc.read_h5ad("your_data.h5ad")
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# 2. Ensure clusters exist for majority voting
if 'leiden' not in adata.obs.columns:
    sc.pp.highly_variable_genes(adata, n_top_genes=2000)
    sc.pp.pca(adata, use_highly_variable=True)
    sc.pp.neighbors(adata)
    sc.tl.leiden(adata, resolution=0.5)

# 3. Download model if needed
celltypist.models.download_models(model='Immune_All_Low.pkl')

# 4. Annotate
predictions = celltypist.annotate(
    adata,
    model='Immune_All_Low.pkl',
    mode='best match',
    majority_voting=True,
    over_clustering='leiden'
)

# 5. Add to AnnData
adata = predictions.to_adata(prefix='celltypist_')

# 6. Filter low confidence
from core_analysis import filter_by_confidence
adata = filter_by_confidence(adata, threshold=0.5)

# 7. Summarize
from utils import summarize_annotations
print(summarize_annotations(adata))

# 8. Save
adata.write('annotated_data.h5ad')
```

## Skill-Provided Functions

**Pipeline orchestration**
- `run_celltypist_annotation(adata, model, majority_voting, over_clustering, mode, prefix)` — validation + annotate + add to adata in one call

**Annotation helpers**
- `annotate_cells(adata, model, mode, p_thres, majority_voting, over_clustering, use_GPU, min_prop)` — wrapper around `celltypist.annotate()` with auto model loading
- `add_predictions_to_adata(predictions, prefix)` — calls `predictions.to_adata()` and adds convenience `celltypist_label` column

**Quality control**
- `validate_celltypist_input(adata, check_normalized)` — checks for ENSEMBL IDs, raw counts, empty data
- `filter_by_confidence(adata, conf_col, label_col, threshold, unassigned_label)` — marks low-confidence cells as Unassigned
- `check_gene_overlap(adata, model)` — reports overlap fraction between data genes and model genes; auto-downloads model if missing

**Data preparation**
- `prepare_data_for_celltypist(adata, layer, normalize, target_sum, log_transform)` — handles layer extraction, auto-detects raw counts, normalizes

**Model selection**
- `recommend_model(tissue, species, resolution)` — maps tissue/species to model name string

**Post-analysis**
- `summarize_annotations(adata, label_col, conf_col)` — per-cell-type summary with proportions and confidence stats
- `export_annotations(adata, output_file, label_col, conf_col)` — CSV export with barcode + label + confidence
- `create_annotation_report(adata, model_name, output_file)` — human-readable text report

**Advanced**
- `compare_models(adata, models, majority_voting)` — run multiple models and compare cell type counts
- `train_celltypist_model(adata, labels, genes, model_file, **kwargs)` — train custom model; passes kwargs to `celltypist.train`

**Visualization**
- `plot_confidence_distribution(adata)` — histogram + boxplot by cell type
- `plot_celltype_proportions(adata, groupby)` — stacked bar plot by sample/condition
- `plot_umap_with_predictions(adata)` — UMAP side-by-side: labels + confidence
- `plot_prediction_heatmap(adata, cluster_col)` — cluster vs prediction heatmap
- `plot_annotation_summary(adata, output_dir)` — 6-panel comprehensive figure

## Official API — Agents Often Miss These

**1. `celltypist.annotate()` first argument is `filename`, not `adata`**
The signature is `annotate(filename='', model=None, ...)`. When passing an AnnData object, you **must** use the keyword `model=` for the model:
```python
# WRONG: celltypist.annotate(adata, 'Immune_All_Low.pkl')
# RIGHT:
celltypist.annotate(adata, model='Immune_All_Low.pkl')
```

**2. Model names require `.pkl` suffix**
```python
# WRONG
celltypist.models.Model.load('Immune_All_Low')
# RIGHT
celltypist.models.Model.load('Immune_All_Low.pkl')
```

**3. `majority_voting=True` without `over_clustering` auto-clusters your data**
CellTypist will internally over-cluster the data. If you want control, explicitly provide `over_clustering='leiden'`.

**4. `mode='prob match'` assigns MULTIPLE labels per cell**
A cell can end up with 0, 1, or ≥2 labels. The result is stored as comma-separated strings in `predicted_labels`.

**5. `use_GPU=False` is the default and GPU only affects over-clustering**
The actual logistic regression prediction is always CPU-based. `use_GPU=True` only accelerates the Leiden clustering step when `majority_voting=True`.

**6. `celltypist.train()` defaults to `check_expression=True`**
If your training data is raw counts, `celltypist.train()` will raise an error. Pass `check_expression=False` to bypass (not recommended unless you know what you're doing).

**7. Access `probability_matrix` and `decision_matrix` from the result object, not AnnData**
```python
prob = predictions.probability_matrix   # DataFrame: cells × cell types
dec = predictions.decision_matrix       # DataFrame: raw logistic scores
```
These are **not** inserted into AnnData by default; set `insert_prob=True` or `insert_decision=True` in `to_adata()`.

**8. `predictions.summary_frequency(by='majority_voting')` for majority-voting summary**
Default is `by='predicted_labels'`. If you used majority voting, explicitly request the majority voting summary.

## Common Pitfalls

1. **⚠️ Passing raw counts to CellTypist**  
   CellTypist expects log-normalized data. Raw counts cause nonsensical predictions or errors. Always run `sc.pp.normalize_total(adata, target_sum=1e4); sc.pp.log1p(adata)` first.

2. **⚠️ Using ENSEMBL gene IDs**  
   CellTypist models use gene symbols (e.g., `CD3D`). ENSEMBL IDs result in "No features overlap with the model". Convert IDs beforehand using biomart or `scanpy` mapping tools.

3. **⚠️ Subsetting to HVGs before annotation**  
   If you subset genes to HVGs, you may remove critical marker genes the model relies on. Annotate on the **full gene set**, then subset afterward if needed.

4. **⚠️ Forgetting `.pkl` in model name**  
   `celltypist.models.Model.load('Immune_All_Low')` raises `FileNotFoundError`. Always include `.pkl`.

5. **⚠️ Expecting `to_adata()` to modify the original AnnData in place**  
   `predictions.to_adata()` returns a **new** AnnData. It does not modify `predictions.adata` in place.

6. **⚠️ Using `mode='prob match'` without understanding multi-label output**  
   Multi-label predictions are comma-separated strings (e.g., `"T cell, B cell"`). Downstream analyses expecting single labels will break.

7. **⚠️ Sklearn version incompatibility warning**  
   Official models were trained with sklearn ~0.24. Loading them in sklearn ≥1.0 produces an `InconsistentVersionWarning`. This is usually harmless, but retraining custom models with your current sklearn version avoids it entirely.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `ValueError: No features overlap with the model` | Gene symbols mismatch (ENSEML IDs or different naming convention) | Convert to gene symbols; check `adata.var_names[:10]` |
| `FileNotFoundError: No such file: Immune_All_Low.pkl` | Model not downloaded or missing `.pkl` suffix | Run `celltypist.models.download_models(model='Immune_All_Low.pkl')` |
| Predictions all have very low confidence (<0.3) | Wrong tissue / model mismatch; or data not log-normalized | Check gene overlap with `check_gene_overlap()`; verify normalization |
| `KeyError: 'celltypist_conf_score'` | Tried to filter/summarize before adding predictions to AnnData | Run `adata = predictions.to_adata(prefix='celltypist_')` first |
| `ValueError` from `celltypist.train()` about expression | Training data is raw counts and `check_expression=True` (default) | Normalize first, or pass `check_expression=False` (not recommended) |
| Majority voting produces only 1–2 cell types | Over-clustering resolution too low or data is homogeneous | Try `over_clustering` with higher-resolution clusters or disable majority voting |
| UMAP plot fails in visualization | No `X_umap` in `adata.obsm` | Run `sc.tl.umap(adata)` after `sc.pp.neighbors(adata)` |

## Expected Output Artifacts

For the chat summarizer to render a Claude-Code-style end-to-end report, the agent **must** persist the following artifacts. The summarizer parses the exact filenames and report sections listed below.

### Required files

1. `{input_basename}_celltypist.h5ad` — annotated AnnData with `celltypist_*` obs columns.
2. `{input_basename}_celltypist_labels.csv` — per-cell labels with at least:
   - `barcode` (or `cell_id`)
   - `predicted_labels` or `celltypist_predicted_labels`
   - `conf_score` or `celltypist_conf_score`
3. `{input_basename}_celltypist_report.txt` — human-readable report containing these exact lines (Chinese preferred):
   - `输入数据: {n_cells} 细胞 × {n_genes} 基因`
   - `使用模型: {model_name}.pkl`
   - `基因重叠: {n_overlap} / {n_model_genes}`
   - `预测模式: best match + majority voting`
   - `置信度阈值: 0.5`
   - `平均置信度: {mean_conf}`
   - `Unassigned 占比: {pct}%`
   - `ARI（全部）: {ari}`
   - `NMI（全部）: {nmi}`
   - `数据预处理说明: {note}`
4. `model_info.json` — `{"model": "Immune_All_Low.pkl", "n_cell_types": 28}`
5. `gene_overlap.json` — `{"n_adata_genes": 29057, "n_model_genes": 6639, "n_overlap": 6023}`

### Comparison artifacts (when the user asks to compare with a reference column)

6. `{input_basename}_celltypist_per_reference.csv` — columns:
   - `reference` or `all_celltype`
   - `best_match`
   - `recall`
   - `count` / `n_cells`
7. `{input_basename}_celltypist_confusion.csv` — confusion matrix with reference labels as rows and predicted labels as columns.
8. `comparison_report.txt` — start with the header `CellTypist vs all_celltype comparison`, followed by:
   - `Total cells: {n}`
   - `Mean CellTypist confidence: {mean_conf}`
   - `Coarse overall agreement: {agreement}`
   - `ARI: {ari}`
   - `NMI: {nmi}`
   - Per-label rows: `{ref_label} n={n} recall={recall} top_pred={best_pred}`

### Figures

9. `figures/{input_basename}_celltypist_confidence_distribution.png`
10. `figures/{input_basename}_celltypist_celltype_proportions.png`
11. `figures/{input_basename}_celltypist_umap_predictions.png`
12. `figures/{input_basename}_celltypist_summary.png`
13. `figures/{input_basename}_celltypist_vs_all_celltype_heatmap.png` (when a reference label exists)

> **Agent note:** Use the exact filenames and section headers above. The chat summarizer extracts the model name, gene overlap, ARI/NMI, and the output-inventory table from these artifacts. Missing or inconsistently named files will produce a degraded report.

## Related Skills

- [bio-single-cell-annotation-sctype-r](../bio-single-cell-annotation-sctype-r/SKILL.md) — Marker-based annotation (R, good for any tissue with marker lists)
- [bio-single-cell-annotation-singler-r](../bio-single-cell-annotation-singler-r/SKILL.md) — Reference-based annotation (R, uses bulk reference profiles)
- [bio-single-cell-clustering](../bio-single-cell-clustering/SKILL.md) — Leiden/Louvain clustering (required for majority voting)

## References

1. Domínguez Conde et al. (2022). Cross-tissue immune cell analysis reveals tissue-specific features in humans. *Science*, 376, eabl5197.
2. CellTypist documentation: https://www.celltypist.org/
3. GitHub: https://github.com/Teichlab/celltypist
