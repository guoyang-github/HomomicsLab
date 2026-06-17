# FastCCC Usage Guide

## Overview

FastCCC is a permutation-free framework for scalable, robust, and reference-based cell-cell communication (CCC) analysis in single-cell transcriptomics studies. It uses FFT-based convolution to compute p-values analytically without permutations, making it orders of magnitude faster than traditional methods.

## When to Use FastCCC

- **Large-scale datasets**: 10k+ cells where traditional methods are too slow
- **Multiple conditions**: When comparing CCC across multiple samples or conditions
- **Reference-based analysis**: When leveraging atlas-scale references for query data
- **Spatial transcriptomics**: For analyzing CCC in spatial context
- **Screening**: Fast initial screening of L-R interactions

## Key Features

| Feature | Benefit |
|---------|---------|
| **Permutation-free** | Analytical p-values via FFT convolution |
| **Scalable** | Handles 100k+ cells efficiently |
| **Reference-based** | Leverage existing atlases for enhanced analysis |
| **Modular scoring** | Multiple summary methods (Mean, Median, Quantile) |
| **Cauchy combination** | Robust aggregation of multiple scoring methods |

## Step-by-Step Guide

### Step 1: Validate Installation

```python
from utils import validate_fastccc_installation

validation = validate_fastccc_installation()
print(f"FastCCC installed: {validation['fastccc_installed']}")
print(f"Scanpy installed: {validation['scanpy_installed']}")

if validation['errors']:
    for error in validation['errors']:
        print(f"Error: {error}")
```

### Step 2: Prepare Your Data

```python
import scanpy as sc
from core_analysis import validate_fastccc_input
from utils import check_lr_gene_overlap, prepare_anndata_for_fastccc

# Load data
adata = sc.read_h5ad("your_data.h5ad")

# Ensure sparse matrix format
if not hasattr(adata.X, 'toarray'):
    from scipy.sparse import csr_matrix
    adata.X = csr_matrix(adata.X)

# Validate input
validation = validate_fastccc_input(adata, groupby='cell_type')
if validation['warnings']:
    for warning in validation['warnings']:
        print(f"⚠️  {warning}")

# Check gene overlap
database_path = './cellphonedb_data'
overlap = check_lr_gene_overlap(adata, database_path)
print(f"Gene overlap: {overlap['n_overlap']}/{overlap['n_db_genes']} "
      f"({overlap['overlap_fraction']*100:.1f}%)")

if overlap['overlap_fraction'] < 0.5:
    print("⚠️  Low gene overlap may affect results")

# Prepare data (filter cell types, ensure sparse)
adata = prepare_anndata_for_fastccc(
    adata,
    groupby='cell_type',
    min_cells=10  # Filter cell types with < 10 cells
)
```

### Step 3: Run FastCCC (Basic)

```python
from core_analysis import run_fastccc

# Basic analysis with default parameters
results = run_fastccc(
    adata,
    database_file_path=database_path,
    groupby='cell_type',
    save_path='./fastccc_results',
    single_unit_summary='Mean',
    complex_aggregation='Minimum',
    lr_combination='Arithmetic',
    min_percentile=0.1,
    verbose=True
)

# Access results
print(f"P-values shape: {results['pvals'].shape}")
print(f"Cell pairs: {results['pvals'].shape[0]}")
print(f"Interactions: {results['pvals'].shape[1]}")
```

### Step 4: Run with Cauchy Combination (Recommended)

```python
from core_analysis import run_fastccc_cauchy_combined

# Run multiple scoring methods and combine with Cauchy combination
# This provides more robust results than single-method analysis
results = run_fastccc_cauchy_combined(
    adata,
    database_file_path=database_path,
    groupby='cell_type',
    save_path='./fastccc_cauchy_results',
    single_unit_summary_list=['Mean', 'Median', 'Q3', 'Quantile_0.9'],
    complex_aggregation_list=['Minimum', 'Average'],
    lr_combination_list=['Arithmetic', 'Geometric'],
    min_percentile=0.1,
    use_deg=False,
    verbose=True
)

# Load Cauchy combined results
from core_analysis import load_fastccc_results
results = load_fastccc_results('./fastccc_cauchy_results')
print(f"Cauchy combined p-values shape: {results['cauchy_pvals'].shape}")
```

### Step 5: Explore Results

```python
from core_analysis import (
    get_significant_interactions,
    get_top_interactions,
    summarize_interactions_by_cellpair
)

# Get significant interactions
significant = get_significant_interactions(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05,
    database_file_path=database_path
)

print(f"Significant interactions: {len(significant)}")

# Top interactions by strength
top_by_strength = get_top_interactions(
    results['interactions_strength'],
    results['pvals'],
    n_top=20,
    by='strength'
)

print("\nTop 10 by strength:")
print(top_by_strength.head(10)[['cell_pair', 'interaction', 'strength', 'pvalue']])

# Summarize by cell pair
pair_summary = summarize_interactions_by_cellpair(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05
)

print("\nTop cell pairs by significant interactions:")
print(pair_summary.head(10))
```

### Step 6: Cell Type Pair Analysis

```python
from core_analysis import analyze_celltype_specific_interactions

# Analyze specific sender -> receiver pair
pair_results = analyze_celltype_specific_interactions(
    results['pvals'],
    results['interactions_strength'],
    source_celltype='CD4_T',
    target_celltype='B_cell',
    pval_threshold=0.05
)

print(f"\nInteractions from CD4_T to B_cell:")
print(f"  Total: {len(pair_results)}")
print(f"  Significant: {pair_results['significant'].sum()}")

# Top significant interactions
sig_pairs = pair_results[pair_results['significant']].sort_values('pvalue')
print("\nTop significant interactions:")
print(sig_pairs.head(10)[['interaction_id', 'strength', 'pvalue']])
```

### Step 7: Visualization

```python
from visualization import (
    plot_interaction_heatmap,
    plot_significant_interactions_bar,
    plot_interaction_network,
    plot_fastccc_summary
)

# Generate all standard plots
plots = plot_fastccc_summary(
    results['pvals'],
    results['interactions_strength'],
    output_dir='./fastccc_plots',
    prefix='analysis_',
    pval_threshold=0.05
)

print(f"Generated plots: {list(plots.keys())}")

# Individual plots
# Heatmap
fig = plot_interaction_heatmap(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05,
    use_strength=True,
    save_path='./fastccc_plots/heatmap.png'
)

# Bar plot of significant interactions
fig = plot_significant_interactions_bar(
    results['pvals'],
    pval_threshold=0.05,
    top_n=20,
    save_path='./fastccc_plots/barplot.png'
)

# Network visualization
from utils import create_interaction_network_data
node_df, edge_df = create_interaction_network_data(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05
)

fig = plot_interaction_network(
    node_df, edge_df,
    layout='spring',
    save_path='./fastccc_plots/network.png'
)
```

### Step 8: Compare Multiple Conditions

```python
from core_analysis import compare_conditions_fastccc

# Split data by condition
conditions = {}
for cond in adata.obs['condition'].unique():
    conditions[cond] = adata[adata.obs['condition'] == cond].copy()

# Compare conditions
comparison_results = compare_conditions_fastccc(
    conditions,
    database_file_path=database_path,
    groupby='cell_type',
    save_path='./fastccc_comparison',
    verbose=True
)

# View comparison
print("Condition comparison:")
print(comparison_results['comparison'])
```

### Step 9: Build and Use Reference Panel

```python
from reference_builder import (
    build_reference_panel,
    infer_ccc_with_reference,
    get_reference_info
)

# Split data into reference and query
reference_adata = adata[adata.obs['condition'] == 'Control'].copy()
query_adata = adata[adata.obs['condition'] == 'Treatment'].copy()

# Step 9a: Build reference panel
print("Building reference panel...")
ref_path = build_reference_panel(
    reference_adata,
    database_file_path=database_path,
    reference_name='PBMC_reference',
    save_path='./reference_panels',
    groupby='cell_type',
    min_percentile=0.1,
    verbose=True
)

# Get reference info
info = get_reference_info(ref_path)
print(f"\nReference: {info['reference_name']}")
print(f"Cell types: {info['n_celltypes']}")
print(f"Total cells: {info['total_cells']}")

# Step 9b: Infer CCC on query data
print("\nRunning reference-based inference...")
infer_results = infer_ccc_with_reference(
    query_adata,
    database_file_path=database_path,
    reference_path=ref_path,
    save_path='./reference_results',
    groupby='cell_type'
)

# View comparison results
print(f"\nInference results shape: {infer_results.shape}")
print("\nComparison categories:")
print(infer_results['trend_vs_ref'].value_counts())

# Visualize comparison
from visualization import plot_reference_comparison
fig = plot_reference_comparison(
    infer_results,
    save_path='./fastccc_plots/ref_comparison.png'
)
```

### Step 10: Complete Pipeline

```python
from core_analysis import run_fastccc_pipeline

# Run complete pipeline
results = run_fastccc_pipeline(
    adata,
    database_file_path=database_path,
    groupby='cell_type',
    output_dir='./fastccc_output',
    use_cauchy=True,
    compare_conditions={
        'Control': adata[adata.obs['condition'] == 'Control'],
        'Treatment': adata[adata.obs['condition'] == 'Treatment']
    },
    verbose=True
)

# Access all results
main_results = results['main']
comparison_results = results['comparison']
```

## Advanced Topics

### Custom Scoring Strategy

```python
# Define custom scoring parameters
results = run_fastccc(
    adata,
    database_file_path=database_path,
    groupby='cell_type',
    single_unit_summary='Quantile_0.95',  # 95th percentile
    complex_aggregation='Average',           # Average for complexes
    lr_combination='Geometric',              # Geometric mean
    min_percentile=0.05,                     # Lower threshold
    verbose=True
)
```

### Filter and Export Results

```python
from utils import filter_interactions, export_results_to_cellchat_format

# Filter interactions
pvals_filtered, strength_filtered = filter_interactions(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05,
    min_strength=0.5,
    cell_pairs=['CD4_T|B_cell', 'B_cell|CD4_T']  # Specific pairs
)

# Export to CellChat format
exported = export_results_to_cellchat_format(
    pvals_filtered,
    strength_filtered,
    output_dir='./fastccc_export'
)

print(f"Exported: {list(exported.keys())}")
```

### Cell Type Mapping for Reference Analysis

```python
from reference_builder import (
    create_celltype_mapping,
    save_celltype_mapping,
    load_celltype_mapping
)

# Create mapping if query and reference use different nomenclature
mapping = {
    'CD4_T_cell': 'CD4_T',      # reference -> query
    'CD8_T_cell': 'CD8_T',
    'B_cell': 'B_cell',
    'Monocyte_CD14': 'Monocyte',
    'DC_cell': 'DC'
}

# Save mapping
save_celltype_mapping(mapping, './celltype_mapping.json')

# Use in inference
infer_results = infer_ccc_with_reference(
    query_adata,
    database_file_path=database_path,
    reference_path=ref_path,
    save_path='./reference_results',
    groupby='cell_type',
    celltype_mapping_dict='./celltype_mapping.json'  # or pass dict directly
)
```

## Parameter Selection Guide

### Single Unit Summary

| Method | Use Case |
|--------|----------|
| `Mean` | General purpose, balanced sensitivity |
| `Median` | Robust to outliers |
| `Q3` (75th percentile) | Sparse data, permissive |
| `Quantile_0.9` | Very sparse data |
| `Quantile_0.95` | Extremely sparse data |

### Complex Aggregation

| Method | Use Case |
|--------|----------|
| `Minimum` | Conservative (CellPhoneDB-style), all subunits required |
| `Average` | Permissive, partial complexes allowed |

### L-R Combination

| Method | Use Case |
|--------|----------|
| `Arithmetic` | Additive effects, standard CCC analysis |
| `Geometric` | Multiplicative effects, synergy detection |

### Min Percentile

| Value | Use Case |
|-------|----------|
| 0.05 | Permissive, more interactions detected |
| 0.10 | Default, balanced |
| 0.20 | Stringent, fewer false positives |

## Speed Comparison

| Dataset Size | FastCCC | CellPhoneDB | CellChat |
|--------------|---------|-------------|----------|
| 1k cells | 30s | 5min | 10min |
| 10k cells | 2min | 1hr | 2hr |
| 50k cells | 10min | 8hr | 16hr |
| 100k cells | 20min | 24hr+ | 48hr+ |

*Times are approximate for ~2,000 interactions on a modern CPU*

## Troubleshooting

### Common Issues

**"Anndata.X should be a sparse matrix format"**
```python
from scipy.sparse import csr_matrix
adata.X = csr_matrix(adata.X)
```

**"Low gene overlap"**
- Convert ENSEMBL to gene symbols
- Check gene naming convention (HGNC symbols required)
- Verify database version matches your species

**"No significant interactions"**
- Check cell type annotations are correct
- Verify sufficient cells per cell type (≥10 recommended)
- Try lowering min_percentile threshold
- Check gene expression quality

**"Memory error"**
- Ensure data is in sparse format
- Process in chunks for very large datasets
- Use reference-based analysis instead

### Debugging Tips

```python
# Check data format
print(f"Data type: {type(adata.X)}")
print(f"Is sparse: {hasattr(adata.X, 'toarray')}")
print(f"Cell types: {adata.obs['cell_type'].value_counts()}")

# Test with small dataset first
adata_test = adata[:100, :].copy()
results_test = run_fastccc(adata_test, ...)
```

## Best Practices

### Data Quality
- Filter low-quality cells before analysis
- Ensure adequate gene coverage (>50% of database)
- Check for batch effects in multi-sample analysis
- Use biological replicates when possible

### Analysis Design
- Start with Cauchy combination for robust results
- Use 'Mean' + 'Minimum' + 'Arithmetic' for CellPhoneDB-like results
- Compare multiple scoring strategies
- Validate key findings with experimental data

### Result Interpretation
- Focus on consistent signals across methods
- Consider interaction directionality
- Account for cell type proportions
- Correlate with gene expression patterns

## References

1. Hou et al. (2025). FastCCC: a permutation-free framework for scalable, robust, and reference-based cell-cell communication analysis in single cell transcriptomics studies. *Nature Communications* 16, 11428.

2. FastCCC Tutorial: https://svvord.github.io/FastCCC/

3. GitHub: https://github.com/Svvord/FastCCC
