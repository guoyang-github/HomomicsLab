#!/bin/bash
set -euo pipefail
# Example: Build reference indexes for Ribo-seq analysis
# Usage: bash build_indexes.sh [GENOME_FA] [GTF] [RRNA_FA]
# TODO: Replace paths below with your actual reference file paths

GENOME_FA="${1:-genome.fa}"
GTF="${2:-annotation.gtf}"
RRNA_FA="${3:-rrna.fa}"
OUTDIR="results/00_index"

mkdir -p "$OUTDIR"/star_genome "$OUTDIR"/bowtie2_transcriptome \
         "$OUTDIR"/bowtie2_rrna "$OUTDIR"/bowtie2_genome

# Clean GTF
awk -F'\t' '$1 !~ /^#/ && $9 ~ /gene_id/ && $9 ~ /transcript_id/' "$GTF" \
  > "$OUTDIR"/annotation_clean.gtf

# NOTE: For plant species (Arabidopsis, rice), uncomment the lines below to
# remove chloroplast and mitochondrial annotations for cytoplasmic Ribo-seq.
# If studying organellar translation, skip this filtering step.
# grep -vE '^ATCG|^ATMG' "$OUTDIR"/annotation_clean.gtf > "$OUTDIR"/annotation_nuclear.gtf
# mv "$OUTDIR"/annotation_nuclear.gtf "$OUTDIR"/annotation_clean.gtf

# Generate transcriptome FASTA
gffread -w "$OUTDIR"/transcriptome.fa -g "$GENOME_FA" "$OUTDIR"/annotation_clean.gtf

# Build STAR genome index
STAR --runMode genomeGenerate \
  --genomeDir "$OUTDIR"/star_genome/ \
  --genomeFastaFiles "$GENOME_FA" \
  --sjdbGTFfile "$OUTDIR"/annotation_clean.gtf \
  --sjdbOverhang 49 \
  --runThreadN 8

# Build Bowtie2 indexes
bowtie2-build "$OUTDIR"/transcriptome.fa "$OUTDIR"/bowtie2_transcriptome/transcriptome
bowtie2-build "$GENOME_FA" "$OUTDIR"/bowtie2_genome/genome
bowtie2-build "$RRNA_FA" "$OUTDIR"/bowtie2_rrna/rrna

echo "Index building complete. Output: $OUTDIR"
