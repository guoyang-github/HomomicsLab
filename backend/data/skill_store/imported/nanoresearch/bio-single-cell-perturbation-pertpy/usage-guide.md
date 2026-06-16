# pertpy Usage Guide

## Overview

pertpy is a Python toolkit for analyzing single-cell perturbation data. This skill provides wrapper functions for common perturbation analysis workflows including CRISPR screen analysis, drug perturbations, and differential expression.

## When to Use

- **CRISPR Screen Analysis**: Identify cells with successful gene knockouts
- **Drug Perturbation Studies**: Characterize transcriptional responses to treatments
- **Genetic Perturbations**: Analyze KO/KD effects on gene expression
- **Perturbation Classification**: Rank perturbations by effect size using ML
- **Differential Expression**: Find genes affected by specific perturbations

## Prerequisites

### Required Packages

```bash
pip install pertpy scanpy pandas numpy matplotlib seaborn
```

### Data Format

Your AnnData object should contain:

```python
adata.X                    # Gene expression matrix
adata.obs['perturbation']  # Perturbation labels (e.g., 'control', 'KO_gene1')
adata.obs['replicate']     # Biological replicate information
adata.obs['guide_identity'] # For CRISPR: gRNA assignments (optional)
adata.obs['cell_type']     # Cell type annotations (optional)
```

## Step-by-Step Guide

### Step 1: Setup and Data Loading

```python
import scanpy as sc
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join('scripts', 'python'))

from core_analysis import check_perturbation_data, compute_pseudobulk_space
from visualization import plot_perturbation_summary

# Load your perturbation data
adata = sc.read_h5ad("perturbation_data.h5ad")

# Validate the data
check_perturbation_data(
    adata,
    perturbation_col='perturbation',
    control='control'
)

# Get summary statistics
from utils import get_perturbation_summary
summary = get_perturbation_summary(adata, perturbation_col='perturbation')
print(summary)
```

### Step 2: Data Preprocessing

```python
# Basic preprocessing (if not already done)
sc.pp.normalize_total(adata)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes=2000)
sc.pp.scale(adata)

# Dimensionality reduction for visualization
sc.tl.pca(adata, n_comps=50)
sc.pp.neighbors(adata, n_pcs=30)
sc.tl.umap(adata)

# Visualize perturbations
plot_perturbation_summary(adata, perturbation_col='perturbation', save='summary.png')
```

### Step 3: Guide RNA Assignment (CRISPR Screens)

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

### Step 4: Compute Perturbation Spaces

#### 4.1 Pseudobulk Space (for DE Analysis)

```python
from core_analysis import compute_pseudobulk_space

# Aggregate cells by perturbation and replicate
ps_adata = compute_pseudobulk_space(
    adata,
    perturbation_col='perturbation',
    replicate_col='replicate'
)

print(f"Created {ps_adata.n_obs} pseudobulk profiles")
```

#### 4.2 Centroid Space (for Distance Analysis)

```python
from core_analysis import compute_centroid_space

# Compute centroids in UMAP space
cs_adata = compute_centroid_space(
    adata,
    perturbation_col='perturbation',
    embedding_key='X_umap'
)

print(f"Created {cs_adata.n_obs} centroids")
```

### Step 5: Calculate Perturbation Distances

```python
from core_analysis import calculate_perturbation_distances
from visualization import plot_perturbation_distance_heatmap, plot_distance_dendrogram

# Calculate distances between perturbations
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

### Step 6: Differential Expression Analysis

```python
from core_analysis import compare_perturbations
from utils import export_de_results, get_top_de_genes
from visualization import plot_de_volcano

# Compare each perturbation to control
# Available methods: "pydeseq2", "edger", "ttest", "wilcoxon"
de_results = compare_perturbations(
    adata,
    perturbation_col='perturbation',
    reference='control',
    method='pydeseq2',
    replicate_col='replicate'
)

# Get top DE genes for a specific perturbation
top_genes = get_top_de_genes(
    de_results['KO_gene1'],
    n_genes=20,
    sort_by='log2FoldChange'
)
print(top_genes)

# Export all DE results
export_de_results(
    de_results,
    output_prefix='de_results',
    significant_only=True,
    pval_threshold=0.05
)

# Plot volcano for a specific perturbation
plot_de_volcano(
    de_results['KO_gene1'],
    pval_threshold=0.05,
    logfc_threshold=0.5,
    save='volcano_KO_gene1.png'
)
```

### Step 7: Mixscape Analysis (CRISPR Screens)

```python
from core_analysis import compute_perturbation_signature, run_mixscape_classification
from visualization import plot_mixscape_results

# Step 7.1: Compute perturbation signatures
# This calculates expression change relative to control cells
adata = compute_perturbation_signature(
    adata,
    perturbation_col='perturbation',
    control='control',
    split_by='replicate',  # Optional: account for batch effects
    n_neighbors=20
)

# Step 7.2: Run Mixscape classification
# Classifies cells as successfully perturbed or non-perturbed (NP)
adata = run_mixscape_classification(
    adata,
    perturbation_col='perturbation',
    control='control',
    new_class_name='mixscape_class',
    min_de_genes=5,
    logfc_threshold=0.25
)

# View classification results
print(adata.obs['mixscape_class'].value_counts())

# Visualize
plot_mixscape_results(
    adata,
    perturbation_col='perturbation',
    mixscape_col='mixscape_class',
    save='mixscape_results.png'
)
```

### Step 8: Augur Classification

```python
from core_analysis import run_augur_classification
from visualization import plot_augur_results
from utils import summarize_augment_results

# Run Augur to classify perturbations
# Uses machine learning to quantify perturbation effects
adata = run_augur_classification(
    adata,
    estimator='random_forest_classifier',  # or 'logistic_regression_classifier'
    labels_col='perturbation',
    cell_type_col='cell_type',  # Optional: analyze per cell type
    n_estimators=100,
    random_state=42
)

# Summarize results
summary = summarize_augment_results(adata)
print(f"Mean AUC: {summary['mean_auc']:.3f}")

# Visualize
plot_augur_results(adata, save='augur_results.png')
```

### Step 9: Complete Pipeline

```python
from core_analysis import run_complete_perturbation_analysis

# Run the complete analysis pipeline
adata = run_complete_perturbation_analysis(
    adata,
    perturbation_col='perturbation',
    control='control',
    compute_signature=True,
    run_mixscape=True,
    run_augur=True
)

# Generate comprehensive report
from utils import create_perturbation_report
report = create_perturbation_report(
    adata,
    perturbation_col='perturbation',
    output_file='perturbation_report.txt'
)
```

## Advanced Usage

### Finding High-Confidence Perturbations

```python
from utils import find_high_confidence_perturbations

# Identify perturbations with strongest effects
high_conf = find_high_confidence_perturbations(
    distance_df,
    control='control',
    threshold_percentile=90
)
print(f"High confidence perturbations: {high_conf}")
```

### Comparing Two Perturbations

```python
from utils import compare_perturbation_effects

# Compare DE results between two perturbations
comparison = compare_perturbation_effects(
    de_results['KO_gene1'],
    de_results['KO_gene2']
)
```

### Custom Distance Analysis

```python
# Try different distance metrics
for metric in ['edistance', 'euclidean', 'cosine_distance']:
    dist_df = calculate_perturbation_distances(
        adata,
        perturbation_col='perturbation',
        metric=metric
    )
    print(f"\n{metric} distances:")
    print(dist_df)
```

## Common Workflows

### Workflow 1: Basic CRISPR Screen Analysis

```python
# 1. Assign guides
adata = assign_guide_rna(adata, guide_rna_column='guide_identity')

# 2. Compute perturbation signatures
adata = compute_perturbation_signature(adata, perturbation_col='perturbation', control='NT')

# 3. Run Mixscape
adata = run_mixscape_classification(adata, perturbation_col='perturbation', control='NT')

# 4. DE analysis on successfully perturbed cells
perturbed_cells = adata[adata.obs['mixscape_class'] != 'NP']
de_results = compare_perturbations(perturbed_cells, reference='NT')
```

### Workflow 2: Drug Perturbation Analysis

```python
# 1. Pseudobulk DE
ps_adata = compute_pseudobulk_space(adata, perturbation_col='drug', replicate_col='replicate')

# 2. Distance analysis
dist_df = calculate_perturbation_distances(adata, perturbation_col='drug', metric='edistance')

# 3. Augur classification
adata = run_augur_classification(adata, labels_col='drug', cell_type_col='cell_type')
```

### Workflow 3: Comparing Multiple KO Conditions

```python
# Calculate all pairwise distances
dist_df = calculate_perturbation_distances(adata, perturbation_col='perturbation')

# Cluster perturbations by similarity
from visualization import plot_distance_dendrogram
plot_distance_dendrogram(dist_df, method='average')

# DE analysis
de_results = compare_perturbations(adata, perturbation_col='perturbation', reference='control')
```

## Troubleshooting

### Error: "Perturbation column not found"

```python
# Check available columns
print(adata.obs.columns)

# Verify your column name
check_perturbation_data(adata, perturbation_col='your_column_name')
```

### Error: "Need at least 2 perturbations"

```python
# Check perturbation distribution
print(adata.obs['perturbation'].value_counts())

# Ensure you have both control and perturbation samples
```

### Error: "Perturbation signature not found"

```python
# Must run signature computation before Mixscape
adata = compute_perturbation_signature(adata, perturbation_col='perturbation', control='control')
adata = run_mixscape_classification(adata, perturbation_col='perturbation', control='control')
```

## AI Agent Test Cases

### Basic Perturbation Analysis
> "Run pseudobulk DE analysis on my CRISPR screen data"
```python
ps_adata = compute_pseudobulk_space(adata, perturbation_col='perturbation', replicate_col='replicate')
de_results = compare_perturbations(adata, reference='control', method='pydeseq2')
```

### Augur Classification
> "Use Augur to rank perturbations by effect size"
```python
adata = run_augur_classification(adata, labels_col='perturbation', cell_type_col='cell_type')
plot_augur_results(adata)
```

### Mixscape Analysis
> "Identify successfully transduced cells in my CRISPR screen"
```python
adata = compute_perturbation_signature(adata, perturbation_col='perturbation', control='NT')
adata = run_mixscape_classification(adata, perturbation_col='perturbation', control='NT')
```

### Distance Analysis
> "Calculate energy distances between all perturbations"
```python
dist_df = calculate_perturbation_distances(adata, perturbation_col='perturbation', metric='edistance')
plot_perturbation_distance_heatmap(dist_df)
```

### Complete Workflow
> "Run complete perturbation analysis pipeline"
```python
adata = run_complete_perturbation_analysis(adata, perturbation_col='perturbation', control='control')
```

## References

1. Schaer et al. (2023). pertpy: A Python toolkit for perturbation analysis. *bioRxiv*.
2. Papathanasiou et al. (2023). Augur: Cell type prioritization in single-cell data. *Nature Methods*.
3. Replogle et al. (2022). Mapping information-rich genotype-phenotype landscapes with genome-scale Perturb-seq. *Cell*.
4. [pertpy Documentation](https://pertpy.readthedocs.io/)
