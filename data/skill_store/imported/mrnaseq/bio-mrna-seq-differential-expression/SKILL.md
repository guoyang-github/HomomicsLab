---
name: bio-mrna-seq-differential-expression
description: Differential expression analysis for bulk mRNA-seq. Covers DESeq2, edgeR, limma-voom (R), and PyDESeq2 (Python). Includes model fitting, contrast extraction, LFC shrinkage, result filtering, volcano/MA plots, and heatmaps. Use with prepared count matrices and metadata.
tool_type: mixed
primary_tool: DESeq2
---


Reference examples tested with: DESeq2 1.42+, edgeR 3.42+, limma 3.56+, PyDESeq2 0.4+, pheatmap 1.0.12+

# mRNA-seq Differential Expression

## Overview

Identify differentially expressed genes from bulk mRNA-seq count data using standard statistical frameworks in both R and Python.

## Framework Selection

| Framework | Best For | Key Strength |
|-----------|----------|--------------|
| **DESeq2** | General-purpose DE; small-to-moderate sample sizes | Stable shrinkage, excellent documentation, LFC shrinkage (apeglm) |
| **edgeR (glmQLF)** | When precise p-values matter; complex designs | QL F-test is robust to uncertainty in dispersion estimates |
| **limma-voom** | Large sample sizes; when prior information exists | Fast, borrows information across genes effectively |
| **PyDESeq2** | Python-only environments; integration with Python ML pipelines | API-close to R DESeq2, but less mature and API changes frequently |

**Rule of thumb**: Start with DESeq2 for most bulk RNA-seq DE analyses. Use edgeR glmQLF when you need the most accurate p-values under uncertainty. Use limma-voom for very large datasets (n > 100). Use PyDESeq2 only if you are constrained to a Python workflow.

---

## R: DESeq2

### Setup and Model Fitting

```r
library(DESeq2)

dds <- DESeqDataSetFromMatrix(
    countData = as.matrix(counts),
    colData = metadata,
    design = ~ condition
)

dds <- DESeq(dds)
```

For large datasets (many samples or high depth), use `glmGamPoi` as the fitting method. It is faster and often more numerically stable than the default negative binomial fitting.

```r
library(DESeq2)
# install glmGamPoi from Bioconductor if not already available
# BiocManager::install('glmGamPoi')

dds <- DESeqDataSetFromMatrix(
    countData = as.matrix(counts),
    colData = metadata,
    design = ~ condition
)
dds <- DESeq(dds, test='LRT', reduced=~1, fitType='glmGamPoi')
# NOTE: LRT + glmGamPoi may not be compatible in all DESeq2 versions.
# If you encounter an error, use Wald tests instead:
# dds <- DESeq(dds, fitType='glmGamPoi')
```

### Multi-Factor Design

```r
design(dds) <- ~ batch + condition
dds <- DESeq(dds)
```

### Extract Results

```r
# Basic results
res <- results(dds, contrast=c('condition', 'treated', 'control'), alpha=0.05)

# With LFC shrinkage (apeglm)
# Use contrast instead of coef to avoid dependency on factor level ordering
res_shrunk <- lfcShrink(dds, contrast=c('condition', 'treated', 'control'), type='apeglm')

# For complex contrasts or when apeglm fails, ashr is a robust general alternative
# res_shrunk <- lfcShrink(dds, contrast=c('condition', 'treated', 'control'), type='ashr')

res_df <- as.data.frame(res)
res_df$gene <- rownames(res_df)
```

### Filter Significant Genes

```r
sig_genes <- subset(res, padj < 0.05 & abs(log2FoldChange) > 1)
up_genes <- subset(res, padj < 0.05 & log2FoldChange > 1)
down_genes <- subset(res, padj < 0.05 & log2FoldChange < -1)
```

### Independent Hypothesis Weighting (IHW)

For improved power, use `IHW` to weight hypotheses by an informative covariate (e.g., mean of normalized counts).

```r
library(IHW)

res_ihw <- results(dds, contrast=c('condition', 'treated', 'control'), filterFun=ihw)
summary(res_ihw)
# Genes with padj < 0.1 are significant at FDR 10% (padj is already IHW-adjusted)
```

### Summary Statistics

```r
summary(res)
n_sig <- sum(res$padj < 0.05, na.rm=TRUE)
n_up <- sum(res$padj < 0.05 & res$log2FoldChange > 0, na.rm=TRUE)
n_down <- sum(res$padj < 0.05 & res$log2FoldChange < 0, na.rm=TRUE)
```

### Add Gene Annotations

```r
library(org.Hs.eg.db)
res_df$symbol <- mapIds(org.Hs.eg.db, keys=rownames(res_df),
                         column='SYMBOL', keytype='ENSEMBL', multiVals='first')
```

### Visualization

```r
plotMA(res)
plotDispEsts(dds)
plotCounts(dds, gene=which.min(res$padj), intgroup='condition')
```

---

## R: edgeR

```r
library(edgeR)

y <- DGEList(counts=counts, group=metadata$condition)
y <- calcNormFactors(y)

# Filter low counts
keep <- filterByExpr(y)
y <- y[keep, , keep.lib.sizes=TRUE]

design <- model.matrix(~ condition, data=metadata)
y <- estimateDisp(y, design)
fit <- glmQLFit(y, design)

# Inspect design matrix columns and build contrast
# For a 2-level factor with reference = control, the design only has an intercept and a
# single coefficient for conditiontreated (the effect of treated vs control).
# Use that coefficient directly instead of constructing a contrast of two non-existent columns.
print(colnames(design))
qlf <- glmQLFTest(fit, coef = 'conditiontreated')

results <- topTags(qlf, n=Inf)$table
sig_genes <- subset(results, FDR < 0.05 & abs(logFC) > 1)
```

---

## R: limma-voom

```r
library(limma)
library(edgeR)

# Prepare DGEList and apply TMM normalization
dge <- DGEList(counts=counts)
dge <- calcNormFactors(dge)

design <- model.matrix(~ condition, data=metadata)
v <- voom(dge, design, plot=TRUE)
fit <- lmFit(v, design)

fit <- eBayes(fit)
results <- topTable(fit, coef='conditiontreated', n=Inf)
```

---

## Python: PyDESeq2

### Quick Start

```python
import pandas as pd
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

# Load data (samples x genes)
counts_df = pd.read_csv('counts.csv', index_col=0).T
metadata = pd.read_csv('metadata.csv', index_col=0)

# Filter low-count genes using CPM > 0.5 in at least 3 samples
lib_sizes = counts_df.sum(axis=1)
cpm = counts_df.div(lib_sizes, axis=0) * 1e6
genes_to_keep = cpm.columns[(cpm > 0.5).sum(axis=0) >= 3]
counts_df = counts_df[genes_to_keep]

# Fit
# NOTE: PyDESeq2 APIs change frequently. Verify with pydeseq2.__version__ and help(DeseqDataSet)
dds = DeseqDataSet(counts=counts_df, metadata=metadata, design='~condition')
# Depending on version, use dds.fit_size_factors() + dds.fit_genewise_dispersions() + dds.fit_dispersion_trend() + dds.fit_LFC()
# or the convenience wrapper (if available in your installed version):
try:
    dds.deseq2()
except AttributeError:
    dds.fit_size_factors()
    dds.fit_genewise_dispersions()
    dds.fit_dispersion_trend()
    dds.fit_LFC()

# Contrast
stat_res = DeseqStats(dds, contrast=['condition', 'treated', 'control'])
stat_res.summary()
results_df = stat_res.results_df
```

### LFC Shrinkage

```python
# PyDESeq2 LFC shrinkage API varies by version; verify with help(stat_res.lfc_shrink)
try:
    stat_res.lfc_shrink(coeff='condition[T.treated]')
except (AttributeError, TypeError):
    print('LFC shrinkage not available or API changed in this PyDESeq2 version')
```

### Filter and Export

```python
sig = results_df[(results_df['padj'] < 0.05) & (abs(results_df['log2FoldChange']) > 1)]
sig.to_csv('significant_genes.csv')
```

---

## Visualization

### Volcano Plot (Python)

```python
import matplotlib.pyplot as plt
import numpy as np

# Warn: padj=0 is mathematically possible due to numeric underflow.
# Replacing 0 with the smallest positive float allows plotting but inflates the y-axis.
# An alternative is to cap at the machine minimum or use the raw p-value for visualization.
min_pos = np.nextafter(0, 1)
results_df['-log10_padj'] = -np.log10(results_df['padj'].replace(0, min_pos).fillna(1))

plt.scatter(results_df['log2FoldChange'], results_df['-log10_padj'],
            c=np.where(results_df['padj'] < 0.05, 'red', 'gray'), s=5)
plt.xlabel('log2 Fold Change')
plt.ylabel('-log10 adjusted p-value')
plt.axhline(-np.log10(0.05), color='blue', linestyle='--')
plt.savefig('volcano_plot.png')
```

### Heatmap of Top DEGs (R)

```r
library(pheatmap)

top_genes <- head(rownames(res[order(res$padj), ]), 50)
mat <- assay(vsd)[top_genes, ]
mat <- t(scale(t(mat)))

pheatmap(mat, annotation_col=metadata, cluster_cols=TRUE, show_rownames=TRUE)
```

For publication-quality complex layouts (split rows/columns, multiple annotations, legends), consider `ComplexHeatmap`:

```r
library(ComplexHeatmap)
library(circlize)

mat <- assay(vsd)[top_genes, ]
mat <- t(scale(t(mat)))

col_fun <- colorRamp2(c(-2, 0, 2), c('blue', 'white', 'red'))
ha <- HeatmapAnnotation(condition = metadata$condition)

Heatmap(mat, name = 'Z-score', top_annotation = ha,
        col = col_fun, cluster_columns = TRUE, show_row_names = TRUE)
```

---

## Export Results

```r
# CSV
write.csv(res_df, 'de_results.csv', row.names=FALSE)

# Excel workbook with sheets
library(openxlsx)
wb <- createWorkbook()
addWorksheet(wb, 'All Results'); writeData(wb, 'All Results', res_df)
addWorksheet(wb, 'Significant'); writeData(wb, 'Significant', sig_genes)
saveWorkbook(wb, 'de_results.xlsx', overwrite=TRUE)

# GSEA ranked list
gsea_input <- res_df[, c('gene', 'log2FoldChange')]
gsea_input <- gsea_input[order(-gsea_input$log2FoldChange), ]
write.table(gsea_input, 'gsea_input.rnk', sep='\t', quote=FALSE, row.names=FALSE, col.names=FALSE)
```

## Related Skills

- `bio-mrna-seq-count-prep` - Prepare input data
- `bio-mrna-seq-qc-exploratory` - Inspect sample quality
- `bio-mrna-seq-pathway-enrichment` - Functional interpretation
- `bio-mrna-seq-pipeline` - End-to-end workflow
