#!/bin/bash
set -euo pipefail
# Reference: Bowtie2 2.5.3+, STAR 2.7.11+, cutadapt 4.4+, numpy 1.26+, pysam 0.22+, samtools 1.19+ | Verify API if version differs
# Ribo-seq preprocessing pipeline

INPUT="$1"
OUTPUT_PREFIX="${2:-riboseq}"
ADAPTER="${3:-CTGTAGGCACCATCAAT}"

mkdir -p logs

echo "Ribo-seq preprocessing: $INPUT"

echo "Trimming adapters..."
cutadapt \
    -a "$ADAPTER" \
    -m 20 \
    -M 40 \
    -j 4 \
    -o "${OUTPUT_PREFIX}_trimmed.fastq.gz" \
    "$INPUT" \
    > "logs/${OUTPUT_PREFIX}_cutadapt.log" 2>&1

MIN_LEN=28
MAX_LEN=32
echo "Selecting ${MIN_LEN}-${MAX_LEN} nt reads..."
cutadapt \
    -m "$MIN_LEN" \
    -M "$MAX_LEN" \
    -o "${OUTPUT_PREFIX}_sized.fastq.gz" \
    "${OUTPUT_PREFIX}_trimmed.fastq.gz" \
    > "logs/${OUTPUT_PREFIX}_size_select.log" 2>&1

SIZED_READS=$(zcat "${OUTPUT_PREFIX}_sized.fastq.gz" | wc -l)
SIZED_READS=$((SIZED_READS / 4))
echo "Reads in size range: $SIZED_READS"

echo "Removing rRNA..."
if command -v sortmerna &> /dev/null; then
    # TODO: Replace /path/to/rRNA_databases/ with your actual SortMeRNA database path
    sortmerna \
        --ref /path/to/rRNA_databases/silva-euk-18s-id95.fasta \
        --ref /path/to/rRNA_databases/silva-euk-28s-id98.fasta \
        --reads "${OUTPUT_PREFIX}_sized.fastq.gz" \
        --aligned "${OUTPUT_PREFIX}_rRNA" \
        --other "${OUTPUT_PREFIX}_non_rRNA" \
        --fastx \
        --threads 8 \
        > "logs/${OUTPUT_PREFIX}_sortmerna.log" 2>&1
    NON_RRNA="${OUTPUT_PREFIX}_non_rRNA.fastq.gz"
else
    # TODO: Replace rRNA_index with your actual bowtie2 index prefix
    bowtie2 -x rRNA_index \
        -U "${OUTPUT_PREFIX}_sized.fastq.gz" \
        --un-gz "${OUTPUT_PREFIX}_non_rRNA.fastq.gz" \
        -S /dev/null \
        -p 8 \
        2> "logs/${OUTPUT_PREFIX}_rrna_removal.log"
    NON_RRNA="${OUTPUT_PREFIX}_non_rRNA.fastq.gz"
fi

echo "Aligning to genome..."
# TODO: Replace /path/to/STAR_index with your actual STAR index directory
STAR --runMode alignReads \
    --genomeDir /path/to/STAR_index \
    --readFilesIn "$NON_RRNA" \
    --readFilesCommand zcat \
    --outFilterMultimapNmax 1 \
    --outFilterMismatchNmax 2 \
    --alignIntronMax 1 \
    --outSAMtype BAM SortedByCoordinate \
    --outFileNamePrefix "${OUTPUT_PREFIX}_" \
    --runThreadN 8 \
    > "logs/${OUTPUT_PREFIX}_star.log" 2>&1

samtools index "${OUTPUT_PREFIX}_Aligned.sortedByCoord.out.bam"

echo ""
echo "Preprocessing complete!"
echo "Read length distribution:"
samtools view "${OUTPUT_PREFIX}_Aligned.sortedByCoord.out.bam" | \
    awk '{lengths[length($10)]++} END {for (l in lengths) print l, lengths[l]}' | \
    sort -k1n | head -10

echo ""
echo "Alignment stats:"
samtools flagstat "${OUTPUT_PREFIX}_Aligned.sortedByCoord.out.bam"
