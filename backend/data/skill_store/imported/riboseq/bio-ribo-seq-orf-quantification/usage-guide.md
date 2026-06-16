# ORF Quantification - Usage Guide

## Overview

Quantify ribosome occupancy at detected ORFs and perform differential ORF expression analysis using ORFik and DESeq2.

## Prerequisites

```r
BiocManager::install(c('ORFik', 'GenomicFeatures', 'DESeq2'))
```

## Quick Start

Tell your AI agent:
- "Quantify translation at detected ORFs"
- "Build an ORF count matrix for all samples"
- "Run DESeq2 on ORF-level counts"
- "Compare uORF expression between conditions"

## Example Prompts

### Quantification

> "Count P-sites per ORF using ORFik"

> "Calculate ORF-level FPKM from my Ribo-seq data"

> "Quantify uORFs with at least 10 reads"

### Differential Analysis

> "Find differentially expressed ORFs between treatment and control"

> "Merge RiboCode predictions with DESeq2 results"

> "Create a volcano plot for differential ORF expression"

## What the Agent Will Do

1. Load ORF annotations and detected ORFs
2. Apply P-site offsets for corrected quantification
3. Build ORF x sample count matrices
4. Run DESeq2 for differential ORF expression
5. Merge quantification with ORF detection metadata
6. Generate visualization plots

## Tips

- **P-site correction** is essential for accurate ORF quantification
- Use the **same P-site offsets** calculated in periodicity analysis
- CDS-level counts for canonical ORFs; 5' UTR counts for uORFs
- Filter low-count ORFs before DESeq2 to improve power
