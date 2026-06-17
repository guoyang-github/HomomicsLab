#!/bin/bash
# Detect translated ORFs with RiboCode
# Usage: bash scripts/detect_orfs.sh [PROJECT_DIR] [MIN_LENGTH] [MAX_LENGTH]

set -euo pipefail

PROJECT_DIR="${1:-riboseq_project}"
MIN_LENGTH="${2:-28}"
MAX_LENGTH="${3:-32}"

outdir="$PROJECT_DIR/results/05_orf_detection"
mkdir -p "$outdir"

echo "[7/11] ORF detection..."

# Build comma-separated length list for RiboCode (expects all individual lengths, not min-max)
lengths=$(seq "$MIN_LENGTH" "$MAX_LENGTH" | paste -sd ',' -)

while IFS=, read -r sample condition ribo_fastq rna_r1 rna_r2; do
    # Strip UTF-8 BOM if present
    sample="${sample#$'\xEF\xBB\xBF'}"
    [[ "$sample" == "sample" ]] && continue
    [[ -z "$ribo_fastq" ]] && continue

    RiboCode_onestep \
        -g "$PROJECT_DIR/results/00_index/annotation_clean.gtf" \
        -r "$PROJECT_DIR/results/02_ribo_preprocessing/${sample}.sorted.bam" \
        -f "$PROJECT_DIR/results/00_index/genome.fa" \
        -l "$lengths" \
        -o "$outdir/${sample}"

    echo "  [orf-detection] $sample done"
done < "$PROJECT_DIR/samplesheet.csv"

echo "[7/11] ORF detection complete."
