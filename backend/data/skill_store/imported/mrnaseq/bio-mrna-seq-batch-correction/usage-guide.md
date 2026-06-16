# Usage Guide: bio-mrna-seq-batch-correction

## When to Use
Use this skill when exploratory QC reveals that samples cluster by technical batch rather than biological condition, or when samples were processed in multiple batches/sequencing runs.

## Inputs
- Raw or normalized count matrix
- Sample metadata with batch labels
- Known biological group information (to preserve)

## Outputs
- Batch-corrected count or expression matrix
- Before/after PCA plots
- Updated metadata with surrogate variables (SVA)

## Quick Start
### Correct Raw Counts (ComBat-Seq)
```r
library(sva)
corrected_counts <- ComBat_seq(counts=as.matrix(counts), batch=metadata$batch, group=metadata$condition)
```

### Correct Normalized Data (ComBat)
```r
corrected_norm <- ComBat(dat=norm_matrix, batch=metadata$batch, mod=model.matrix(~condition, metadata))
```

### Unknown Batch Effects (SVA)
```r
svaobj <- svaseq(as.matrix(counts), mod=mod, mod0=mod0)
metadata$SV1 <- svaobj$sv[,1]
```

## Tips
- **For DE analysis**, prefer including batch as a covariate in the design formula rather than pre-correcting counts.
- Use **ComBat-Seq** only for visualization/clustering when you need integer counts.
- Always benchmark with **PCA before and after** correction.

## Workflow Position
**Upstream**: `bio-mrna-seq-qc-exploratory` (batch detection)  
**Downstream**: `bio-mrna-seq-differential-expression` or `bio-mrna-seq-qc-exploratory`
