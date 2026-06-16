---
name: bio-single-cell-perturbation-pertpy
description: pertpy is a Python toolkit for perturbation analysis of single-cell data. Use for differential expression, log fold change, and signature scoring in perturbation screens.
tool_type: python
primary_tool: pertpy
languages: [python]
keywords: ["single-cell", "perturbation", "CRISPR", "screen", "differential-expression", "pertpy", "python", "Augur", "Mixscape"]
---

## Version Compatibility

- **Python**: >=3.8
- **pertpy**: >=0.6
- **scanpy**: >=1.9
- **pandas**: >=1.3
- **numpy**: >=1.20

## Installation

```bash
pip install pertpy
```

## Core Analysis Workflow

The pertpy skill provides comprehensive perturbation analysis for single-cell data. Follow this step-by-step workflow for CRISPR screens, drug perturbations, or genetic knockouts.

### Step 1: Setup and Data Loading

Validate perturbation data and check required columns exist in `adata.obs`.

```python
from core_analysis import check_perturbation_data
from utils import get_perturbation_summary

# Validate the data
check_perturbation_data(
    adata,
    perturbation_col='perturbation',
    control='control'
)

# Get summary statistics
summary = get_perturbation_summary(adata, perturbation_col='perturbation')
print(summary)
```

**Key Points:**
- Verify at least 2 perturbations present
- Confirm control perturbation label
- Check cell counts per perturbation

### Step 2: Data Preprocessing

Preprocess data if not already done. Normalize counts, log-transform, compute variable genes, and run dimensionality reduction.

```python
import scanpy as sc
from visualization import plot_perturbation_summary

# Basic preprocessing
sc.pp.normalize_total(adata)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes=2000)
sc.pp.scale(adata)

# Dimensionality reduction
sc.tl.pca(adata, n_comps=50)
sc.pp.neighbors(adata, n_pcs=30)
sc.tl.umap(adata)

# Visualize perturbations
plot_perturbation_summary(adata, perturbation_col='perturbation', save='summary.png')
```

### Step 3: Guide RNA Assignment (CRISPR Screens)

For CRISPR screens, assign guide RNAs to cells using threshold-based or mixture model methods.

```python
from core_analysis import assign_guide_rna

# Option 1: Threshold-based assignment
adata = assign_guide_rna(
    adata,
    guide_rna_column='guide_identity',
    assignment_method='threshold',
    threshold=5  # Minimum counts for assignment
)

# Option 2: Mixture model (for noisy data)
adata = assign_guide_rna(
    adata,
    guide_rna_column='guide_identity',
    assignment_method='mixture'
)
```

**Key Points:**
- Use threshold method for clear guide capture
- Use mixture model for noisy guide data
- Filter cells with ambiguous assignments

### Step 4: Compute Perturbation Spaces

#### 4.1 Pseudobulk Space (for DE Analysis)

Aggregate cells by perturbation and replicate for differential expression analysis.

```python
from core_analysis import compute_pseudobulk_space

ps_adata = compute_pseudobulk_space(
    adata,
    perturbation_col='perturbation',
    replicate_col='replicate'
)
print(f"Created {ps_adata.n_obs} pseudobulk profiles")
```

**Key Points:**
- Creates one profile per perturbation-replicate combination
- Required for PyDESeq2/edgeR differential expression

#### 4.2 Centroid Space (for Distance Analysis)

Compute centroids in embedding space for visualizing perturbation relationships.

```python
from core_analysis import compute_centroid_space

cs_adata = compute_centroid_space(
    adata,
    perturbation_col='perturbation',
    embedding_key='X_umap'
)
print(f"Created {cs_adata.n_obs} centroids")
```

**Key Points:**
- Creates one centroid per perturbation
- Requires pre-computed embedding (UMAP/PCA)

### Step 5: Calculate Perturbation Distances

Compute pairwise distances between perturbations using various metrics.

```python
from core_analysis import calculate_perturbation_distances
from visualization import plot_perturbation_distance_heatmap, plot_distance_dendrogram

# Available metrics: "edistance", "euclidean", "cosine_distance", "mmd", "wasserstein"
distance_df = calculate_perturbation_distances(
    adata,
    perturbation_col='perturbation',
    metric='edistance',
    control='control'
)

# Visualize distances
plot_perturbation_distance_heatmap(distance_df, save='distance_heatmap.png')
plot_distance_dendrogram(distance_df, save='distance_dendrogram.png')
```

**Available Metrics:**
- `edistance`: Energy distance (default)
- `euclidean`: Euclidean distance
- `cosine_distance`: Cosine distance
- `mmd`: Maximum Mean Discrepancy
- `wasserstein`: Wasserstein distance

### Step 6: Differential Expression Analysis

Compare each perturbation to control using DE tests.

```python
from core_analysis import compare_perturbations
from utils import export_de_results, get_top_de_genes
from visualization import plot_de_volcano

# Available methods: "pydeseq2", "edger", "ttest", "wilcoxon"
de_results = compare_perturbations(
    adata,
    perturbation_col='perturbation',
    reference='control',
    method='pydeseq2',
    replicate_col='replicate'
)

# Get top DE genes
top_genes = get_top_de_genes(de_results['KO_gene1'], n_genes=20)

# Export results
export_de_results(de_results, output_prefix='de_results', significant_only=True)

# Plot volcano
plot_de_volcano(de_results['KO_gene1'], save='volcano.png')
```

**Key Points:**
- Requires replicate information for statistical power
- Filter by adjusted p-value and log fold change

### Step 7: Mixscape Analysis (CRISPR Screens)

Identify successfully perturbed cells in CRISPR screens.

```python
from core_analysis import compute_perturbation_signature, run_mixscape_classification
from visualization import plot_mixscape_results

# Step 7.1: Compute perturbation signatures
adata = compute_perturbation_signature(
    adata,
    perturbation_col='perturbation',
    control='control',
    split_by='replicate',
    n_neighbors=20
)

# Step 7.2: Run Mixscape classification
adata = run_mixscape_classification(
    adata,
    perturbation_col='perturbation',
    control='control',
    new_class_name='mixscape_class',
    min_de_genes=5,
    logfc_threshold=0.25
)

# Visualize
plot_mixscape_results(adata, save='mixscape_results.png')
```

**Key Points:**
- Must compute perturbation signatures before Mixscape
- Classifies cells as perturbed or non-perturbed (NP)
- Results stored in `adata.obs['mixscape_class']`

### Step 8: Augur Classification

Use machine learning to quantify perturbation effects.

```python
from core_analysis import run_augur_classification
from visualization import plot_augur_results
from utils import summarize_augment_results

adata = run_augur_classification(
    adata,
    estimator='random_forest_classifier',
    labels_col='perturbation',
    cell_type_col='cell_type',
    n_estimators=100,
    random_state=42
)

# Summarize results
summary = summarize_augment_results(adata)
print(f"Mean AUC: {summary['mean_auc']:.3f}")

# Visualize
plot_augur_results(adata, save='augur_results.png')
```

**Key Points:**
- Higher AUC = more distinct perturbation effect
- Can analyze per cell type
- Results stored in `adata.uns['augur_results']`

### Step 9: Complete Pipeline

Run the complete analysis pipeline with one function call.

```python
from core_analysis import run_complete_perturbation_analysis
from utils import create_perturbation_report

adata = run_complete_perturbation_analysis(
    adata,
    perturbation_col='perturbation',
    control='control',
    compute_signature=True,
    run_mixscape=True,
    run_augur=True
)

# Generate report
report = create_perturbation_report(
    adata,
    perturbation_col='perturbation',
    output_file='perturbation_report.txt'
)
```

## Input Requirements

### Required Data Format

```python
# AnnData object with:
adata.X  # Normalized or raw counts matrix
adata.obs['perturbation']  # Perturbation labels (e.g., 'control', 'KO_gene1')
adata.obs['replicate']     # Biological replicate info (for DE analysis)
```

### Optional Columns

```python
adata.obs['guide_identity']  # For CRISPR screens - gRNA assignments
adata.obs['cell_type']       # For cell type-specific analysis
adata.obsm['X_umap']         # Pre-computed UMAP embedding
adata.obsm['X_pca']          # Pre-computed PCA
```

## Output Specifications

### Core Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Pseudobulk profiles | Returned AnnData | One obs per perturbation |
| Distance matrix | pd.DataFrame | Pairwise perturbation distances |
| DE results | Dict[str, pd.DataFrame] | DE genes per perturbation |
| Perturbation signature | `adata.layers['X_pert']` | Expression change matrix |
| Mixscape class | `adata.obs['mixscape_class']` | Perturbed/NP labels |
| Augur results | `adata.uns['augur_results']` | AUC scores per cell type |

### Visualization Outputs

- Distance heatmap (PNG/PDF)
- DE volcano plots (PNG/PDF)
- UMAP embeddings (PNG/PDF)
- Augur scatter plot (PNG/PDF)

## Key Parameters

### Data Validation

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `perturbation_col` | str | "perturbation" | Column with perturbation labels |
| `control` | str | None | Control perturbation name |
| `replicate_col` | str | None | Column with replicate info |

### Perturbation Space

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `layer` | str | None | Layer to use (None = .X) |
| `embedding_key` | str | "X_umap" | Embedding for centroid space |

### Distance Calculation

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `metric` | str | "edistance" | Distance metric |

### DE Analysis

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | str | "pydeseq2" | DE test method |
| `reference` | str | "control" | Reference perturbation |
| `pval_threshold` | float | 0.05 | Significance threshold |
| `logfc_threshold` | float | 0.5 | Log fold change threshold |

### Mixscape

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_neighbors` | int | 20 | Control neighbors for signature |
| `min_de_genes` | int | 5 | Min DE genes for classification |
| `new_class_name` | str | "mixscape_class" | Output column name |

### Augur

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `estimator` | str | "random_forest_classifier" | ML estimator |
| `n_estimators` | int | 100 | Number of trees (RF) |
| `random_state` | int | None | Random seed |

## Expected Runtime

| Dataset Size | Pseudobulk | Distance | DE (PyDESeq2) | Mixscape | Augur |
|--------------|------------|----------|---------------|----------|-------|
| 1K cells, 3 perturbations | <1s | <1s | 5-10s | 10-20s | 30-60s |
| 10K cells, 10 perturbations | <1s | 1-2s | 30-60s | 1-2min | 2-5min |
| 50K cells, 50 perturbations | 1-2s | 5-10s | 5-10min | 5-10min | 10-20min |
| 100K+ cells, 100+ perturbations | 2-5s | 10-30s | 20-30min | 20-30min | 30-60min |

*Runtime estimates on 8-core CPU with 32GB RAM*

## Error Handling

### Common Errors and Solutions

**Missing perturbation column**
```
ValueError: Column 'perturbation' not found in adata.obs
```
→ Verify column name exists in `adata.obs.columns`

**Single perturbation detected**
```
ValueError: Need at least 2 perturbations, found 1
```
→ Ensure data contains both control and perturbed cells

**Control not found**
```
ValueError: Control 'control' not found in perturbation
```
→ Check control label matches exactly (case-sensitive)

**Missing embedding for centroid space**
```
ValueError: Embedding 'X_umap' not found in adata.obsm
```
→ Run `sc.tl.umap()` before computing centroid space

**Missing perturbation signature for Mixscape**
```
ValueError: Perturbation signature not found. Run compute_perturbation_signature first.
```
→ Call `compute_perturbation_signature()` before `run_mixscape_classification()`

**Missing Augur results for plotting**
```
ValueError: Augur results not found in .uns['augur_results']
```
→ Run `run_augur_classification()` before plotting

## Related Skills

- [bio-single-cell-perturbation-sctenifoldknk-r](../bio-single-cell-perturbation-sctenifoldknk-r/SKILL.md) - Alternative perturbation analysis in R
- [bio-single-cell-de-deseq2-r](../bio-single-cell-de-deseq2-r/SKILL.md) - Differential expression with DESeq2
- [bio-single-cell-clustering](../bio-single-cell-clustering/SKILL.md) - Cell clustering and annotation

## References

1. Schaer et al. (2023). pertpy: A Python toolkit for perturbation analysis. *bioRxiv*.
2. Papathanasiou et al. (2023). Augur: Cell type prioritization in single-cell data. *Nature Methods*.
3. Replogle et al. (2022). Mapping information-rich genotype-phenotype landscapes with genome-scale Perturb-seq. *Cell*.
4. pertpy documentation: https://pertpy.readthedocs.io/
5. pertpy GitHub: https://github.com/scverse/pertpy
