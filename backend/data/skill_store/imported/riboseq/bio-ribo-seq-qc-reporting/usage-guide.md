# QC Reporting - Usage Guide

## Overview

Generate comprehensive quality control reports for Ribo-seq experiments, combining FastQC, MultiQC, length distributions, and periodicity summaries.

## Prerequisites

```bash
conda install -c bioconda fastqc multiqc samtools
pip install pysam matplotlib numpy pandas
```

## Quick Start

Tell your AI agent:
- "Generate QC reports for my Ribo-seq data"
- "Plot read length distributions for all samples"
- "Create a periodicity summary across my samples"

## Example Prompts

### QC Reports

> "Run FastQC and MultiQC on my Ribo-seq samples"

> "Plot length distributions from aligned BAM files"

> "Generate a QC summary table with mapping rates and periodicity scores"

## What the Agent Will Do

1. Run FastQC on raw and/or trimmed FASTQ files
2. Aggregate results with MultiQC
3. Plot read length distributions from BAM files
4. Summarize P-site offsets and periodicity scores across samples
5. Output a unified QC summary table

## Tips

- **Length distribution peak** at ~28-32 nt indicates good library quality
- **Periodicity score > 0.5** is a common quality threshold
- Run QC after preprocessing but before downstream analysis
- Use the summary table to flag low-quality samples
