# Usage Guide: bio-mrna-seq-timeseries

## When to Use
Use this skill when your experiment involves multiple time points (e.g., drug treatment over 0h, 2h, 6h, 24h) and you want to identify genes with dynamic expression patterns rather than simple pairwise comparisons.

## Inputs
- Time-course count matrix
- Sample metadata with `time`, `condition`, and `replicate` columns

## Outputs
- Genes with significant temporal dynamics
- Trajectory plots and impulse/spline fits
- Gene clustering by temporal profile

## Quick Start
### limma with Splines (smooth continuous time)
```r
library(limma)
library(edgeR)
library(splines)

dge <- DGEList(counts=counts)
dge <- calcNormFactors(dge)
keep <- filterByExpr(dge)
dge <- dge[keep, , keep.lib.sizes=TRUE]

n_time <- length(unique(metadata$time))
df_spline <- min(3, max(1, n_time - 1))
time_ns <- ns(metadata$time, df=df_spline)
design <- model.matrix(~ time_ns)

v <- voom(dge, design, plot=TRUE)
fit <- lmFit(v, design)
fit <- eBayes(fit)

spline_coefs <- grep("time_ns", colnames(design), value=TRUE)
top <- topTable(fit, coef=spline_coefs, n=Inf, sort.by='F')
```

### maSigPro (regression-based)
```r
edesign <- cbind(Time=metadata$time, Replicate=as.numeric(metadata$replicate),
                 Control=ifelse(metadata$condition=='control',1,0),
                 Treated=ifelse(metadata$condition=='treated',1,0))
design <- make.design.matrix(edesign, degree=2)
fit <- p.vector(counts, design, Q=0.05)
sigs <- Tfit(fit, step.method='backward', alfa=0.05)
```

## Tips
- **limma splines** work best for continuous time with smooth trajectories.
- **ImpulseDE2** is ideal for transient up/down impulses.
- **DESeq2 LRT** can test any time effect by comparing full (`~ time`) vs reduced (`~ 1`) models.

## Workflow Position
**Upstream**: `bio-mrna-seq-count-prep`  
**Downstream**: `bio-mrna-seq-pathway-enrichment` (time-clustered gene lists)
