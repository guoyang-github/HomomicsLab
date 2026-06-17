# Usage Guide: bio-mrna-seq-qc-exploratory

## When to Use
Use this skill after count matrix preparation to validate sample quality, detect outliers, and inspect batch effects before running differential expression.

## Inputs
- Clean count matrix (genes × samples)
- Sample metadata with condition, batch, and other covariates

## Outputs
- PCA plots (colored by condition/batch)
- Sample correlation/distance heatmaps
- Outlier report (sample IDs with extreme PC z-scores)
- Library complexity plots

## Quick Start
1. **Normalize** for visualization: DESeq2 `vst()` or `rlog()` in R; log2 CPM in Python.
2. **Run PCA** and color by condition and batch.
3. **Check sample clustering** — biological replicates should cluster together.
4. **Flag outliers** — samples with |z-score| > 3 on PC1 or PC2 warrant investigation.

## Tips
- **VST** is fast and good for n > 30; **rlog** is better for small sample sizes.
- If samples cluster strongly by batch rather than condition, proceed to `bio-mrna-seq-batch-correction` or include batch in the DE design.
- Do not remove outliers blindly — check upstream QC metrics first.

## Workflow Position
**Upstream**: `bio-mrna-seq-count-prep`  
**Downstream**: `bio-mrna-seq-differential-expression` or `bio-mrna-seq-batch-correction`
