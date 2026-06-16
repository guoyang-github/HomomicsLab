---
name: bio-ribo-seq-rna-preprocessing
description: Preprocess mRNA-seq data for Ribo-seq translation efficiency analysis including adapter trimming, optional rRNA removal, alignment, and gene-level quantification. Use when paired mRNA-seq data is available for TE calculation.
tool_type: cli
primary_tool: STAR
---

## Version Compatibility

Reference examples tested with: STAR 2.7.11+, cutadapt 4.4+, HTSeq 2.0+, featureCounts 2.0+, samtools 1.19+

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `<tool> --version` then `<tool> --help` to confirm flags
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws errors, introspect the installed package and adapt the example to match the actual API rather than retrying.

# mRNA-seq Preprocessing for Ribo-seq TE

**"Preprocess my mRNA-seq data for translation efficiency analysis"** → Trim adapters, optionally remove rRNA, align to the genome with splice-aware settings, and quantify gene-level counts for downstream TE calculation.

## Output Directory Structure

```
results/02_rna_preprocessing/
├── {sample}_trimmed.fastq.gz
├── {sample}.sorted.bam
├── {sample}.sorted.bam.bai
├── {sample}.flagstat
└── counts/
    └── rna_counts.tsv
```

## Workflow Overview

```
mRNA-seq FASTQ
    |
    v
Adapter trimming (cutadapt)
    |
    v
Optional rRNA removal (bowtie2)
    |
    v
Genome alignment (STAR)
    |
    v
Gene-level quantification (featureCounts / HTSeq)
    |
    v
counts matrix for TE
```

## Step 1: Adapter Trimming

```bash
# Typical mRNA-seq uses TruSeq or Nextera adapters
# Auto-detect with cutadapt if unknown, or specify explicitly

cutadapt \
  -a AGATCGGAAGAGCACACGTCTGAACTCCAGTCA \
  -A AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT \
  -m 20 \
  -o results/02_rna_preprocessing/${SAMPLE}_R1_trimmed.fastq.gz \
  -p results/02_rna_preprocessing/${SAMPLE}_R2_trimmed.fastq.gz \
  ${SAMPLE}_R1.fastq.gz ${SAMPLE}_R2.fastq.gz
```

## Step 2: Optional rRNA Removal

mRNA-seq typically has lower rRNA than Ribo-seq, but aggressive removal improves quantification accuracy.

```bash
bowtie2 -x results/00_index/bowtie2_rrna/rrna \
  -1 results/02_rna_preprocessing/${SAMPLE}_R1_trimmed.fastq.gz \
  -2 results/02_rna_preprocessing/${SAMPLE}_R2_trimmed.fastq.gz \
  --un-conc-gz results/02_rna_preprocessing/${SAMPLE}_trimmed.fastq.gz \
  -S /dev/null -p 8

# Output will be ${SAMPLE}_trimmed.1.fastq.gz and ${SAMPLE}_trimmed.2.fastq.gz
```

## Step 3: STAR Alignment

Use the same STAR genome index built in `index-building`. Allow splicing for mRNA-seq.

```bash
STAR --runMode alignReads \
  --genomeDir results/00_index/star_genome/ \
  --readFilesIn results/02_rna_preprocessing/${SAMPLE}_trimmed.1.fastq.gz \
                results/02_rna_preprocessing/${SAMPLE}_trimmed.2.fastq.gz \
  --readFilesCommand zcat \
  --outFilterMultimapNmax 20 \
  --outFilterMismatchNmax 2 \
  --alignIntronMin 20 \
  --alignIntronMax 1000000 \
  --outSAMtype BAM SortedByCoordinate \
  --outFileNamePrefix results/02_rna_preprocessing/${SAMPLE}_

# Rename output for consistency
mv results/02_rna_preprocessing/${SAMPLE}_Aligned.sortedByCoord.out.bam \
   results/02_rna_preprocessing/${SAMPLE}.sorted.bam

samtools index results/02_rna_preprocessing/${SAMPLE}.sorted.bam
samtools flagstat results/02_rna_preprocessing/${SAMPLE}.sorted.bam \
  > results/02_rna_preprocessing/${SAMPLE}.flagstat
```

## Step 4: Gene-Level Quantification

### featureCounts (Recommended)

```bash
# Gather all BAM files
BAMS=$(ls results/02_rna_preprocessing/*.sorted.bam)

featureCounts -T 8 -p -t exon -g gene_id \
  -a results/00_index/annotation_clean.gtf \
  -o results/02_rna_preprocessing/counts/rna_counts.tsv \
  $BAMS
```

### HTSeq-count (Alternative)

```bash
htseq-count -f bam -r pos -s no -t exon -i gene_id \
  results/02_rna_preprocessing/${SAMPLE}.sorted.bam \
  results/00_index/annotation_clean.gtf \
  > results/02_rna_preprocessing/counts/${SAMPLE}_counts.txt
```

## Step 5: Format Count Matrix for TE

```python
import pandas as pd

def format_featurecounts(counts_file, out_file):
    '''Format featureCounts output to a clean gene x sample matrix'''
    df = pd.read_csv(counts_file, sep='\t', comment='#', index_col=0)
    # Drop annotation columns
    count_cols = [c for c in df.columns if c not in
                  ['Chr', 'Start', 'End', 'Strand', 'Length']]
    counts = df[count_cols]
    # Clean sample names
    counts.columns = [c.replace('results/02_rna_preprocessing/', '')
                       .replace('.sorted.bam', '') for c in counts.columns]
    counts.to_csv(out_file, sep='\t')

# Example
# format_featurecounts('results/02_rna_preprocessing/counts/rna_counts.tsv',
#                      'results/02_rna_preprocessing/counts/rna_counts_matrix.tsv')
```

## Complete Bash Pipeline

```bash
#!/bin/bash
# preprocess_mrna.sh

SAMPLE=$1
R1=$2
R2=$3
RRNA_INDEX="results/00_index/bowtie2_rrna/rrna"
STAR_INDEX="results/00_index/star_genome"
GTF="results/00_index/annotation_clean.gtf"
OUTDIR="results/02_rna_preprocessing"

mkdir -p "$OUTDIR"/counts

# Trim
cutadapt -a AGATCGGAAGAGCACACGTCTGAACTCCAGTCA \
  -A AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT \
  -m 20 \
  -o "$OUTDIR"/${SAMPLE}_R1_trimmed.fastq.gz \
  -p "$OUTDIR"/${SAMPLE}_R2_trimmed.fastq.gz "$R1" "$R2"

# Optional rRNA removal
bowtie2 -x "$RRNA_INDEX" \
  -1 "$OUTDIR"/${SAMPLE}_R1_trimmed.fastq.gz \
  -2 "$OUTDIR"/${SAMPLE}_R2_trimmed.fastq.gz \
  --un-conc-gz "$OUTDIR"/${SAMPLE}_trimmed.fastq.gz \
  -S /dev/null -p 8

# Align
STAR --runMode alignReads \
  --genomeDir "$STAR_INDEX" \
  --readFilesIn "$OUTDIR"/${SAMPLE}_trimmed.1.fastq.gz \
                "$OUTDIR"/${SAMPLE}_trimmed.2.fastq.gz \
  --readFilesCommand zcat \
  --outFilterMultimapNmax 20 \
  --outFilterMismatchNmax 2 \
  --alignIntronMin 20 \
  --alignIntronMax 1000000 \
  --outSAMtype BAM SortedByCoordinate \
  --outFileNamePrefix "$OUTDIR"/${SAMPLE}_

mv "$OUTDIR"/${SAMPLE}_Aligned.sortedByCoord.out.bam "$OUTDIR"/${SAMPLE}.sorted.bam
samtools index "$OUTDIR"/${SAMPLE}.sorted.bam
samtools flagstat "$OUTDIR"/${SAMPLE}.sorted.bam > "$OUTDIR"/${SAMPLE}.flagstat

echo "mRNA-seq preprocessing complete for $SAMPLE"
```

## Related Skills

- bio-ribo-seq-index-building - Provides STAR genome index and annotation GTF
- bio-ribo-seq-translation-efficiency - Consumes the rna_counts_matrix.tsv generated here
- bio-ribo-seq-riboseq-preprocessing - Parallel preprocessing for Ribo-seq data
