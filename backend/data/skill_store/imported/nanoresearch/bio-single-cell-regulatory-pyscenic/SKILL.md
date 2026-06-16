---
name: bio-single-cell-regulatory-pyscenic
description: pySCENIC infers gene regulatory networks and cell-type-specific regulons from single-cell RNA-seq data. Three-step pipeline — GRN inference (GRNBoost2/GENIE3), cisTarget motif pruning, AUCell scoring — with automated cisTarget database management.
tool_type: python
primary_tool: pyscenic
supported_tools: [scanpy, arboreto, ctxcore]
languages: [python]
keywords: ["single-cell", "regulatory-network", "TF", "regulon", "scenic", "pyscenic", "grnboost2", "genie3", "cistarget", "aucell"]
code_location: scripts/python/
version_compatibility:
  python: ">=3.9"
  pyscenic: ">=0.12"
  scanpy: ">=1.9"
  arboreto: ">=0.1.5"
  ctxcore: ">=0.2"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| Python | >= 3.9 | |
| pyscenic | >= 0.12 | Core pipeline |
| scanpy | >= 1.9 | AnnData I/O |
| arboreto | >= 0.1.5 | GRNBoost2 / GENIE3 |
| ctxcore | >= 0.2 | cisTarget database I/O |
| pandas | >= 1.3 | Adjacency / AUC tables |
| dask | >= 2021 | Distributed computing backend |

## Installation

```bash
pip install pyscenic scanpy arboreto
```

Databases (~1 GB per organism) are downloaded automatically on first run.

## Skill Overview

pySCENIC identifies transcription factor (TF) regulons — sets of genes co-regulated by a TF — using a three-phase pipeline. Each phase produces an intermediate result that can be saved and resumed.

**Core workflow**: Database check → GRN inference → cisTarget pruning → AUCell scoring → Add to AnnData → Analysis

**When to use**:
- Identify TF-driven regulatory programs in scRNA-seq data
- Map cell-type-specific master regulators
- Link clustering/annotation results to transcriptional regulation
- Generate regulon activity matrices for downstream ML or visualization

**When NOT to use**:
- < 100 cells or < 5,000 genes — regulon inference is underpowered
- Gene names are Ensembl IDs — cisTarget databases require **gene symbols**
- Noisy, low-capture data where gene ranking is unstable
- Needing causal directionality — SCENIC infers associations, not causation
- ATAC-seq or multi-omic data — use the R SCENIC + chromVAR workflow instead

## Core Workflow (Step-by-Step)

### Step 1: Prepare Data

**Goal**: Ensure gene symbols and sufficient cell/gene counts.

**Input**: `AnnData` with raw counts or normalized expression in `adata.X`.

```python
import scanpy as sc

adata = sc.read_h5ad("your_data.h5ad")

# Filter low-quality cells/genes only — do NOT normalize or log-transform
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)

# CRITICAL: Gene names MUST be gene symbols (e.g., TP53, SOX10)
# If you have Ensembl IDs, convert them BEFORE running pySCENIC.
# SCENIC uses ranking-based methods; normalization has minimal impact.
```

**After this step**: `adata` is QC-filtered, gene symbols confirmed.

---

### Step 2: Check / Download Databases

**Goal**: Ensure cisTarget databases are cached before the long-running GRN step.

```python
from scripts.python.pyscenic_analysis import check_database, download_databases

status = check_database(organism="human", db_type="10kb", motif_version="v10")

if not status["all_ready"]:
    download_databases(organism="human", db_type="10kb", motif_version="v10")
# Databases cached in: skills/bio-single-cell-regulatory-pyscenic/assets/ (preferred)
# or ~/.pyscenic/ (fallback)
```

| Parameter | Options | Description |
|-----------|---------|-------------|
| `db_type` | `"500bp"` | Promoter-focused (500 bp upstream + 100 bp downstream of TSS) |
| `db_type` | `"10kb"` | Broader landscape (10 kb up/downstream; includes enhancers) |
| `motif_version` | `"v9"` | Classic motifs |
| `motif_version` | `"v10"` | Cluster-optimized motifs (better signal-to-noise) |

**Recommendation**: Start with `"10kb"` + `"v10"`. Use `"500bp"` for focused promoter analysis.

**⚠️ fly only supports v9**: `check_database("fly", "10kb", "v10")` will report `motif_annotations=False`. Use `"v9"` for fly.

**After this step**: Database files exist locally. This is a one-time ~1 GB download.

---

### Step 3: GRN Inference

**Goal**: Infer TF–target co-expression relationships.

```python
from scripts.python.pyscenic_analysis import run_grn_inference

adjacencies = run_grn_inference(
    adata=adata,
    tf_file="allTFs_hg38.txt",   # Auto-downloaded if using run_pyscenic_pipeline
    method="grnboost2",           # or "genie3" for smaller datasets
    num_workers=4,
    seed=42
)
# Returns DataFrame: columns [TF, target, importance]
```

| Method | Speed | Best For |
|--------|-------|----------|
| `"grnboost2"` | Fast (~2–5×) | Large datasets (>10k cells), screening |
| `"genie3"` | Slower, more accurate | Small datasets (<5k cells), publication |

**Memory**: ~2 GB per worker. Reduce to 2 workers if RAM < 16 GB.

**After this step**: `adjacencies` DataFrame with TF–target edge weights.

---

### Step 4: cisTarget Pruning

**Goal**: Validate TF–target links using motif enrichment (keep only direct targets).

```python
from scripts.python.pyscenic_analysis import run_cistarget

regulons = run_cistarget(
    adjacencies=adjacencies,
    database_path="path/to/hg38_10kb.feather",
    motif_annotations_path="path/to/motifs-v10.tbl",
    adata=adata,                  # REQUIRED: expression matrix for module creation
    num_workers=4,
    nes_threshold=3.0             # Only keep regulons with NES > 3
)
# Returns List[Regulon]
```

**What this wrapper adds**: Internally calls `modules_from_adjacencies(adjacencies, ex_mtx)` — the required intermediate step that converts raw adjacencies into co-expression modules before `prune2df` can process them. Without this step, `prune2df` receives the wrong input type.

**After this step**: `regulons` list. Each item has `.name` (e.g., `"SOX10 (45g)"`), `.gene2weight` (dict), `.transcription_factor`.

---

### Step 5: AUCell Scoring

**Goal**: Score each cell for activity of each regulon.

```python
from scripts.python.pyscenic_analysis import run_aucell

auc_matrix = run_aucell(
    adata=adata,
    regulons=regulons,
    num_workers=4,
    seed=42
)
# Returns DataFrame: (n_cells, n_regulons), values 0–1
```

| AUC Range | Interpretation |
|-----------|----------------|
| 0.0 – 0.3 | Inactive |
| 0.3 – 0.5 | Low activity |
| 0.5 – 0.8 | Moderate (likely functional) |
| 0.8 – 1.0 | High activity (driver regulon) |

**After this step**: `auc_matrix` DataFrame ready for visualization or clustering.

---

### Step 6: Add to AnnData

**Goal**: Store AUC scores in `obsm` for scanpy visualization tools.

```python
from scripts.python.pyscenic_analysis import add_aucell_to_adata

adata = add_aucell_to_adata(adata, auc_matrix, assay_name="X_aucell")

# Now available:
#   adata.obsm["X_aucell"]  → (n_cells × n_regulons)
#   adata.uns["regulon_names"] → list of regulon names

# Visualize on UMAP (if precomputed)
sc.pl.umap(adata, color=["SOX10 (45g)", "MITF (32g)"])
```

**⚠️ Returns modified `adata`** (not `None`).

---

### Step 7: Identify Cell-Type-Specific Regulons

**Goal**: Find regulons most active in each cell type.

```python
from scripts.python.pyscenic_analysis import get_top_regulons_per_celltype

top = get_top_regulons_per_celltype(
    adata,
    celltype_col="cell_type",
    auc_key="X_aucell",
    top_n=10
)
# Returns DataFrame: [cell_type, regulon, mean_auc]
```

**After this step**: Table of top regulons per cell type for interpretation or reporting.

---

### Step 8: Export Regulons

**Goal**: Save regulons in GMT format for GSEA or sharing.

```python
from scripts.python.pyscenic_analysis import export_regulons_to_gmt

export_regulons_to_gmt(
    regulons=regulons,
    output_file="regulons.gmt",
    min_genes=5               # Skip tiny regulons (low confidence)
)
```

---

## Complete Pipeline

```python
from scripts.python.pyscenic_analysis import (
    check_database, download_databases,
    run_pyscenic_pipeline, add_aucell_to_adata,
    get_top_regulons_per_celltype, export_regulons_to_gmt
)
import scanpy as sc

# 1. Load and QC (NO normalization)
adata = sc.read_h5ad("raw_counts.h5ad")
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)

# 2. Run complete pipeline (auto-downloads databases if missing)
adjacencies, regulons, auc_matrix = run_pyscenic_pipeline(
    adata=adata,
    organism="human",
    db_type="10kb",
    motif_version="v10",
    grn_method="grnboost2",
    num_workers=4,
    seed=42,
    download_if_missing=True
)

# 3. Add to AnnData
adata = add_aucell_to_adata(adata, auc_matrix, assay_name="X_aucell")

# 4. Identify cell-type-specific regulons
top = get_top_regulons_per_celltype(
    adata, celltype_col="cell_type", auc_key="X_aucell", top_n=10
)

# 5. Export
export_regulons_to_gmt(regulons, "regulons.gmt", min_genes=5)

# 6. Visualize (requires precomputed UMAP)
sc.pl.umap(adata, color=top["regulon"].unique()[:4].tolist())
```

## Skill-Provided Functions

Source: `scripts/python/pyscenic_analysis.py`

### Pipeline Orchestration

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `run_pyscenic_pipeline(adata, ...)` | `organism`, `db_type`, `grn_method`, `num_workers`, `download_if_missing` | End-to-end: DB check → GRN → cisTarget → AUCell. **Returns** `(adjacencies, regulons, auc_matrix)` |
| `run_grn_inference(adata, ...)` | `tf_file`/`tf_names`, `method`, `num_workers`, `seed` | Sparse-to-dense conversion + arboreto call. Returns adjacency DataFrame |
| `run_cistarget(adjacencies, ...)` | `database_path`, `motif_annotations_path`, `adata`/`ex_mtx`, `nes_threshold` | **Calls `modules_from_adjacencies` internally** (required step agents often miss). Returns `List[Regulon]` |
| `run_aucell(adata, regulons, ...)` | `num_workers`, `seed`, `noweights` | Sparse-to-dense + `aucell()`. Returns AUC DataFrame |

### Result Handling

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `add_aucell_to_adata(adata, auc_matrix, ...)` | `assay_name` | Stores AUC in `obsm[assay_name]` + regulon names in `uns["regulon_names"]`. **Returns modified adata** |
| `get_top_regulons_per_celltype(adata, ...)` | `celltype_col`, `auc_key`, `top_n` | Mean AUC per cell type; returns tidy DataFrame |
| `export_regulons_to_gmt(regulons, ...)` | `output_file`, `min_genes` | GMT export; logs actual count after `min_genes` filtering |

### Database Management

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `check_database(organism, db_type, motif_version)` | — | Returns dict with `database`, `motif_annotations`, `tf_list`, `all_ready` booleans |
| `download_databases(organism, db_type, ...)` | `force` | Downloads DB + motifs + TF list. Raises `ValueError` for invalid `motif_version` |
| `list_available_databases()` | — | Checks all organism/type combos using **latest available motif version per organism** |
| `get_pyscenic_dir(prefer_skill_assets=True)` | — | Returns cache Path (skill `assets/` or `~/.pyscenic/`) |
| `migrate_databases_to_skill_assets(dry_run=True)` | — | Move files from `~/.pyscenic/` to skill `assets/` |

## Official API — Agents Often Miss These

| Pattern | Key Point |
|---------|-----------|
| `modules_from_adjacencies(adjacencies, ex_mtx)` | **Required** intermediate step between GRN and cisTarget. Creates co-expression modules with Pearson correlation. Our `run_cistarget()` wrapper calls this automatically. |
| `prune2df(modules=..., not adjacencies)` | `prune2df` expects **modules** (from `modules_from_adjacencies`), not raw adjacencies DataFrame. Passing adjacencies directly is a common agent mistake. |
| `prune2df` `rank_threshold` | **Integer** (default 1500 = top 1500 ranked genes), not a fraction. Do not confuse with `auc_threshold` (float, default 0.05). |
| `prune2df` param names | Correct names: `motif_similarity_fdr`, `orthologuous_identity_threshold`, `weighted_recovery`, `module_chunksize`. No `fraction_overlap_w_target` or `annotations_to_transfer`. |
| `aucell(exp_mtx, signatures=regulons)` | AUCell ranks genes **within each cell** and computes enrichment of regulon targets. Works on raw counts or normalized data. |
| Regulon object attributes | `.name` (e.g., `"SOX10 (45g)"`), `.gene2weight` (dict), `.transcription_factor` (str). The gene count in parentheses is approximate. |
| Database URLs | From `resources.aertslab.org/cistarget/`. Files are `.feather` (ranking DB) and `.tbl` (motif annotations). |

## Common Pitfalls

1. **Forgetting `modules_from_adjacencies`**  
   `prune2df` does **not** accept raw adjacencies DataFrame. The correct flow is `adjacencies → modules_from_adjacencies → prune2df → df2regulons`. Our `run_cistarget()` wrapper handles this, but agents writing raw pySCENIC code often skip it.

2. **Gene names are Ensembl IDs**  
   cisTarget databases map **gene symbols** to genomic regions. Ensembl IDs will produce zero matches and empty regulons. Convert IDs before Step 1.

3. **`rank_threshold` is an integer, not a fraction**  
   `prune2df(rank_threshold=1500)` means "consider top 1500 ranked genes". Setting it to `0.05` is invalid and causes silent misbehavior or errors.

4. **Normalizing before SCENIC**  
   Normalization is unnecessary — AUCell uses per-cell gene ranking, which is robust to count depth. Normalizing does not hurt, but adds no benefit.

5. **Fly + motif v10**  
   Fly databases only have motif version `"v9"`. Using `"v10"` raises `ValueError` from `download_databases()`.

6. **Memory underestimation for cisTarget**  
   Each cisTarget worker loads the full ~1 GB database. `num_workers=4` + cisTarget ≈ 4–8 GB additional RAM. Reduce workers if memory-limited.

7. **AUC scores stored in `obsm`, not `obsp` or `layers`**  
   `add_aucell_to_adata` stores in `adata.obsm["X_aucell"]` (n_cells × n_regulons). This is the correct slot for multi-dimensional cell annotations.

## Troubleshooting

### `ValueError: Either adata or ex_mtx must be provided for cisTarget module creation`

`run_cistarget()` now requires expression data to create modules internally. Pass `adata=adata` or `ex_mtx=expr_df`.

```python
# Fix
regulons = run_cistarget(adjacencies, db_path, motif_path, adata=adata, num_workers=4)
```

### `ValueError: Motif version 'v10' not available for organism 'fly'`

Fly only supports v9.

```python
# Fix
status = check_database("fly", "10kb", "v9")
download_databases("fly", "10kb", "v9")
```

### Empty regulon list after cisTarget

- Gene names may be Ensembl IDs instead of symbols.
- Database organism may not match data organism (e.g., human data + mouse database).
- `nes_threshold` may be too stringent; try lowering to 2.0 for exploration.

```python
# Debug: check gene name overlap
import pyscenic
from ctxcore.rnkdb import opendb
db = opendb("path/to/db.feather")
print(f"DB genes: {len(db.genes)}")
print(f"Overlap: {len(set(adata.var_names) & set(db.genes))}")
```

### GRN inference runs forever

- Reduce `num_workers` if CPU-bound, or subsample cells.
- GRNBoost2 is 2–5× faster than GENIE3; switch methods for large datasets.

```python
# Fix: subsample for speed
sc.pp.subsample(adata, n_obs=10000, random_state=42)
adjacencies = run_grn_inference(adata, tf_file=tf_path, method="grnboost2")
```

### `dask` multiprocessing errors on Windows

Windows multiprocessing with dask can be unstable. Set `client_or_address="custom_multiprocessing"` in `run_cistarget` or reduce `num_workers=1`.

```python
regulons = run_cistarget(
    ..., adata=adata,
    client_or_address="custom_multiprocessing",
    num_workers=2
)
```

## Related Skills

- [bio-single-cell-regulatory-scenic-r](../bio-single-cell-regulatory-scenic-r/SKILL.md) — R-based SCENIC with Seurat integration; ATAC-seq compatible
- [bio-single-cell-clustering](../bio-single-cell-clustering/SKILL.md) — Leiden/Louvain clustering for cell-type annotation before regulon analysis
- [bio-single-cell-annotation-celltypist](../bio-single-cell-annotation-celltypist/SKILL.md) — Automated cell-type annotation; output column used for `get_top_regulons_per_celltype`

## References

1. Aibar et al. (2017). SCENIC: single-cell regulatory network inference and clustering. *Nature Methods*, 14, 1083–1086.
2. Van de Sande et al. (2020). A scalable SCENIC workflow for single-cell gene regulatory network analysis. *Nature Protocols*, 15, 2247–2276.
3. pySCENIC documentation: https://github.com/aertslab/pySCENIC
4. cisTarget databases: https://resources.aertslab.org/cistarget/
