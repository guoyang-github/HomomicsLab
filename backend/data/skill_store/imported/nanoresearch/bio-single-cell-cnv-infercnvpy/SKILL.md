---
name: bio-single-cell-cnv-infercnvpy
description: infercnvpy infers copy number variation (CNV) from single-cell transcriptomics data using Python. Compatible with Scanpy/AnnData workflow, scalable alternative to R-based InferCNV.
tool_type: python
primary_tool: infercnvpy
supported_tools: [scanpy, anndata]
languages: [python]
keywords: ["single-cell", "CNV", "copy-number", "cancer", "infercnv", "python", "scanpy"]
code_location: scripts/python/
version_compatibility:
  python: ">=3.10"
  infercnvpy: ">=0.4"
  scanpy: ">=1.9"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| Python | >= 3.10 | |
| infercnvpy | >= 0.4 | Core CNV inference |
| scanpy | >= 1.9 | AnnData operations |
| anndata | >= 0.8 | Data structure |
| scipy | >= 1.7 | Sparse matrix operations |
| leidenalg | >= 0.9 | For CNV-based clustering |

## Installation

```bash
pip install infercnvpy scanpy anndata leidenalg
```

## Skill Overview

infercnvpy infers copy number variation (CNV) from single-cell RNA-seq using a sliding window approach. It compares expression in tumor cells against reference (normal) cells to detect chromosomal amplifications and deletions.

**Core workflow**: Add gene positions → Run CNV inference → Cluster by CNV profile → Identify altered regions → Export

**When to use**:
- Identify large-scale chromosomal copy number alterations in tumor cells
- Distinguish tumor cells from normal cells based on CNV profiles
- Identify subclonal populations with distinct CNV patterns
- Validate cell type annotations in cancer samples

**When NOT to use**:
- Non-cancer samples without CNVs — the method has no signal to detect
- Reference cells are unknown or unavailable — baseline correction is impossible
- Focal alterations (< 1 Mb) — sliding window resolution is limited by gene density
- Need exact copy number counts — infercnvpy gives relative log-fold changes, not absolute ploidy

## Core Workflow

### Step 1: Add Gene Positions

**Goal**: Ensure `adata.var` has `chromosome`, `start`, `end` columns.

**Input requirements**:
- Gene symbols as `adata.var_names` (must be unique)
- Chromosome names with `chr` prefix (e.g., `chr1`, `chrX`)

```python
from infercnv_analysis import add_gene_positions

# Option A: From GTF file
adata = add_gene_positions(adata, gtf_file="gencode.v38.annotation.gtf")

# Option B: From pre-loaded DataFrame
gene_pos = pd.DataFrame({
    "gene_name": ["TP53", "MYC"],
    "chromosome": ["chr17", "chr8"],
    "start": [7661779, 1277356],
    "end": [7687538, 1280304]
}).set_index("gene_name")
adata = add_gene_positions(adata, gene_positions=gene_pos)
```

**What `add_gene_positions` adds over raw infercnvpy:**
- Accepts either a DataFrame or a GTF file path
- Validates gene overlap (warns if < 50% match)
- Safe reindex with NA handling for missing genes
- Always returns the modified AnnData

**CRITICAL**: Ensure `adata.var_names` are unique before running:
```python
adata.var_names_make_unique()
```

---

### Step 2: Run CNV Inference

**Goal**: Compute CNV profiles relative to reference (normal) cells.

```python
from infercnv_analysis import run_infercnv_pipeline

run_infercnv_pipeline(
    adata,
    reference_key="cell_type",                 # Column in adata.obs
    reference_cat=["T_cell", "B_cell", "Macrophage"],  # Normal cell labels
    window_size=100,                           # Genes per sliding window
    step=10,                                   # Window step size
    lfc_clip=3.0,                              # Clip extreme log-fold changes
    dynamic_threshold=1.5,                     # Noise filtering multiplier
    exclude_chromosomes=("chrX", "chrY"),      # Sex chromosomes to exclude
    chunksize=5000,                            # Cells per chunk (memory control)
    n_jobs=-1,                                 # Parallel jobs (-1 = all cores)
    key_added="cnv",                           # Key for storing results
    calculate_gene_values=False                # Per-gene CNV (memory intensive)
)
```

| Parameter | Default | Small (<5k cells) | Medium (5k-20k) | Large (>20k) |
|-----------|---------|-------------------|-----------------|--------------|
| `window_size` | 100 | 50 | 100 | 200 |
| `step` | 10 | 5 | 10 | 20 |
| `chunksize` | 5000 | 5000 | 5000 | 2000 |
| `n_jobs` | -1 | -1 | -1 | 4 |

**Results stored**:
- `adata.obsm["X_cnv"]`: CNV matrix (cells × windows), log-fold change vs reference
- `adata.uns["cnv"]["chr_pos"]`: Window-to-chromosome mapping
- `adata.layers["gene_values_cnv"]`: Per-gene CNV (if `calculate_gene_values=True`)

**Interpretation**:

| CNV Value | Interpretation |
|-----------|----------------|
| > 0.3 | Likely amplification |
| -0.3 to 0.3 | Normal diploid |
| < -0.3 | Likely deletion |
| > 1.0 | High-level amplification |
| < -1.0 | Homozygous deletion |

**What `run_infercnv_pipeline` adds over raw `cnv.tl.infercnv`:**
- Input validation (checks chromosome/start/end columns exist)
- Progress logging with shape and parameter info
- Error handling with descriptive messages

---

### Step 3: Cluster by CNV Profile

**Goal**: Identify subclones with distinct CNV patterns.

```python
from infercnv_analysis import cluster_by_cnv

cluster_by_cnv(adata, key="cnv", resolution=0.5)
# Adds: adata.obs["cnv_leiden"], overwrites adata.obsm["X_pca"] and neighbors/umap
```

**What it adds**: Runs PCA → neighbors → UMAP → Leiden on the CNV matrix (`adata.obsm["X_cnv"]`), not on gene expression. This clusters cells by chromosomal alteration pattern, not by transcriptomic similarity.

---

### Step 4: Identify Altered Regions

```python
from infercnv_analysis import identify_cnv_regions, summarize_cnv_by_chromosome

# Find significantly altered chromosomes
cnv_regions = identify_cnv_regions(
    adata, key="cnv", threshold=0.3, min_cells=10
)

# Summarize by chromosome and cell type
chr_summary = summarize_cnv_by_chromosome(
    adata, key="cnv", groupby="cell_type"
)
```

---

### Step 5: CNV Scoring

**Goal**: Quantify CNV burden per cell or per cluster.

```python
from infercnv_analysis import calculate_cnv_score

# Cell-level score: mean absolute CNV per cell
calculate_cnv_score(adata, method="cell", key_added="cnv_score")

# Cluster-level score: mean absolute CNV per cluster
calculate_cnv_score(adata, method="cluster", groupby="cnv_leiden")

# Thresholds:
#   cnv_score > 0.05: likely tumor cell
#   cnv_score > 0.10: high-confidence tumor cell
```

---

### Step 6: Export Results

```python
from infercnv_analysis import export_cnv_results

export_cnv_results(adata, output_dir="./cnv_results/", key="cnv")
# Creates: cnv_matrix.csv.gz, chr_pos.csv, cell_metadata.csv
```

---

### Step 7: Visualize

```python
import infercnvpy as cnv

# Chromosome heatmap
cnv.pl.chromosome_heatmap(adata, groupby="cell_type")

# UMAP of CNV clusters
sc.pl.umap(adata, color=["cnv_leiden", "cell_type"])
```

## Complete Pipeline

```python
import scanpy as sc
import infercnvpy as cnv
from infercnv_analysis import (
    add_gene_positions, run_infercnv_pipeline,
    cluster_by_cnv, identify_cnv_regions,
    calculate_cnv_score, export_cnv_results
)

# 1. Load data
adata = sc.read_h5ad("tumor_data.h5ad")
adata.var_names_make_unique()

# 2. Add gene positions
adata = add_gene_positions(adata, gtf_file="gencode.v38.annotation.gtf")

# 3. Run CNV inference
run_infercnv_pipeline(
    adata,
    reference_key="cell_type",
    reference_cat=["T_cell", "B_cell", "Macrophage"],
    window_size=100,
    step=10,
    key_added="cnv"
)

# 4. Cluster by CNV
cluster_by_cnv(adata, key="cnv", resolution=0.5)

# 5. Score
calculate_cnv_score(adata, method="cell", key_added="cnv_score")

# 6. Identify altered regions
regions = identify_cnv_regions(adata, key="cnv", threshold=0.3)
print(regions)

# 7. Export
export_cnv_results(adata, output_dir="./cnv_results/", key="cnv")

# 8. Visualize
cnv.pl.chromosome_heatmap(adata, groupby="cell_type")
sc.pl.umap(adata, color=["cnv_leiden", "cnv_score"])
```

## Skill-Provided Functions

### Data Preparation

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `add_gene_positions(adata, ...)` | `gtf_file` or `gene_positions` | Adds `chromosome`/`start`/`end` to `.var`; validates overlap; safe reindex |
| `read_gtf_positions(gtf_file, ...)` | `gene_id_attribute` | Wraps `cnv.io.genomic_position_from_gtf` with logging |

### CNV Inference

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `run_infercnv_pipeline(adata, ...)` | `reference_key`, `reference_cat`, `window_size`, `step` | Validates input, runs `cnv.tl.infercnv`, logs progress |

### Analysis

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `cluster_by_cnv(adata, ...)` | `key`, `resolution` | PCA + neighbors + UMAP + Leiden on CNV matrix (not expression) |
| `identify_cnv_regions(adata, ...)` | `threshold`, `min_cells` | Per-chromosome alteration summary; filters by min cells |
| `summarize_cnv_by_chromosome(adata, ...)` | `groupby` | Mean/std/min/max per chromosome; optional grouping |
| `calculate_cnv_score(adata, ...)` | `method` ("cell"/"cluster") | Mean absolute CNV per cell or per cluster |

### Export

| Function | Key Parameters | Description |
|----------|---------------|-------------|
| `export_cnv_results(adata, ...)` | `output_dir`, `prefix` | Exports CNV matrix, chr positions, and cell metadata |

## Official API — Agents Often Miss These

| Pattern | Key Point |
|---------|-----------|
| `cnv.tl.infercnv(..., inplace=True)` | Modifies `adata` in place. Results in `obsm["X_cnv"]` and `uns["cnv"]` — not returned as separate objects. |
| `add_gene_positions(..., inplace=True)` | **Always returns `adata`** regardless of `inplace`. This wrapper deviates from scanpy convention to prevent accidental `adata = None` assignments. |
| `cluster_by_cnv()` | **Overwrites** `adata.obsm["X_pca"]`, neighbors, and UMAP computed from gene expression. Run this **after** saving expression-based embeddings, or on a copy. |
| `calculate_gene_values=True` | Creates `adata.layers["gene_values_cnv"]` (n_cells × n_genes). Very memory-intensive for large datasets. Default is False. |
| `reference_cat` | Can be a single string `"Normal"` or a list `["T_cell", "B_cell"]`.
| Sex chromosomes | Default excludes `chrX` and `chrY`. Include them only if you know sample sex and want to analyze sex-chromosome CNVs. |
| Gene name uniqueness | `infercnvpy` requires unique `var_names`. Call `adata.var_names_make_unique()` before running. |

## Common Pitfalls

1. **Gene names not unique**  
   infercnvpy throws "Ensure your var_names are unique". Fix: `adata.var_names_make_unique()` before Step 1.

2. **Gene position columns missing**  
   `run_infercnv_pipeline()` validates that `chromosome`, `start`, `end` exist in `adata.var`. If missing, run `add_gene_positions()` first.

3. **Low gene overlap with GTF**  
   `add_gene_positions()` warns if < 50% of genes match. Usually caused by mismatched gene ID formats (e.g., Ensembl IDs in AnnData but gene symbols in GTF). Use `gene_id_attribute="gene_id"` when reading GTF.

4. **`cluster_by_cnv` overwrites expression embeddings**  
   It recomputes PCA, neighbors, and UMAP from the CNV matrix. If you need the expression-based UMAP later, save it: `adata.obsm["X_umap_expr"] = adata.obsm["X_umap"].copy()` before clustering.

5. **Reference cells are not truly normal**  
   If reference cells contain tumor cells, the baseline is corrupted and tumor CNVs are underestimated. Verify reference identity with marker genes.

6. **No clear CNV signal**  
   Possible causes: tumor purity too low, window size too large masking focal events, or reference cells have CNVs themselves. Try smaller `window_size` or different references.

7. **Memory errors on large datasets**  
   Reduce `chunksize` (e.g., 1000), increase `step` and `window_size` (e.g., 200/20), and set `calculate_gene_values=False`.

## Troubleshooting

### `ValueError: Gene positions not found in adata.var`

```python
# Fix: add positions first
adata = add_gene_positions(adata, gtf_file="annotation.gtf")
```

### `ValueError: Ensure your var_names are unique`

```python
# Fix: make unique before any processing
adata.var_names_make_unique()
```

### Low gene overlap warning from `add_gene_positions`

```python
# Check gene name format
print(adata.var_names[:10])

# If Ensembl IDs, read GTF with gene_id attribute
gene_pos = read_gtf_positions("gtf_file", gene_id_attribute="gene_id")
adata = add_gene_positions(adata, gene_positions=gene_pos)
```

### Memory error during inference

```python
# Fix: larger window/step, smaller chunks, fewer jobs
run_infercnv_pipeline(
    adata, reference_key="cell_type", reference_cat="Normal",
    window_size=200, step=20, chunksize=1000, n_jobs=4
)
```

### No clear CNV signal in heatmap

```python
# Possible causes and fixes:
# 1. Verify reference identity
sc.pl.dotplot(adata, marker_genes, groupby="cell_type")

# 2. Try smaller window for focal alterations
run_infercnv_pipeline(adata, ..., window_size=50, step=5)

# 3. Check individual chromosomes
regions = identify_cnv_regions(adata, threshold=0.2)
print(regions)
```

### `cluster_by_cnv` says "CNV matrix not found"

```python
# Fix: run inference first
run_infercnv_pipeline(adata, reference_key="cell_type", reference_cat="Normal")
cluster_by_cnv(adata, key="cnv")
```

## Related Skills

- [bio-single-cell-cnv-infercnv-r](../bio-single-cell-cnv-infercnv-r/SKILL.md) — R-based InferCNV
- [bio-single-cell-annotation-markers](../bio-single-cell-annotation-markers/SKILL.md) — For identifying reference cell types before CNV analysis

## References

1. Miller et al. (2018). InferCNV of the TCGA Glioblastoma dataset. *bioRxiv*.
2. infercnvpy documentation: https://infercnvpy.readthedocs.io/
3. Original InferCNV: https://github.com/broadinstitute/inferCNV
