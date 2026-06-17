---
name: bio-single-cell-metabolism-compass
description: Metabolic flux inference using COMPASS for single-cell transcriptomics
version: 1.0
tool_type: python
primary_tool: COMPASS
supported_tools: [scanpy, pandas, numpy, matplotlib, seaborn]
languages: [python]
keywords: ["single-cell", "metabolism", "COMPASS", "flux-balance-analysis", "FBA", "metabolic-modeling", "systems-biology"]
---

## Version Compatibility

| Component | Version |
|-----------|---------|
| Python | >= 3.8 |
| COMPASS | >= 0.9.0 |
| scanpy | >= 1.9 |
| pandas | >= 1.5 |
| numpy | >= 1.20 |
| CPLEX | >= 12.8 |

## Installation

```bash
# Install COMPASS (requires IBM CPLEX)
pip install compass-sc

# Install additional dependencies
pip install scanpy pandas numpy matplotlib seaborn statsmodels
```

**Note**: COMPASS requires IBM CPLEX optimization solver. Academic licenses are free.
Download from: https://www.ibm.com/products/ilog-cplex-optimization-studio

## Quick Start

```python
from core_analysis import run_compass, add_compass_results_to_adata

# Run COMPASS analysis
compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=4
)

# Add results to AnnData
adata = add_compass_results_to_adata(adata, compass_results)
```

## Import Wrapper Functions

Source the wrapper scripts before using the functions:

```python
import sys
sys.path.append('scripts/python')

from core_analysis import (
    validate_compass_input,
    run_compass,
    load_compass_results,
    add_compass_results_to_adata,
    get_available_models,
    list_model_genes,
    list_model_reactions,
    analyze_differential_flux,
    summarize_metabolic_activity,
    infer_subsystems,
    run_compass_pipeline
)
from utils import (
    check_gene_overlap,
    recommend_model,
    get_model_catalog,
    summarize_compass_results,
    filter_reactions_by_activity,
    get_top_reactions,
    get_top_metabolites,
    estimate_compass_runtime,
    convert_ensembl_to_symbols,
    create_reaction_subset_file,
    create_subsystem_subset_file,
    export_compass_results,
    create_test_data,
    validate_compass_installation
)
from visualization import (
    plot_reaction_heatmap,
    plot_metabolite_scores,
    plot_reaction_distribution,
    plot_differential_flux,
    plot_subsystem_activity,
    plot_umap_with_metabolism,
    plot_sample_comparison,
    plot_reaction_correlation,
    plot_compass_summary,
    create_interactive_viz
)
```

## Core Analysis Workflow

### Step 1: Data Validation and Preparation

```python
from core_analysis import validate_compass_input
from utils import check_gene_overlap

# Validate input data
validation = validate_compass_input(adata)
if validation['warnings']:
    for warning in validation['warnings']:
        print(f"Warning: {warning}")

# Check gene overlap with metabolic model
model_genes = list_model_genes(model='RECON2_mat', species='homo_sapiens')
overlap = check_gene_overlap(adata, model_genes)
print(f"Gene overlap: {overlap['overlap_fraction']*100:.1f}%")
```

**Input Requirements:**
- Raw or normalized gene expression counts
- Gene symbols (not ENSEMBL IDs)
- AnnData format preferred

### Step 2: Model Selection

```python
from utils import recommend_model, get_model_catalog

# View available models
catalog = get_model_catalog()
print(catalog[['model', 'species', 'use_case']])

# Get recommendation
model = recommend_model(species='human')  # Returns 'RECON2_mat'
```

**Available Models:**

| Model | Species | Reactions | Use Case |
|-------|---------|-----------|----------|
| RECON2_mat | Human | ~7,440 | General metabolism (recommended) |
| RECON1_mat | Human | ~3,740 | Core metabolism |
| RECON2.2 | Human | ~7,780 | Updated annotations |
| Mouse-GEM | Mouse | ~7,600 | Mouse metabolism |

### Step 3: Run COMPASS Analysis

```python
from core_analysis import run_compass

# Basic run
compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=4
)

# Advanced run with penalty diffusion
compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=8,
    lambda_param=0.25,          # Penalty sharing between cells
    num_neighbors=30,           # k-NN for penalty diffusion
    penalty_diffusion='knn',    # 'knn' or 'gaussian'
    and_function='mean',        # Gene aggregation: 'min', 'median', 'mean'
    calc_metabolites=True,      # Calculate uptake/secretion
    microcluster_size=50        # For large datasets (>500 cells)
)
```

### Step 4: Load and Integrate Results

```python
from core_analysis import load_compass_results, add_compass_results_to_adata

# Load existing results
compass_results = load_compass_results('./compass_output', prefix='compass_')

# Add to AnnData
adata = add_compass_results_to_adata(
    adata,
    compass_results,
    reaction_scores_obs=False,  # Store in obsm vs obs
    prefix='compass_'
)
```

### Step 5: Differential Flux Analysis

```python
from core_analysis import analyze_differential_flux

# Compare conditions
diff_results = analyze_differential_flux(
    compass_results['reaction_scores'],
    adata.obs['condition'],
    method='wilcoxon'  # or 't-test'
)

# View top differential reactions
print(diff_results.head(10)[['reaction', 'log2FC', 'padj']])
```

### Step 6: Visualization

```python
from visualization import (
    plot_reaction_heatmap,
    plot_differential_flux,
    plot_compass_summary
)

# Generate comprehensive plots
plots = plot_compass_summary(
    compass_results['reaction_scores'],
    compass_results.get('uptake_scores'),
    compass_results.get('secretion_scores'),
    output_dir='./compass_plots'
)
```

## Key Parameters

### COMPASS Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | str | 'RECON2_mat' | Metabolic model to use |
| `species` | str | 'homo_sapiens' | Species ('homo_sapiens' or 'mus_musculus') |
| `media` | str | 'default-media' | Culture media condition |
| `num_processes` | int | CPU count | Parallel processes |
| `lambda_param` | float | 0.0 | Penalty diffusion strength (0-1) |
| `num_neighbors` | int | 30 | k-NN for penalty diffusion |
| `penalty_diffusion` | str | 'knn' | Diffusion mode ('knn' or 'gaussian') |
| `and_function` | str | 'mean' | Gene rule aggregation |
| `microcluster_size` | int | None | Target cells per microcluster |

### Analysis Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `calc_metabolites` | bool | True | Calculate metabolite uptake/secretion |
| `select_reactions` | str | None | File with reactions to analyze |
| `select_subsystems` | str | None | File with subsystems to analyze |

## API Reference

### Core Analysis Functions

| Function | Description |
|----------|-------------|
| `run_compass()` | Run COMPASS metabolic flux analysis |
| `load_compass_results()` | Load results from output directory |
| `add_compass_results_to_adata()` | Integrate results into AnnData |
| `analyze_differential_flux()` | Differential flux between groups |
| `summarize_metabolic_activity()` | Subsystem-level summaries |
| `get_available_models()` | List available metabolic models |
| `list_model_genes()` | Get genes in metabolic model |
| `list_model_reactions()` | Get reactions in metabolic model |

### Utility Functions

| Function | Description |
|----------|-------------|
| `check_gene_overlap()` | Check data/model gene overlap |
| `recommend_model()` | Get model recommendation |
| `filter_reactions_by_activity()` | Filter by activity threshold |
| `get_top_reactions()` | Get most active/variable reactions |
| `estimate_compass_runtime()` | Estimate analysis time |
| `create_test_data()` | Generate synthetic test data |

### Visualization Functions

| Function | Description |
|----------|-------------|
| `plot_reaction_heatmap()` | Heatmap of reaction scores |
| `plot_metabolite_scores()` | Top uptake/secretion scores |
| `plot_differential_flux()` | Volcano and bar plots |
| `plot_subsystem_activity()` | Subsystem-level activity |
| `plot_umap_with_metabolism()` | UMAP with metabolic overlay |
| `plot_compass_summary()` | Generate all standard plots |

## Output Specifications

### Reaction Scores

- **Format**: DataFrame (reactions × cells)
- **Values**: Minimum penalty achieved for each reaction
- **Interpretation**: Lower scores = higher metabolic activity

### Uptake/Secretion Scores

- **Format**: DataFrame (metabolites × cells)
- **Values**: Minimum penalty for metabolite exchange
- **Interpretation**: Lower scores = higher uptake/secretion potential

### Integration with AnnData

```python
# Reaction scores stored in obsm (cells × reactions)
adata.obsm['compass_reaction_scores']
adata.uns['compass_reaction_names']

# Metabolite scores stored in obs (one column per metabolite)
adata.obs['compass_uptake_M_glc__D_e']
adata.obs['compass_secretion_M_lac__L_e']
```

## Best Practices

### Data Preparation
1. **Use gene symbols** - Convert ENSEMBL IDs before running
2. **Check gene overlap** - Aim for >50% model coverage
3. **Consider microclustering** - Use for datasets >500 cells
4. **Raw counts preferred** - COMPASS handles normalization internally

### Parameter Selection
1. **Lambda (λ)** - Use 0 for small datasets, 0.25 for larger datasets
2. **Number of processes** - Match CPU cores, ~4GB RAM per process
3. **Microcluster size** - 50-100 cells for large datasets
4. **Metabolic model** - RECON2_mat for human, Mouse-GEM for mouse

### Computational Considerations
- **Runtime**: ~30 seconds per cell (RECON2, single process)
- **Memory**: ~4GB per parallel process
- **Disk**: Temporary files can be large; use SSD if possible

## Troubleshooting

### CPLEX Not Found
```
ImportError: No module named 'cplex'
```
→ Install IBM CPLEX and Python API

### Low Gene Overlap
```
Warning: Gene overlap is only 23%
```
→ Convert ENSEMBL IDs to gene symbols

### Out of Memory
```
MemoryError: Unable to allocate array
```
→ Reduce num_processes or enable microclustering

## Related Skills

- [bio-single-cell-metabolism-scmetabolism-r](../bio-single-cell-metabolism-scmetabolism-r/SKILL.md) - SCORPIUS metabolic analysis (R)
- [bio-single-cell-annotation-celltypist](../bio-single-cell-annotation-celltypist/SKILL.md) - Cell type annotation
- [bio-single-cell-clustering](../bio-single-cell-clustering/SKILL.md) - Cell clustering

## References

1. **Wagner et al. (2021)**. Metabolic modeling of single cells via flux balance analysis and constraint programming. *Nature Communications* 12, 3635. https://doi.org/10.1038/s41467-021-23713-5

2. **COMPASS Documentation**: https://yoseflab.github.io/Compass/

3. **GitHub**: https://github.com/wagnerlab-berkeley/Compass

4. **Thiele et al. (2013)**. A community-driven global reconstruction of human metabolism. *Nature Biotechnology* 31, 419-425.
