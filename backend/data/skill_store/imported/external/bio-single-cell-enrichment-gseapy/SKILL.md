---
name: bio-single-cell-enrichment-gseapy
description: Gene set enrichment analysis using GSEApy — ORA, GSEA, and ssGSEA for single-cell data
tool_type: python
primary_tool: gseapy
supported_tools: [scanpy, pandas, numpy, seaborn]
languages: [python]
keywords: ["single-cell", "enrichment", "GSEA", "ORA", "ssGSEA", "pathway", "gseapy"]
code_location: scripts/python/
version_compatibility:
  python: ">=3.9"
  gseapy: ">=1.0.0"
  scanpy: ">=1.10.0"
---

## Version Compatibility & Installation

```bash
pip install gseapy>=1.0.0 scanpy>=1.10.0 pandas numpy matplotlib seaborn
```

Tested with gseapy 1.2.1, scanpy 1.10+, pandas 2.2+, numpy 1.26+.

## Skill Overview

**When to use:** You have single-cell RNA-seq data and want to interpret differentially expressed genes (DEGs) or gene rankings in terms of biological pathways.

**When NOT to use:**
- You need transcription factor activity inference → use `bio-single-cell-enrichment-decoupler` (decoupler / LIANA)
- You need regulon-based enrichment → use `bio-single-cell-regulatory-pyscenic`
- Your gene IDs are ENSEMBL (gseapy expects HGNC gene symbols for human, MGI for mouse)

**Three methods, three use cases:**

| Method | Input | Output | Best For |
|--------|-------|--------|----------|
| **ORA** (Over-Representation) | DEG list per cluster | Enriched pathways per cluster | Quick cluster annotation |
| **GSEA** (Preranked) | Ranked gene list | NES, p-value, leading edge | Condition comparison, full ranking |
| **ssGSEA** (Single-Sample) | Expression matrix | Per-cell pathway scores | Pathway UMAP, per-cell activity |

---

## Core Workflow

### Step 1: Preprocess & Compute DEGs (Input → DEG-ready adata)

Run on **log-normalized, unscaled** data. **Do NOT run `sc.pp.scale()` before `rank_genes_groups`** — scaling produces negative expression values that break log2FC calculation, yielding NaN and crashing gseapy.

```python
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.tl.rank_genes_groups(adata, groupby='leiden', method='wilcoxon')
# rank_genes_groups defaults to n_genes=100; use n_genes=adata.n_vars for full ranking
```

**State after Step 1:** `adata.uns['rank_genes_groups']` contains `names`, `logfoldchanges`, `scores`, `pvals`, `pvals_adj` for each group.

### Step 2a: ORA — Pathway Annotation per Cluster

```python
from scripts.python.ora_analysis import run_ora, run_ora_per_cluster

# Single cluster
results = run_ora(
    adata,
    group='0',                       # cluster name from rank_genes_groups
    gene_sets='KEGG_2021_Human',
    pval_cutoff=0.05,
    log2fc_cutoff=0.25,
    top_n=None,                      # use cutoffs; or set top_n=100 to use top N genes
)
# results: DataFrame with columns Term, Overlap, P-value, Adjusted P-value, Odds Ratio, Genes

# All clusters at once
all_results = run_ora_per_cluster(adata, gene_sets='GO_Biological_Process_2021')
# all_results: Dict[str, DataFrame]
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `group` | first group | Cluster to analyze |
| `gene_sets` | `'KEGG_2021_Human'` | Database name or list of names; also accepts custom dict |
| `pval_cutoff` | `0.05` | Adjusted p-value threshold for DEG selection |
| `log2fc_cutoff` | `0.25` | Absolute log2FC threshold |
| `top_n` | `None` | If set, use top N DEGs instead of pval/log2fc cutoffs |

**Popular gene sets:** `KEGG_2021_Human`, `GO_Biological_Process_2021`, `Reactome_2022`, `MSigDB_Hallmark_2020`, `WikiPathways_2019_Human`

**State after Step 2a:** `results` DataFrame (or dict) saved in memory; plot with `plot_enrichment()`.

### Step 2b: GSEA — Rank-Based Enrichment

```python
from scripts.python.gsea_analysis import prepare_ranked_list, run_prerank, run_gsea

# From rank_genes_groups results
ranked = prepare_ranked_list(adata, group='0', ranking_method='logfoldchanges')
# ranked: pd.Series with gene names as index, sorted descending

pre_res = run_prerank(
    ranked,
    gene_sets='MSigDB_Hallmark_2020',
    permutation_num=1000,    # Increase for publication; 100 is fast but underpowered
    min_size=5,
    max_size=500,
)
# Access results: pre_res.res2d  (columns: Name, Term, ES, NES, NOM p-val, FDR q-val, ...)

# Direct group comparison (computes log2FC + t-test, then prerank)
pre_res = run_gsea(
    adata,
    groupby='condition',
    group1='treatment',
    group2='control',
    gene_sets='MSigDB_Hallmark_2020',
    permutation_num=1000,
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `permutation_num` | `100` | Permutations for null distribution (1000+ recommended) |
| `min_size` / `max_size` | `5` / `500` | Gene set size filters |
| `weight` | `1.0` | Enrichment weight (0=classic, 1=weighted, 1.5, 2) |

**State after Step 2b:** `pre_res` is a `gp.Prerank` object; `pre_res.res2d` is a DataFrame.

### Step 2c: ssGSEA — Per-Cell Pathway Scores

```python
from scripts.python.ssgsea_analysis import run_ssgsea

run_ssgsea(
    adata,
    gene_sets='MSigDB_Hallmark_2020',
    key_added='X_ssgsea',
    sample_norm_method='rank',
    min_size=5,
    max_size=500,
    inplace=True,
)
# Results stored in:
#   adata.obsm['X_ssgsea']      → numpy array (n_cells, n_pathways), dtype float64
#   adata.uns['X_ssgsea_names'] → list of pathway names

# Visualize a pathway on existing UMAP
from scripts.python.ssgsea_analysis import score_pathway_on_umap
score_pathway_on_umap(adata, pathway='Hallmark_TNFA_Signaling_via_NFKB', ssgsea_key='X_ssgsea')
```

**State after Step 2c:** `adata.obsm['X_ssgsea']` contains per-cell NES scores; can be used as embedding for neighbors/UMAP.

### Step 3: Visualization

```python
from scripts.python.visualization import plot_enrichment, plot_gsea, plot_ssgsea_heatmap

# ORA / GSEA bar plot
fig = plot_enrichment(pre_res.res2d, top_n=10, pval_cutoff=0.05, title='Top Pathways')

# GSEA enrichment plot for one pathway (pass terms as list)
fig = pre_res.plot(terms=['Hallmark_TNFA_Signaling_via_NFKB'])

# ssGSEA heatmap
fig = plot_ssgsea_heatmap(
    adata, ssgsea_key='X_ssgsea', groupby='leiden',
    top_n_pathways=20, figsize=(12, 8)
)
```

---

## Complete Pipeline

```python
import scanpy as sc
import gseapy as gp
from scripts.python.ora_analysis import run_ora_per_cluster
from scripts.python.gsea_analysis import prepare_ranked_list, run_prerank, run_gsea
from scripts.python.ssgsea_analysis import run_ssgsea, score_pathway_on_umap
from scripts.python.visualization import plot_enrichment, plot_ssgsea_heatmap

# 1. Preprocess (log-normalized, UNSCALED)
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.tl.rank_genes_groups(adata, groupby='leiden', method='wilcoxon')

# 2. ORA per cluster
ora_results = run_ora_per_cluster(adata, gene_sets='KEGG_2021_Human')

# 3. GSEA for cluster 0 vs rest
ranked = prepare_ranked_list(adata, group='0')
gsea_res = run_prerank(ranked, gene_sets='MSigDB_Hallmark_2020', permutation_num=1000)

# 4. ssGSEA per-cell scores
run_ssgsea(adata, gene_sets='MSigDB_Hallmark_2020', key_added='X_ssgsea')

# 5. Visualize
fig = plot_enrichment(ora_results['0'], top_n=10)
score_pathway_on_umap(adata, pathway='Hallmark_TNFA_Signaling_via_NFKB')
```

---

## Skill-Provided Functions

### ORA
- `run_enrichr(gene_list, gene_sets, organism='human')` → `DataFrame`
- `run_ora(adata, group, gene_sets, pval_cutoff, log2fc_cutoff, top_n)` → `DataFrame`
- `run_ora_per_cluster(adata, gene_sets, pval_cutoff)` → `Dict[str, DataFrame]`

### GSEA
- `prepare_ranked_list(adata, group, deg_key, ranking_method)` → `pd.Series` (descending, NaN-cleaned)
- `run_prerank(ranked_list, gene_sets, permutation_num, min_size, max_size)` → `gp.Prerank`
- `run_gsea(adata, groupby, group1, group2, gene_sets)` → `gp.Prerank` (computes log2FC, then prerank)
- `run_gsea_per_cluster(adata, cluster_key, control_cluster, gene_sets)` → `Dict[str, gp.Prerank]`

### ssGSEA
- `run_ssgsea(adata, gene_sets, key_added, sample_norm_method, inplace)` → `AnnData` or `None`
- `run_ssgsea_pseudobulk(adata, groupby, gene_sets, min_cells)` → `DataFrame` (long format)
- `score_pathway_on_umap(adata, pathway, ssgsea_key)` → shows UMAP plot
- `compare_pathways_across_groups(adata, groupby, pathways, ssgsea_key)` → `DataFrame`

### Visualization
- `plot_enrichment(results, top_n, pval_cutoff)` → `Figure`
- `plot_gsea(prerank_result, gene_set)` → `Figure`
- `plot_ssgsea_heatmap(adata, ssgsea_key, groupby, top_n_pathways)` → `ClusterGrid`
- `plot_pathway_comparison(results_df, x_col, y_col, hue_col)` → `Figure`

### Utilities
- `prepare_gene_list(adata, group, key, pval_cutoff, log2fc_cutoff, top_n, direction)` → `List[str]`
- `filter_gene_sets(gene_sets_dict, min_genes, max_genes, background_genes, min_coverage)` → `dict`
- `load_gene_set(filepath, format)` → `dict` (supports `.gmt`, `.json`)

---

## Official API — Agents Often Miss These

### GSEApy `prerank` results structure
```python
pre_res = gp.prerank(...)
pre_res.res2d           # DataFrame; index is INTEGER, NOT pathway names
pre_res.res2d['Term']   # Column containing pathway names
pre_res.res2d['NES']    # Normalized enrichment score
pre_res.res2d['FDR q-val']  # Adjusted p-value
```
Common mistake: `pre_res.res2d.index[0]` returns `0`, not the top pathway. Use `pre_res.res2d.iloc[0]['Term']`.

### `Prerank.plot()` requires a **list** of terms
```python
pre_res.plot(terms=['KEGG_APOPTOSIS'])   # ✓ correct
pre_res.plot(terms='KEGG_APOPTOSIS')     # ✗ returns None or errors
```

### ssGSEA returns long-format `res2d`
```python
ssgs = gp.ssgsea(...)
ssgs.res2d.columns  # ['Name', 'Term', 'ES', 'NES', ...]
# 'Name' = cell/sample, 'Term' = pathway
```
The skill's `run_ssgsea` pivots this to wide format and stores as `adata.obsm[key_added]`.

### Gene sets can be a dict of lists
```python
custom = {'My_Pathway': ['Gene1', 'Gene2', ...]}
gp.enrichr(gene_list=genes, gene_sets=custom)   # works
```

### Enrichr database names are case-sensitive
Use exact names like `'KEGG_2021_Human'`, not `'kegg'`.

---

## Common Pitfalls

1. **⚠️ `sc.pp.scale()` before `rank_genes_groups` → gseapy crash**
   - Scaling produces negative values; log2FC computation yields NaN
   - Gseapy drops NaNs, often leaving too few genes, then crashes with `AttributeError: 'numpy.bool' object has no attribute 'values'`
   - **Fix:** Run `rank_genes_groups` on log-normalized but **unscaled** data. The skill's `prepare_ranked_list` now drops NaN with a descriptive error.

2. **⚠️ Sparse matrix boolean indexing fails with pandas Series**
   - `expr[adata.obs['condition'] == 'treat']` fails on scipy sparse matrices
   - **Fix:** The skill's `run_gsea` now converts masks with `.to_numpy()` before indexing.

3. **⚠️ ssGSEA stores object dtype without `.astype(float)`**
   - Causes `np.var()` and clustermap to fail downstream
   - **Fix:** `run_ssgsea` now stores `adata.obsm[key_added]` as `float64`.

4. **Custom gene sets dropped silently**
   - If fewer than `min_size` genes (default 5) from a custom set are found in the data, gseapy drops the entire set with a `LookupError`
   - **Fix:** Lower `min_size` or verify gene symbols match your data's `var_names`

5. **Duplicated ranking values**
   - Gseapy warns: `Duplicated values found in preranked stats`
   - Usually harmless (~0.01% of genes); arises when `rank_genes_groups` assigns identical scores to ties

6. **Gene ID mismatch**
   - Gseapy expects HGNC symbols (e.g., `TP53`, not `ENSG00000141510`)
   - Mouse data uses MGI symbols; set `organism='mouse'` in `run_enrichr`

7. **`plot_ssgsea_heatmap` fails with <2 pathways**
   - Seaborn `clustermap` cannot cluster a single column
   - **Fix:** The skill now auto-sets `col_cluster=False` when fewer than 2 pathways are present

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `AttributeError: 'numpy.bool' object has no attribute 'values'` | NaN in ranked list from scaled data | Re-run `rank_genes_groups` on unscaled data |
| `AttributeError: 'Series' object has no attribute 'nonzero'` | Sparse matrix indexed with pandas Series | Fixed in skill's `run_gsea` |
| `LookupError: No gene sets passed through filtering` | Custom gene set has <5 matching genes | Lower `min_size` or check gene symbols |
| `ValueError: empty distance matrix` in clustermap | Only 1 pathway in ssGSEA results | Use larger gene sets; skill auto-handles this now |
| `TypeError: ufunc 'isnan'` on `adata.obsm['X_ssgsea']` | Object dtype array stored | Fixed in skill — now stores float64 |
| `pre_res.plot(terms=...)` returns `None` | Passed single string instead of list | Use `terms=['Pathway_Name']` |

---

## Related Skills

- `bio-single-cell-enrichment-clusterprofiler-r` — clusterProfiler (R) for ORA/GSEA with richer organism support
- `bio-single-cell-enrichment-decoupler` — decoupler (Python) for transcription factor and pathway activity
- `bio-single-cell-enrichment-aucell-r` — AUCell (R) for gene-set activity scoring
- `bio-single-cell-enrichment-ucell-r` — UCell (R) for fast per-cell scoring

## References

1. Mootha et al. (2003). PGC-1α-responsive genes involved in oxidative phosphorylation are coordinately downregulated in human diabetes. *Nature Genetics*.
2. Subramanian et al. (2005). Gene set enrichment analysis. *PNAS*.
3. Barbie et al. (2009). Systematic RNA interference reveals that oncogenic KRAS-driven cancers require TBK1. *Nature*.
4. GSEApy documentation: https://gseapy.readthedocs.io/
5. Enrichr gene set libraries: https://maayanlab.cloud/Enrichr/#libraries
