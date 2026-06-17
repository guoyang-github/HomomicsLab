#!/bin/bash
set -euo pipefail
# Example: Preprocess paired-end mRNA-seq data for TE analysis
# Usage: bash preprocess_mrna.sh [SAMPLE] [R1.fastq.gz] [R2.fastq.gz]
# TODO: Replace paths below with your actual index and GTF paths

SAMPLE="${1:-sample1}"
R1="${2:-sample1_rna_R1.fastq.gz}"
R2="${3:-sample1_rna_R2.fastq.gz}"

RRNA_INDEX="results/00_index/bowtie2_rrna/rrna"
STAR_INDEX="results/00_index/star_genome"
OUTDIR="results/02_rna_preprocessing"

mkdir -p "$OUTDIR"/counts

echo "Trimming $SAMPLE..."
cutadapt -a AGATCGGAAGAGCACACGTCTGAACTCCAGTCA \
  -A AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT \
  -m 20 \
  -o "$OUTDIR"/"${SAMPLE}_R1_trimmed.fastq.gz" \
  -p "$OUTDIR"/"${SAMPLE}_R2_trimmed.fastq.gz" \
  "$R1" "$R2"

echo "Removing rRNA..."
bowtie2 -x "$RRNA_INDEX" \
  -1 "$OUTDIR/${SAMPLE}_R1_trimmed.fastq.gz" \
  -2 "$OUTDIR/${SAMPLE}_R2_trimmed.fastq.gz" \
  --un-conc-gz "$OUTDIR/${SAMPLE}_trimmed.fastq.gz" \
  -S /dev/null -p 8

mv "$OUTDIR/${SAMPLE}_trimmed.fastq.1.gz" "$OUTDIR/${SAMPLE}_trimmed.1.fastq.gz" || true
mv "$OUTDIR/${SAMPLE}_trimmed.fastq.2.gz" "$OUTDIR/${SAMPLE}_trimmed.2.fastq.gz" || true

echo "Aligning with STAR..."
STAR --runMode alignReads \
  --genomeDir "$STAR_INDEX" \
  --readFilesIn "$OUTDIR/${SAMPLE}_trimmed.1.fastq.gz" \
              "$OUTDIR/${SAMPLE}_trimmed.2.fastq.gz" \
  --readFilesCommand zcat \
  --outFilterMultimapNmax 20 \
  --outFilterMismatchNmax 2 \
  --alignIntronMin 20 \
  --alignIntronMax 1000000 \
  --outSAMtype BAM SortedByCoordinate \
  --outFileNamePrefix "$OUTDIR/${SAMPLE}_"

mv "$OUTDIR/${SAMPLE}_Aligned.sortedByCoord.out.bam" "$OUTDIR/${SAMPLE}.sorted.bam"
samtools index "$OUTDIR/${SAMPLE}.sorted.bam"
samtools flagstat "$OUTDIR/${SAMPLE}.sorted.bam" > "$OUTDIR/${SAMPLE}.flagstat"

echo "mRNA-seq preprocessing complete for $SAMPLE"
