---
name: bio-single-cell-differential-abundance-sccoda
description: |
  scCODA is a Bayesian model for differential compositional analysis of single-cell data.
  Uses a Dirichlet-multinomial model with spike-and-slab prior to identify cell types with
  statistically credible changes in abundance between conditions, accounting for compositional
tool_type: python
primary_tool: scCODA
languages: [python]
keywords: ["single-cell", "differential-abundance", "DA", "scCODA", "compositional",
           "bayesian", "mcmc", "cell-proportion", "python"]
---

## Version Compatibility

- **Python**: >=3.8
- **scCODA**: >=0.1.9
- **tensorflow**: >=2.8,<2.16 (required for MCMC sampling)
- **tensorflow-probability**: >=0.16
- **scanpy**: >=1.9
- **pandas**: >=1.3
- **numpy**: >=1.20
- **arviz**: >=0.11
- **patsy**: >=0.5

## Installation

```bash
pip install sccoda
```

**Note**: scCODA requires TensorFlow. For Apple Silicon (M1/M2/M3), use:
```bash
pip install tensorflow-macos tensorflow-metal
pip install sccoda
```

## Data Requirements

Input requirements:
- **AnnData object**: Created from cell count matrix via `from_scanpy()` or `from_pandas()`
- **Cell counts**: Raw cell counts per sample (not normalized)
- **Covariates**: Sample-level metadata (condition, batch, etc.)
- **Cell types**: Columns in the count matrix

**Data Format:**
The input to scCODA is fundamentally different from standard scRNA-seq analysis:
- Rows = Samples (not cells)
- Columns = Cell types
- Values = Cell counts per sample

**Data Validation:**
```python
from scripts.python.utils import validate_sccoda_data

# Check if data is suitable for scCODA
is_valid = validate_sccoda_data(
    adata,
    min_samples_per_group=2,
    min_cell_types=3,
    max_zero_proportion=0.5
)
```

## Core Analysis Workflow

### 1. Data Loading and Preparation

**Input formats supported:**
```python
from sccoda.util import cell_composition_data as dat

# Option 1: From scanpy AnnData (most common)
# Requires cell-level AnnData with cell_type and sample_id columns
sccoda_data = dat.from_scanpy(
    adata,
    cell_type_identifier="cell_type",
    sample_identifier="sample_id",
    covariate_df=covariates_df  # DataFrame with sample-level metadata
)

# Option 2: From pandas DataFrame
cell_counts_df = pd.read_csv("cell_counts.csv", index_col=0)
sccoda_data = dat.from_pandas(
    cell_counts_df,
    covariate_columns=["condition", "batch"]
)

# Option 3: From list of scanpy objects
sccoda_data = dat.from_scanpy_list(
    [adata1, adata2, adata3],
    cell_type_identifier="cell_type",
    covariate_df=covariates_df
)
```

**Key Points:**
- Cell counts must be raw counts (not normalized)
- Each sample must have at least 2 replicates per condition
- Covariates must be at sample level (not cell level)

### 2. Data Visualization (Before Analysis)

```python
from sccoda.util import data_visualization as viz

# Stacked barplot of cell type compositions
viz.stacked_barplot(sccoda_data, feature_name="condition")

# Boxplots by cell type
viz.boxplots(sccoda_data, feature_name="condition", y_scale="relative")

# Dispersion plot for reference cell type selection
viz.rel_abundance_dispersion_plot(sccoda_data)
```

### 3. Model Setup and Inference

Function: `run_sccoda_analysis(data, formula, reference_cell_type, ...)`

**Purpose:** Run differential compositional analysis using Bayesian MCMC sampling.

**Key Parameters:**
- `formula`: R-style formula for covariates (e.g., "condition", "condition + batch")
- `reference_cell_type`: Reference cell type for compositional analysis
  - String: Name of cell type column
  - Integer: Column index
  - "automatic": Select cell type with lowest dispersion present in >90% samples
- `num_results`: MCMC chain length (default: 20000)
- `num_burnin`: Burn-in samples (default: 5000)

**Process:**
1. Build covariate matrix from formula
2. Select reference cell type
3. Run HMC (Hamiltonian Monte Carlo) sampling
4. Calculate inclusion probabilities
5. Identify credible effects

**Example:**
```python
from scripts.python.core_analysis import run_sccoda_analysis

results = run_sccoda_analysis(
    sccoda_data,
    formula="condition",
    reference_cell_type="automatic",
    num_results=20000,
    num_burnin=5000
)
```

### 4. Result Interpretation

Function: `summarize_results(results, est_fdr)`

**Purpose:** Extract and interpret scCODA analysis results.

**Output Columns:**
- `Final Parameter`: Effect size (0 = no credible change)
- `Expected Sample`: Predicted cell counts
- `log2-fold change`: Log2 fold change vs reference
- `Inclusion probability`: Probability of true effect

**Example:**
```python
from scripts.python.utils import summarize_results, get_credible_effects

# View summary
summarize_results(results)

# Get significant cell types
credible_effects = get_credible_effects(results)
significant_cell_types = credible_effects[credible_effects].index.tolist()

# Get detailed effect dataframe
effects_df = results.effect_df
```

### 5. Adjust False Discovery Rate

Function: `results.set_fdr(est_fdr)`

**Purpose:** Adjust the threshold for credible effects.

**Parameters:**
- `est_fdr`: Target false discovery rate (default: 0.05)
  - Lower value (0.01): More conservative, fewer effects
  - Higher value (0.2): Less conservative, more effects

**Example:**
```python
# More liberal threshold
results.set_fdr(est_fdr=0.2)
summarize_results(results)
```

### 6. Visualization of Results

```python
from scripts.python.visualization import (
    plot_effect_barplot,
    plot_credible_effects,
    plot_fold_changes
)

# Barplot of effects
plot_effect_barplot(results, save_path="effects.png")

# Highlight credible effects
plot_credible_effects(results, save_path="credible_effects.png")

# Plot fold changes
plot_fold_changes(results, save_path="fold_changes.png")
```

### 7. Multi-condition Analysis

```python
# Multiple covariates
results = run_sccoda_analysis(
    sccoda_data,
    formula="condition + batch + age",
    reference_cell_type="automatic"
)

# Interaction terms
results = run_sccoda_analysis(
    sccoda_data,
    formula="condition * genotype",
    reference_cell_type="automatic"
)

# Categorical with reference level
results = run_sccoda_analysis(
    sccoda_data,
    formula="C(condition, Treatment('control'))",
    reference_cell_type="automatic"
)
```

### 8. Complete Pipeline

```python
from scripts.python.core_analysis import run_complete_analysis
from scripts.python.utils import create_analysis_report

# Run complete analysis
results, sccoda_data = run_complete_analysis(
    adata,
    sample_key="sample_id",
    cell_type_key="cell_type",
    condition_key="condition",
    covariate_columns=["batch"],
    reference_cell_type="automatic",
    output_dir="sccoda_results"
)

# Generate report
report = create_analysis_report(
    results,
    output_file="sccoda_report.txt"
)
```

### 9. Export Results

Function: `export_results(results, output_dir, ...)`

**Example:**
```python
from scripts.python.utils import export_results

export_results(
    results,
    output_dir="sccoda_output",
    prefix="analysis",
    export_summary=True,
    export_effects=True,
    export_diagnostics=True
)
```

## Input Requirements

### Required Data Format

```python
# For from_scanpy:
adata.obs['cell_type']  # Cell type labels
adata.obs['sample_id']  # Sample identifiers
covariate_df = pd.DataFrame({
    'sample_id': ['S1', 'S2', 'S3'],
    'condition': ['ctrl', 'treat', 'treat'],
    'batch': ['A', 'A', 'B']
}).set_index('sample_id')
```

### For from_pandas:

```python
cell_counts_df = pd.DataFrame({
    'sample_id': ['S1', 'S2', 'S3'],
    'T_cell': [100, 150, 120],
    'B_cell': [50, 60, 55],
    'Mono': [30, 40, 35],
    'condition': ['ctrl', 'treat', 'treat'],
    'batch': ['A', 'A', 'B']
}).set_index('sample_id')
```

## Output Specifications

### Core Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Intercept summary | `results.intercept_df` | Baseline cell type proportions |
| Effect summary | `results.effect_df` | Differential effects per covariate/cell type |
| Credible effects | `results.credible_effects()` | Boolean mask for significant effects |
| Inclusion probability | `results.effect_df['Inclusion probability']` | Posterior probability of effect |
| MCMC diagnostics | `results.sampling_stats` | Chain length, acceptance rate, duration |

### Diagnostic Outputs

- Acceptance rate (target: 20-80%)
- MCMC chain convergence
- Posterior predictive checks

## Key Parameters

### Data Preparation

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cell_type_identifier` | str | Required | Column with cell type labels |
| `sample_identifier` | str | Required | Column with sample labels |
| `covariate_df` | DataFrame | None | Sample-level metadata |

### Model Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `formula` | str | Required | R-style formula for covariates |
| `reference_cell_type` | str/int | "automatic" | Reference for compositional analysis |
| `automatic_reference_absence_threshold` | float | 0.05 | Max zero fraction for auto reference |

### MCMC Sampling

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_results` | int | 20000 | MCMC chain length |
| `num_burnin` | int | 5000 | Burn-in iterations |
| `num_leapfrog_steps` | int | 10 | HMC leapfrog steps |
| `step_size` | float | 0.01 | Initial step size |

### Result Interpretation

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `est_fdr` | float | 0.05 | False discovery rate threshold |

## Expected Runtime

| Dataset Size | Data Prep | MCMC (20k iter) | Total |
|--------------|-----------|-----------------|-------|
| 10 samples, 8 cell types | <1s | 30-60s | 1-2 min |
| 20 samples, 15 cell types | <1s | 60-120s | 2-3 min |
| 50 samples, 20 cell types | 1-2s | 2-5 min | 3-6 min |
| 100 samples, 30 cell types | 2-5s | 5-10 min | 6-12 min |

*Runtime estimates on 8-core CPU with 32GB RAM*

## Error Handling

### Common Errors and Solutions

**Missing required columns**
```
ValueError: Column 'cell_type' not found in adata.obs
```
→ Verify column names in `adata.obs.columns`

**Insufficient samples per condition**
```
ValueError: Need at least 2 samples per condition
```
→ Ensure each condition has >=2 replicates

**Invalid reference cell type**
```
NameError: Reference index is not a valid cell type name
```
→ Check cell type name exists in `data.var.index`

**No cell types meet threshold**
```
ValueError: No cell types that have large enough presence!
```
→ Increase `automatic_reference_absence_threshold` or specify reference manually

**MCMC convergence issues**
```
Acceptance rate: 0.1% (too low)
```
→ Increase `step_size` or reduce `num_leapfrog_steps`

**TensorFlow errors**
```
RuntimeError: CUDA out of memory
```
→ Use CPU-only mode or reduce `num_results`

## Common Analysis Patterns

### Pattern 1: Quick Two-group Comparison
```python
sccoda_data = dat.from_scanpy(adata, "cell_type", "sample_id", covariate_df=covs)
results = run_sccoda_analysis(sccoda_data, formula="condition", reference_cell_type="automatic")
summarize_results(results)
```

### Pattern 2: With Batch Correction
```python
results = run_sccoda_analysis(
    sccoda_data,
    formula="condition + batch",
    reference_cell_type="automatic"
)
```

### Pattern 3: Custom Reference Selection
```python
# Select most stable cell type as reference
viz.rel_abundance_dispersion_plot(sccoda_data)
results = run_sccoda_analysis(
    sccoda_data,
    formula="condition",
    reference_cell_type="T_cell"  # Manually selected
)
```

### Pattern 4: Multiple Comparisons
```python
# Pairwise comparisons between multiple conditions
from scripts.python.utils import pairwise_comparisons

results_dict = pairwise_comparisons(
    sccoda_data,
    condition_col="condition",
    reference_conditions=["control"]
)
```

### Pattern 5: Comprehensive Report
```python
results, sccoda_data = run_complete_analysis(
    adata,
    sample_key="sample_id",
    cell_type_key="cell_type",
    condition_key="condition"
)
export_results(results, output_dir="results/")
```

## Module Structure

```
scripts/python/
├── core_analysis.py      # run_sccoda_analysis(), run_complete_analysis()
├── data_preparation.py   # prepare_sccoda_data(), check_data_requirements()
├── visualization.py      # plot_effect_barplot(), plot_credible_effects(),
│                         # plot_fold_changes(), plot_composition_summary()
└── utils.py              # validate_sccoda_data(), summarize_results(),
                          # get_credible_effects(), export_results(),
                          # create_analysis_report()

examples/
├── minimal_example.py    # Basic two-group comparison
└── advanced_example.py   # Multi-condition, batch correction, visualization

tests/
└── test_sccoda.py        # Unit tests for all modules
```

## Interpretation Guidelines

### Understanding Results

**Intercepts:**
- Represent baseline cell type proportions
- "Expected Sample" shows predicted counts for a sample with average total cells

**Effects:**
- Final Parameter = 0: No credible change detected
- Final Parameter != 0: Credible change (positive = increase, negative = decrease)
- Log2-fold change calculated relative to intercept

**Inclusion Probability:**
- Probability that the effect is not zero (spike-and-slab prior)
- Threshold determined by FDR control
- Higher = more confidence in effect

### Compositional Effects

Important: Due to compositional nature, non-significant cell types may still show changes in abundance when another cell type has a credible effect. This is expected behavior - changes must sum to zero.

### Reference Cell Type Selection

Good reference criteria:
1. Present in most samples (>90%)
2. Low variance in relative abundance
3. Biologically expected to be stable
4. Not expected to change between conditions

## Related Skills

- [bio-single-cell-differential-abundance-diffcyt-r](../bio-single-cell-differential-abundance-diffcyt-r/SKILL.md) - Alternative DA analysis for clustering results
- [bio-single-cell-differential-abundance-milor-r](../bio-single-cell-differential-abundance-milor-r/SKILL.md) - DA analysis on graph neighborhoods
- [bio-single-cell-differential-abundance-roe-r](../bio-single-cell-differential-abundance-roe-r/SKILL.md) - DA analysis using regions of interest

## References

1. Büttner, Ostner et al. (2021). scCODA is a Bayesian model for compositional single-cell data analysis. *Nature Communications*, 12:6876. https://doi.org/10.1038/s41467-021-27150-6
2. scCODA GitHub: https://github.com/theislab/scCODA
3. scCODA Documentation: https://sccoda.readthedocs.io/
4. Haber et al. (2017). A single-cell survey of the small intestinal epithelium. *Nature*, 551:333-339.
