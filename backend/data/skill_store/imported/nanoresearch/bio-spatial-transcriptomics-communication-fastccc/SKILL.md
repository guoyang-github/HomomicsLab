---
name: bio-spatial-transcriptomics-communication-fastccc
description: Fast cell-cell communication analysis using FastCCC for single-cell and spatial transcriptomics
version: 1.0
tool_type: python
primary_tool: FastCCC
supported_tools: [scanpy, pandas, numpy, matplotlib, seaborn]
languages: [python]
keywords: ["spatial", "cell-communication", "FastCCC", "ligand-receptor", "permutation-free", "scalable", "reference-based"]
---

## Version Compatibility

| Component | Version |
|-----------|---------|
| Python | >= 3.9 |
| FastCCC | >= 0.2.0 |
| scanpy | >= 1.9 |
| pandas | >= 1.5 |
| numpy | >= 1.20 |

## Installation

```bash
# Install FastCCC
pip install fastccc

# Install additional dependencies
pip install scanpy pandas numpy matplotlib seaborn networkx
```

## Quick Start

```python
from core_analysis import run_fastccc, get_significant_interactions

# Run FastCCC analysis
results = run_fastccc(
    adata,
    database_file_path='./cellphonedb_data',
    groupby='cell_type',
    save_path='./fastccc_results'
)

# Get significant interactions
significant = get_significant_interactions(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05
)
```

## Import Wrapper Functions

Source the wrapper scripts before using the functions:

```python
import sys
sys.path.append('scripts/python')

from core_analysis import (
    validate_fastccc_input,
    run_fastccc,
    run_fastccc_cauchy_combined,
    load_fastccc_results,
    get_significant_interactions,
    analyze_celltype_specific_interactions,
    get_top_interactions,
    summarize_interactions_by_cellpair,
    compare_conditions_fastccc,
    run_fastccc_pipeline
)
from reference_builder import (
    build_reference_panel,
    infer_ccc_with_reference,
    get_reference_info,
    list_available_references,
    create_celltype_mapping
)
from utils import (
    check_lr_gene_overlap,
    get_database_info,
    summarize_fastccc_results,
    filter_interactions,
    get_top_cell_pairs,
    estimate_fastccc_runtime,
    prepare_anndata_for_fastccc,
    export_results_to_cellchat_format,
    validate_fastccc_installation
)
from visualization import (
    plot_interaction_heatmap,
    plot_significant_interactions_bar,
    plot_interaction_network,
    plot_top_interactions_dot,
    plot_pvalue_distribution,
    plot_celltype_communication_chord,
    plot_reference_comparison,
    plot_fastccc_summary
)
```

## Core Analysis Workflow

### Step 1: Data Validation and Preparation

```python
from core_analysis import validate_fastccc_input
from utils import check_lr_gene_overlap, prepare_anndata_for_fastccc

# Validate input data
validation = validate_fastccc_input(adata, groupby='cell_type')
if validation['warnings']:
    for warning in validation['warnings']:
        print(f"Warning: {warning}")

# Check gene overlap with LR database
database_path = './cellphonedb_data'
overlap = check_lr_gene_overlap(adata, database_path)
print(f"Gene overlap: {overlap['overlap_fraction']*100:.1f}%")

# Prepare data (ensure sparse matrix, filter cell types)
adata = prepare_anndata_for_fastccc(adata, groupby='cell_type', min_cells=10)
```

**Input Requirements:**
- Sparse matrix format (CSR preferred)
- Cell type annotations in `obs`
- Gene symbols (not ENSEMBL IDs)
- Minimum 2 cell types with sufficient cells

### Step 2: Database Selection

```python
from utils import get_database_info

# Check database information
db_info = get_database_info(database_path)
print(f"Interactions: {db_info['n_interactions']}")
print(f"Ligands: {db_info['n_ligands']}")
print(f"Receptors: {db_info['n_receptors']}")
```

**Supported Databases:**

| Database | Interactions | Source |
|----------|--------------|--------|
| CellPhoneDB | ~2,000 | Vento-Tormo et al., 2018 |
| CellChat | ~2,000 | Jin et al., 2021 |
| SingleCellSignalR | ~900 | Efremova et al., 2020 |

### Step 3: Run FastCCC Analysis

```python
from core_analysis import run_fastccc

# Basic analysis
results = run_fastccc(
    adata,
    database_file_path=database_path,
    groupby='cell_type',
    save_path='./fastccc_results',
    single_unit_summary='Mean',      # 'Mean', 'Median', 'Q3', 'Quantile_0.9'
    complex_aggregation='Minimum',   # 'Minimum', 'Average'
    lr_combination='Arithmetic',     # 'Arithmetic', 'Geometric'
    min_percentile=0.1,
    use_deg=False,
    verbose=True
)
```

### Step 4: Run with Cauchy Combination (Recommended)

```python
from core_analysis import run_fastccc_cauchy_combined

# Run multiple methods and combine with Cauchy combination
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
```

### Step 5: Analyze Results

```python
from core_analysis import (
    get_significant_interactions,
    analyze_celltype_specific_interactions,
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

# Analyze specific cell type pair
pair_results = analyze_celltype_specific_interactions(
    results['pvals'],
    results['interactions_strength'],
    source_celltype='CD4_T',
    target_celltype='B_cell',
    pval_threshold=0.05
)

# Get top interactions by strength
top_interactions = get_top_interactions(
    results['interactions_strength'],
    results['pvals'],
    n_top=20,
    by='strength'
)

# Summarize by cell pair
pair_summary = summarize_interactions_by_cellpair(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05
)
```

### Step 6: Visualization

```python
from visualization import (
    plot_interaction_heatmap,
    plot_significant_interactions_bar,
    plot_fastccc_summary
)

# Generate comprehensive plots
plots = plot_fastccc_summary(
    results['pvals'],
    results['interactions_strength'],
    output_dir='./fastccc_plots',
    prefix='analysis_',
    pval_threshold=0.05
)
```

### Step 7: Reference-Based Analysis (Optional)

```python
from reference_builder import (
    build_reference_panel,
    infer_ccc_with_reference
)

# Build reference panel
ref_path = build_reference_panel(
    reference_adata,
    database_file_path=database_path,
    reference_name='PBMC_reference',
    save_path='./reference_panels',
    groupby='cell_type',
    min_percentile=0.1
)

# Infer CCC on query data
infer_results = infer_ccc_with_reference(
    query_adata,
    database_file_path=database_path,
    reference_path=ref_path,
    save_path='./reference_results',
    groupby='cell_type'
)
```

## Key Parameters

### FastCCC Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `database_file_path` | str | Required | Path to LR database |
| `groupby` | str | Required | Cell type column name |
| `single_unit_summary` | str | 'Mean' | Method for single-unit summary |
| `complex_aggregation` | str | 'Minimum' | Method for complex aggregation |
| `lr_combination` | str | 'Arithmetic' | Method for L-R combination |
| `min_percentile` | float | 0.1 | Minimum percentile for expression |
| `use_deg` | bool | False | Filter by differential expression |
| `style` | str | None | Analysis style ('cpdb' for CellPhoneDB) |

### Cauchy Combination Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `single_unit_summary_list` | list | ['Mean', 'Median', 'Q3', 'Quantile_0.9'] | Methods to combine |
| `complex_aggregation_list` | list | ['Minimum', 'Average'] | Complex aggregation methods |
| `lr_combination_list` | list | ['Arithmetic', 'Geometric'] | L-R combination methods |

## API Reference

### Core Analysis Functions

| Function | Description |
|----------|-------------|
| `run_fastccc()` | Run FastCCC analysis |
| `run_fastccc_cauchy_combined()` | Run with Cauchy combination |
| `load_fastccc_results()` | Load results from directory |
| `get_significant_interactions()` | Extract significant interactions |
| `analyze_celltype_specific_interactions()` | Analyze specific cell pair |
| `get_top_interactions()` | Get top interactions by metric |
| `summarize_interactions_by_cellpair()` | Summary by cell pair |
| `compare_conditions_fastccc()` | Compare multiple conditions |
| `run_fastccc_pipeline()` | Complete analysis pipeline |

### Reference Builder Functions

| Function | Description |
|----------|-------------|
| `build_reference_panel()` | Build CCC reference panel |
| `infer_ccc_with_reference()` | Reference-based inference |
| `get_reference_info()` | Get reference information |
| `list_available_references()` | List available references |
| `create_celltype_mapping()` | Create cell type mapping |

### Utility Functions

| Function | Description |
|----------|-------------|
| `check_lr_gene_overlap()` | Check gene overlap with database |
| `get_database_info()` | Get database information |
| `summarize_fastccc_results()` | Summarize results |
| `filter_interactions()` | Filter interactions |
| `get_top_cell_pairs()` | Get top cell pairs |
| `estimate_fastccc_runtime()` | Estimate runtime |
| `prepare_anndata_for_fastccc()` | Prepare AnnData |
| `export_results_to_cellchat_format()` | Export to CellChat format |

### Visualization Functions

| Function | Description |
|----------|-------------|
| `plot_interaction_heatmap()` | Heatmap of interactions |
| `plot_significant_interactions_bar()` | Bar plot of significant interactions |
| `plot_interaction_network()` | Network visualization |
| `plot_top_interactions_dot()` | Dot plot of top interactions |
| `plot_pvalue_distribution()` | P-value distribution |
| `plot_celltype_communication_chord()` | Chord diagram |
| `plot_reference_comparison()` | Query vs reference comparison |
| `plot_fastccc_summary()` | Generate all standard plots |

## Output Specifications

### P-values Matrix

- **Format**: DataFrame (cell_pairs × interactions)
- **Values**: P-values from FastCCC analysis
- **Interpretation**: Lower p-values indicate more significant interactions

### Interaction Strength Matrix

- **Format**: DataFrame (cell_pairs × interactions)
- **Values**: Communication strength scores
- **Interpretation**: Higher values indicate stronger potential communication

### Significant Interactions DataFrame

| Column | Description |
|--------|-------------|
| `cell_pair` | Sender|Receiver cell types |
| `interaction_id` | L-R interaction identifier |
| `ligand` | Ligand gene symbol |
| `receptor` | Receptor gene symbol(s) |
| `pvalue` | Significance p-value |
| `strength` | Interaction strength |

## Best Practices

### Data Preparation
1. **Use sparse matrices** - FastCCC is optimized for sparse data
2. **Check gene overlap** - Aim for >50% of database genes
3. **Filter low-quality cells** - Remove cells with few genes detected
4. **Ensure sufficient cells** - Minimum 10 cells per cell type

### Parameter Selection
1. **Single unit summary** - 'Mean' for general use, 'Quantile_0.9' for sparse data
2. **Complex aggregation** - 'Minimum' for conservative (CellPhoneDB-style), 'Average' for permissive
3. **L-R combination** - 'Arithmetic' for additive effects, 'Geometric' for multiplicative
4. **Min percentile** - 0.1 for most datasets, increase for noisy data

### Computational Considerations
- **Runtime**: Scales linearly with cell types and interactions
- **Memory**: Requires ~2-4GB for 10k cells
- **Cauchy combination**: Adds ~3-5x computational cost

## Troubleshooting

### Low Gene Overlap
```
Warning: Gene overlap is only 23%
```
→ Convert ENSEMBL IDs to gene symbols
→ Check gene naming convention (HGNC symbols)

### Dense Matrix Warning
```
Anndata.X should be a sparse matrix format
```
→ Convert to sparse: `adata.X = csr_matrix(adata.X)`

### No Significant Interactions
```
No significant interactions found
```
→ Check cell type annotations
→ Increase min_percentile threshold
→ Verify gene expression quality

## Related Skills

- [bio-spatial-transcriptomics-communication-liana](../bio-spatial-transcriptomics-communication-liana/SKILL.md) - LIANA cell-cell communication
- [bio-spatial-transcriptomics-communication-cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/SKILL.md) - CellChat (R)
- [bio-spatial-transcriptomics-communication-cellphonedb](../bio-spatial-transcriptomics-communication-cellphonedb/SKILL.md) - CellPhoneDB

## References

1. **Hou et al. (2025)**. FastCCC: a permutation-free framework for scalable, robust, and reference-based cell-cell communication analysis in single cell transcriptomics studies. *Nature Communications* 16, 11428. https://doi.org/10.1038/s41467-025-66272-z

2. **FastCCC Documentation**: https://svvord.github.io/FastCCC/

3. **GitHub**: https://github.com/Svvord/FastCCC
