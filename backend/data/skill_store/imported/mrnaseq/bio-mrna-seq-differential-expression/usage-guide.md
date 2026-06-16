# Usage Guide: bio-mrna-seq-differential-expression

## When to Use
Use this skill when you have a prepared count matrix and metadata and want to identify genes that are differentially expressed between conditions.

## Inputs
- Filtered raw count matrix (genes × samples)
- Sample metadata with design variables (condition, batch, covariates)
- Contrasts of interest (e.g., treated vs control)

## Outputs
- Differential expression results table (log2FC, p-value, padj)
- Significant gene lists (up/down-regulated)
- Volcano plots, MA plots, heatmaps
- GSEA-ranked gene list

## Quick Start
### R: DESeq2
```r
dds <- DESeqDataSetFromMatrix(countData=counts, colData=metadata, design=~ condition)
dds <- DESeq(dds)
res <- results(dds, contrast=c('condition', 'treated', 'control'), alpha=0.05)
```

### Python: PyDESeq2
```python
dds = DeseqDataSet(counts=counts_df, metadata=metadata, design='~condition')
# Check pydeseq2 version; API may require explicit fitting steps
dds.deseq2()
stat_res = DeseqStats(dds, contrast=['condition', 'treated', 'control'])
```

## Tips
- **Use raw counts** — never input TPM, CPM, or log-transformed data to DESeq2/edgeR.
- **Include batch in design** rather than pre-correcting counts when possible.
- **LFC shrinkage** (`apeglm` or `ashr`) improves interpretability for low-count genes.
- **Large datasets**: use `fitType='glmGamPoi'` in `DESeq()` for faster, more stable fitting.
- **Power**: consider `IHW` for multiple-testing correction when you have an informative covariate (e.g., mean count).
- Typical thresholds: padj < 0.05 and |log2FC| > 1.

## Workflow Position
**Upstream**: `bio-mrna-seq-count-prep` or `bio-mrna-seq-qc-exploratory`  
**Downstream**: `bio-mrna-seq-pathway-enrichment`, `bio-mrna-seq-ppi`, or `bio-mrna-seq-wgcna`
