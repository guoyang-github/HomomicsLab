# Usage Guide: bio-mrna-seq-wgcna

## When to Use
Use this skill when you want to discover co-expressed gene modules from bulk mRNA-seq data and relate them to sample traits (e.g., disease status, age, treatment response).

## Inputs
- Normalized or log-transformed expression matrix (samples × genes)
- Sample trait metadata

## Outputs
- Co-expression module assignments (gene → module color)
- Module eigengenes (MEs) per sample
- Module-trait correlation heatmap
- Hub gene lists per module

## Quick Start
1. **Filter** to the most variable genes (e.g., top 5,000 by MAD or variance).
2. **Pick soft-threshold power** using `pickSoftThreshold()` (target scale-free R² > 0.9).
3. **Build network** with `blockwiseModules()`.
4. **Correlate modules** with traits using `cor(MEs, traitData)`.
5. **Extract hub genes** from modules of interest.

## Tips
- WGCNA is **computationally intensive** — start with 2,000–10,000 most variable genes.
- Modules with high trait correlation are biologically interesting; inspect their hub genes.
- Grey module = unassigned genes.
- Consider merging highly similar modules (`mergeCutHeight` parameter).
- For very large datasets or single-cell data, use **hdWGCNA** instead of standard WGCNA.

## Workflow Position
**Upstream**: `bio-mrna-seq-count-prep` or `bio-mrna-seq-differential-expression`  
**Downstream**: `bio-mrna-seq-pathway-enrichment` (module gene lists), `bio-mrna-seq-ppi`
