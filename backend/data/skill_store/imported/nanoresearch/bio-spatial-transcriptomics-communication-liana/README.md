# LIANA+ Cell-Cell Communication Analysis Skill

Python-based skill for cell-cell communication (CCC) inference using LIANA+. Integrates multiple methods (CellPhoneDB, NATMI, CellChat, Connectome, etc.) and supports both single-cell and spatial transcriptomics.

## Features

- **Multi-Method Consensus**: Rank aggregation across CellPhoneDB, NATMI, CellChat, Connectome, SingleCellSignalR
- **Spatial CCC**: Bivariate spatial analysis (Visium), inflow scores (Xenium/CosMx), MISTy multi-view learning
- **Cross-Condition Comparison**: Per-condition analysis and by-sample aggregation
- **Native Visualization**: Direct calls to `liana.plotting` (dotplot, tileplot, circle plot, connectivity)

## Quick Start

```python
import scanpy as sc
import liana as ln

# Load data
adata = sc.read_h5ad("annotated_data.h5ad")

# Run rank aggregate (recommended default)
ln.mt.rank_aggregate(adata, groupby='cell_type', resource_name='consensus')

# Access results
liana_res = adata.uns['liana_res']

# Visualize
ln.pl.dotplot(adata, colour='magnitude_rank', size='specificity_rank')
```

## File Structure

```
bio-spatial-transcriptomics-communication-liana/
├── SKILL.md                      # Agent operation document (scenario-driven)
├── README.md                     # This file
├── usage-guide.md                # Detailed step-by-step guide
├── scripts/
│   └── python/
│       ├── core_analysis.py      # Analysis wrappers (rank_aggregate, individual methods)
│       └── utils.py              # Validation, filtering, helpers
├── tests/
│   └── test_liana.py             # Unit tests
└── examples/
    ├── minimal_example.py        # Basic workflow
    └── advanced_example.py       # Multi-method, spatial, cross-condition
```

## Requirements

- Python >= 3.9
- liana >= 1.7.0
- scanpy >= 1.10.0
- anndata >= 0.10.0
- pandas >= 2.0
- numpy >= 1.24
- plotnine >= 0.12 (for native liana plots)
- squidpy >= 1.4 (for spatial analysis)

## Installation

```bash
# Core
pip install liana

# Additional dependencies
pip install plotnine

# For spatial analysis
pip install squidpy
```

## Core Wrappers

### Analysis

| Function | Purpose | Native API |
|----------|---------|------------|
| `run_rank_aggregate()` | Multi-method consensus | `ln.mt.rank_aggregate()` |
| `run_individual_method()` | Run specific CCC method | `ln.mt.{method}()` |
| `get_top_interactions()` | Get top N results | -- |
| `summarize_by_cell_pair()` | Summary matrix by cell pair | -- |
| `export_results()` | Export to CSV/TSV/Excel | -- |

### Utilities

| Function | Purpose |
|----------|---------|
| `validate_anndata()` | Validate AnnData before analysis |
| `filter_cell_types()` | Filter by min cells/genes |
| `subset_cell_types()` | Subset to specific cell types |
| `get_interaction_matrix()` | Convert results to source x target matrix |

### Visualization (Native)

Call `liana.plotting` functions directly:

| Function | Purpose |
|----------|---------|
| `ln.pl.dotplot()` | Primary dot plot |
| `ln.pl.tileplot()` | Aggregate tile view |
| `ln.pl.circle_plot()` | Network circle plot |
| `ln.pl.connectivity()` | Spatial neighbor weights (not CCC results) |
| `ln.pl.dotplot_by_sample()` | Multi-condition dot plot |

## Workflow Scenarios

### 1. Basic Single-Cell CCC

```python
import liana as ln
from scripts.python.core_analysis import run_rank_aggregate, get_top_interactions
from scripts.python.utils import validate_anndata

validate_anndata(adata, groupby='cell_type')
run_rank_aggregate(adata, groupby='cell_type', resource_name='consensus')
top20 = get_top_interactions(adata.uns['liana_res'], n=20)
```

### 2. Multi-Method Comparison

```python
from scripts.python.core_analysis import run_individual_method

for method in ['cellphonedb', 'cellchat', 'connectome', 'natmi']:
    run_individual_method(adata, method=method, groupby='cell_type')
```

### 3. Spatial (Visium) — Bivariate

```python
import squidpy as sq
import liana as ln

sq.gr.spatial_neighbors(adata, coord_type="grid", n_neighs=6)
lrdata = ln.method.bivariate(
    adata, local_name='morans', global_name=['morans', 'lee'],
    resource_name='consensus'
)
ln.mt.compute_global_specificity(lrdata, groupby='cell_type')
```

### 4. Spatial (Xenium) — Inflow

```python
import liana as ln

ln.ut.spatial_neighbors(adata, bandwidth=50)
resource = ln.rs.select_resource('consensus')
lrdata = ln.mt.inflow(adata, groupby='cell_type', resource=resource)
ln.mt.compute_global_specificity(lrdata, groupby='cell_type')
```

### 5. Cross-Condition Comparison

```python
import liana as ln

ln.mt.rank_aggregate.by_sample(
    adata, groupby='cell_type', sample_key='condition',
    resource_name='consensus'
)
```

## Available Methods

| Method | Key Score | Description |
|--------|-----------|-------------|
| `rank_aggregate` | `magnitude_rank`, `specificity_rank` | Consensus (recommended) |
| `cellphonedb` | `cellphonedb_pvalue` | Permutation-based stats |
| `cellchat` | `lr_probs` | Trimean aggregation |
| `connectome` | `weight_sc` | Network-based |
| `natmi` | `edge_specificity` | Weighted expression |
| `singlecellsignalr` | `lr_score` | Pathway-informed |
| `geometric_mean` | `lr_means` | Simple geometric mean |
| `scseqcomm` | `score` | Scaled expression |
| `logfc` | `lr_logfc` | Log fold change |

## Available Resources

Run `ln.rs.show_resources()` to see all available resources.

| Resource | Best For |
|----------|----------|
| `consensus` | Default. Curated human LR pairs from multiple sources |
| `CellChatDB` | Mammalian CCC, well-curated |
| `CellPhoneDB` | Human, statistical validation |
| `MouseConsensus` | Murine homolog of consensus resource |

## Output Columns

| Column | Description |
|--------|-------------|
| `source` | Source cell type |
| `target` | Target cell type |
| `ligand` | Ligand gene symbol |
| `receptor` | Receptor gene symbol |
| `magnitude_rank` | Consensus magnitude (lower = stronger) |
| `specificity_rank` | Cell-type specificity (lower = more specific) |
| `ligand_props` | Fraction of source cells expressing ligand |
| `receptor_props` | Fraction of target cells expressing receptor |

## References

1. Dimitrov D., et al. (2024). LIANA+ provides an all-in-one framework for cell-cell communication inference. *Nature Cell Biology*. https://doi.org/10.1038/s41556-024-01469-w
2. Dimitrov D., et al. (2022). Comparison of methods and resources for cell-cell communication inference from single-cell RNA-Seq data. *Nature Communications*, 13, 3224.
3. LIANA+ documentation: https://liana-py.readthedocs.io/
4. LIANA+ GitHub: https://github.com/saezlab/liana-py
