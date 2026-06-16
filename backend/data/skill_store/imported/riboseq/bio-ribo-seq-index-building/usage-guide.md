# Index Building - Usage Guide

## Overview

Build reference indexes (STAR, bowtie2) and preprocess annotations before running the Ribo-seq pipeline.

## Prerequisites

```bash
conda install -c bioconda star bowtie2 samtools gffread
```

## Quick Start

Tell your AI agent:
- "Build reference indexes for my Ribo-seq analysis"
- "Prepare STAR genome index and bowtie2 transcriptome index"
- "Preprocess my GTF for RiboCode and Plastid"

## Example Prompts

### Index Building

> "Build STAR and bowtie2 indexes from my genome FASTA and GTF"

> "Preprocess yeast GTF for Ribo-seq analysis"

> "Build rRNA index for SortMeRNA and bowtie2"

## What the Agent Will Do

1. Clean and filter the input GTF
2. Generate transcriptome FASTA
3. Build STAR genome index with appropriate `sjdbOverhang`
4. Build bowtie2 indexes for transcriptome, genome, and rRNA
5. Apply species-specific GTF handling rules

## Tips

- Run this step **once per reference genome**
- Use the same annotation for STAR, bowtie2, and quantification
- For **plants**, consider building separate nuclear and organelle indexes
- Save `sjdbOverhang` value for downstream compatibility checks
