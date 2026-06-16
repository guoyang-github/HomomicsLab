---
name: bio-mrna-seq-wgcna
description: Weighted gene co-expression network analysis (WGCNA) for bulk mRNA-seq. Covers data preprocessing, soft-threshold selection, module detection, eigengene-trait correlations, and hub gene extraction. Use for discovering co-expression modules and trait associations.
tool_type: mixed
primary_tool: WGCNA
---


Reference examples tested with: WGCNA 1.72+, hdWGCNA 0.2+, omicverse 1.6+, statsmodels 0.14+

# mRNA-seq WGCNA

## Overview

Construct weighted gene co-expression networks from bulk mRNA-seq data to identify modules of co-expressed genes and their association with sample traits.

## Tool Selection

| Tool | Best For | Scale |
|------|----------|-------|
| **WGCNA** | Standard bulk RNA-seq; 20–500 samples | Genes: 2,000–20,000 |
| **hdWGCNA** | High-dimensional data; single-cell RNA-seq; very large bulk datasets | Genes: >20,000; metacell construction reduces noise |
| **omicverse PyWGCNA** | Python-only workflows; integration with scanpy/omicverse ecosystem | Similar to WGCNA |

**Rule of thumb**: Use standard WGCNA for typical bulk RNA-seq. Use hdWGCNA when working with single-cell data or when the gene count exceeds ~20,000. Use omicverse only if you need to stay in Python.

## R: WGCNA

### Setup

```r
library(WGCNA)

# Transpose to samples x genes
datExpr <- t(log2(counts + 1))

# Filter most variable genes (e.g., top 5000)
vars <- apply(datExpr, 2, var)
datExpr <- datExpr[, order(vars, decreasing=TRUE)[1:5000]]
```

### Soft-Threshold Selection

```r
powers <- c(1:20)
sft <- pickSoftThreshold(datExpr, powerVector=powers, verbose=5)

plot(sft$fitIndices[,1], -sign(sft$fitIndices[,3])*sft$fitIndices[,2],
     xlab='Soft Threshold (power)', ylab='Scale Free Topology Model Fit')
abline(h=0.9, col='red')
```

### Network Construction

```r
# Use the power estimated from pickSoftThreshold, or a sensible default
power <- sft$powerEstimate
if (is.na(power)) power <- 6

net <- blockwiseModules(datExpr, power=power, TOMType='unsigned',
                        minModuleSize=30, reassignThreshold=0,
                        mergeCutHeight=0.25, numericLabels=TRUE,
                        pamRespectsDendro=FALSE, verbose=3)

# Module colors
moduleColors <- labels2colors(net$colors)
```

### Module-Trait Relationships

```r
MEs <- net$MEs
traitData <- metadata[, c('condition', 'age')]

moduleTraitCor <- cor(MEs, traitData, use='p')
moduleTraitPvalue <- corPvalueStudent(moduleTraitCor, nSamples=nrow(datExpr))

# Heatmap
textMatrix <- paste(signif(moduleTraitCor, 2), '\n(', signif(moduleTraitPvalue, 1), ')', sep='')
dim(textMatrix) <- dim(moduleTraitCor)

labeledHeatmap(Matrix=moduleTraitCor, xLabels=names(traitData),
               yLabels=names(MEs), colorLabels=FALSE,
               colors=blueWhiteRed(50), textMatrix=textMatrix,
               setStdMargins=TRUE, cex.text=0.5, zlim=c(-1,1))
```

### Hub Genes

```r
# Top hub genes in a module
geneModuleMembership <- as.data.frame(cor(datExpr, MEs, use='p'))
MMPvalue <- as.data.frame(corPvalueStudent(as.matrix(geneModuleMembership), nSamples=nrow(datExpr)))

module <- 'MEblue'
hub_genes <- names(sort(abs(geneModuleMembership[[module]]), decreasing=TRUE))[1:30]
```

## R: hdWGCNA (High-Dimensional WGCNA)

hdWGCNA extends WGCNA for large-scale datasets (e.g., scRNA-seq or high-depth bulk RNA-seq) by enabling metacell construction and module preservation across conditions.

```r
library(Seurat)
library(hdWGCNA)

# seurat_obj: a Seurat object with log-normalized expression
seurat_obj <- SetupForWGCNA(
    seurat_obj,
    gene_select = 'fraction',
    fraction = 0.05,
    wgcna_name = 'hdwgcna'
)

# Construct metacells
seurat_obj <- MetacellsByGroups(
    seurat_obj = seurat_obj,
    group.by = 'condition',
    reduction = 'pca',
    k = 25,
    max_shared = 10,
    ident.group = 'condition'
)

# Normalize metacell expression
seurat_obj <- NormalizeMetacells(seurat_obj)

# Select soft-threshold power and construct network
seurat_obj <- SetDatExpr(seurat_obj, group_name = 'treated', group.by='condition')
seurat_obj <- TestSoftPowers(seurat_obj)
seurat_obj <- ConstructNetwork(seurat_obj, soft_power=8)

# Module eigengenes and trait associations
seurat_obj <- ModuleEigengenes(seurat_obj, group.by='condition')
seurat_obj <- ModuleConnectivity(seurat_obj)
plot_list <- ModuleCorrelogram(seurat_obj)
```

## Python: omicverse PyWGCNA

```python
import omicverse as ov
from statsmodels import robust

# counts: genes x samples. Compute MAD per gene (axis=1) and select top variable genes.
mad = counts.apply(robust.mad, axis=1)
data = counts.loc[mad.sort_values(ascending=False).index[:2000]].T

wgcna = ov.bulk.pyWGCNA(name='project', species='human', geneExp=data, outputPath='', save=True)
wgcna.preprocess()
wgcna.calculate_soft_threshold()
wgcna.calculating_adjacency_matrix()
wgcna.calculating_TOM_similarity_matrix()
wgcna.calculate_geneTree()
wgcna.calculate_dynamicMods(
    kwargs_function={
        'cutreeHybrid': {
            'deepSplit': 2,
            'minClusterSize': 30,
            'pamRespectsDendro': False
        }
    }
)
wgcna.calculate_gene_module(kwargs_function={'moduleEigengenes': {'softPower': 8}})
```

## Related Skills

- `bio-mrna-seq-count-prep` - Prepare expression matrix
- `bio-mrna-seq-qc-exploratory` - Sample QC before network building
- `bio-mrna-seq-pipeline` - End-to-end workflow
