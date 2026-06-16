---
name: bio-single-cell-enrichment-clusterprofiler-r
description: Universal enrichment analysis and visualization for single-cell data using clusterProfiler. Supports ORA, GSEA, and multi-cluster comparison for GO, KEGG, DO, and MSigDB gene sets.
tool_type: r
primary_tool: clusterProfiler
supported_tools: [enrichplot, org.Hs.eg.db, org.Mm.eg.db, msigdbr, Seurat, dplyr]
languages: [r]
keywords: ["single-cell", "clusterprofiler", "enrichment", "ORA", "GSEA", "GO", "KEGG", "MSigDB", "pathway", "R"]
version: 1.1
---

## Version Compatibility & Installation

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.2.0 | |
| clusterProfiler | >= 4.6 | Bioconductor |
| org.Hs.eg.db | >= 3.16 | Human annotation; use org.Mm.eg.db for mouse |
| enrichplot | >= 1.18 | Visualization |
| GOSemSim | >= 2.24 | Required for GO simplification |
| msigdbr | >= 7.4 | MSigDB gene sets (CRAN) |
| Seurat / SeuratObject | >= 5.0 | For marker extraction; wrappers use `LayerData()` for v5 compat |
| openxlsx | >= 4.2 | Excel export |
| patchwork | >= 1.1 | Multi-panel figures |

```r
if (!requireNamespace("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install(c("clusterProfiler", "org.Hs.eg.db", "enrichplot", "GOSemSim"))
install.packages(c("msigdbr", "openxlsx", "patchwork"))
```

## Skill Overview

clusterProfiler performs enrichment analysis (ORA and GSEA) on gene lists derived from single-cell clusters. It supports GO, KEGG, MSigDB, and custom gene sets with extensive visualization options.

**When to use:**
- Annotate cluster marker genes with GO/KEGG pathways
- Compare pathway enrichment across multiple clusters
- GSEA on ranked gene lists (e.g., all DEGs sorted by log2FC)
- Custom gene set enrichment (MSigDB Hallmark, Reactome, etc.)

**When NOT to use:**
- Very small gene lists (< 10 genes) — statistical power too low
- When you need cell-level (not gene-level) pathway scoring — use decoupler or UCell instead
- When gene symbols cannot be mapped to the organism database (check ID mapping first)

## Core Workflow

### Step 1: Prepare Gene List(s)

**For ORA:** Character vector of gene symbols  
**For GSEA:** Named numeric vector (names = gene symbols, values = ranking metric like log2FC), sorted decreasing

```r
library(Seurat)

# After FindAllMarkers
markers <- FindAllMarkers(seurat_obj, only.pos = TRUE)

# ---- ORA: extract significant markers for one cluster ----
genes <- run_ora_seurat(
    markers,
    cluster = "0",
    logfc_threshold = 0.25,
    pval_threshold = 0.05
)
# Returns: character vector of gene symbols
# (NOT an enrichment result — this is just gene extraction)

# ---- GSEA: prepare ranked list for one cluster ----
ranked_genes <- prepare_ranked_list(
    markers,
    cluster = "0",
    rank_by = "log2FC",
    signed = TRUE
)
# Returns: named numeric vector sorted by metric
```

> **Agent note:** `run_ora_seurat()` **does NOT run enrichment**. It only extracts a character vector of gene symbols from Seurat markers. You must pass the result to `run_enrichGO()` or `run_enrichKEGG()` afterward.

### Step 2: Run ORA (Over-Representation Analysis)

**Input:** Character vector of gene symbols  
**Output:** `enrichResult` object

```r
# GO enrichment (accepts SYMBOL directly)
go_result <- run_enrichGO(
    gene_list = genes,
    org_db = org.Hs.eg.db,
    keyType = "SYMBOL",
    ont = "BP",           # "BP", "MF", "CC", or "ALL"
    pvalueCutoff = 0.05,
    pAdjustMethod = "BH",
    readable = TRUE       # Auto-convert gene IDs to symbols in output
)

# KEGG enrichment (requires ENTREZID; auto-convert from SYMBOL)
kegg_result <- run_enrichKEGG(
    gene_list = genes,
    organism = "hsa",     # hsa=human, mmu=mouse, rno=rat
    convert_ids = TRUE,   # Auto-convert SYMBOL → ENTREZID
    org_db = org.Hs.eg.db
)

# MSigDB / custom gene sets
library(msigdbr)
hallmark <- msigdbr(species = "Homo sapiens", category = "H")
term2gene <- hallmark[, c("gs_name", "gene_symbol")]

msig_result <- run_enricher(
    gene_list = genes,
    term2gene = term2gene
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pvalueCutoff` | 0.05 | Raw p-value threshold |
| `pAdjustMethod` | "BH" | Multiple testing: "holm", "hochberg", "bonferroni", "BH", "BY", "fdr", "none" |
| `qvalueCutoff` | 0.2 | Q-value threshold |
| `minGSSize` | 10 | Min genes in a tested gene set |
| `maxGSSize` | 500 | Max genes in a tested gene set |
| `universe` | all genes in OrgDb | Background gene set; **recommend using expressed genes** |

### Step 3: Run GSEA (Gene Set Enrichment Analysis)

**Input:** Named numeric vector (sorted decreasing)  
**Output:** `gseaResult` object

```r
gsea_go <- run_gseGO(
    gene_list = ranked_genes,
    org_db = org.Hs.eg.db,
    keyType = "SYMBOL",
    ont = "BP",
    method = "multilevel",   # "multilevel" (default), "fgsea", "monte carlo"
    pvalueCutoff = 0.05
)

# KEGG GSEA
# Convert IDs first because gseKEGG needs ENTREZID
converted <- convert_gene_ids(
    names(ranked_genes),
    fromType = "SYMBOL",
    toType = "ENTREZID",
    org_db = org.Hs.eg.db
)
# Build new named vector with ENTREZ IDs
entrez_ranked <- setNames(ranked_genes[converted$SYMBOL], converted$ENTREZID)
entrez_ranked <- sort(entrez_ranked, decreasing = TRUE)

gsea_kegg <- run_gseKEGG(
    gene_list = entrez_ranked,
    organism = "hsa"
)

# MSigDB GSEA
prepared <- prepare_msigdb_for_enrichment(hallmark, id_type = "gene_symbol")
gsea_msig <- run_GSEA(
    gene_list = ranked_genes,
    term2gene = prepared$TERM2GENE,
    term2name = prepared$TERM2NAME
)
```

### Step 4: Multi-Cluster Comparison

**ORA compareCluster** (one gene list per cluster):

```r
# Method A: from marker data frame
result <- compareCluster_seurat(
    markers,
    top_n = 100,                       # Top N genes per cluster
    logfc_threshold = 0.25,
    pval_threshold = 0.05,
    fun = "enrichGO",
    OrgDb = org.Hs.eg.db,
    ont = "BP"
)

# Method B: manual gene_clusters list
gene_clusters <- split(markers$gene, markers$cluster)
result <- run_compareCluster(
    gene_clusters,
    fun = "enrichGO",
    OrgDb = org.Hs.eg.db,
    ont = "BP"
)
```

**GSEA compareCluster** (one ranked vector per cluster):

```r
result <- compareGSEA_seurat(
    markers,
    gsea_fun = "gseGO",
    OrgDb = org.Hs.eg.db,
    ont = "BP"
)
```

### Step 5: Simplify and Export

```r
# Remove redundant GO terms (GO only)
simplified <- simplify_go_results(go_result, cutoff = 0.7, measure = "Wang")

# Simplify compareCluster results (GO only)
simplified_comp <- simplify_compareCluster(result, cutoff = 0.7)

# Export
export_enrichment(go_result, "go_results.csv")
export_enrichment(go_result, "go_results.xlsx")

# Top terms
top10 <- get_top_terms(go_result, n = 10, by = "p.adjust")

# Filter
filtered <- filter_enrichment(
    go_result,
    pvalueCutoff = 0.01,
    minCount = 5,
    term_contains = c("immune", "signaling")
)
```

### Step 6: Visualize

```r
# Dot plot (works for enrichResult / gseaResult / compareClusterResult)
plot_enrichment_dot(go_result, showCategory = 15)

# Bar plot
plot_enrichment_bar(go_result, showCategory = 15)

# Gene-concept network with fold change coloring
fc <- setNames(markers$avg_log2FC, markers$gene)
plot_gene_concept_network(go_result, showCategory = 5, foldChange = fc)

# Enrichment map (similarity network)
plot_enrichment_map(go_result, showCategory = 20)

# GSEA running score
plot_gsea_running(gsea_go, geneSetID = 1:3)

# Ridge plot
plot_gsea_ridge(gsea_go, showCategory = 15)

# Multi-panel comprehensive figure
plot_enrichment_comprehensive(
    go_result,
    save_path = "enrichment_overview.pdf",
    top_n = 10,
    foldChange = fc
)
```

## Complete Pipeline (Copy-Pasteable)

```r
library(Seurat)
library(clusterProfiler)
library(org.Hs.eg.db)
library(enrichplot)

source("scripts/r/ora_analysis.R")
source("scripts/r/gsea_analysis.R")
source("scripts/r/compare_cluster.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# 1. Find markers
markers <- FindAllMarkers(seurat_obj, only.pos = TRUE, logfc.threshold = 0.25)

# 2. Extract cluster 0 genes for ORA
genes <- run_ora_seurat(
    markers, cluster = "0",
    logfc_threshold = 0.25, pval_threshold = 0.05
)

# 3. ORA
result <- run_enrichGO(
    gene_list = genes,
    org_db = org.Hs.eg.db,
    keyType = "SYMBOL",
    ont = "BP",
    pvalueCutoff = 0.05
)

# 4. Simplify
result <- simplify_go_results(result, cutoff = 0.7)

# 5. Visualize
plot_enrichment_dot(result, showCategory = 15)

# 6. Export
export_enrichment(result, "cluster0_go.csv")
```

## Skill-Provided Functions

**ORA**
- `run_enrichGO(gene_list, org_db, keyType, ont, pvalueCutoff, ...)` — GO enrichment; accepts SYMBOL directly
- `run_enrichKEGG(gene_list, organism, convert_ids, org_db, ...)` — KEGG pathway enrichment; auto-converts SYMBOL→ENTREZID when `convert_ids=TRUE`
- `run_enricher(gene_list, term2gene, term2name, ...)` — Universal enrichment with custom gene sets (MSigDB, Reactome, etc.)
- `run_ora_seurat(markers, cluster, logfc_threshold, pval_threshold, top_n, only.pos)` — **Extracts gene symbols** from Seurat markers (does NOT run enrichment)
- `run_ora_all_clusters(markers, enrich_fun, logfc_threshold, pval_threshold, top_n, ...)` — Loop over clusters; passes `...` only to the enrichment function

**GSEA**
- `run_gseGO(gene_list, org_db, keyType, ont, method, ...)` — GO GSEA; validates gene_list is named and auto-sorts
- `run_gseKEGG(gene_list, organism, convert_ids, org_db, ...)` — KEGG GSEA
- `run_GSEA(gene_list, term2gene, term2name, ...)` — Universal GSEA with custom gene sets
- `prepare_ranked_list(markers, cluster, rank_by, signed)` — Create named numeric vector from Seurat markers; removes NA/Inf
- `run_gsea_all_clusters(markers, gsea_fun, rank_by, signed, min_genes, ...)` — Loop over clusters; separates ranking params from GSEA params

**Multi-cluster comparison**
- `run_compareCluster(gene_clusters, fun, ...)` — Wrapper for `clusterProfiler::compareCluster`; validates list input
- `compareCluster_seurat(markers, top_n, logfc_threshold, pval_threshold, ...)` — Build gene_clusters from Seurat markers and run compareCluster with ORA
- `compareGSEA_seurat(markers, gsea_fun, min_genes, ...)` — Build ranked vectors per cluster and run compareCluster with GSEA
- `merge_enrichResults(enrich_list)` — Merge multiple enrichResult objects into one compareClusterResult

**Simplification & export**
- `simplify_go_results(enrich_result, cutoff, by, measure)` — Remove redundant GO terms; checks ontology compatibility
- `simplify_compareCluster(compare_result, cutoff, by, measure)` — Simplify compareCluster GO results
- `get_top_terms(enrich_result, n, by)` — Extract top N terms; handles compareClusterResult by group
- `filter_enrichment(enrich_result, pvalueCutoff, qvalueCutoff, minCount, maxCount, term_contains)` — Subset results; supports enrichResult, gseaResult, and compareClusterResult
- `export_enrichment(enrich_result, file, sheet_name)` — Export to CSV / XLSX / TSV; auto-detects format from extension

**Utilities**
- `convert_gene_ids(genes, fromType, toType, org_db, drop)` — ID conversion with mapping stats
- `get_msigdb_genesets(species, category, subcategory)` — Fetch MSigDB gene sets
- `prepare_msigdb_for_enrichment(msigdb_df, id_type)` — Format MSigDB data frame into TERM2GENE / TERM2NAME
- `create_gene_list_seurat(seurat_obj, cluster, group.by, only.pos, min.pct, logfc.threshold)` — Extract genes via Seurat markers; preserves original Idents

**Visualization**
- `plot_enrichment_dot(result, showCategory, color, size, save_path)` — Dot plot; works on enrich/gsea/compareCluster results
- `plot_enrichment_bar(result, showCategory, color, save_path)` — Bar plot
- `plot_gene_concept_network(result, showCategory, foldChange, circular, save_path)` — Cnetplot with optional fold change coloring
- `plot_enrichment_map(result, showCategory, layout, save_path)` — Emapplot with auto pairwise_termsim
- `plot_upset(result, n, save_path)` — Upset plot for overlap visualization
- `plot_gsea_running(gsea_result, geneSetID, save_path)` — GSEA running score; supports multiple gene sets
- `plot_gsea_ridge(gsea_result, showCategory, fill, save_path)` — Ridge plot
- `plot_enrichment_comprehensive(result, save_path, top_n, foldChange)` — 4-panel figure (dot + bar + emap + cnet)

## Official API — Agents Often Miss These

**1. `run_ora_seurat()` extracts genes, NOT enrichment results**
```r
# WRONG mental model:
result <- run_ora_seurat(markers, cluster = "0")  # Returns char vector!

# RIGHT:
genes <- run_ora_seurat(markers, cluster = "0")   # char vector
result <- run_enrichGO(gene_list = genes, org_db = org.Hs.eg.db)  # enrichment
```

**2. KEGG functions need ENTREZ IDs, not gene symbols**
`run_enrichKEGG()` and `run_gseKEGG()` require Entrez IDs by default. Use `convert_ids = TRUE` (for `run_enrichKEGG`) or `convert_gene_ids()` + manual conversion (for `run_gseKEGG`). GO functions accept SYMBOL directly.

**3. GSEA input must be a named numeric vector, sorted decreasing**
```r
# WRONG:
gsea_input <- c("TP53", "BRCA1", "EGFR")  # character vector

# RIGHT:
gsea_input <- c(TP53 = 2.5, BRCA1 = -1.8, EGFR = 3.2)
gsea_input <- sort(gsea_input, decreasing = TRUE)
```
`prepare_ranked_list()` does this automatically from Seurat markers.

**4. `compareCluster` `fun` argument is a character string, not a function object**
```r
# RIGHT:
run_compareCluster(gene_clusters, fun = "enrichGO", OrgDb = org.Hs.eg.db)

# WRONG:
run_compareCluster(gene_clusters, fun = enrichGO, ...)  # will fail
```

**5. `universe` for ORA should be expressed genes, not all genes in the genome**
Using the full genome as background inflates significance. Use the set of genes detected in your dataset:
```r
# Seurat v5
expr_genes <- rownames(seurat_obj)[
    Matrix::rowSums(SeuratObject::LayerData(seurat_obj, layer = "counts") > 0) > 10
]
result <- run_enrichGO(genes, org_db = org.Hs.eg.db, universe = expr_genes)
```

**6. `ont = "ALL"` pools BP + MF + CC, which creates redundant results**
For cleaner output, run each ontology separately and simplify:
```r
bp <- run_enrichGO(genes, org_db = org.Hs.eg.db, ont = "BP")
bp <- simplify_go_results(bp, cutoff = 0.7)
```

**7. GO simplification only works on GO results**
`simplify_go_results()` and `simplify_compareCluster()` check the ontology slot and will error on KEGG or MSigDB results. For non-GO databases, use `filter_enrichment(term_contains = ...)` to focus on relevant terms.

**8. `run_ora_all_clusters` and `run_gsea_all_clusters` trap errors per cluster**
If one cluster fails (e.g., too few genes), the loop continues for remaining clusters. Check `names(results)` to see which succeeded.

## Common Pitfalls

1. **⚠️ Passing gene symbols to KEGG without conversion**
   `run_enrichKEGG()` defaults to `convert_ids = FALSE`. If you pass SYMBOLs, set `convert_ids = TRUE` or pre-convert with `convert_gene_ids()`.

2. **⚠️ Using `run_ora_seurat()` and expecting an enrichment table**
   This function returns a character vector. Always pipe it into `run_enrichGO()` / `run_enrichKEGG()` / `run_enricher()`.

3. **⚠️ compareCluster with GSEA and mismatched gene IDs**
   `compareGSEA_seurat()` builds ranked vectors with SYMBOLs. If `gsea_fun = "gseKEGG"`, the vectors contain SYMBOLs but `gseKEGG` expects ENTREZIDs. Convert first or use GO/MSigDB GSEA functions.

4. **⚠️ Forgetting to simplify GO results**
   GO BP often returns hundreds of highly overlapping terms. Always run `simplify_go_results()` to reduce redundancy.

5. **⚠️ Running ORA on all genes in a cluster**
   ORA needs a focused gene list. Use thresholds (`logfc_threshold`, `pval_threshold`) or `top_n` to select the most significant markers.

6. **⚠️ Seurat v4 vs v5 slot access**
   Direct access like `seurat_obj@assays$RNA@counts` fails in v5. Use `SeuratObject::LayerData(seurat_obj, layer = "counts")` instead.

7. **⚠️ `filter_enrichment` returns a modified copy**
   The function returns a new object with filtered `@result`; assign the return value to capture it. The original object is unchanged.

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `No gene can be mapped` | Wrong `keyType` or gene symbols not in OrgDb | Check `keytypes(org.Hs.eg.db)`; try `keyType = "ENSEMBL"` or `keyType = "ENTREZID"` |
| `No enrichment found` | Cutoffs too strict or gene list too small | Relax `pvalueCutoff` to 0.1; ensure `length(genes) > 10` |
| `unused argument (cluster = ...)` in `run_gsea_all_clusters` | Old version forwarded `...` incorrectly to `prepare_ranked_list` | Use latest skill version; rank params (`rank_by`, `signed`) are now explicit |
| KEGG download fails | KEGG server down or no internet | Use `use_internal_data = TRUE` (requires KEGG.db) or switch to MSigDB |
| `simplify only works with GO` | Trying to simplify KEGG/MSigDB results | Use `filter_enrichment(term_contains = ...)` instead |
| `dotplot` shows nothing | Result object has 0 significant terms | Relax cutoffs or check input gene list |
| `compareCluster` returns empty | All gene clusters have too few genes | Lower `logfc_threshold` or increase `top_n` |
| Multi-panel plot fails | `plot_enrichment_map` needs pairwise similarity | Ensure result has > 2 terms; try reducing `top_n` |

## Related Skills

- [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md) — GSEApy (Python)
- [bio-single-cell-enrichment-decoupler](../bio-single-cell-enrichment-decoupler/SKILL.md) — decoupler (Python, cell-level pathway scores)
- [bio-single-cell-enrichment-irgsea-r](../bio-single-cell-enrichment-irgsea-r/SKILL.md) — irGSEA (R, integrated rank-based GSEA)

## References

1. Yu G, Wang LG, Han Y, He QY. clusterProfiler: an R package for comparing biological themes among gene clusters. *OMICS*. 2012;16(5):284-287.
2. Wu T, Hu E, Xu S, et al. clusterProfiler 4.0: A universal enrichment tool for interpreting omics data. *The Innovation*. 2021;2(3):100141.
3. Yu G. Gene Ontology Semantic Similarity Analysis Using GOSemSim. *Methods in Molecular Biology*. 2020;2117:207-215.
4. Liberzon A, et al. The Molecular Signatures Database (MSigDB) hallmark gene set collection. *Cell Systems*. 2015;1(6):417-425.
5. clusterProfiler book: https://yulab-smu.top/biomedical-knowledge-mining-book/
