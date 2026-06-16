---
name: bio-ribo-seq-riboseq-preprocessing
description: Preprocess ribosome profiling data including adapter trimming, size selection, rRNA removal, and alignment. Use when preparing Ribo-seq reads for downstream analysis of translation.
tool_type: cli
primary_tool: bowtie2
---

## Version Compatibility

Reference examples tested with: Bowtie2 2.5.3+, STAR 2.7.11+, cutadapt 4.4+, numpy 1.26+, pysam 0.22+, samtools 1.19+

Before using code patterns, verify installed versions match. If versions differ:
- Python: `pip show <package>` then `help(module.function)` to check signatures
- CLI: `<tool> --version` then `<tool> --help` to confirm flags

If code throws ImportError, AttributeError, or TypeError, introspect the installed
package and adapt the example to match the actual API rather than retrying.

# Ribo-seq Preprocessing

**"Preprocess my ribosome profiling data"** → Trim adapters, size-select ribosome-protected fragments (26-34 nt), remove rRNA contamination, and align to the transcriptome for translation analysis.
- CLI: `cutadapt` → `bowtie2` (rRNA removal) → `STAR` (genome alignment)

## Standard Output Directory

```
results/02_ribo_preprocessing/
├── {sample}_trimmed.fastq.gz
├── {sample}_size_selected.fastq.gz
├── {sample}_non_rRNA.fastq.gz
├── {sample}.sorted.bam
├── {sample}.sorted.bam.bai
└── {sample}.flagstat
```

## Workflow Overview

```
Raw Ribo-seq FASTQ
    |
    v
Adapter trimming (cutadapt)
    |
    v
Size selection (species-specific, e.g. 28-32 nt for human)
    |
    v
rRNA removal (SortMeRNA/bowtie2)
    |
    v
Alignment to genome (STAR)
    |
    v
Quality filtered BAM
```

## Adapter Trimming

**Goal:** Remove 3' adapter sequences from ribosome footprint reads to recover the true insert.

**Approach:** Run cutadapt with the known adapter sequence and length filters to discard fragments outside the expected footprint range.

```bash
mkdir -p results/02_ribo_preprocessing

# Trim 3' adapter
cutadapt \
    -a CTGTAGGCACCATCAAT \
    -m 20 \
    -M 40 \
    -o results/02_ribo_preprocessing/${SAMPLE}_trimmed.fastq.gz \
    input.fastq.gz
```

## Size Selection

**Goal:** Retain only reads corresponding to ribosome-protected fragments (species-specific; typically 28-32 nt for mammals, 27-31 nt for yeast).

**Approach:** Apply minimum and maximum length filters with cutadapt to select the footprint size range.

```bash
# Select ribosome footprint size range
# Typical mammal: 28-32 nt (protected by ribosome)
# Typical yeast: 27-31 nt
cutadapt \
    -m 28 \
    -M 32 \
    -o results/02_ribo_preprocessing/${SAMPLE}_size_selected.fastq.gz \
    results/02_ribo_preprocessing/${SAMPLE}_trimmed.fastq.gz
```

## rRNA Removal

**Goal:** Deplete ribosomal RNA reads that typically constitute the majority of a Ribo-seq library.

**Approach:** Align reads against rRNA reference databases using SortMeRNA or Bowtie2 and collect only unmapped (non-rRNA) reads.

```bash
# Option 1: SortMeRNA (comprehensive)
sortmerna \
    --ref rRNA_databases/silva-bac-16s-id90.fasta \
    --ref rRNA_databases/silva-euk-18s-id95.fasta \
    --ref rRNA_databases/silva-euk-28s-id98.fasta \
    --reads results/02_ribo_preprocessing/${SAMPLE}_size_selected.fastq.gz \
    --aligned results/02_ribo_preprocessing/${SAMPLE}_rRNA_reads \
    --other results/02_ribo_preprocessing/${SAMPLE}_non_rRNA_reads \
    --fastx \
    --threads 8

# Rename SortMeRNA output
mv results/02_ribo_preprocessing/${SAMPLE}_non_rRNA_reads.fq.gz \
   results/02_ribo_preprocessing/${SAMPLE}_non_rRNA.fastq.gz

# Option 2: Bowtie2 to rRNA index
bowtie2 -x results/00_index/bowtie2_rrna/rrna \
    -U results/02_ribo_preprocessing/${SAMPLE}_size_selected.fastq.gz \
    --un results/02_ribo_preprocessing/${SAMPLE}_non_rRNA.fastq.gz \
    -S /dev/null \
    -p 8
```

### Species-Specific rRNA Notes

- **Human/Mouse**: Use SILVA eukaryotic 18S/28S databases.
- **Yeast**: Use fungal/yeast-specific rRNA sequences.
- **Plants (Arabidopsis/Rice)**: Use plant rRNA databases and additionally filter chloroplast rRNA reads (see species-templates skill).

## Alignment to Transcriptome

**Goal:** Map cleaned ribosome footprint reads to the genome or transcriptome for positional analysis.

**Approach:** Align with STAR (spliced) or Bowtie2 (transcriptome) using stringent filters for uniquely mapped reads with few mismatches.

```bash
# STAR alignment (genome, unspliced)
# --alignIntronMax 1: Ribo-seq footprints should not span splice junctions
STAR --runMode alignReads \
    --genomeDir results/00_index/star_genome/ \
    --readFilesIn results/02_ribo_preprocessing/${SAMPLE}_non_rRNA.fastq.gz \
    --readFilesCommand zcat \
    --outFilterMultimapNmax 1 \
    --outFilterMismatchNmax 2 \
    --alignIntronMax 1 \
    --outSAMtype BAM SortedByCoordinate \
    --outFileNamePrefix results/02_ribo_preprocessing/${SAMPLE}_

# Rename for standard naming
mv results/02_ribo_preprocessing/${SAMPLE}_Aligned.sortedByCoord.out.bam \
   results/02_ribo_preprocessing/${SAMPLE}.sorted.bam

samtools index results/02_ribo_preprocessing/${SAMPLE}.sorted.bam
samtools flagstat results/02_ribo_preprocessing/${SAMPLE}.sorted.bam \
    > results/02_ribo_preprocessing/${SAMPLE}.flagstat
```

## Quality Metrics

**Goal:** Assess preprocessing success by checking read length distribution and mapping rates.

**Approach:** Extract read lengths from the aligned BAM and run samtools flagstat to verify expected footprint sizes and mapping efficiency.

```bash
# Check read length distribution
samtools view results/02_ribo_preprocessing/${SAMPLE}.sorted.bam | \
    awk '{print length($10)}' | \
    sort | uniq -c | sort -k2n

# Expected: Peak at 28-30 nt for mammals

# Check mapping rate
samtools flagstat results/02_ribo_preprocessing/${SAMPLE}.sorted.bam
```

## Python Preprocessing Helpers

```python
import pysam
import numpy as np
from collections import Counter
import os

def get_length_distribution(bam_path):
    '''Get read length distribution from BAM'''
    lengths = Counter()
    with pysam.AlignmentFile(bam_path, 'rb') as bam:
        for read in bam:
            if not read.is_unmapped:
                lengths[read.query_length] += 1
    return lengths

def filter_by_length(bam_in, bam_out, min_len=28, max_len=32):
    '''Filter BAM by read length'''
    with pysam.AlignmentFile(bam_in, 'rb') as infile:
        with pysam.AlignmentFile(bam_out, 'wb', template=infile) as outfile:
            for read in infile:
                if min_len <= read.query_length <= max_len:
                    outfile.write(read)
```

## Complete Per-Sample Bash Script

```bash
#!/bin/bash
# preprocess_riboseq.sh

SAMPLE=$1
RAW_FASTQ=$2
ADAPTER=${3:-CTGTAGGCACCATCAAT}
MIN_LEN=${4:-28}
MAX_LEN=${5:-32}
RRNA_INDEX=${6:-results/00_index/bowtie2_rrna/rrna}
STAR_INDEX=${7:-results/00_index/star_genome}
OUTDIR="results/02_ribo_preprocessing"

mkdir -p "$OUTDIR"

cutadapt -a "$ADAPTER" -m 20 -M 40 \
  -o "$OUTDIR"/${SAMPLE}_trimmed.fastq.gz "$RAW_FASTQ"

cutadapt -m "$MIN_LEN" -M "$MAX_LEN" \
  -o "$OUTDIR"/${SAMPLE}_size_selected.fastq.gz \
  "$OUTDIR"/${SAMPLE}_trimmed.fastq.gz

bowtie2 -x "$RRNA_INDEX" \
  -U "$OUTDIR"/${SAMPLE}_size_selected.fastq.gz \
  --un "$OUTDIR"/${SAMPLE}_non_rRNA.fastq.gz \
  -S /dev/null -p 8

STAR --runMode alignReads \
  --genomeDir "$STAR_INDEX" \
  --readFilesIn "$OUTDIR"/${SAMPLE}_non_rRNA.fastq.gz \
  --readFilesCommand zcat \
  --outFilterMultimapNmax 1 \
  --outFilterMismatchNmax 2 \
  --alignIntronMax 1 \
  --outSAMtype BAM SortedByCoordinate \
  --outFileNamePrefix "$OUTDIR"/${SAMPLE}_

mv "$OUTDIR"/${SAMPLE}_Aligned.sortedByCoord.out.bam "$OUTDIR"/${SAMPLE}.sorted.bam
samtools index "$OUTDIR"/${SAMPLE}.sorted.bam
samtools flagstat "$OUTDIR"/${SAMPLE}.sorted.bam > "$OUTDIR"/${SAMPLE}.flagstat

echo "Preprocessing complete for $SAMPLE"
```

## Related Skills

- bio-ribo-seq-species-templates - Retrieve organism-specific adapter, length, and rRNA parameters
- bio-ribo-seq-index-building - Provides STAR and rRNA indexes
- bio-ribo-seq-ribosome-periodicity - Validates preprocessing quality using the BAMs generated here
- bio-ribo-seq-qc-reporting - Uses trimmed BAM and flagstat inputs
