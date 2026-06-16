# COMPASS Usage Guide

## Overview

COMPASS (COBRA for Personalized Analysis of Single-cell metabolism) performs metabolic flux inference using flux balance analysis (FBA) for single-cell transcriptomics data. It predicts metabolic reaction activities and metabolite uptake/secretion potentials at single-cell resolution.

## When to Use COMPASS

- **Metabolic heterogeneity**: Characterize metabolic differences between cell types or states
- **Metabolic dependencies**: Identify metabolic pathways critical for cell populations
- **Drug target discovery**: Find metabolic vulnerabilities in disease cells
- **Microenvironment analysis**: Study metabolite exchange between cells
- **Integration with expression**: Connect gene expression to metabolic function

## Prerequisites

### Required Software
- Python >= 3.8
- IBM CPLEX >= 12.8 (free academic license available)
- COMPASS (`pip install compass-sc`)

### Hardware Requirements
- **CPU**: Multi-core processor recommended
- **RAM**: 16GB minimum, 32GB+ recommended for large datasets
- **Storage**: SSD recommended for temporary files

## Step-by-Step Guide

### Step 1: Validate Installation

```python
from utils import validate_compass_installation

validation = validate_compass_installation()
print(f"COMPASS installed: {validation['compass_installed']}")
print(f"CPLEX installed: {validation['cplex_installed']}")

if validation['errors']:
    for error in validation['errors']:
        print(f"Error: {error}")
```

### Step 2: Prepare Your Data

```python
import scanpy as sc
from core_analysis import validate_compass_input
from utils import check_gene_overlap, convert_ensembl_to_symbols

# Load data
adata = sc.read_h5ad("your_data.h5ad")

# Check for ENSEMBL IDs and convert if needed
if any(str(g).startswith('ENSG') for g in adata.var_names[:10]):
    adata = convert_ensembl_to_symbols(adata)

# Validate input
validation = validate_compass_input(adata)
if validation['warnings']:
    for warning in validation['warnings']:
        print(f"⚠️  {warning}")

# Check gene overlap
from core_analysis import list_model_genes
model_genes = list_model_genes(model='RECON2_mat', species='homo_sapiens')
overlap = check_gene_overlap(adata, model_genes)

print(f"Gene overlap: {overlap['n_overlap']}/{overlap['n_model_genes']} "
      f"({overlap['overlap_fraction']*100:.1f}%)")

if overlap['overlap_fraction'] < 0.5:
    print("⚠️  Low gene overlap may affect results. Check gene naming.")
```

### Step 3: Select Metabolic Model

```python
from utils import get_model_catalog, recommend_model

# View all models
catalog = get_model_catalog()
print(catalog[['model', 'species', 'use_case']])

# Get recommendation
model = recommend_model(species='human')
print(f"Recommended model: {model}")
```

**Model Selection Guidelines:**

| Dataset Type | Recommended Model | Notes |
|--------------|-------------------|-------|
| Human cells | RECON2_mat | General purpose, most comprehensive |
| Human - core pathways | RECON1_mat | Faster, fewer reactions |
| Mouse cells | Mouse-GEM | Mouse-specific metabolism |
| Human - updated | RECON2.2 | Latest annotations |

### Step 4: Estimate Runtime

```python
from utils import estimate_compass_runtime

estimate = estimate_compass_runtime(
    n_cells=adata.n_obs,
    n_processes=4,
    model='RECON2_mat'
)

print(f"Estimated runtime: {estimate['estimated_total']}")
print(f"Notes: {estimate['notes']}")
```

### Step 5: Run COMPASS

#### Small Dataset (< 500 cells)

```python
from core_analysis import run_compass

compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=4,
    lambda_param=0.0,  # No penalty sharing needed
    calc_metabolites=True,
    verbose=True
)
```

#### Large Dataset (> 500 cells)

```python
from core_analysis import run_compass

compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=8,
    lambda_param=0.25,          # Enable penalty sharing
    num_neighbors=30,
    penalty_diffusion='knn',
    microcluster_size=50,       # Reduce to 50-cell microclusters
    calc_metabolites=True,
    verbose=True
)
```

#### Focused Analysis (Specific Pathways)

```python
from utils import create_subsystem_subset_file

# Create subsystem file
subsystems = ['Glycolysis/Gluconeogenesis', 'Citric acid cycle']
create_subsystem_subset_file(subsystems, './glycolysis_tca.txt')

# Run COMPASS on selected subsystems
compass_results = run_compass(
    adata,
    output_dir='./compass_output_focused',
    model='RECON2_mat',
    species='homo_sapiens',
    select_subsystems='./glycolysis_tca.txt',
    num_processes=4
)
```

### Step 6: Explore Results

```python
# View reaction scores
reaction_scores = compass_results['reaction_scores']
print(f"Reactions: {reaction_scores.shape[0]}")
print(f"Cells: {reaction_scores.shape[1]}")

# Top reactions by mean activity
from utils import get_top_reactions
top_rxns = get_top_reactions(reaction_scores, n=10, by='mean')
print("\nTop reactions by mean score:")
print(top_rxns.mean(axis=1))

# Filter to active reactions
from utils import filter_reactions_by_activity
active_rxns = filter_reactions_by_activity(
    reaction_scores,
    min_activity=0.5,
    min_cells=10
)
print(f"\nActive reactions: {active_rxns.shape[0]}")

# Metabolite scores
if 'uptake_scores' in compass_results:
    uptake = compass_results['uptake_scores']
    top_uptake = uptake.mean(axis=1).nlargest(10)
    print("\nTop uptake metabolites:")
    print(top_uptake)
```

### Step 7: Integrate with AnnData

```python
from core_analysis import add_compass_results_to_adata

# Add results to AnnData
adata = add_compass_results_to_adata(
    adata,
    compass_results,
    reaction_scores_obs=False,  # Store in obsm (recommended)
    prefix='compass_'
)

# Access reaction scores
print(adata.obsm['compass_reaction_scores'].shape)
print(adata.uns['compass_reaction_names'][:5])

# Access metabolite scores
print(adata.obs.filter(like='compass_uptake').columns[:5])
```

### Step 8: Differential Analysis

```python
from core_analysis import analyze_differential_flux

# Compare two conditions
diff_results = analyze_differential_flux(
    compass_results['reaction_scores'],
    adata.obs['condition'],
    method='wilcoxon'
)

# View significant results
significant = diff_results[diff_results['padj'] < 0.05]
print(f"Significant reactions: {len(significant)}")

# Top upregulated in condition B
top_up = diff_results[(diff_results['padj'] < 0.05) & (diff_results['log2FC'] > 0)]
print("\nUpregulated in condition B:")
print(top_up.head(10)[['reaction', 'log2FC', 'padj']])
```

### Step 9: Subsystem Analysis

```python
from core_analysis import summarize_metabolic_activity, infer_subsystems

# Infer subsystems from reaction IDs
subsystems = infer_subsystems(compass_results['reaction_scores'].index)

# Summarize by subsystem
subsystem_summary = summarize_metabolic_activity(
    compass_results['reaction_scores'],
    subsystems
)

print("Subsystem activity summary:")
print(subsystem_summary.groupby('subsystem').mean().mean(axis=1).sort_values(ascending=False))
```

### Step 10: Visualization

```python
from visualization import (
    plot_reaction_heatmap,
    plot_metabolite_scores,
    plot_differential_flux,
    plot_compass_summary
)

# Generate all summary plots
plots = plot_compass_summary(
    compass_results['reaction_scores'],
    compass_results.get('uptake_scores'),
    compass_results.get('secretion_scores'),
    output_dir='./compass_plots',
    prefix='analysis_'
)

print(f"Plots saved: {list(plots.keys())}")

# Individual plots
fig = plot_reaction_heatmap(
    compass_results['reaction_scores'],
    n_top=50,
    save_path='./compass_plots/reaction_heatmap.png'
)

fig = plot_differential_flux(
    diff_results,
    fdr_threshold=0.05,
    save_path='./compass_plots/differential_flux.png'
)
```

### Step 11: Complete Pipeline

```python
from core_analysis import run_compass_pipeline

# Run complete pipeline with differential analysis
results = run_compass_pipeline(
    adata,
    output_dir='./compass_output',
    groupby='condition',
    compare_groups=['control', 'treatment'],
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=4,
    lambda_param=0.25
)

# Access results
adata_with_compass = results['adata']
compass_results = results['compass_results']
diff_results = results.get('differential_flux')
```

## Advanced Topics

### Custom Media Conditions

```python
# Create custom media file (JSON format)
media_config = {
    "EX_glc(e)_neg": 10.0,      # Glucose uptake limit
    "EX_o2(e)_neg": 20.0,        # Oxygen uptake limit
    "EX_lac__L(e)_pos": 10.0     # Lactate secretion limit
}

import json
with open('custom_media.json', 'w') as f:
    json.dump(media_config, f)

# Run with custom media
compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    media='custom_media',  # Name without .json extension
    # ... other parameters
)
```

### Batch Correction Integration

```python
# Use pre-computed k-NN graph for penalty diffusion
compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    input_knn='./batch_corrected_knn.tsv',  # Pre-computed k-NN
    penalty_diffusion='knn',
    # ... other parameters
)
```

### Working with Existing Results

```python
from core_analysis import load_compass_results

# Load results from previous run
compass_results = load_compass_results(
    './compass_output',
    prefix='compass_'
)

# Export to different formats
from utils import export_compass_results
exported = export_compass_results(
    compass_results,
    output_dir='./compass_export',
    format='csv'  # 'csv', 'tsv', or 'excel'
)
```

## Parameter Tuning Guide

### Lambda (λ) - Penalty Diffusion

| Value | Use Case |
|-------|----------|
| 0.0 | Small datasets (< 100 cells), independent cell analysis |
| 0.25 | Medium datasets (100-1000 cells), moderate information sharing |
| 0.5 | Large datasets (> 1000 cells), strong information sharing |

### Microcluster Size

| Dataset Size | Microcluster Size | Expected Speedup |
|--------------|-------------------|------------------|
| 500-1000 | 50 | 2-4x |
| 1000-5000 | 50-100 | 5-10x |
| 5000+ | 100 | 10-50x |

### Number of Processes

- Match to CPU core count
- Leave 1-2 cores for system processes
- Each process needs ~4GB RAM

## Troubleshooting

### Common Issues

**CPLEX License Error**
```
CPLEX Error  1014: Problem size exceeds demo limit.
```
→ Install full CPLEX with valid license

**Low Gene Overlap**
```
Warning: Gene overlap is only 15%
```
→ Convert ENSEMBL to gene symbols
→ Check that gene names are uppercase

**Out of Memory**
```
MemoryError: Unable to allocate array
```
→ Reduce `num_processes`
→ Enable `microcluster_size`
→ Increase system RAM or use compute cluster

**Slow Performance**
```
Progress stuck at X%
```
→ Check disk space (temp files can be large)
→ Use SSD for temp directory
→ Reduce model size with `select_subsystems`

### Debugging Tips

1. **Test with small dataset first**
```python
adata_test = adata[:50, :].copy()
compass_results = run_compass(adata_test, ...)
```

2. **Check intermediate files**
```bash
ls -la ./compass_output/_tmp/
```

3. **Enable verbose logging**
```python
compass_results = run_compass(adata, ..., verbose=True)
```

## Best Practices

### Data Quality
- Ensure adequate gene coverage (>50% model genes)
- Use appropriate normalization (COMPASS handles it internally)
- Filter low-quality cells before analysis

### Analysis Design
- Use biological replicates
- Match cell numbers across conditions when possible
- Consider batch effects in penalty diffusion

### Result Interpretation
- Focus on relative differences, not absolute values
- Validate key findings with experimental data
- Consider pathway-level rather than single-reaction analysis

## References

1. Wagner et al. (2021). Metabolic modeling of single cells via flux balance analysis. *Nature Communications* 12, 3635.
2. YosefLab Compass documentation: https://yoseflab.github.io/Compass/
3. Thiele et al. (2013). A community-driven global reconstruction of human metabolism. *Nature Biotechnology* 31, 419-425.
