# Usage Guide: bio-mrna-seq-pathway-enrichment

## When to Use
Use this skill after differential expression analysis to interpret gene lists biologically through functional enrichment and gene set analysis.

## Inputs
- Differential expression results (full table or significant gene list)
- Optional: background gene list (all genes tested)
- Organism specification (human, mouse, etc.)

## Outputs
- Enrichment tables (GO, KEGG, Reactome) with p-values and q-values
- GSEA results (ranked list enrichment)
- Visualization plots: dot plots, bar plots, network plots, GSEA curves

## Quick Start
### Over-Representation Analysis (R)
```r
sig_genes <- rownames(subset(res, padj < 0.05 & abs(log2FoldChange) > 1))
go_bp <- enrichGO(gene=sig_genes, OrgDb=org.Hs.eg.db, ont='BP')
dotplot(go_bp, showCategory=15)
```

### GSEA (Python)
```python
rnk = res_df[['gene', 'log2FoldChange']].sort_values('log2FoldChange', ascending=False)
gsea = gp.gsea(data='gene.rnk', gene_sets='KEGG_2021_Human', outdir='gsea_output')
```

## Tips
- **Map to Entrez IDs** for KEGG/Reactome if starting from Ensembl/symbols.
- Use **qvalue < 0.05** or **FDR < 0.25** (GSEA) as significance thresholds.
- Combine multiple ontologies (BP + MF + KEGG) for a comprehensive view.

## Workflow Position
**Upstream**: `bio-mrna-seq-differential-expression`  
**Downstream**: Publication figures, biological interpretation
