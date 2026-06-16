---
name: bio-spatial-transcriptomics-communication-commot
description: Spatial cell-cell communication analysis using optimal transport (COMMOT)
tool_type: python
primary_tool: commot
supported_tools: [scanpy, pandas, numpy, matplotlib]
languages: [python]
keywords: ["spatial", "communication", "COMMOT", "optimal-transport", "ligand-receptor", "direction", "cell-cell-communication", "spatial-transcriptomics"]
code_location: scripts/python/
version_compatibility:
  python: ">=3.9"
  commot: "0.0.3"
  scanpy: ">=1.9.0"
---

## Version Compatibility & Installation

| Component | Version | Notes |
|-----------|---------|-------|
| Python | ≥ 3.9 | |
| COMMOT | 0.0.3 | Latest PyPI release |
| scanpy | ≥ 1.9.0 | |
| anndata | ≥ 0.8.0 | |
| numpy | < 2.0 | ⚠️ COMMOT 0.0.3 uses `np.Inf` removed in NumPy 2.0 |

```bash
# Install COMMOT
pip install commot

# Optional: for tradeSeq DEG analysis
pip install commot[tradeSeq]

# Core dependencies
pip install scanpy anndata pandas numpy matplotlib seaborn
```

> **⚠️ NumPy 2.0 incompatibility**: COMMOT 0.0.3 uses `np.Inf` which was removed in NumPy 2.0. If you encounter `AttributeError: 'np.Inf' was removed`, downgrade numpy: `pip install "numpy<2.0"`.

---

## Skill Overview

**Optimal transport-based spatial cell-cell communication analysis** with distance constraints and directionality inference. COMMOT computes per-spot sender/receiver scores and spot-to-spot communication matrices, constrained by physical distance.

### When to Use COMMOT

- **Spatial transcriptomics data** with physical coordinates (Visium, MERFISH, Xenium, Slide-seq)
- Need **distance-aware** communication (not just expression correlation)
- Want to **infer communication direction** (vector fields, streamlines)
- **Heteromeric receptor complexes** are important (e.g., TGFBR1_TGFBR2)
- Prefer **optimal transport** over correlation-based methods

### When NOT to Use COMMOT

- **Non-spatial scRNA-seq** without coordinates (use CellChat, CellPhoneDB, LIANA instead)
- **No spatial coordinates** available
- Very large datasets with limited memory
- Only need simple LR expression correlation
- Running on **NumPy ≥ 2.0** without patching (COMMOT 0.0.3 incompatible)

---

## Core Workflow

> **Precondition**: AnnData with `adata.obsm['spatial']` (N × 2 or N × 3) in **microns**. Raw counts or normalized data accepted.

### Step 1 — Prepare Data

**Input**: `AnnData` with spatial coordinates  
**Output**: `AnnData` filtered, normalized, log-transformed

```python
from scripts.python.core_analysis import prepare_data, check_spatial_units

adata = prepare_data(
    adata,
    spatial_key='spatial',    # key in adata.obsm
    min_counts=100,           # filter low-quality spots
    normalize=True,           # total-count normalization
    log1p=True,               # log1p transform
)

# Verify coordinates are in microns (critical!)
check_spatial_units(adata, spatial_key='spatial')
```

| Parameter | Type | Default | What It Does | When to Change |
|-----------|------|---------|--------------|----------------|
| `spatial_key` | str | `'spatial'` | Key for coordinates in `obsm` | Only if you use a different key |
| `min_counts` | int | 100 | Min total counts per spot | Lower for low-coverage data; higher for QC |
| `normalize` | bool | `True` | `sc.pp.normalize_total()` | Keep `True` unless already normalized |
| `log1p` | bool | `True` | `sc.pp.log1p()` | Keep `True` unless already log-transformed |

### Step 2 — Load Ligand-Receptor Database

**Input**: `AnnData` (to check which genes are present)  
**Output**: `pd.DataFrame` with LR pairs

```python
from scripts.python.core_analysis import get_lr_database, filter_lr_database

# Built-in CellChat database
df_lr = get_lr_database(
    database='CellChat',              # or 'CellPhoneDB_v4.0'
    species='human',                  # 'human', 'mouse', 'zebrafish' (CellChat only)
    signaling_type='Secreted Signaling',  # or 'Cell-Cell Contact', 'ECM-Receptor'
)

# Filter to pairs actually expressed in your data
df_lr = filter_lr_database(
    df_lr,
    adata,
    min_cell_pct=0.05,        # expressed in ≥ 5% of cells
    heteromeric=True,
)
```

| Parameter | Type | Default | What It Does |
|-----------|------|---------|--------------|
| `database` | str | `'CellChat'` | `'CellChat'` or `'CellPhoneDB_v4.0'` |
| `species` | str | `'human'` | `'human'`, `'mouse'`, `'zebrafish'` |
| `signaling_type` | str | `'Secreted Signaling'` | `'Secreted Signaling'`, `'Cell-Cell Contact'`, `'ECM-Receptor'`, or `None` for all |
| `min_cell_pct` | float | 0.05 | Min fraction of cells expressing both ligand and receptor |

#### Custom Database

```python
from scripts.python.core_analysis import create_custom_lr_database

df_lr = create_custom_lr_database(
    ligands=['TGFB1', 'IL6'],
    receptors=['TGFBR1_TGFBR2', 'IL6R_IL6ST'],  # use '_' for heteromeric
    pathways=['TGFb', 'IL6'],
)
```

### Step 3 — Run COMMOT

**Input**: `AnnData` + `pd.DataFrame` of LR pairs  
**Output**: `AnnData` with results in `obsm` / `obsp` / `uns`

```python
from scripts.python.core_analysis import run_commot, run_commot_database

# Method A: Run with your own LR database
run_commot(
    adata,
    df_ligrec=df_lr,
    database_name='cellchat',       # REQUIRED — namespaces all results
    distance_threshold=200.0,       # max communication distance in microns
    heteromeric=True,
    heteromeric_rule='min',         # 'min' or 'ave' for complex quantification
    heteromeric_delimiter='_',
    cost_type='euc',                # 'euc' or 'euc_square'
    cot_eps_p=0.1,                  # entropy regularization
    cot_rho=10.0,                   # marginal relaxation
    pathway_sum=True,               # sum communication by pathway
)

# Method B: One-liner with built-in database
adata = run_commot_database(
    adata,
    database='CellChat',
    species='human',
    signaling_type='Secreted Signaling',
    filter_pairs=True,
    min_cell_pct=0.05,
    distance_threshold=200.0,
)
```

| Parameter | Type | Default | What It Does | When to Change |
|-----------|------|---------|--------------|----------------|
| `database_name` | str | **required** | Namespaces all results (e.g., `'cellchat'`, `'custom'`) | Use a short lowercase identifier |
| `distance_threshold` | float | 200.0 | Max communication distance (μm) | See platform table below |
| `heteromeric` | bool | `True` | Handle multi-subunit complexes | Keep `True` for accuracy |
| `heteromeric_rule` | str | `'min'` | `'min'` = all subunits required; `'ave'` = average | `'min'` for strict complexes |
| `cost_type` | str | `'euc'` | Cost function | `'euc'` for most cases |
| `cot_eps_p` | float | 0.1 | OT entropy regularization | Higher = smoother solution |
| `cot_rho` | float | 10.0 | OT marginal relaxation | Higher = more relaxed constraints |
| `pathway_sum` | bool | `True` | Aggregate by pathway | Keep `True` for pathway-level analysis |

#### Platform-Specific Distance Thresholds

| Platform | Spot Size | Recommended `distance_threshold` | Rationale |
|----------|-----------|----------------------------------|-----------|
| Visium (55 μm) | ~55 μm | 200–500 μm | ~4–9 spot diameters |
| Visium HD | ~2 μm | 50–100 μm | Higher resolution |
| Xenium | ~0.5 μm | 30–100 μm | Subcellular resolution |
| MERFISH | ~1 μm | 50–100 μm | Single-cell resolution |
| Slide-seq | ~10 μm | 100–200 μm | Puck-based |

### Step 4 — Access Results

**Input**: `AnnData` after `run_commot()`  
**Output**: Extracted matrices / DataFrames

```python
# Key pattern: all results use 'commot-{database_name}-...'

db = 'cellchat'  # must match the database_name used in run_commot()

# Sender/receiver summaries per spot (DataFrames)
sender_df = adata.obsm[f'commot-{db}-sum-sender']
receiver_df = adata.obsm[f'commot-{db}-sum-receiver']

# Individual LR pair communication matrix (sparse, n_spots × n_spots)
comm_mat = adata.obsp[f'commot-{db}-TGFB1-TGFBR1_TGFBR2']

# Total communication across all pairs
comm_total = adata.obsp[f'commot-{db}-total-total']

# Analysis metadata
info = adata.uns[f'commot-{db}-info']

# Get top LR pairs by total strength
from scripts.python.core_analysis import get_top_lr_pairs
df_top = get_top_lr_pairs(adata, n=10, database_name=db)

# Get communication matrix for a specific pair
from scripts.python.core_analysis import get_communication_matrix
mat = get_communication_matrix(adata, 'TGFB1-TGFBR1_TGFBR2', database_name=db)
```

### Step 5 — Infer Direction & Visualize

**Input**: `AnnData` with COMMOT results  
**Output**: Plots (matplotlib axes/figures)

```python
from scripts.python.core_analysis import infer_communication_direction
from scripts.python.visualization import (
    plot_communication_strength,
    plot_communication_direction,
    plot_lr_expression,
    plot_cluster_communication_network,
    plot_cluster_communication_dotplot,
)

db = 'cellchat'

# --- Communication strength map ---
plot_communication_strength(
    adata,
    lr_pair='TGFB1-TGFBR1_TGFBR2',
    database_name=db,
    summary='receiver',
    cmap='coolwarm',
)

# --- Communication direction (vector field) ---
# Must infer direction BEFORE plotting
infer_communication_direction(
    adata,
    database_name=db,
    pathway_name='TGFb',           # or lr_pair=('TGFB1', 'TGFBR1_TGFBR2')
    k=5,
)

plot_communication_direction(
    adata,
    database_name=db,
    pathway_name='TGFb',
    plot_method='stream',          # 'cell', 'grid', or 'stream'
    scale=1.0,
)

# --- Ligand & receptor expression side by side ---
plot_lr_expression(adata, ligand='TGFB1', receptor='TGFBR1')

# --- Cluster-level communication ---
from scripts.python.core_analysis import cluster_communication

comm_matrix = cluster_communication(
    adata,
    cluster_key='leiden',          # mapped to native 'clustering'
    database_name=db,
    pathway_name='TGFb',
)

plot_cluster_communication_network(
    adata,
    database_name=db,
    cluster_key='leiden',
)

plot_cluster_communication_dotplot(
    adata,
    database_name=db,
    cluster_key='leiden',
    pathway_name='TGFb',
)
```

### Step 6 — Export Results

```python
from scripts.python.core_analysis import export_results

export_results(
    adata,
    output_dir='./commot_results',
    database_name='cellchat',
    include_matrices=False,  # Set True to export large sparse matrices
)

# Save full AnnData
adata.write_h5ad('adata_commot.h5ad')
```

---

## Complete Pipeline

Copy-pasteable single script for a full COMMOT workflow:

```python
from scripts.python.core_analysis import (
    prepare_data, get_lr_database, filter_lr_database,
    run_commot, infer_communication_direction, cluster_communication,
    get_top_lr_pairs, export_results,
)
from scripts.python.visualization import (
    plot_communication_strength, plot_communication_direction,
    plot_cluster_communication_network, plot_top_lr_pairs,
)

# 1. Prepare
adata = prepare_data(adata, min_counts=100)

# 2. Database
df_lr = get_lr_database('CellChat', 'human', 'Secreted Signaling')
df_lr = filter_lr_database(df_lr, adata, min_cell_pct=0.05)

# 3. Run
run_commot(adata, df_lr, database_name='cellchat', distance_threshold=250.0)

# 4. Direction
infer_communication_direction(adata, database_name='cellchat', pathway_name='TGFb')

# 5. Visualize
plot_communication_strength(adata, 'TGFB1-TGFBR1_TGFBR2', database_name='cellchat')
plot_communication_direction(adata, database_name='cellchat', pathway_name='TGFb')

# 6. Cluster-level
cluster_communication(adata, cluster_key='leiden', database_name='cellchat')
plot_cluster_communication_network(adata, database_name='cellchat', cluster_key='leiden')

# 7. Export
export_results(adata, './commot_results', database_name='cellchat')
adata.write_h5ad('adata_commot.h5ad')
```

---

## Skill-Provided Functions

### Main Analysis

| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `run_commot()` | Run `spatial_communication()` with validated inputs | Validates `spatial` exists; maps `distance_threshold` → `dis_thr` |
| `run_commot_database()` | One-liner with built-in DB | Loads DB, filters, runs, stores metadata |

### Database

| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `get_lr_database()` | Load CellChat/CellPhoneDB | Wraps `pp.ligand_receptor_database()` |
| `filter_lr_database()` | Filter by expression | Wraps `pp.filter_lr_database()` |
| `create_custom_lr_database()` | Custom LR pairs | Pure Python helper; no COMMOT dependency |

### Downstream Analysis

| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `infer_communication_direction()` | Compute direction vectors | Maps wrapper params to native `database_name`/`pathway_name`/`lr_pair` |
| `cluster_communication()` | Cluster-level summary | Maps `cluster_key` → native `clustering`; auto-extracts result matrix |
| `detect_communication_deg()` | tradeSeq DEG analysis | Validates tradeSeq dependencies; passes correct `database_name` |
| `communication_spatial_autocorrelation()` | Spatial autocorrelation | Auto-discovers `keys` from `database_name` if not provided |

### Result Access

| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `get_communication_matrix()` | Get sparse matrix for one LR pair | Correct key pattern lookup with helpful error |
| `get_communication_summary()` | Get sender/receiver DataFrame | Correct key pattern lookup |
| `get_top_lr_pairs()` | Top N pairs by strength | **Aligns sender/receiver by pair name**; strips `s-`/`r-` prefixes |
| `export_results()` | Export CSV + matrices | Handles missing data gracefully; Seurat-style file organization |

### Visualization

| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `plot_communication_strength()` | Spatial strength map | Manual matplotlib scatter (no squidpy dependency); correct key lookup |
| `plot_communication_direction()` | Vector field plot | Auto-computes direction if missing; maps wrapper params to native |
| `plot_lr_expression()` | Ligand + receptor expression | **No squidpy dependency**; manual matplotlib scatter |
| `plot_cluster_communication_network()` | Network diagram | Auto-constructs `uns_names` from `database_name`/`cluster_key` |
| `plot_cluster_communication_dotplot()` | Dot plot | Maps `cluster_key` → native `clustering` |
| `plot_cluster_communication_chord()` | Chord diagram | Maps `cluster_key` → native `clustering` |
| `plot_communication_heatmap()` | Heatmap across spots | Samples to 500 cells if too many |
| `plot_top_lr_pairs()` | Bar chart | Handles missing sender/receiver gracefully |
| `plot_multiple_lr_pairs()` | Grid of plots | Uses `create_figure_grid()` with error fallback per subplot |
| `plot_communication_summary_by_cluster()` | Box plot by cluster | Sender/receiver side-by-side |
| `plot_communication_comparison()` | Multi-sample comparison | Compare same LR pair across conditions |

---

## Official API — Agents Often Miss These

### Native COMMOT Functions (Direct from Package)

```python
# Preprocessing
commot.pp.ligand_receptor_database(database, species, signaling_type)
commot.pp.filter_lr_database(df_ligrec, adata, heteromeric, ...)

# Core analysis
commot.tl.spatial_communication(
    adata, database_name, df_ligrec,
    dis_thr, heteromeric, heteromeric_rule,
    cost_type, cot_eps_p, cot_rho, pathway_sum, copy
)

# Direction inference
commot.tl.communication_direction(
    adata, database_name, pathway_name, lr_pair, k, copy
)

# Cluster communication
commot.tl.cluster_communication(
    adata, database_name, pathway_name, lr_pair,
    clustering, n_permutations, copy
)

# Plotting
commot.pl.plot_cell_communication(
    adata, database_name, pathway_name, lr_pair,
    plot_method, background, clustering, summary, ...
)
commot.pl.plot_cluster_communication_network(
    adata, uns_names, clustering, quantile_cutoff, ...
)
commot.pl.plot_cluster_communication_dotplot(
    adata, database_name, pathway_name, clustering, keys, ...
)
```

### Native Parameter Names That Differ from Wrappers

| Wrapper Param | Native Param | Notes |
|---------------|-------------|-------|
| `distance_threshold` | `dis_thr` | `run_commot()` maps this |
| `cluster_key` | `clustering` | `cluster_communication()` and all cluster plot wrappers map this |
| `database_name` | — | Native uses `database_name` directly; wrappers use same name |

### Result Key Patterns (Critical)

All COMMOT results are namespaced by `database_name`:

| What | Key Pattern | Example |
|------|-------------|---------|
| Sender summary | `obsm['commot-{db}-sum-sender']` | `commot-cellchat-sum-sender` |
| Receiver summary | `obsm['commot-{db}-sum-receiver']` | `commot-cellchat-sum-receiver` |
| LR pair matrix | `obsp['commot-{db}-{ligand}-{receptor}']` | `commot-cellchat-TGFB1-TGFBR1_TGFBR2` |
| Pathway matrix | `obsp['commot-{db}-{pathway}']` | `commot-cellchat-TGFb` |
| Total matrix | `obsp['commot-{db}-total-total']` | `commot-cellchat-total-total` |
| Sender direction | `obsm['commot_sender_vf-{db}-{pathway}']` | `commot_sender_vf-cellchat-TGFb` |
| Receiver direction | `obsm['commot_receiver_vf-{db}-{pathway}']` | `commot_receiver_vf-cellchat-TGFb` |
| Cluster matrix | `uns['commot_cluster-{clustering}-{db}-{pathway}']` | `commot_cluster-leiden-cellchat-TGFb` |
| Metadata | `uns['commot-{db}-info']` | `commot-cellchat-info` |

---

## Common Pitfalls

1. **⚠️ `database_name` is required and must match across all calls**  
   `run_commot(adata, df_lr, database_name='cellchat')` stores results with prefix `commot-cellchat`. All downstream functions (`plot_communication_strength`, `infer_communication_direction`, `cluster_communication`, etc.) must use the **same** `database_name`. Using `'custom'` in one place and `'cellchat'` in another will cause `KeyError`.

2. **⚠️ `lr_pair` for direction/plotting is a tuple, not a string**  
   Native `communication_direction` and `plot_cell_communication` expect `lr_pair=('TGFB1', 'TGFBR1_TGFBR2')`, not `lr_pair='TGFB1-TGFBR1_TGFBR2'`. The string format is only used for result access (`get_communication_matrix`, `plot_communication_strength`).

3. **⚠️ NumPy 2.0 breaks COMMOT 0.0.3**  
   COMMOT uses `np.Inf` which was removed in NumPy 2.0. Install `numpy<2.0` or patch `/commot/_optimal_transport/_usot.py`.

4. **⚠️ `spatial_key` and `key_added` are NOT native COMMOT params**  
   The native `spatial_communication()` always reads from `adata.obsm['spatial']`. It does not accept `spatial_key`, `key_added`, or `min_exp_frac`. The wrapper validates spatial exists but does not pass these to native.

5. **⚠️ Cluster communication plots need `uns_names`, not `database_name`**  
   Native `plot_cluster_communication_network()` requires `uns_names` (a list of keys from `adata.uns`), not `database_name`. The wrapper auto-constructs `uns_names` from `database_name` + `cluster_key` + `pathway_name`/`lr_pair`.

6. **⚠️ Direction inference must be run before direction plots**  
   `plot_communication_direction()` will auto-compute direction if missing, but this can be slow. Best practice: call `infer_communication_direction()` explicitly first.

7. **⚠️ Heteromeric receptor format uses underscore**  
   In custom databases, use `'TGFBR1_TGFBR2'` (not `'TGFBR1-TGFBR2'`). The dash is reserved for the ligand-receptor separator in result keys.

8. **⚠️ COMMOT is memory-intensive for large datasets**  
   Each LR pair produces an N×N sparse matrix in `adata.obsp`. With 1000 LR pairs and 5000 spots, this is ~1000 × 25M elements. Filter LR pairs aggressively before running.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `TypeError: spatial_communication() got unexpected keyword argument 'spatial_key'` | Old wrapper passing invalid params to native | Use updated `run_commot()` which does NOT pass `spatial_key`/`key_added`/`min_exp_frac` |
| `KeyError: 'commot-cellchat-sum-receiver'` | Wrong `database_name` | Ensure `database_name` matches what was passed to `run_commot()` |
| `AttributeError: 'np.Inf' was removed` | NumPy 2.0 incompatibility | `pip install "numpy<2.0"` |
| `IndexError: single positional indexer is out-of-bounds` | No LR pairs have both genes present in data | Check gene symbols match; use `filter_lr_database` with lower `min_cell_pct` |
| `NameError: name 'sq' is not defined` | Old `plot_lr_expression` missing squidpy import | Use updated wrapper which uses manual matplotlib |
| Direction plot shows nothing | Direction not computed | Run `infer_communication_direction()` first |
| Cluster network plot fails | `uns_names` not constructed correctly | Use wrapper `plot_cluster_communication_network()` which auto-builds `uns_names` |
| Out of memory | Too many LR pairs × too many spots | Filter to < 100 LR pairs; subsample spots; increase `min_cell_pct` |
| `ValueError: 'spatial' not found in adata.obsm` | Missing spatial coordinates | Ensure `adata.obsm['spatial']` exists with shape (N, 2) or (N, 3) |

---

## Related Skills

- [bio-spatial-transcriptomics-communication-liana](../bio-spatial-transcriptomics-communication-liana/SKILL.md) — Alternative CCC (Python, non-OT)
- [bio-spatial-transcriptomics-communication-cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/SKILL.md) — CellChat R implementation
- [bio-spatial-transcriptomics-analysis-scanpy](../bio-spatial-transcriptomics-analysis-scanpy/SKILL.md) — General spatial analysis with scanpy

---

## References

1. **Primary Citation**  
   Cang, Z., Zhao, Y., Almet, A.A. et al. Screening cell–cell communication in spatial transcriptomics via collective optimal transport. *Nat Methods* 20, 218–228 (2023). https://doi.org/10.1038/s41592-022-01728-4

2. **Documentation**  
   https://commot.readthedocs.io/

3. **Package Source**  
   https://github.com/zcang/COMMOT

4. **LR Databases**
   - CellChat: Jin et al. (2021). Inference and analysis of cell-cell communication using CellChat. *Nature Communications*.
   - CellPhoneDB: Efremova et al. (2020). CellPhoneDB v4.0. *Nature Protocols*.
