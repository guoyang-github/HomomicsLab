# mRNA-seq Preprocessing - Usage Guide

## Overview

Preprocess paired-end mRNA-seq data for translation efficiency (TE) analysis. Outputs gene-level count matrices compatible with downstream TE skills.

## Prerequisites

```bash
conda install -c bioconda star cutadapt subread samtools
```

## Quick Start

Tell your AI agent:
- "Preprocess my mRNA-seq data for TE analysis"
- "Align my RNA-seq reads and generate count matrices"
- "Quantify gene expression from mRNA-seq BAM files"

## Example Prompts

### Preprocessing

> "Trim adapters and align my mRNA-seq reads to the genome"

> "Generate a gene-level count matrix for all mRNA-seq samples"

> "Run featureCounts on my aligned mRNA-seq BAMs"

### Quantification

> "Format featureCounts output for DESeq2 / riborex"

> "Combine all sample counts into one matrix"

## What the Agent Will Do

1. Trim adapters from paired-end mRNA-seq reads
2. Optionally remove rRNA contamination
3. Align reads with STAR (splice-aware)
4. Generate sorted, indexed BAM files
5. Quantify gene-level counts with featureCounts or HTSeq
6. Format output as a clean gene x sample matrix

## Tips

- Use the **same annotation GTF** as for Ribo-seq preprocessing
- mRNA-seq alignment should allow **splicing** (unlike Ribo-seq intron-max=1)
- **Paired-end** data is standard for mRNA-seq TE analysis
- Count matrix will be consumed by `translation-efficiency`
