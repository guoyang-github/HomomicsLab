# scCODA Usage Guide

## Overview

scCODA (single-cell Compositional Data Analysis) is a Bayesian model for detecting statistically credible changes in cell type proportions between conditions. It properly accounts for the compositional nature of single-cell data, where the sum of proportions is constrained to 1.

### Key Features

- Bayesian inference with Hamiltonian Monte Carlo (HMC) sampling
- Spike-and-slab prior for automatic effect selection
- Handles multiple covariates and interaction terms
- Automatic or manual reference cell type selection
- False discovery rate (FDR) control

### When to Use scCODA

| Scenario | Recommended Tool |
|----------|------------------|
| Compare cell type proportions between conditions | **scCODA** |
| Multiple conditions with batch effects | **scCODA** |
| Need compositional correction | **scCODA** |
| Identify specific changing cell types | **scCODA** |
| Graph-based DA analysis | miloR |
| DA on clustering results | diffcyt |

## Quick Start

### Installation

```bash
pip install sccoda
```

For Apple Silicon (M1/M2/M3):
```bash
pip install tensorflow-macos tensorflow-metal
pip install sccoda
```

### Basic Workflow

```python
from sccoda.util import cell_composition_data as dat
from sccoda.util import comp_ana as mod

# 1. Prepare compositional data
sccoda_data = dat.from_scanpy(
    adata,
    cell_type_identifier="cell_type",
    sample_identifier="sample_id",
    covariate_df=covariates
)

# 2. Run scCODA
model = mod.CompositionalAnalysis(
    sccoda_data,
    formula="condition",
    reference_cell_type="automatic"
)
results = model.sample_hmc(num_results=20000)

# 3. View results
results.summary()
```

## Step-by-Step Guide

### Step 1: Data Preparation

#### From Single-Cell Data (Recommended)

```python
import scanpy as sc
from sccoda.util import cell_composition_data as dat

# Load cell-level data
adata = sc.read_h5ad("single_cell_data.h5ad")

# Check required columns
print(adata.obs.columns)
# Required: 'sample_id', 'cell_type'
# Optional: 'condition', 'batch', etc.

# Create sample-level covariates
covariates = adata.obs.groupby("sample_id").agg({
    "condition": "first",
    "batch": "first",
    "age": "first",
}).reset_index().set_index("sample_id")

# Convert to compositional format
sccoda_data = dat.from_scanpy(
    adata,
    cell_type_identifier="cell_type",
    sample_identifier="sample_id",
    covariate_df=covariates
)

print(sccoda_data)
# AnnData object with n_obs × n_vars = 10 × 8
#     obs: 'condition', 'batch', 'age'
```

#### From Pandas DataFrame

```python
import pandas as pd
from sccoda.util import cell_composition_data as dat

# Load or create cell counts table
cell_counts = pd.read_csv("cell_counts.csv", index_col=0)
# Format: rows=samples, columns=cell_types + covariates

print(cell_counts.head())
#          T_cell  B_cell  Mono  condition  batch
# Sample1     100      50    30      ctrl      A
# Sample2     120      45    35      treat     A

# Convert to scCODA format
sccoda_data = dat.from_pandas(
    cell_counts,
    covariate_columns=["condition", "batch"]
)
```

#### Data Validation

```python
from scripts.python.utils import validate_sccoda_data

validation = validate_sccoda_data(sccoda_data)

if validation["valid"]:
    print("✅ Data is valid for scCODA analysis")
else:
    print("❌ Data validation failed:")
    for error in validation["errors"]:
        print(f"  - {error}")
```

### Step 2: Exploratory Visualization

```python
from sccoda.util import data_visualization as viz
import matplotlib.pyplot as plt

# Stacked barplot of compositions by condition
viz.stacked_barplot(sccoda_data, feature_name="condition")
plt.savefig("composition_by_condition.png")

# Boxplots of cell type proportions
viz.boxplots(sccoda_data, feature_name="condition", y_scale="relative")
plt.savefig("proportion_boxplots.png")

# Reference cell type selection helper
viz.rel_abundance_dispersion_plot(sccoda_data)
plt.savefig("dispersion_plot.png")
```

### Step 3: Model Setup and Inference

```python
from scripts.python.core_analysis import run_sccoda_analysis

# Option 1: Automatic reference selection
results = run_sccoda_analysis(
    sccoda_data,
    formula="condition",
    reference_cell_type="automatic",
    num_results=20000,
    num_burnin=5000,
    verbose=True
)

# Option 2: Specify reference cell type
results = run_sccoda_analysis(
    sccoda_data,
    formula="condition",
    reference_cell_type="T_cell",  # Name of stable cell type
    num_results=20000,
    num_burnin=5000,
    verbose=True
)

# Option 3: Multi-condition with batch correction
results = run_sccoda_analysis(
    sccoda_data,
    formula="condition + batch + age",
    reference_cell_type="automatic",
    num_results=20000,
    num_burnin=5000
)
```

**MCMC Parameters:**

| Parameter | Default | Description | When to Adjust |
|-----------|---------|-------------|----------------|
| `num_results` | 20000 | MCMC chain length | Increase for complex models |
| `num_burnin` | 5000 | Burn-in iterations | Typically 25% of chain length |
| `num_leapfrog_steps` | 10 | HMC leapfrog steps | Increase if acceptance rate low |
| `step_size` | 0.01 | Initial step size | Adjust to get 20-80% acceptance |

### Step 4: Result Interpretation

```python
# Basic summary
results.summary()
```

**Output Explanation:**

```
Compositional Analysis summary:

Data: 10 samples, 8 cell types
Reference index: 2
Formula: condition

Intercepts:
                       Final Parameter  Expected Sample
Cell Type
T_cell                        2.500          250.0
B_cell                        1.800          150.0
...

Effects:
                                         Final Parameter  Expected Sample  log2-fold change
Covariate         Cell Type
treatment[T.treat] T_cell                     0.0000          250.0            0.0000
                   B_cell                     0.5000          200.0            0.4150
...
```

**Understanding Results:**

| Column | Interpretation |
|--------|----------------|
| `Final Parameter` | Effect size (0 = no credible change) |
| `Expected Sample` | Predicted cell counts for average total |
| `log2-fold change` | Log2 fold change vs reference |
| `Inclusion probability` | Posterior probability of effect |

### Step 5: Extract Significant Results

```python
from scripts.python.utils import get_significant_cell_types

# Get credible (significant) effects
credible = results.credible_effects()
print(credible)

# Get significant cell types
significant = get_significant_cell_types(results)
print(f"Significant cell types: {significant}")

# Get detailed statistics
from scripts.python.utils import summarize_results

summary = summarize_results(results, extended=True)
print(f"Total significant effects: {summary['statistics']['n_credible_effects']}")
print(f"Acceptance rate: {summary['statistics']['acceptance_rate']:.1%}")
```

### Step 6: Adjust FDR Threshold

```python
# Default FDR = 0.05
results.set_fdr(est_fdr=0.1)  # More liberal
results.summary()

# Or more conservative
results.set_fdr(est_fdr=0.01)  # More strict
results.summary()
```

### Step 7: Visualization of Results

```python
from scripts.python.visualization import (
    plot_effect_barplot,
    plot_credible_effects,
    plot_fold_changes,
    plot_inclusion_probability,
    plot_results_summary
)

# Effect sizes
plot_effect_barplot(results, save_path="effects.png")

# Credible effects heatmap
plot_credible_effects(results, save_path="credible_effects.png")

# Log2 fold changes
plot_fold_changes(results, save_path="fold_changes.png")

# Inclusion probabilities
plot_inclusion_probability(results, save_path="inclusion_prob.png")

# Comprehensive summary figure
plot_results_summary(results, save_path="results_summary.png")
```

### Step 8: Export Results

```python
from scripts.python.utils import export_results, create_analysis_report

# Export all results
export_results(
    results,
    output_dir="sccoda_results",
    prefix="analysis",
    export_summary=True,
    export_effects=True,
    export_diagnostics=True
)

# Create text report
report = create_analysis_report(
    results,
    output_file="sccoda_report.txt"
)
print(report)
```

## Advanced Topics

### Multi-Condition Analysis

```python
# Multiple conditions with pairwise comparisons
from scripts.python.core_analysis import compare_multiple_conditions

pairwise_results = compare_multiple_conditions(
    sccoda_data,
    condition_col="treatment",
    reference_condition="control",
    reference_cell_type="automatic",
    num_results=20000
)

# Access individual results
for condition, result in pairwise_results.items():
    print(f"\n{condition}:")
    sig = result.credible_effects().sum()
    print(f"  {sig} significant changes")
```

### Reference Cell Type Robustness

```python
# Test different reference cell types
from scripts.python.core_analysis import run_sccoda_with_different_references

ref_results = run_sccoda_with_different_references(
    sccoda_data,
    formula="condition",
    reference_cell_types=["automatic", "T_cell", "B_cell", "Monocyte"],
    num_results=20000
)

# Compare consistency
for ref, result in ref_results.items():
    print(f"{ref}: {result.credible_effects().sum()} effects")
```

### Complete Pipeline

```python
from scripts.python.core_analysis import run_complete_analysis

results, sccoda_data = run_complete_analysis(
    adata,
    sample_key="sample_id",
    cell_type_key="cell_type",
    condition_key="condition",
    covariate_columns=["batch", "age"],
    reference_cell_type="automatic",
    output_dir="results",
    verbose=True
)
```

## Formula Syntax

scCODA uses R-style formula syntax via `patsy`:

```python
# Simple comparison
"condition"

# Multiple covariates
"condition + batch"

# With interaction
"condition * genotype"

# Custom reference level
"C(condition, Treatment('control'))"

# Continuous covariate
"condition + age"

# Polynomial term
"condition + np.power(age, 2)"
```

## Troubleshooting

### Low Acceptance Rate

```python
# If acceptance rate < 20%, increase step_size or decrease leapfrog steps
results = run_sccoda_analysis(
    sccoda_data,
    formula="condition",
    step_size=0.05,  # Increase from 0.01
    num_leapfrog_steps=5  # Decrease from 10
)
```

### High Acceptance Rate

```python
# If acceptance rate > 80%, decrease step_size
results = run_sccoda_analysis(
    sccoda_data,
    formula="condition",
    step_size=0.005  # Decrease from 0.01
)
```

### No Significant Effects Found

```python
# Try more liberal FDR threshold
results.set_fdr(est_fdr=0.2)
results.summary()

# Or check if sample size is sufficient
from scripts.python.data_preparation import check_data_requirements
check_data_requirements(sccoda_data, min_samples_per_group=2)
```

### TensorFlow Warnings

```python
# Suppress TF warnings
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import warnings
warnings.filterwarnings("ignore")
```

## Best Practices

1. **Sample Size**: Use ≥3 samples per condition (≥5 recommended)
2. **Reference Selection**: Choose biologically stable cell type
3. **Batch Correction**: Include batch as covariate when needed
4. **MCMC Convergence**: Check acceptance rate (target 20-80%)
5. **FDR Control**: Start with 0.05, adjust based on results
6. **Validation**: Run with multiple reference cell types

## AI Agent Test Cases

### Basic Usage
> "Run scCODA to compare cell type proportions between control and treatment groups"

```python
results = run_sccoda_analysis(
    sccoda_data,
    formula="condition",
    reference_cell_type="automatic"
)
```

### With Batch Correction
> "Run scCODA with batch correction for cell type proportion analysis"

```python
results = run_sccoda_analysis(
    sccoda_data,
    formula="condition + batch",
    reference_cell_type="automatic"
)
```

### Multi-condition
> "Compare multiple treatment conditions against control using scCODA"

```python
pairwise_results = compare_multiple_conditions(
    sccoda_data,
    condition_col="treatment",
    reference_condition="control"
)
```

### Export and Report
> "Run scCODA analysis and export all results with a summary report"

```python
results = run_sccoda_analysis(sccoda_data, formula="condition")
export_results(results, output_dir="results")
report = create_analysis_report(results, output_file="report.txt")
```

## References

1. Büttner, Ostner et al. (2021). scCODA is a Bayesian model for compositional single-cell data analysis. *Nature Communications*, 12:6876.
2. scCODA GitHub: https://github.com/theislab/scCODA
3. scCODA Documentation: https://sccoda.readthedocs.io/
