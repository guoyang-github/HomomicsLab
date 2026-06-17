---
name: bio-mrna-seq-pathway-enrichment
description: Functional enrichment and pathway analysis for bulk mRNA-seq differential expression results. Covers GO, KEGG, Reactome over-representation, GSEA, and visualization with clusterProfiler (R) and gseapy (Python). Use after obtaining DE results.
tool_type: mixed
primary_tool: clusterProfiler
---


Reference examples tested with: clusterProfiler 4.10+, ReactomePA 1.46+, org.Hs.eg.db 3.18+, gseapy 1.1+

# mRNA-seq Pathway Enrichment

## Overview

Convert differential expression results into biological insights via functional enrichment and gene set analysis.

## Tool Selection

| Tool | Best For | Notes |
|------|----------|-------|
| **clusterProfiler (R)** | Full functionality; GO/KEGG/Reactome/GSEA; publication-ready plots | R-only; richest ecosystem; `ReactomePA` extends to Reactome |
| **gseapy (Python)** | Python-only workflows; Enrichr API access | Simpler API; good for quick Enrichr queries; GSEA support is basic |

**Rule of thumb**: Use clusterProfiler for comprehensive pathway analysis with publication-quality visualization. Use gseapy only when constrained to Python or for quick Enrichr lookups.

---

## R: clusterProfiler

### GO Enrichment

```r
library(clusterProfiler)
library(org.Hs.eg.db)

# Gene list from DE results
sig_genes <- rownames(subset(res, padj < 0.05 & abs(log2FoldChange) > 1))
gene_entrez <- bitr(sig_genes, fromType='ENSEMBL', toType='ENTREZID', OrgDb=org.Hs.eg.db)$ENTREZID

# BP enrichment
go_bp <- enrichGO(gene=gene_entrez, OrgDb=org.Hs.eg.db, ont='BP', pAdjustMethod='BH', qvalueCutoff=0.05)
head(go_bp)

# Visualize
barplot(go_bp, showCategory=15)
dotplot(go_bp, showCategory=15)
```

### KEGG Pathways

```r
kegg <- enrichKEGG(gene=gene_entrez, organism='hsa', pAdjustMethod='BH', qvalueCutoff=0.05)
dotplot(kegg, showCategory=15)
```

### Reactome

```r
library(ReactomePA)
reactome <- enrichPathway(gene=gene_entrez, pvalueCutoff=0.05, readable=TRUE)
dotplot(reactome, showCategory=15)
```

### GSEA

```r
# Ranked gene list
ranked <- res_df$log2FoldChange
names(ranked) <- res_df$gene
ranked <- sort(ranked, decreasing=TRUE)

# Remove NAs and duplicates
ranked <- ranked[!is.na(ranked)]
# For duplicate symbols, choose the strategy that matches your biological question:
# max (magnitude) emphasizes strongest effect; mean smooths across transcripts
ranked <- tapply(ranked, names(ranked), max)

# KEGG GSEA (nPerm is deprecated in newer clusterProfiler versions)
gsea_kegg <- gseKEGG(geneList=ranked, organism='hsa', pAdjustMethod='BH')
gseaplot2(gsea_kegg, geneSetID=1:3)
```

---

## Python: gseapy

### Over-Representation Analysis

```python
import gseapy as gp

# Enrichr API
gene_list = sig['gene'].tolist()
enr = gp.enrichr(gene_list=gene_list, gene_sets='KEGG_2021_Human', organism='human', outdir='enrichr_kegg')
gp.barplot(enr.results, title='KEGG Enrichment')
```

### GSEA

```python
# Ranked list
rnk = res_df[['gene', 'log2FoldChange']].dropna()
rnk = rnk.groupby('gene').max().reset_index()
rnk = rnk.sort_values('log2FoldChange', ascending=False)
rnk.to_csv('gene.rnk', sep='\t', index=False, header=False)

# Run GSEA
# Note: parameter name may differ by gseapy version (data vs rnk); verify with help(gp.gsea)
gsea = gp.gsea(data='gene.rnk', gene_sets='KEGG_2021_Human', outdir='gsea_output')
```

---

## Visualization Best Practices

- **Bar plot**: Quick view of top enriched terms
- **Dot plot**: Shows term enrichment ratio and gene count
- **Network plot (cnetplot)**: Links genes to enriched terms
- **GSEA running enrichment plot**: Shows distribution of gene set enrichment

```r
cnetplot(go_bp, categorySize='pvalue', foldChange=ranked)
```

---

## Gene Set Variation Analysis (GSVA)

For scoring pathway activity per sample (rather than per comparison), use GSVA.

```r
library(GSVA)
library(org.Hs.eg.db)

# Build a gene set list from MSigDB (download .gmt files from https://www.gsea-msigdb.org/)
# Example using msigdbr:
# library(msigdbr)
# gene_sets <- split(msigdbr(species = 'Homo sapiens', category = 'H')$gene_symbol,
#                    msigdbr(species = 'Homo sapiens', category = 'H')$gs_name)
#
# Or manually define curated sets from your domain knowledge:
# gene_sets <- list(
#     HALLMARK_APOPTOSIS = c('BAX', 'BAK1', 'CASP3', 'CASP9', 'BCL2', ...),
#     HALLMARK_DNA_REPAIR = c('BRCA1', 'BRCA2', 'ATM', 'ATR', 'XRCC5', ...)
# )

# Use normalized expression matrix (e.g., vst or log2-TPM)
expr_mat <- assay(vsd)  # genes x samples

gsva_scores <- gsva(expr = expr_mat,
                    gset.idx.list = gene_sets,
                    method = 'gsva',
                    kcdf = 'Gaussian',
                    verbose = FALSE)
```

## Related Skills

- `bio-mrna-seq-differential-expression` - Generate DE input
- `bio-mrna-seq-pipeline` - End-to-end workflow
