---
name: bio-mrna-seq-pipeline
description: End-to-end bulk mRNA-seq best-practice workflow from FASTQ to pathway enrichment. Orchestrates QC, alignment/quantification, count prep, exploratory QC, differential expression, and functional interpretation. Use as the master skill for complete mRNA-seq projects.
tool_type: mixed
primary_tool: mixed
workflow: true
---


Reference examples tested with: fastp 0.23+, STAR 2.7.11b+, featureCounts 2.0.6+, Salmon 1.10+, DESeq2 1.42+, clusterProfiler 4.10+

# mRNA-seq Best-Practice Pipeline

## Overview

This skill orchestrates the complete bulk mRNA-seq analysis workflow from raw FASTQ files to biological interpretation. It links all standard `bio-mrna-seq-*` skills into a coherent, checkpoint-driven pipeline.

## Pipeline Flow

```
Raw FASTQ
    |
    v
[1. QC & Preprocessing] ---- bio-mrna-seq-qc-preprocessing
    |
    v
[2. Alignment / Quantification] ---- bio-mrna-seq-alignment  OR  bio-mrna-seq-quantification
    |
    v
[3. Count Matrix Preparation] ---- bio-mrna-seq-count-prep
    |
    v
[4. Exploratory QC] ---- bio-mrna-seq-qc-exploratory
    |
    v
[5. Differential Expression] ---- bio-mrna-seq-differential-expression
    |
    v
[6. Pathway Enrichment] ---- bio-mrna-seq-pathway-enrichment
```

## Stage 1: QC and Preprocessing

**Goal**: Ensure high-quality reads before alignment.

```bash
fastqc *.fastq.gz -t 8 -o fastqc_output/
fastp -i sample_R1.fastq.gz -I sample_R2.fastq.gz \
    -o sample_clean_R1.fastq.gz -O sample_clean_R2.fastq.gz \
    --detect_adapter_for_pe --cut_front --cut_tail \
    --cut_window_size 4 --cut_mean_quality 20 --length_required 36
multiqc fastqc_output/ . --outdir multiqc/
```

**QC Checkpoints**:
- Per-base Q30 > 80%
- Adapter content < 5%

## Stage 2: Alignment and Quantification

Choose **one** path based on resources and downstream needs:

### Path A: Alignment-Based (STAR → featureCounts)

```bash
# STAR alignment
STAR --runThreadN 8 --genomeDir star_index/ \
    --readFilesIn sample_clean_R1.fastq.gz sample_clean_R2.fastq.gz \
    --readFilesCommand zcat \
    --outSAMtype BAM SortedByCoordinate \
    --outFileNamePrefix sample_

# featureCounts
featureCounts -p --countReadPairs -a annotation.gtf -o counts.txt *.bam
```

### Path B: Alignment-Free (Salmon)

```bash
salmon quant -i salmon_index -l A \
    -1 sample_clean_R1.fastq.gz -2 sample_clean_R2.fastq.gz \
    -o sample_quant -p 8 --gcBias --seqBias
```

**Important**: For DE analysis with DESeq2/edgeR, summarize Salmon results via `tximeta` or `tximport` (see `bio-mrna-seq-quantification`). `tximeta` is preferred because it automatically attaches transcript metadata and verifies the reference version.

## Stage 3: Count Matrix Preparation

```python
import pandas as pd

# Ingest counts
counts = pd.read_csv('count_matrix.csv', index_col=0)
metadata = pd.read_csv('metadata.csv', index_col=0)

# Align and filter
common = counts.columns.intersection(metadata.index)
counts = counts[common]
metadata = metadata.loc[common]

# CPM-based low-expression filtering (best practice)
cpm = counts.div(counts.sum(axis=0), axis=1) * 1e6
expressed = (cpm > 0.5).sum(axis=1) >= 3
counts = counts.loc[expressed]
```

## Stage 4: Exploratory QC

```r
library(DESeq2)
dds <- DESeqDataSetFromMatrix(countData=as.matrix(counts), colData=metadata, design=~ condition)

# Use vst for n > 30; use rlog(dds, blind=TRUE) for smaller datasets
vsd <- vst(dds, blind=TRUE)
plotPCA(vsd, intgroup=c('condition', 'batch'))
```

For complex heatmaps with multiple annotations, consider `ComplexHeatmap` instead of `pheatmap` (see `bio-mrna-seq-differential-expression`).

**Checkpoints**:
- Samples cluster by biological condition
- No strong batch-driven clustering (or batch is documented)
- No extreme outliers

## Stage 5: Differential Expression

```r
# Default DESeq2 fit
dds <- DESeq(dds)

# For large datasets, consider glmGamPoi:
# dds <- DESeq(dds, fitType='glmGamPoi')

res <- results(dds, contrast=c('condition', 'treated', 'control'), alpha=0.05)
summary(res)

# For improved power, optionally use IHW:
# res <- results(dds, contrast=c('condition', 'treated', 'control'), filterFun=ihw)
```

## Stage 6: Pathway Enrichment

```r
library(clusterProfiler)
sig_genes <- rownames(subset(res, padj < 0.05 & abs(log2FoldChange) > 1))
go_bp <- enrichGO(gene=sig_genes, OrgDb=org.Hs.eg.db, ont='BP')
dotplot(go_bp, showCategory=15)
```

## Recommended Directory Structure

```
project/
├── 01_fastq/
├── 02_qc/
├── 03_alignment/          or 03_quantification/
├── 04_counts/
├── 05_de/
├── 06_pathways/
└── multiqc_report/
```

## When to Use Advanced Modules

| Scenario | Advanced Skill |
|----------|---------------|
| Strong batch effects | `bio-mrna-seq-batch-correction` |
| Time-series design | `bio-mrna-seq-timeseries` |
| Alternative splicing interest | `bio-mrna-seq-splicing` |
| Co-expression network discovery | `bio-mrna-seq-wgcna` |
| Protein interaction networks | `bio-mrna-seq-ppi` |
| Cell type deconvolution | `bio-mrna-seq-deconvolution` |

## Related Skills

- `bio-mrna-seq-qc-preprocessing`
- `bio-mrna-seq-alignment`
- `bio-mrna-seq-quantification`
- `bio-mrna-seq-count-prep`
- `bio-mrna-seq-qc-exploratory`
- `bio-mrna-seq-differential-expression`
- `bio-mrna-seq-pathway-enrichment`
