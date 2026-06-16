# Single-Cell Enrichment (GSEApy) - Usage Guide

## Overview

This skill provides gene set enrichment analysis using GSEApy for single-cell data. Supports ORA, GSEA, and ssGSEA methods.

## Prerequisites

```bash
pip install gseapy scanpy pandas matplotlib seaborn
```

## Quick Start Prompts

Ask your AI agent:

> "Run pathway enrichment on cluster 0 DEGs"

> "Compute per-cell pathway scores using ssGSEA"

> "Compare treated vs control using GSEA"

> "Visualize pathway activity on UMAP"

## What the Agent Will Do

1. **ORA Workflow:**
   - Run `sc.tl.rank_genes_groups()` if needed
   - Extract significant DEGs
   - Run Enrichr ORA
   - Generate enrichment bar plot

2. **ssGSEA Workflow:**
   - Compute per-cell pathway scores
   - Store in `adata.obsm['X_ssgsea']`
   - Visualize on UMAP
   - Compare across cell types

3. **GSEA Workflow:**
   - Prepare ranked gene list
   - Run preranked GSEA
   - Generate enrichment plots

## Common Workflows

### Annotate Clusters with Pathways

```python
# 1. Get DEGs per cluster
sc.tl.rank_genes_groups(adata, groupby='leiden')

# 2. Run ORA for each cluster
from scripts.python.ora_analysis import run_ora_per_cluster
results = run_ora_per_cluster(adata, gene_sets='KEGG_2021_Human')

# 3. Check top pathways for cluster 0
print(results['0'].head())
```

### Create Pathway Activity UMAP

```python
# 1. Compute ssGSEA scores
from scripts.python.ssgsea_analysis import run_ssgsea
run_ssgsea(adata, gene_sets='MSigDB_Hallmark_2020')

# 2. Use scores for dimensionality reduction
sc.pp.neighbors(adata, use_rep='X_ssgsea', key_added='pathway_neighbors')
sc.tl.umap(adata, neighbors_key='pathway_neighbors')

# 3. Visualize
sc.pl.umap(adata, color=['leiden'])  # Cells colored by cluster
```

### Compare Conditions

```python
# GSEA comparing treatment vs control
from scripts.python.gsea_analysis import run_gsea

results = run_gsea(
    adata,
    groupby='condition',
    group1='treatment',
    group2='control',
    gene_sets='MSigDB_Hallmark_2020',
)

# View significant pathways
print(results.res2d[results.res2d['FDR q-val'] < 0.05])
```

## Tips

- **Choose gene sets wisely:**
  - KEGG: Well-curated pathways
  - GO: Comprehensive but can be broad
  - Hallmark: ~50 core pathways, good for overview
  - Custom: Use known markers or literature-derived sets

- **ORA vs GSEA vs ssGSEA:**
  - ORA: Simple, fast, needs DEGs first
  - GSEA: More sensitive, uses full ranking
  - ssGSEA: Per-cell resolution for visualization

- **Computational considerations:**
  - ssGSEA on large datasets (>50k cells) can be slow
  - Consider pseudobulk for initial exploration
  - Use `top_n` parameter to limit gene sets

- **Common issues:**
  - Gene symbol mismatches: Check if data uses HGNC symbols
  - Too few significant pathways: Relax cutoffs or try different gene sets
  - Memory: For ssGSEA on large data, use chunked processing

## Available Gene Sets

GSEApy provides access to:
- **Enrichr databases:** KEGG, GO, Reactome, WikiPathways
- **MSigDB:** Hallmark, C1-C8 collections
- **Custom:** Provide your own gene lists

Full list: https://maayanlab.cloud/Enrichr/#libraries
