---
name: bio-single-cell-metabolism-compass
description: |
  Metabolic flux inference for single-cell transcriptomics using COMPASS.
  Performs flux-balance-analysis-based reaction penalty scoring, metabolite
  uptake/secretion prediction, differential flux analysis, and subsystem-level
  summarization with Scanpy/AnnData integration.
version: "1.1"
tool_type: python
primary_tool: COMPASS
supported_tools: [scanpy, pandas, numpy, scipy, matplotlib, seaborn, plotly, pybiomart]
languages: [python]
dependencies:
  - compass-sc
  - scanpy >= 1.9.0
  - anndata >= 0.8.0
  - numpy >= 1.20.0
  - pandas >= 1.5.0
  - matplotlib >= 3.5.0
  - seaborn >= 0.11.0
  - scipy >= 1.7.0
  - statsmodels >= 0.13.0
  - plotly >= 5.0.0
  - pybiomart >= 0.2.0
system_requirements:
  - Python >= 3.8
  - IBM CPLEX >= 12.8
keywords: ["single-cell", "metabolism", "COMPASS", "FBA", "flux-balance-analysis",
           "metabolic-modeling", "python"]
---

## Version Compatibility & Installation

| Package | Required | Notes |
|---------|----------|-------|
| Python | >= 3.8 | |
| COMPASS | `compass-sc` | PyPI wrapper; calls the `compass` CLI |
| IBM CPLEX | >= 12.8 | Required solver; free academic license |
| scanpy | >= 1.9.0 | AnnData I/O |
| pandas | >= 1.5.0 | |
| numpy | >= 1.20.0 | |
| scipy | >= 1.7.0 | Statistics |
| matplotlib | >= 3.5.0 | Plotting |
| seaborn | >= 0.11.0 | Heatmaps |
| statsmodels | >= 0.13.0 | Multiple-testing correction |
| plotly | >= 5.0.0 | Interactive dashboard |
| pybiomart | >= 0.2.0 | ENSEMBL-to-symbol conversion |

```bash
pip install compass-sc
pip install -r requirements.txt
```

> **Agent warning:** `compass-sc` does **not** include CPLEX. Download and install IBM ILOG CPLEX Optimization Studio and ensure `import cplex` works.

## Skill Overview

COMPASS infers per-cell metabolic reaction activity by solving a flux-balance-analysis problem with a penalty objective. This skill prepares an AnnData object, runs the COMPASS CLI, loads penalty matrices, and integrates them back into AnnData.

**Key characteristics:** lower penalty = higher activity; requires IBM CPLEX; ~30 s/cell for RECON2.

**When to use:**
- Genome-scale metabolic reaction scores at single-cell resolution.
- Metabolite uptake/secretion potential estimates.
- Differential flux comparison between two conditions or cell types.
- Datasets with >50% model gene coverage.

**When NOT to use:**
- You need a fast or license-free method → use [bio-single-cell-metabolism-scmetabolism-r](../bio-single-cell-metabolism-scmetabolism-r/SKILL.md).
- You need ORA/GSEA on DEGs → use [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md) or [bio-single-cell-enrichment-clusterprofiler-r](../bio-single-cell-enrichment-clusterprofiler-r/SKILL.md).
- You need TF/signaling pathway activity → use [bio-single-cell-enrichment-decoupler-r](../bio-single-cell-enrichment-decoupler-r/SKILL.md).
- CPLEX is unavailable.

## Core Workflow

### Step 1: Validate Data and Check Gene Overlap

```python
import sys
sys.path.append('scripts/python')

from core_analysis import validate_compass_input, list_model_genes
from utils import check_gene_overlap

validation = validate_compass_input(adata)
model_genes = list_model_genes(model='RECON2_mat', species='homo_sapiens')
overlap = check_gene_overlap(adata, model_genes)
print(f"Overlap: {overlap['overlap_fraction']*100:.1f}%")
```

**Requirements:** gene symbols (not ENSEMBL), non-negative values, >50% model coverage preferred.

### Step 2: Select Model

```python
from utils import recommend_model
model = recommend_model(species='human')  # RECON2_mat
```

**Models:** `RECON2_mat` (human, recommended), `RECON1_mat` (human, core), `RECON2.2` (human, updated), `Mouse-GEM` (mouse).

### Step 3: Run COMPASS

```python
from core_analysis import run_compass

compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=4,
    lambda_param=0.25,
    microcluster_size=50 if adata.n_obs > 500 else None,
    calc_metabolites=True,
    verbose=True
)
```

**Output:** dict with `reaction_scores`, `uptake_scores`, `secretion_scores` DataFrames (rows = reactions/metabolites, columns = cells).

### Step 4: Integrate, Analyze, and Visualize

```python
from core_analysis import add_compass_results_to_adata, analyze_differential_flux
from visualization import plot_compass_summary

adata = add_compass_results_to_adata(adata, compass_results, prefix='compass_')
diff_results = analyze_differential_flux(
    compass_results['reaction_scores'],
    adata.obs['condition']
)
plot_compass_summary(
    compass_results['reaction_scores'],
    compass_results.get('uptake_scores'),
    compass_results.get('secretion_scores'),
    output_dir='./compass_plots'
)
```

### Common Import Pattern

```python
from core_analysis import (
    run_compass, load_compass_results, add_compass_results_to_adata,
    analyze_differential_flux, summarize_metabolic_activity
)
from utils import (
    check_gene_overlap, list_model_genes, recommend_model,
    validate_compass_installation
)
from visualization import plot_compass_summary, plot_differential_flux
```

## Complete Pipeline (Copy-Pasteable)

```python
import scanpy as sc
import sys
sys.path.append('scripts/python')

from core_analysis import run_compass, add_compass_results_to_adata, analyze_differential_flux
from utils import check_gene_overlap, list_model_genes, recommend_model
from visualization import plot_compass_summary

adata = sc.read_h5ad('your_data.h5ad')
model = recommend_model(species='human')
model_genes = list_model_genes(model=model, species='homo_sapiens')
print(f"Overlap: {check_gene_overlap(adata, model_genes)['overlap_fraction']*100:.1f}%")

compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model=model,
    species='homo_sapiens',
    num_processes=4,
    lambda_param=0.25,
    microcluster_size=50 if adata.n_obs > 500 else None,
    calc_metabolites=True
)

adata = add_compass_results_to_adata(adata, compass_results)
diff_results = analyze_differential_flux(
    compass_results['reaction_scores'], adata.obs['condition']
)
plot_compass_summary(
    compass_results['reaction_scores'],
    compass_results.get('uptake_scores'),
    compass_results.get('secretion_scores'),
    output_dir='./compass_plots'
)
```

## Skill-Provided Functions

### Core analysis
- `run_compass(...)` — main COMPASS runner.
- `load_compass_results(output_dir, prefix)` — load existing outputs.
- `add_compass_results_to_adata(...)` — integrate results into AnnData.
- `analyze_differential_flux(...)` — two-group differential test.
- `summarize_metabolic_activity(...)` — subsystem summary.
- `get_available_models()` / `list_model_genes()` / `list_model_reactions()`.
- `run_compass_pipeline(...)` — end-to-end wrapper.

### Utilities
- `check_gene_overlap`, `recommend_model`.
- `filter_reactions_by_activity`, `get_top_reactions`, `get_top_metabolites`.
- `export_compass_results`, `convert_ensembl_to_symbols`.
- `validate_compass_installation`.

### Visualization
- `plot_reaction_heatmap`, `plot_differential_flux`, `plot_subsystem_activity`, `plot_compass_summary`.

## Official API — Agents Often Miss These

**1. COMPASS scores are penalties: lower = more active**

```python
compass_results['reaction_scores'].mean(axis=1).nsmallest(10)
```

**2. Differential log2FC direction is reversed**

`analyze_differential_flux()` returns `log2FC = log2(mean_B / mean_A)`. Because higher penalty means lower activity, `log2FC > 0` means group B is **less active** than A.

**3. Reaction scores shape is reactions × cells; AnnData storage transposes them**

```python
compass_results['reaction_scores'].shape        # (n_reactions, n_cells)
adata.obsm['compass_reaction_scores'].shape     # (n_cells, n_reactions)
```

**4. Gene symbols are uppercased and duplicates summed during input preparation**

`prepare_compass_input()` handles mixed case and duplicate gene symbols automatically.

## Common Pitfalls

1. **Scores are penalties, not activities** — lower score = higher predicted flux.
2. **Differential log2FC sign is reversed** — positive log2FC means group B is less active.
3. **CPLEX is required but not installed by `pip install compass-sc`** — install IBM CPLEX separately.
4. **Low gene overlap (<50%) yields unreliable estimates** — convert ENSEMBL IDs and verify species/model.
5. **Differential flux requires exactly two groups** — subset your labels accordingly.

## Scenarios

### Scenario 1: Basic COMPASS Run

```python
from core_analysis import run_compass

compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=4,
    lambda_param=0.0,
    calc_metabolites=True
)
```

### Scenario 2: Large Dataset with Microclustering

```python
compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=8,
    lambda_param=0.25,
    microcluster_size=50,
    calc_metabolites=True
)
```

### Scenario 3: Advanced Run with All Key Parameters

```python
compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=4,
    lambda_param=0.0,
    num_neighbors=30,
    penalty_diffusion='knn',
    and_function='mean',
    microcluster_size=None,
    calc_metabolites=True
)
```

## Best Practices & Computational Notes

- **Use raw counts when possible**; if normalized, ensure values are non-negative.
- **Set `lambda_param=0`** for small/noisy datasets to avoid over-smoothing; use **`0.25`** for large datasets (≥1,000 cells) with microclustering.
- **Plan ~4 GB RAM per process**; choose `num_processes` so total memory fits your machine.
- **COMPASS writes large temporary files**; place `output_dir` on a fast local disk (SSD preferred) and ensure free space ≥ output size × 2.
- **Run microclustering** (`microcluster_size=50`) when `adata.n_obs > 500` to reduce runtime and memory.
- **Verify gene overlap >50%** before running; convert ENSEMBL IDs to gene symbols with `pybiomart` if needed.
- **Always check differential log2FC direction**: positive log2FC means group B is *less* active than group A.

## Parameters

`run_compass(adata, output_dir, model='RECON2_mat', species='homo_sapiens', lambda_param=0.0, microcluster_size=None, calc_metabolites=True, ...)`

| Parameter | Notes |
|-----------|-------|
| `model` | `RECON2_mat` (human), `Mouse-GEM` (mouse), `RECON1_mat`, `RECON2.2` |
| `lambda_param` | Penalty diffusion strength; use 0 for small datasets, 0.25 for large |
| `microcluster_size` | Target cells per microcluster; recommended for >500 cells |
| `calc_metabolites` | Compute uptake/secretion scores |
| `select_reactions` / `select_subsystems` | Files limiting the analysis |

`add_compass_results_to_adata(adata, compass_results, reaction_scores_obs=False, prefix='compass_')` stores reaction scores in `obsm` and metabolite scores in `obs`.

`analyze_differential_flux(reaction_scores, group_labels)` requires exactly two groups and returns `log2FC = log2(mean_B / mean_A)`.

## Output Description

`run_compass()` returns:

| Key | Shape | Interpretation |
|-----|-------|----------------|
| `reaction_scores` | reactions × cells | Penalty scores; **lower = higher activity** |
| `uptake_scores` | metabolites × cells | Lower = higher uptake potential |
| `secretion_scores` | metabolites × cells | Lower = higher secretion potential |

After `add_compass_results_to_adata(..., reaction_scores_obs=False, prefix='compass_')`, reaction scores are in `adata.obsm['compass_reaction_scores']` (cells × reactions) with IDs in `adata.uns['compass_reaction_names']`; metabolite scores are in `adata.obs` columns `compass_uptake_<metabolite>` and `compass_secretion_<metabolite>`.

`analyze_differential_flux()` columns: `reaction`, `mean_A`, `mean_B`, `log2FC`, `statistic`, `pvalue`, `padj`.

## API Reference

### Core analysis

| Function | Location | Description |
|----------|----------|-------------|
| `run_compass()` | [core_analysis.py:133](scripts/python/core_analysis.py#L133) | Main COMPASS runner |
| `add_compass_results_to_adata()` | [core_analysis.py:324](scripts/python/core_analysis.py#L324) | Integrate into AnnData |
| `analyze_differential_flux()` | [core_analysis.py:481](scripts/python/core_analysis.py#L481) | Two-group differential flux |
| `summarize_metabolic_activity()` | [core_analysis.py:541](scripts/python/core_analysis.py#L541) | Subsystem summaries |
| `infer_subsystems()` | [core_analysis.py:571](scripts/python/core_analysis.py#L571) | Subsystem inference |

### Utilities

| Function | Location | Description |
|----------|----------|-------------|
| `check_gene_overlap()` | [utils.py:17](scripts/python/utils.py#L17) | Data/model overlap |
| `recommend_model()` | [utils.py:58](scripts/python/utils.py#L58) | Model recommendation |
| `export_compass_results()` | [utils.py:398](scripts/python/utils.py#L398) | Export results |
| `validate_compass_installation()` | [utils.py:543](scripts/python/utils.py#L543) | Installation check |

### Visualization

| Function | Location | Description |
|----------|----------|-------------|
| `plot_reaction_heatmap()` | [visualization.py:18](scripts/python/visualization.py#L18) | Reaction clustermap |
| `plot_differential_flux()` | [visualization.py:186](scripts/python/visualization.py#L186) | Volcano + bar plot |
| `plot_subsystem_activity()` | [visualization.py:262](scripts/python/visualization.py#L262) | Subsystem activity |
| `plot_compass_summary()` | [visualization.py:499](scripts/python/visualization.py#L499) | All standard plots |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ImportError: No module named 'cplex'` | CPLEX not installed | Install IBM CPLEX Python API |
| `COMPASS not found` | `compass-sc` missing | `pip install compass-sc` |
| `CPLEX Error 1014` | Demo license limit | Install full CPLEX license |
| Low gene overlap | ENSEMBL IDs / species mismatch | Convert symbols; verify model |
| `MemoryError` | Too many processes / large data | Reduce `num_processes`; use `microcluster_size` |
| Differential flux `ValueError` | Not exactly two groups | Subset labels |

## Related Skills

- [bio-single-cell-metabolism-scmetabolism-r](../bio-single-cell-metabolism-scmetabolism-r/SKILL.md) — scMetabolism (R, no CPLEX)
- [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md) — GSEApy enrichment
- [bio-single-cell-enrichment-decoupler-r](../bio-single-cell-enrichment-decoupler-r/SKILL.md) — Pathway/TF activity
- [bio-single-cell-enrichment-clusterprofiler-r](../bio-single-cell-enrichment-clusterprofiler-r/SKILL.md) — ORA/GSEA

## References

1. Wagner et al. (2021). Metabolic modeling of single cells via flux balance analysis and constraint programming. *Nature Communications* 12, 3635. https://doi.org/10.1038/s41467-021-23713-5
2. COMPASS documentation: https://yoseflab.github.io/Compass/
3. COMPASS GitHub: https://github.com/wagnerlab-berkeley/Compass
4. Thiele et al. (2013). A community-driven global reconstruction of human metabolism. *Nature Biotechnology* 31, 419-425.
