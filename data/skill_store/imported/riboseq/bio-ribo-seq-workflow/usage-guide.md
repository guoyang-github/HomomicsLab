# Ribo-seq Pipeline - Usage Guide

## Overview

Complete end-to-end Ribo-seq analysis workflow using pure Bash. Processes raw FASTQ files through preprocessing, P-site calibration, translation efficiency, ORF detection, and visualization.

## Prerequisites

```bash
# CLI tools
conda install -c bioconda cutadapt bowtie2 star sortmerna samtools subread multiqc fastqc gffread

# Python
pip install plastid pandas numpy matplotlib pysam

# R
BiocManager::install(c('riborex', 'DESeq2', 'ORFik', 'GenomicFeatures'))
```

## Quick Start

Tell your AI agent:
- "Run the complete Ribo-seq pipeline for human samples"
- "Process my Ribo-seq data from FASTQ to ORFs"
- "Calculate translation efficiency with paired mRNA-seq"
- "Run the pipeline in ribo-only mode"

## Example Prompts

### Full Pipeline

> "Run the full Ribo-seq pipeline with samplesheet.csv for yeast"

> "Build indexes and process all my Ribo-seq samples"

> "Generate translation efficiency and ORF detection results"

### Partial Runs

> "Run only Ribo-seq preprocessing and periodicity analysis"

> "Run TE analysis in te-only mode"

> "Detect and quantify ORFs from my preprocessed BAMs"

## What the Agent Will Do

1. Load species-specific parameters
2. Build reference indexes (one-time)
3. Run FastQC on raw reads
4. Preprocess Ribo-seq and mRNA-seq reads
5. Calculate P-site offsets and periodicity
6. Run differential occupancy / TE analysis
7. Detect translated ORFs with RiboCode
8. Quantify ORFs with ORFik / DESeq2
9. Detect ribosome stalling sites
10. Generate metagene plots and heatmaps
11. Compile final MultiQC report

## Tips

- Prepare a `samplesheet.csv` before running the pipeline
- Run `build_indexes` once per reference genome
- Use `ribo-only` mode if you only have Ribo-seq data
- Use `te-only` mode if you want to focus on translation efficiency
- Check `results/99_report/multiqc_report.html` for overall QC
- All intermediate outputs follow the standardized directory structure
