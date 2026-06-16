---
name: bio-mrna-seq-deconvolution
description: Bulk mRNA-seq deconvolution and cell fraction estimation. Covers MuSiC, BSEQ-sc, and omicverse Bulk2Single for reconstructing cell-type proportions or synthetic single-cell profiles. Use when estimating cell-type composition from bulk RNA-seq.
tool_type: mixed
primary_tool: MuSiC
---


Reference examples tested with: MuSiC 1.0+, EPIC 1.1+, xCell 1.3+, MCPcounter 1.2+, BayesPrism 2.0+, omicverse 1.6+

# mRNA-seq Deconvolution

## Overview

Estimate cell-type proportions from bulk RNA-seq data or generate synthetic single-cell profiles using reference scRNA-seq atlases.

## MuSiC (R)

```r
library(MuSiC)

# bulk.eset: ExpressionSet of bulk RNA-seq
# sc.eset: ExpressionSet of single-cell reference

estimates <- music_prop(
    bulk.mtx = exprs(bulk.eset),
    sc.sce = sc.eset,
    clusters = 'cell_type',
    samples = 'sample_id',
    select.ct = NULL,
    verbose = TRUE
)
```

## EPIC (R)

EPIC estimates cell fractions using gene expression signatures curated specifically for tumor-infiltrating immune and stromal cells.

```r
library(EPIC)

# bulk: genes x samples matrix (TPM or counts)
epic_res <- EPIC(bulk = bulk_matrix)
fractions <- epic_res$cellFractions
```

## xCell (R)

xCell performs enrichment-based deconvolution to infer cell type enrichments (not absolute fractions). Best for comparing relative abundance across samples.

```r
library(xCell)

# bulk: genes x samples matrix
# Returns enrichment scores, not proportions
xcell_scores <- xCellAnalysis(bulk_matrix)
```

## MCPcounter (R)

MCPcounter estimates the absolute abundance of immune and stromal cell populations using lineage-specific genes.

```r
library(MCPcounter)

# MCPcounter requires probes/genes as rownames and samples as columns
mcp_scores <- MCPcounter.estimate(
    expression = bulk_matrix,
    featuresType = 'HUGO_symbols'  # or 'ENSEMBL_ID', 'AFFY'
)
```

## BayesPrism (Python/R)

BayesPrism is a Bayesian deconvolution framework that models cell-type-specific gene expression and its variation, improving accuracy in tumor samples.

```python
# Python workflow via the BayesPrism package (install from GitHub)
from BayesPrism import *

# bulk: samples x genes
# sc_ref: single-cell reference with cell type and sample annotations
bp = new.BayesPrism(
    bulk_dat = bulk_matrix.T,
    cell_type_labels = sc_ref['cell_type'],
    cell_state_labels = sc_ref['cell_subtype'],
    sc_dat = sc_ref_expression.T
)

# Run deconvolution
bp_res = run.prism(bp, n_cores = 8)
fractions = bp_res.posterior_initial.theta
```

## omicverse Bulk2Single (Python)

```python
import omicverse as ov
import scanpy as sc

# Load bulk counts and reference scRNA-seq
bulk = ov.utils.read('bulk_counts.csv')
adata = sc.read_h5ad('reference_sc.h5ad')

# Initialize
model = ov.bulk2single.Bulk2Single(
    bulk_data=bulk,
    single_data=adata,
    celltype_key='cell_type',
    bulk_group=['sample1', 'sample2'],
    top_marker_num=200,
    ratio_num=1,
    gpu=0
)

# Estimate fractions
fractions = model.predicted_fraction()

# Train beta-VAE and generate synthetic cells
model.bulk_preprocess_lazy()
model.single_preprocess_lazy()
model.prepare_input()
model.train(batch_size=512, learning_rate=1e-4, hidden_size=256,
            epoch_num=3500, vae_save_dir='./', vae_save_name='vae',
            generate_save_dir='./', generate_save_name='cells')

generated = model.generate()
filtered = model.filtered(generated, leiden_size=25)
```

## Tool Selection

| Tool | Input | Output | Best For |
|------|-------|--------|----------|
| MuSiC | Counts + sc reference | Cell fractions | Cross-tissue, cross-platform |
| EPIC | TPM/counts | Cell fractions | Tumor microenvironment (immune + stromal) |
| xCell | TPM/counts | Enrichment scores | Relative immune/stromal abundance |
| MCPcounter | TPM/counts | Abundance scores | Immune and stromal lineage abundance |
| BayesPrism | Counts + sc reference | Cell fractions | Tumor samples, expression variation |
| Bulk2Single | Counts + sc reference | Synthetic sc profiles | Generative deconvolution |

## Related Skills

- `bio-mrna-seq-count-prep` - Prepare bulk expression matrix
- `bio-mrna-seq-pipeline` - End-to-end workflow
