#!/bin/bash
# Build reference indexes for Ribo-seq analysis
# Usage: bash scripts/build_indexes.sh [PROJECT_DIR] [SPECIES] [GENOME_FA] [GTF] [RRNA_FA] [SJDB_OVERHANG]

set -euo pipefail

PROJECT_DIR="${1:-riboseq_project}"
SPECIES="${2:-human}"
GENOME_FA="${3:-genome.fa}"
GTF="${4:-annotation.gtf}"
RRNA_FA="${5:-rrna.fa}"
SJDB_OVERHANG="${6:-49}"

outdir="$PROJECT_DIR/results/00_index"

mkdir -p "$outdir"/star_genome "$outdir"/bowtie2_transcriptome \
         "$outdir"/bowtie2_rrna "$outdir"/bowtie2_genome

# Validate inputs
for f in "$GENOME_FA" "$GTF" "$RRNA_FA"; do
    if [[ ! -f "$f" ]]; then
        echo "Error: Required file not found: $f" >&2
        exit 1
    fi
done

# Clean GTF
awk -F'\t' '$1 !~ /^#/ && $9 ~ /gene_id/ && $9 ~ /transcript_id/' "$GTF" \
    > "$outdir"/annotation_clean.gtf

# Species-specific GTF handling
# NOTE: For plants, organelle (chloroplast / mitochondrial) annotations are
# removed by default to focus on cytoplasmic translation. If your study targets
# organellar translation, comment out the grep -vE lines below and use the
# original annotation_clean.gtf instead.
if [[ "$SPECIES" == "arabidopsis" ]]; then
    grep -vE '^ATCG|^ATMG' "$outdir"/annotation_clean.gtf \
        > "$outdir"/annotation_nuclear.gtf
    mv "$outdir"/annotation_nuclear.gtf "$outdir"/annotation_clean.gtf
elif [[ "$SPECIES" == "rice" ]]; then
    grep -vE '^OsCG|^OsMG' "$outdir"/annotation_clean.gtf \
        > "$outdir"/annotation_nuclear.gtf
    mv "$outdir"/annotation_nuclear.gtf "$outdir"/annotation_clean.gtf
fi

# Transcriptome FASTA
gffread -w "$outdir"/transcriptome.fa -g "$GENOME_FA" "$outdir"/annotation_clean.gtf

# STAR index (species-specific parameters)
STAR_EXTRA=""
STAR_RAM=31000000000  # ~31 GB default
if [[ "$SPECIES" == "yeast" ]]; then
    STAR_EXTRA="--genomeSAindexNbases 10"
    STAR_RAM=15000000000
elif [[ "$SPECIES" == "rice" ]]; then
    STAR_EXTRA="--genomeChrBinNbits 18"
    STAR_RAM=62000000000
elif [[ "$SPECIES" == "arabidopsis" ]]; then
    STAR_RAM=31000000000
elif [[ "$SPECIES" == "human" ]] || [[ "$SPECIES" == "mouse" ]]; then
    STAR_RAM=62000000000
fi

echo "Building STAR index with sjdbOverhang=${SJDB_OVERHANG}, RAM limit=${STAR_RAM}..."
STAR --runMode genomeGenerate \
    --genomeDir "$outdir"/star_genome/ \
    --genomeFastaFiles "$GENOME_FA" \
    --sjdbGTFfile "$outdir"/annotation_clean.gtf \
    --sjdbOverhang "$SJDB_OVERHANG" \
    --runThreadN 8 \
    --limitGenomeGenerateRAM "$STAR_RAM" $STAR_EXTRA

# Bowtie2 indexes
bowtie2-build "$outdir"/transcriptome.fa "$outdir"/bowtie2_transcriptome/transcriptome
bowtie2-build "$GENOME_FA" "$outdir"/bowtie2_genome/genome
bowtie2-build "$RRNA_FA" "$outdir"/bowtie2_rrna/rrna

# Copy genome FASTA to index directory for downstream tools
cp "$GENOME_FA" "$outdir"/genome.fa

echo "[1/11] Index building complete."
