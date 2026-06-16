# Usage Guide: bio-mrna-seq-deconvolution

## When to Use
Use this skill when you need to estimate cell-type proportions from bulk RNA-seq data or generate synthetic single-cell profiles using a reference scRNA-seq atlas.

## Inputs
- Bulk RNA-seq count or TPM matrix
- Reference scRNA-seq dataset with annotated cell types

## Outputs
- Cell fraction estimates per sample
- Synthetic single-cell AnnData (Bulk2Single)
- Correlation/composition benchmarking plots

## Quick Start

### MuSiC (R)
```r
estimates <- music_prop(bulk.mtx=bulk, sc.sce=sc_ref, clusters='cell_type')
```

### EPIC (R — Tumor Microenvironment)
```r
epic_res <- EPIC(bulk = bulk_matrix)
fractions <- epic_res$cellFractions
```

### xCell (R — Enrichment Scores)
```r
xcell_scores <- xCellAnalysis(bulk_matrix)
```

### MCPcounter (R — Immune/Stromal Lineages)
```r
mcp_scores <- MCPcounter.estimate(expression = bulk_matrix, featuresType = 'HUGO_symbols')
```

### BayesPrism (Python/R — Tumor-Aware Bayesian)
```python
bp = new.BayesPrism(bulk_dat=bulk_matrix.T, sc_dat=sc_ref_expression.T,
                    cell_type_labels=sc_ref['cell_type'])
bp_res = run.prism(bp)
fractions = bp_res.posterior_initial.theta
```

### omicverse Bulk2Single (Python)
```python
model = ov.bulk2single.Bulk2Single(bulk_data=bulk, single_data=adata, celltype_key='cell_type')
fractions = model.predicted_fraction()
model.train(epoch_num=3500)
generated = model.generate()
```

## Tips
- **Reference atlas quality** is the biggest determinant of accuracy — use a well-annotated, matched tissue.
- **No single tool is perfect**: EPIC uses signature matrices; MuSiC and BayesPrism use scRNA-seq references; xCell and MCPcounter return enrichment/abundance scores rather than absolute fractions.
- Bulk2Single is GPU-accelerated; training on CPU can take hours.
- Validate estimated fractions against known biological expectations.

## Workflow Position
**Upstream**: `bio-mrna-seq-count-prep`  
**Downstream**: Cell-type-specific downstream analysis, benchmarking
