# clusterProfiler Usage Guide

## Overview

clusterProfiler provides comprehensive enrichment analysis tools for interpreting gene lists from single-cell RNA-seq data. This skill provides R wrappers for:

- **ORA (Over-Representation Analysis)**: GO, KEGG, MSigDB, custom gene sets
- **GSEA (Gene Set Enrichment Analysis)**: Rank-based enrichment
- **compareCluster**: Multi-cluster comparison
- **Visualization**: Dot plots, networks, GSEA plots

## When to Use

| Scenario | Method | Function |
|----------|--------|----------|
| Annotate cluster markers | ORA | `run_enrichGO()` |
| Find pathways in DEGs | ORA | `run_enrichKEGG()` |
| Condition comparison (ranked) | GSEA | `run_gseGO()` |
| Cross-cluster comparison | compareCluster | `run_compareCluster()` |
| Custom gene sets | Universal | `run_enricher()` / `run_GSEA()` |
| Remove redundant GO terms | Simplify | `simplify_go_results()` |

## Quick Start

### 1. Setup

```r
# Install required packages
BiocManager::install(c("clusterProfiler", "org.Hs.eg.db", "enrichplot"))
install.packages("msigdbr")

# Load libraries
library(clusterProfiler)
library(org.Hs.eg.db)
library(enrichplot)

# Source skill scripts
source("scripts/r/ora_analysis.R")
source("scripts/r/gsea_analysis.R")
source("scripts/r/visualization.R")
```

### 2. Basic ORA

```r
# Run GO enrichment
go_result <- run_enrichGO(
    gene_list = marker_genes,
    org_db = org.Hs.eg.db,
    ont = "BP"
)

# Visualize
dotplot(go_result, showCategory = 15)
```

### 3. Basic GSEA

```r
# Prepare ranked gene list
gene_list <- setNames(markers$avg_log2FC, markers$gene)
gene_list <- sort(gene_list, decreasing = TRUE)

# Run GSEA
gsea_result <- run_gseGO(
    gene_list = gene_list,
    org_db = org.Hs.eg.db,
    ont = "BP"
)

# Plot
plot_gsea_running(gsea_result, geneSetID = 1)
```

## Step-by-Step Guide

### ORA from Seurat

```r
# Step 1: Find markers
markers <- FindAllMarkers(
    seurat_obj,
    only.pos = TRUE,
    min.pct = 0.25,
    logfc.threshold = 0.25
)

# Step 2: Extract genes for cluster 0
genes <- run_ora_seurat(
    seurat_obj,
    markers,
    cluster = "0",
    logfc_threshold = 0.25
)

# Step 3: GO enrichment (all ontologies)
for (ont in c("BP", "MF", "CC")) {
    result <- run_enrichGO(genes, org.Hs.eg.db, ont = ont)
    print(dotplot(result, title = paste("GO", ont)))
}

# Step 4: KEGG enrichment
kegg_result <- run_enrichKEGG(
    genes,
    organism = "hsa",
    convert_ids = TRUE,
    org_db = org.Hs.eg.db
)
```

### MSigDB Enrichment

```r
# Get Hallmark gene sets
h_sets <- get_msigdb_genesets("Homo sapiens", "H")
prepared <- prepare_msigdb_for_enrichment(h_sets)

# Run enrichment
result <- run_enricher(
    gene_list = marker_genes,
    term2gene = prepared$TERM2GENE,
    term2name = prepared$TERM2NAME
)

# Or use all MSigDB collections
msigdb_all <- get_msigdb_genesets("Homo sapiens", category = NULL)
```

### Multi-Cluster Comparison

```r
# Method 1: From marker data frame
gene_clusters <- split(markers$gene, markers$cluster)

result <- run_compareCluster(
    gene_clusters,
    fun = "enrichGO",
    OrgDb = org.Hs.eg.db,
    ont = "BP"
)

# Visualize comparison
dotplot(result, showCategory = 10)

# Method 2: Using helper function
result <- compareCluster_seurat(
    markers,
    top_n = 100,
    fun = "enrichGO",
    OrgDb = org.Hs.eg.db,
    ont = "BP"
)

# Simplify to remove redundancy
simplified <- simplify_compareCluster(result, cutoff = 0.7)
```

### GSEA Workflow

```r
# Prepare ranked list from Seurat markers
gene_list <- prepare_ranked_list(
    markers,
    cluster = "0",
    rank_by = "log2FC"
)

# Run GSEA with different methods
gsea_bp <- run_gseGO(
    gene_list,
    org.Hs.eg.db,
    ont = "BP",
    method = "multilevel"    # or "fgsea", "monte carlo"
)

# Get leading edge genes
leading_edge <- gsea_bp@result$core_enrichment[1]

# Plot top pathways
plot_gsea_running(gsea_bp, geneSetID = 1:3)

# Ridge plot of distributions
plot_gsea_ridge(gsea_bp, showCategory = 15)
```

### Advanced Visualization

```r
# Gene-concept network with fold change
gene_fc <- setNames(markers$avg_log2FC, markers$gene)
plot_gene_concept_network(
    go_result,
    showCategory = 5,
    foldChange = gene_fc,
    circular = FALSE
)

# Enrichment map (requires pairwise similarity)
plot_enrichment_map(go_result, showCategory = 30)

# Comprehensive multi-panel figure
plot_enrichment_comprehensive(
    go_result,
    save_path = "enrichment_figure.pdf",
    top_n = 10,
    foldChange = gene_fc
)
```

### Result Management

```r
# Export results
export_enrichment(go_result, "go_results.csv")
export_enrichment(go_result, "go_results.xlsx")

# Get top terms
top_terms <- get_top_terms(go_result, n = 20, by = "p.adjust")

# Filter by criteria
filtered <- filter_enrichment(
    go_result,
    pvalueCutoff = 0.01,
    minCount = 5,
    term_contains = c("immune", "signaling")
)

# Simplify GO results
simplified <- simplify_go_results(
    go_result,
    cutoff = 0.7,
    measure = "Wang"
)
```

## Parameter Reference

### Common Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pvalueCutoff` | 0.05 | P-value threshold |
| `pAdjustMethod` | "BH" | Multiple testing correction |
| `qvalueCutoff` | 0.2 | Q-value threshold |
| `minGSSize` | 10 | Min genes in gene set |
| `maxGSSize` | 500 | Max genes in gene set |

### GO-Specific

| Parameter | Options | Description |
|-----------|---------|-------------|
| `ont` | "BP", "MF", "CC", "ALL" | GO ontology |
| `keyType` | "SYMBOL", "ENTREZID" | Gene ID type |
| `readable` | TRUE/FALSE | Convert to gene symbols |

### KEGG-Specific

| Parameter | Options | Description |
|-----------|---------|-------------|
| `organism` | "hsa", "mmu", etc. | Species code |
| `keyType` | "kegg", "ncbi-geneid" | Gene ID type |
| `convert_ids` | TRUE/FALSE | Auto-convert symbols |

## Best Practices

### Gene ID Handling

```r
# Always check ID mapping
mapped <- convert_gene_ids(
    genes = my_genes,
    fromType = "SYMBOL",
    toType = "ENTREZID",
    org_db = org.Hs.eg.db
)

# Use consistent IDs throughout
# SYMBOL for GO (with readable=TRUE, clusterProfiler auto-converts)
# ENTREZID for KEGG (required; use convert_ids=TRUE for auto-conversion)
```

### Background Selection

```r
# Use expressed genes as background (recommended)
# Seurat v5 compatible
counts_layer <- SeuratObject::LayerData(seurat_obj, assay = "RNA", layer = "counts")
expressed_genes <- rownames(seurat_obj)[Matrix::rowSums(counts_layer > 0) > 10]

result <- run_enrichGO(
    gene_list = marker_genes,
    universe = expressed_genes,  # Background
    org_db = org.Hs.eg.db
)
```

### GO Simplification

```r
# Always simplify GO results to remove redundancy
go_result <- run_enrichGO(genes, org.Hs.eg.db, ont = "BP")

# Check number of terms before
nrow(as.data.frame(go_result))

# Simplify
simplified <- simplify_go_results(go_result, cutoff = 0.7)

# Check after
nrow(as.data.frame(simplified))
```

### Multiple Testing

```r
# Use BH correction (default)
# For exploratory analysis, may relax pvalueCutoff to 0.1

# For strict analysis
result <- run_enrichGO(
    genes,
    org.Hs.eg.db,
    pvalueCutoff = 0.01,
    qvalueCutoff = 0.05
)
```

## Troubleshooting

### "No gene can be mapped"

```r
# Check gene ID format
head(genes)

# Try different keyType
result <- run_enrichGO(genes, org.Hs.eg.db, keyType = "ENSEMBL")

# Check if genes are in database
keytypes(org.Hs.eg.db)
```

### "No enrichment found"

```r
# Relax cutoffs
result <- run_enrichGO(
    genes,
    org.Hs.eg.db,
    pvalueCutoff = 0.1,
    qvalueCutoff = 0.5
)

# Check gene list size
length(genes)  # Should be > 10

# Try different database
result <- run_enricher(genes, custom_term2gene)
```

### "KEGG download fails"

```r
# Use internal KEGG.db (if available)
result <- run_enrichKEGG(
    genes,
    organism = "hsa",
    use_internal_data = TRUE
)

# Or check network connection
# Try again later if KEGG server is down
```

## References

1. clusterProfiler book: https://yulab-smu.top/biomedical-knowledge-mining-book/
2. Bioconductor page: https://bioconductor.org/packages/clusterProfiler/
3. GitHub: https://github.com/YuLab-SMU/clusterProfiler/
