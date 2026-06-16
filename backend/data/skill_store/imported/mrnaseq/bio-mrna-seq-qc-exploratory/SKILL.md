---
name: bio-mrna-seq-qc-exploratory
description: Exploratory data analysis and quality control of prepared bulk mRNA-seq count matrices. Covers normalization (VST/rlog/log2CPM), PCA, sample clustering, outlier detection, batch inspection, and library complexity checks. Use before differential expression.
tool_type: mixed
primary_tool: DESeq2
---


Reference examples tested with: DESeq2 1.42+, pheatmap 1.0.12+, scikit-learn 1.3+

# mRNA-seq Exploratory QC

## Overview

Assess sample quality, batch effects, and biological signal in a prepared count matrix before differential expression analysis.

---

## 1. Normalization for Visualization

### R: DESeq2 VST / rlog

```r
library(DESeq2)

dds <- DESeqDataSetFromMatrix(countData=counts, colData=metadata, design=~ condition)

# Variance stabilizing transformation (fast, good for n > 30)
vsd <- vst(dds, blind=TRUE)

# Regularized log (better for small n)
rld <- rlog(dds, blind=TRUE)

norm_matrix <- assay(vsd)
```

### Python: log2 CPM

```python
import numpy as np

# Normalize per-column (library-size-aware)
cpm = counts.div(counts.sum(axis=0), axis=1) * 1e6
log_cpm = np.log2(cpm + 1)
```

---

## 2. PCA

### R

```r
plotPCA(vsd, intgroup=c('condition', 'batch'))

# Custom PCA
pca <- prcomp(t(norm_matrix))
pca_df <- data.frame(PC1=pca$x[,1], PC2=pca$x[,2], metadata)

ggplot(pca_df, aes(PC1, PC2, color=condition, shape=batch)) +
    geom_point(size=3) +
    xlab(paste0('PC1 (', round(summary(pca)$importance[2,1]*100, 1), '%)')) +
    ylab(paste0('PC2 (', round(summary(pca)$importance[2,2]*100, 1), '%)'))
```

### Python

```python
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt

pca = PCA(n_components=2)
pca_result = pca.fit_transform(log_cpm.T)

plt.figure(figsize=(8, 6))
for condition in metadata['condition'].unique():
    mask = metadata['condition'] == condition
    plt.scatter(pca_result[mask, 0], pca_result[mask, 1], label=condition)
plt.xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%})')
plt.ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%})')
plt.legend()
plt.savefig('pca_plot.png')
```

---

## 3. Sample Correlation and Clustering

### R

```r
library(pheatmap)

sample_cor <- cor(norm_matrix)
pheatmap(sample_cor, annotation_col=metadata[, c('condition', 'batch')])

sample_dist <- dist(t(norm_matrix))
pheatmap(as.matrix(sample_dist), annotation_col=metadata[, c('condition', 'batch')])
```

### Python

```python
import seaborn as sns

sample_cor = log_cpm.corr()
sns.clustermap(sample_cor, annot=True, cmap='RdBu_r', center=0.9,
               vmin=0.8, vmax=1.0)
plt.savefig('sample_correlation.png')
```

---

## 4. Detect Outliers

### R

```r
# Z-score method on PC1/PC2
z_pc1 <- scale(pca$x[,1])
z_pc2 <- scale(pca$x[,2])
outliers <- abs(z_pc1) > 3 | abs(z_pc2) > 3
metadata$sample_id[outliers]
```

### Python

```python
from scipy import stats

z_scores = stats.zscore(pca_result, axis=0)
outliers = (np.abs(z_scores) > 3).any(axis=1)
print('Potential outliers:', counts.columns[outliers].tolist())
```

---

## 5. Batch Effect Inspection

### R

```r
# Visualize batch in PCA
plotPCA(vsd, intgroup=c('condition', 'batch'))

# Test batch in model
design(dds) <- ~ batch + condition
dds <- DESeq(dds)
```

### Python

```python
# Color PCA by batch
for batch in metadata['batch'].unique():
    mask = metadata['batch'] == batch
    plt.scatter(pca_result[mask, 0], pca_result[mask, 1],
                label=f'Batch {batch}', marker=['o','s','^'][list(metadata['batch'].unique()).index(batch)])
```

---

## 6. Library Complexity

```r
# Genes detected vs library size
plot(colSums(counts(dds)), colSums(counts(dds) > 0),
     xlab='Library Size', ylab='Genes Detected',
     pch=19, col=metadata$condition)
```

```python
plt.scatter(counts.sum(), (counts > 0).sum())
plt.xlabel('Total Counts')
plt.ylabel('Genes Detected')
plt.savefig('library_complexity.png')
```

---

## 7. Gene Expression Distribution

```r
boxplot(log2(counts(dds) + 1), las=2, main='Log2 Counts per Sample')
```

---

## Interpretation Checklist

| Observation | Interpretation | Action |
|-------------|----------------|--------|
| Samples cluster by condition | Good biological signal | Proceed |
| Samples cluster by batch | Batch effect present | Include batch in design; consider correction |
| One sample far from its group | Potential outlier | Investigate QC metrics; consider removal |
| No clustering by condition | Low biological signal or high noise | Check library prep / metadata accuracy |
| Large PC3/PC4 variance | Additional structure (e.g., sex, age) | Inspect loadings; adjust design if known |

## Related Skills

- `bio-mrna-seq-count-prep` - Prepare input matrix
- `bio-mrna-seq-batch-correction` - Correct batch effects
- `bio-mrna-seq-differential-expression` - Downstream DE analysis
- `bio-mrna-seq-pipeline` - End-to-end workflow
