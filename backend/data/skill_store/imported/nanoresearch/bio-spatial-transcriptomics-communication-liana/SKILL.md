---
name: bio-spatial-transcriptomics-communication-liana
description: Cell-cell communication analysis using LIANA+ framework. Supports multi-method inference, spatially-informed analysis, and comprehensive visualization for both single-cell and spatial transcriptomics data.
tool_type: python
primary_tool: liana
supported_tools: [scanpy, anndata, mudata, plotnine]
languages: [python]
keywords: ["single-cell", "spatial", "cell-communication", "LIANA", "ligand-receptor", "CCC", "interaction"]
code_location: scripts/python/
version_compatibility:
  python: ">=3.9"
  liana: ">=1.7.0"
  scanpy: ">=1.10.0"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| Python | >= 3.9 | |
| liana | >= 1.7.0 | Core CCC framework |
| scanpy | >= 1.10.0 | Single-cell analysis |
| anndata | >= 0.10.0 | Data structure |
| pandas | >= 2.0.0 | Data manipulation |
| numpy | >= 1.24.0 | Numerical computing |
| plotnine | >= 0.12.0 | ggplot2-style plots |

## Installation

```bash
# Core installation
pip install liana

# Additional dependencies
pip install plotnine networkx

# For spatial analysis
pip install squidpy
```

# LIANA+ Cell-Cell Communication Skill

Comprehensive Python framework for cell-cell communication inference, integrating multiple methods and supporting both single-cell and spatial transcriptomics.

## Quick Selector

| Data Type | Analysis Goal | Go To |
|-----------|---------------|-------|
| Single-cell | Basic CCC inference | Scenario 1 |
| Single-cell | Compare multiple methods | Scenario 2 |
| Spatial (spot-based) | Spatially-informed CCC | Scenario 3 |
| Spatial (single-cell res) | Inflow scores | Scenario 4 |
| Spatial | Multi-view learning (MISTy) | Scenario 5 |
| Single-cell | Cross-condition comparison | Scenario 6 |
| Any | Extract and visualize | Scenario 7 |

### When to Use LIANA+

- Infer ligand-receptor interactions between cell types from single-cell data
- Compare communication patterns across biological conditions
- Analyze spatially-resolved cell-cell communication
- Obtain consensus predictions via rank aggregation of multiple methods
- Identify key interactions driving biological processes

---

## Scenarios

### Scenario 1: Single-Cell Basic CCC Analysis

**Goal**: Run the recommended rank aggregate analysis on single-cell data.

**Preconditions**:
- AnnData object with cell type annotations in `adata.obs['cell_type']`
- Pre-processed data (normalized, log-transformed)

```python
import scanpy as sc
import liana as ln
from scripts.python.core_analysis import run_rank_aggregate, get_top_interactions
from scripts.python.utils import validate_anndata
# NOTE: scripts.python.* are custom wrappers; ln.mt/pl/rs.* are native liana API

# Load and validate data
adata = sc.read_h5ad("annotated_data.h5ad")
validate_anndata(adata, groupby='cell_type')

# Run rank aggregate (recommended default)
# This runs CellPhoneDB, NATMI, Connectome, SingleCellSignalR internally
# and returns consensus ranks via RRA (RobustRankAggregate)
run_rank_aggregate(
    adata,
    groupby='cell_type',           # cell type annotation column
    resource_name='consensus',     # LR database: 'consensus', 'CellChatDB', 'CellPhoneDB', etc.
    expr_prop=0.1,                 # min fraction of cells expressing gene (0-1)
    min_cells=5,                   # min cells per group
    aggregate_method='rra',        # 'rra' or 'mean'
    n_perms=100,                   # permutations for significance
    seed=42,
    key_added='liana_res',         # results stored in adata.uns['liana_res']
    inplace=True
)

# Access results
liana_res = adata.uns['liana_res']
print(liana_res.head())

# Get top interactions
top20 = get_top_interactions(liana_res, n=20, by='magnitude_rank')

# Agent checkpoint:
# - liana_res should have columns: source, target, ligand, receptor,
#   magnitude_rank, specificity_rank, ligand_props, receptor_props, etc.
# - If empty, check that groupby column exists and has sufficient cells per group
```

**Key parameters**:
- `resource_name`: LR database. 'consensus' (default), 'CellChatDB', 'CellPhoneDB', etc.
- `expr_prop`: Expression proportion threshold. Default 0.1 (10% of cells). Increase for higher confidence.
- `aggregate_method`: 'rra' (default, robust) or 'mean' (simple average)
- `n_perms`: Permutations for statistical testing. 100 (default), increase to 1000 for publication

---

### Scenario 2: Single-Cell Multi-Method Comparison

**Goal**: Run and compare multiple individual CCC methods.

```python
import liana as ln
from scripts.python.core_analysis import run_individual_method

# Run individual methods (each produces different scores)
methods = ['cellphonedb', 'cellchat', 'connectome', 'natmi']
for method in methods:
    run_individual_method(
        adata,
        method=method,
        groupby='cell_type',
        resource_name='consensus',
        expr_prop=0.1,
        inplace=True,
        verbose=True
    )

# Access individual results
res_cpdb = adata.uns['liana_cellphonedb']
res_cellchat = adata.uns['liana_cellchat']

# Compare: find interactions detected by all methods
common = set(res_cpdb['interaction_key']).intersection(
    set(res_cellchat['interaction_key'])
)
print(f"Common interactions: {len(common)}")

# Agent checkpoint:
# - Each method has different scoring columns. Check res.columns for available scores.
# - cellphonedb: uses permutation p-values
# - cellchat: uses trimean aggregation
# - connectome: network-based weights
# - natmi: weighted expression product
```

**Available individual methods**:
| Method | Description | Key Score |
|--------|-------------|-----------|
| `cellphonedb` | Permutation-based statistical testing | `cellphonedb_pvalue` |
| `cellchat` | Trimean aggregation | `lr_probs` |
| `connectome` | Network-based approach | `weight_sc` |
| `natmi` | Weighted expression product | `edge_specificity` |
| `singlecellsignalr` | Pathway-informed scoring | `lr_score` |
| `geometric_mean` | Simple geometric mean | `lr_means` |
| `scseqcomm` | Scaled expression product | `score` |
| `logfc` | Log fold change | `lr_logfc` |

---

### Scenario 3: Spatial Spot-Based Bivariate Analysis

**Goal**: Analyze spatial co-expression of ligand-receptor pairs in spot-based spatial data (Visium, Visium HD).

**Preconditions**:
- Spatial coordinates in `adata.obsm['spatial']`
- Pre-computed spatial neighbor graph in `adata.obsp['spatial_connectivities']`
- Cell type annotations (from deconvolution or clustering)

```python
import liana as ln
import squidpy as sq

# Step 1: Compute spatial neighbors (prerequisite)
# For Visium (hexagonal grid)
sq.gr.spatial_neighbors(adata, coord_type="grid", n_neighs=6)

# Step 2: Run bivariate spatial analysis
# Computes spatial co-expression metrics (Moran's I, Lee's L, etc.)
# for ligand-receptor pairs across all spots
lrdata = ln.method.bivariate(
    adata,
    local_name='morans',         # local metric: 'morans', 'cosine', 'pearson', 'spearman', 'jaccard'
    global_name=['morans', 'lee'],  # global metrics to compute
    resource_name='consensus',   # LR database
    connectivity_key='spatial_connectivities',  # from sq.gr.spatial_neighbors
    n_perms=100,
    seed=1337,
    use_raw=True,  # use adata.raw if present; set False to use adata.X
    verbose=True
)

# Results structure in lrdata (returned AnnData):
# - lrdata.X              : local scores
# - lrdata.var            : global statistics
# - lrdata.layers['pvals']: permutation p-values
# - lrdata.layers['cats'] : co-expression direction (2=both up, 0=mixed, -2=both down)

# Step 3: Summarize global interactions by cell type
ln.mt.compute_global_specificity(
    lrdata,
    groupby='cell_type',
    use_raw=True  # use adata.raw if present; set False to use adata.X,
    verbose=True,
    uns_key='global_interactions'  # results in lrdata.uns['global_interactions']
)

global_res = lrdata.uns['global_interactions']

# Agent checkpoint:
# - bivariate() RETURNS a new AnnData (lrdata), does NOT modify adata in place
# - MUST run spatial_neighbors BEFORE bivariate
# - For Visium: coord_type="grid", n_neighs=6
# - For non-grid (Xenium/CosMx): coord_type="generic", delaunay=True
# - Check lrdata.var for global metrics; lrdata.X for local spot-level scores
```

**Key parameters**:
- `local_name`: Local metric. `'morans'` (default), `'cosine'`, `'pearson'`, `'spearman'`, `'jaccard'`
- `global_name`: Global metrics list. `['morans', 'lee']` or `None`
- `connectivity_key`: Key in `adata.obsp` with spatial connectivities (pre-computed)

---

### Scenario 4: Spatial Single-Cell Resolution Inflow

**Goal**: Compute inflow scores for single-cell resolution spatial data (Xenium, CosMx, MERFISH).

**Preconditions**:
- Single-cell resolution spatial data
- Spatial coordinates in `adata.obsm['spatial']`
- Cell type annotations
- Pre-computed spatial neighbor graph in `adata.obsp['spatial_connectivities']`

```python
import liana as ln

# Step 1: Compute spatial neighbors (prerequisite)
# For single-cell resolution data, use Delaunay triangulation
ln.ut.spatial_neighbors(
    adata,
    bandwidth=50,              # distance threshold in coordinate units
    spatial_key='spatial'
)

# Step 2: Load resource
resource = ln.rs.select_resource('consensus')

# Step 3: Compute inflow scores
# Inflow measures how much signaling a cell type receives from spatial neighbors
lrdata = ln.mt.inflow(
    adata,
    groupby='cell_type',
    resource=resource,         # pass DataFrame (not resource_name string)
    use_raw=False
)

# lrdata is a NEW AnnData with inflow scores in its layers/uns
# lrdata.shape shows (n_cells, n_LR_pairs)

# Step 4: Compute global specificity summary
ln.mt.compute_global_specificity(
    lrdata,
    groupby='cell_type',
    use_raw=False,
    verbose=True,
    uns_key='global_interactions'
)

inflow_res = lrdata.uns['global_interactions']
# Columns include: source, target, ligand_complex, receptor_complex, lr_mean, pval

# Visualize
ln.pl.dotplot(
    lrdata,
    colour='lr_mean',
    size='pval',
    uns_key='global_interactions',
    inverse_size=True
)

# Agent checkpoint:
# - inflow() RETURNS a new AnnData (lrdata), does NOT modify adata in place
# - MUST run spatial_neighbors BEFORE inflow
# - resource parameter takes a DataFrame (use ln.rs.select_resource)
# - For large datasets (>10K cells), spatial_neighbors bandwidth may need tuning
```

---

### Scenario 5: MISTy Multi-View Spatial Analysis

**Goal**: Use MISTy (Multi-view Intercellular Spatial Modeling) to identify spatial interaction patterns and predictor importance.

**Preconditions**:
- Spatial data with coordinates in `adata.obsm['spatial']`
- Cell type annotations

```python
import liana as ln

# Step 1: Create MISTy data object
misty = ln.method.lrMistyData(
    adata,
    resource_name='consensus',   # LR database
    spatial_key='spatial',       # key in adata.obsm
    bandwidth=100,               # spatial neighborhood radius
    kernel='misty_rbf',
    verbose=True
)

# Step 2: Fit MISTy models
misty = misty.fit(n_neighbors=10)  # 10 nearest neighbors for local view

# Step 3: Extract and visualize results
# Target metrics: how well each view predicts each target
misty.plot_target_metrics()

# Interaction importances: which ligand-receptor pairs are most predictive
misty.plot_interactions()

# Contributions: relative importance of intra vs juxta vs paraview
misty.plot_contribution()

# Agent checkpoint:
# - MISTy is computationally intensive. For >5000 spots, consider subsetting.
# - bandwidth should capture biologically relevant neighborhoods
# - Check plot_target_metrics() for views with high R2 (well-predicted targets)
```

---

### Scenario 6: Cross-Condition Comparison

**Goal**: Compare cell-cell communication across biological conditions (e.g., disease vs control).

**Approach 1: Run per-condition and compare**
```python
import liana as ln
import pandas as pd
from scripts.python.core_analysis import run_rank_aggregate

conditions = {}
for cond_name in ['control', 'disease']:
    # Subset to condition
    adata_cond = adata[adata.obs['condition'] == cond_name].copy()
    run_rank_aggregate(adata_cond, groupby='cell_type', inplace=True)
    conditions[cond_name] = adata_cond.uns['liana_res']

# Compare: find interactions present in both conditions
common = set(conditions['control']['interaction_key']).intersection(
    set(conditions['disease']['interaction_key'])
)

# Find condition-specific interactions
disease_specific = set(conditions['disease']['interaction_key']) - common
```

**Approach 2: Use by_sample for within-dataset comparison**
```python
import liana as ln

# If adata contains multiple samples with a sample key
ln.mt.rank_aggregate.by_sample(
    adata,
    groupby='cell_type',
    sample_key='sample_id',      # column in adata.obs
    resource_name='consensus',   # default; use 'CellChatDB' for CellChat
    expr_prop=0.1,
    inplace=True,
    key_added='liana_by_sample'
)

# Results contain a 'sample' column for per-sample interactions
by_sample_res = adata.uns['liana_by_sample']

# Agent checkpoint:
# - Ensure each condition/sample has sufficient cells per cell type (>5)
# - For by_sample, the 'sample_key' must exist in adata.obs
# - Cross-condition comparison is most reliable for top-ranked interactions
```

---

### Scenario 7: Extract Results and Visualize

**Goal**: Extract communication results and create visualizations using native liana-py plotting.

**Extract results**:
```python
# Basic access
liana_res = adata.uns['liana_res']

# Key columns in liana_res:
# - source, target: cell types
# - ligand, receptor: gene symbols
# - magnitude_rank: overall interaction strength (0-1, lower = stronger)
# - specificity_rank: cell-type specificity (0-1, lower = more specific)
# - ligand_props, receptor_props: fraction of cells expressing the gene
# - interaction_key: unique identifier (source|target|ligand|receptor)

# Filter by source-target pair
macro_to_t = liana_res[
    (liana_res['source'] == 'Macrophage') &
    (liana_res['target'] == 'T_cell')
]

# Filter by significance (top ranks)
significant = liana_res[liana_res['magnitude_rank'] <= 0.05]

# Summarize by cell pair
from scripts.python.core_analysis import summarize_by_cell_pair
pair_summary = summarize_by_cell_pair(liana_res, agg_func='count')
```

**Visualize** (call native liana.plotting functions directly):
```python
import liana as ln

# Dot plot (primary visualization)
ln.pl.dotplot(
    adata,
    colour='magnitude_rank',     # dot color: interaction strength
    size='specificity_rank',     # dot size: specificity
    top_n=30,                    # show top 30 interactions
    orderby='magnitude_rank',
    orderby_ascending=True
)

# Tile plot (aggregate view)
# NOTE: tileplot requires fill/label columns for BOTH ligand & receptor.
# Best used with single-method results (e.g., cellphonedb). For rank_aggregate,
# only 'means' and 'props' pairs are reliably available; prefer dotplot instead.
ln.pl.tileplot(
    adata,
    fill='means',            # ligand_means & receptor_means
    label='props',           # ligand_props & receptor_props
    top_n=20,
    orderby='magnitude_rank',
    orderby_ascending=True
)

# Circle plot (network view)
# Requires groupby (cell type column used during analysis)
ln.pl.circle_plot(
    adata,
    groupby='cell_type',
    score_key='magnitude_rank',
    inverse_score=True,          # -log10 transform for rank values
    top_n=20
)

# Multi-sample dot plot
ln.pl.dotplot_by_sample(
    adata,
    sample_key='condition',
    colour='magnitude_rank',
    size='specificity_rank'
)

# Spatial connectivity plot (shows spatial neighbor weights, NOT CCC results)
# Use this to verify spatial neighborhood structure before spatial CCC
ln.pl.connectivity(adata, idx=0, spatial_key='spatial')
```

**Export results**:
```python
from scripts.python.core_analysis import export_results

export_results(liana_res, 'liana_results.csv', format='csv')
export_results(liana_res, 'liana_results.tsv', format='tsv')

# Save full AnnData with results
adata.write_h5ad('adata_with_liana.h5ad')
```

---

## Resource Selection

LIANA+ includes curated ligand-receptor databases. Run `ln.rs.show_resources()` to see all available resources in your installation.

Commonly used resources:

| Resource | Best For |
|----------|----------|
| `consensus` | Default. Curated human LR pairs from multiple sources |
| `CellChatDB` | Mammalian CCC, well-curated |
| `CellPhoneDB` | Human, statistical validation |
| `MouseConsensus` | Murine homolog of consensus resource |

```python
import liana as ln

# List all available resources
ln.rs.show_resources()

# Load a specific resource (returns DataFrame)
resource = ln.rs.select_resource('consensus')

# Check resource coverage in your data
genes_in_data = set(adata.var_names)
resource_genes = set(resource['ligand']) | set(resource['receptor'])
coverage = len(resource_genes & genes_in_data) / len(resource_genes)
print(f"Resource coverage: {coverage:.1%}")
```

---

## Best Practices

### Agent Rules

1. **Always validate data first**: Use `validate_anndata(adata, groupby='cell_type')` before analysis
2. **Use rank_aggregate as default**: For most analyses, `run_rank_aggregate()` is the recommended entry point
3. **Check result columns before filtering**: Different methods produce different column names. Inspect `liana_res.columns` first
4. **For spatial data, choose the right tool**:
   - Spot-based (Visium) → `ln.method.bivariate()` + `ln.mt.compute_global_specificity()` (Scenario 3)
   - Single-cell resolution → `ln.mt.inflow()` + `ln.mt.compute_global_specificity()` (Scenario 4)
   - Complex spatial patterns → `ln.method.lrMistyData()` (Scenario 5)
5. **Pre-compute spatial neighbors before spatial analysis**: `sq.gr.spatial_neighbors()` for Visium, `ln.ut.spatial_neighbors()` for single-cell resolution
6. **Visualize with native functions**: Use `ln.pl.dotplot()`, `ln.pl.tileplot()`, etc. directly. Do not wrap.
7. **Distinguish wrappers from native API**: `scripts.python.core_analysis.*` and `scripts.python.utils.*` are custom wrappers provided by this skill. All `ln.mt.*`, `ln.pl.*`, `ln.method.*`, and `ln.rs.*` are native liana-py API. Do not invent wrapper names.

### Parameter Guidelines

| Parameter | Default | When to Adjust |
|-----------|---------|----------------|
| `expr_prop` | 0.1 | Increase to 0.2 for high-confidence only; decrease to 0.05 for exploratory |
| `n_perms` | 100 | Increase to 1000 for publication; 10 for quick testing |
| `min_cells` | 5 | Increase if cell type annotations are noisy |
| `bandwidth` | N/A (see spatial neighbors) | Set via `sq.gr.spatial_neighbors` or `ln.ut.spatial_neighbors` before analysis |

### Common Pitfalls

**Empty results:**
- Check `groupby` column exists in `adata.obs`
- Ensure each cell type has >= `min_cells` cells
- Verify `resource_name` is valid (`ln.rs.show_resources()`)
- Check gene name matching (e.g., human vs mouse gene symbols)

**Spatial analysis errors:**
- `bivariate` and `inflow` require pre-computed `adata.obsp['spatial_connectivities']`
- For Visium: run `sq.gr.spatial_neighbors(adata, coord_type="grid", n_neighs=6)` first
- For single-cell resolution: run `ln.ut.spatial_neighbors(adata, bandwidth=50)` first
- Both `bivariate()` and `inflow()` RETURN new AnnData objects; they do NOT modify in place

**Inconsistent method comparisons:**
- Different methods have different score columns. Always check `liana_res.columns`
- `magnitude_rank` and `specificity_rank` are only available from `rank_aggregate`

**Memory issues with large datasets:**
- For >20K cells, reduce `n_perms` or use individual methods instead of rank_aggregate
- For spatial data, subset to regions of interest before MISTy analysis

---

## Output Description

### rank_aggregate Output Columns

| Column | Description |
|--------|-------------|
| `source` | Source cell type |
| `target` | Target cell type |
| `ligand` | Ligand gene symbol |
| `receptor` | Receptor gene symbol |
| `magnitude_rank` | Consensus magnitude rank (0-1, lower = stronger) |
| `specificity_rank` | Consensus specificity rank (0-1, lower = more specific) |
| `ligand_props` | Fraction of source cells expressing ligand |
| `receptor_props` | Fraction of target cells expressing receptor |
| `interaction_key` | Unique identifier string |

### Individual Method Columns

Each method adds its own score columns (e.g., `cellphonedb_pvalue`, `lr_means`, `edge_specificity`). Check `liana_res.columns` after running.

### Export Checklist

Agent confirms completion by checking these outputs exist:
- [ ] `adata.uns['liana_res']` DataFrame with interaction results
- [ ] CSV/TSV export file with results
- [ ] Visualization plots (PDF/PNG) from `ln.pl.*` functions

---

## Related Skills

- [bio-spatial-transcriptomics-communication-cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/SKILL.md) - CellChat R implementation (spatial-focused)
- [bio-spatial-transcriptomics-communication-commot](../bio-spatial-transcriptomics-communication-commot/SKILL.md) - COMMOT spatial CCC
- [bio-single-cell-communication-cellchat-r](../bio-single-cell-communication-cellchat-r/SKILL.md) - CellChat single-cell

---

## References

1. Dimitrov D., et al. (2024). LIANA+ provides an all-in-one framework for cell-cell communication inference. *Nature Cell Biology*. https://doi.org/10.1038/s41556-024-01469-w
2. Dimitrov D., et al. (2022). Comparison of methods and resources for cell-cell communication inference from single-cell RNA-Seq data. *Nature Communications*, 13, 3224.
3. LIANA+ documentation: https://liana-py.readthedocs.io/
4. LIANA+ GitHub: https://github.com/saezlab/liana-py
