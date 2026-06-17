---
name: bio-mrna-seq-batch-correction
description: Batch effect correction for bulk mRNA-seq count and normalized expression matrices. Covers ComBat-Seq (counts), ComBat (normalized), limma removeBatchEffect, SVA for unknown batches, and omicverse pyComBat. Use when samples were processed across multiple batches.
tool_type: mixed
primary_tool: sva
---


Reference examples tested with: sva 3.50+, limma 3.56+, omicverse 1.6+

# mRNA-seq Batch Correction

## Overview

Remove technical batch effects from bulk mRNA-seq data while preserving biological variation.

## ComBat-Seq (Raw Counts)

```r
library(sva)

corrected_counts <- ComBat_seq(
    counts = as.matrix(counts),
    batch = metadata$batch,
    group = metadata$condition,
    full_mod = TRUE
)
```

**Note**: Use corrected counts for visualization and clustering, but prefer including batch in the DE design formula rather than pre-correcting counts for DE.

## ComBat (Normalized Data)

```r
library(sva)

mod <- model.matrix(~ condition, data = metadata)
corrected_norm <- ComBat(dat = norm_matrix, batch = metadata$batch, mod = mod)
```

## limma removeBatchEffect

```r
library(limma)

design <- model.matrix(~ condition, data = metadata)
corrected_vst <- removeBatchEffect(vst_matrix, batch = metadata$batch, design = design)
```

## SVA (Unknown Batch Variables)

```r
library(sva)

mod <- model.matrix(~ condition, data = metadata)
mod0 <- model.matrix(~ 1, data = metadata)

# Estimate surrogate variables
svaobj <- svaseq(as.matrix(counts), mod = mod, mod0 = mod0, n.sv = NULL)

# Include surrogate variables in design
metadata$SV1 <- svaobj$sv[, 1]
metadata$SV2 <- svaobj$sv[, 2]

design <- model.matrix(~ condition + SV1 + SV2, data = metadata)
```

## Python: omicverse pyComBat

```python
import omicverse as ov
import anndata

adata = anndata.AnnData(X=counts.T)
adata.obs = metadata
ov.bulk.batch_correction(adata, batch_key='batch')
corrected = adata.to_df(layer='batch_correction').T
```

## Benchmarking

Always compare PCA before and after correction:
- **Before**: Samples cluster by batch
- **After**: Samples from the same condition mix across batches

## Related Skills

- `bio-mrna-seq-qc-exploratory` - Inspect batch effects
- `bio-mrna-seq-differential-expression` - Include batch in design
- `bio-mrna-seq-pipeline` - End-to-end workflow
