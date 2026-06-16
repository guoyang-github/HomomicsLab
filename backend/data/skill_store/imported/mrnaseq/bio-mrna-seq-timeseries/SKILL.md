---
name: bio-mrna-seq-timeseries
description: Time-series and longitudinal differential expression analysis for bulk mRNA-seq. Covers limma with splines, maSigPro, ImpulseDE2, and DESeq2 LRT for temporal patterns. Use when analyzing time-course expression data.
tool_type: r
primary_tool: limma
---


Reference examples tested with: limma 3.56+, edgeR 3.42+, maSigPro 1.72+, ImpulseDE2 1.24+, DESeq2 1.42+

# mRNA-seq Time-Series Analysis

## Overview

Identify genes with dynamic expression patterns across time points in longitudinal RNA-seq experiments.

## limma with Splines

```r
library(limma)
library(edgeR)
library(splines)

dge <- DGEList(counts=counts)
dge <- calcNormFactors(dge)
keep <- filterByExpr(dge)
dge <- dge[keep, , keep.lib.sizes=TRUE]

# Natural spline basis for time
# Choose df based on number of time points: df ≈ min(3, n_timepoints - 1)
n_time <- length(unique(metadata$time))
df_spline <- min(3, max(1, n_time - 1))
time_ns <- ns(metadata$time, df=df_spline)
design <- model.matrix(~ time_ns)

v <- voom(dge, design, plot=TRUE)
fit <- lmFit(v, design)
fit <- eBayes(fit)

# Test all non-intercept spline coefficients dynamically
spline_coefs <- grep("time_ns", colnames(design), value=TRUE)
if (length(spline_coefs) == 0) {
    stop("No spline coefficients found in design matrix. Inspect colnames(design).")
}
top <- topTable(fit, coef=spline_coefs, n=Inf, sort.by='F')
```

## maSigPro

```r
library(maSigPro)

# Design: time + condition + replicate
# Replicate must be numeric; convert factor replicates to integers if necessary
edesign <- cbind(Time=metadata$time, Replicate=as.numeric(metadata$replicate),
                 Control=ifelse(metadata$condition=='control',1,0),
                 Treated=ifelse(metadata$condition=='treated',1,0))

design <- make.design.matrix(edesign, degree=2)
fit <- p.vector(counts, design, Q=0.05, MT.adjust='BH', min.obs=20)
sigs <- Tfit(fit, step.method='backward', alfa=0.05)
```

## ImpulseDE2

```r
library(ImpulseDE2)

df_annotation <- data.frame(
    Sample=colnames(counts),
    Condition=metadata$condition,
    Time=metadata$time,
    Batch=metadata$batch,
    row.names=colnames(counts)
)

impulse_results <- ImpulseDE2(
    counts = as.matrix(counts),
    annotation = df_annotation,
    colname_time = 'Time',
    colname_condition = 'Condition',
    case_control = TRUE,
    control_gene = NULL,
    n_process = 8
)
```

## DESeq2 LRT (Discrete Time)

```r
# Full model with time as factor
full <- ~ time
reduced <- ~ 1

dds <- DESeqDataSetFromMatrix(countData=counts, colData=metadata, design=full)
dds$time <- factor(dds$time)
dds <- DESeq(dds, test='LRT', reduced=reduced)
res <- results(dds)
```

## Method Selection

| Method | Best For |
|--------|----------|
| limma splines | Smooth continuous time |
| maSigPro | Multiple time points with replicates |
| ImpulseDE2 | Impulse-like up/down patterns |
| DESeq2 LRT | Discrete time comparisons |

## Related Skills

- `bio-mrna-seq-differential-expression` - Standard DE frameworks
- `bio-mrna-seq-pipeline` - End-to-end workflow
