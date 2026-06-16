#!/bin/bash
# Optional UMI deduplication for Ribo-seq BAM files
# Usage: bash scripts/dedup_umi.sh [BAM_DIR] [OUT_DIR]
# Requires: umi_tools (pip install umi_tools)

set -euo pipefail

BAM_DIR="${1:-results/02_ribo_preprocessing}"
OUT_DIR="${2:-results/02_ribo_preprocessing/dedup}"

mkdir -p "$OUT_DIR"

echo "UMI deduplication starting..."

for bam in "$BAM_DIR"/*.sorted.bam; do
    [[ -e "$bam" ]] || continue
    sample=$(basename "$bam" .sorted.bam)
    echo "  [umi_dedup] Processing $sample..."

    # umi_tools dedup expects UMIs in read names (e.g., "read_1_ACGT")
    # If UMIs were extracted during cutadapt, they should already be in the name
    umi_tools dedup \
        -I "$bam" \
        -S "$OUT_DIR/${sample}.dedup.bam" \
        --method=unique \
        --extract-umi-method=read_id \
        --umi-separator=":"

    samtools index "$OUT_DIR/${sample}.dedup.bam"
    samtools flagstat "$OUT_DIR/${sample}.dedup.bam" > "$OUT_DIR/${sample}.dedup.flagstat"
    echo "  [umi_dedup] $sample done ($(samtools view -c "$OUT_DIR/${sample}.dedup.bam") reads)"
done

echo "UMI deduplication complete. Output: $OUT_DIR"
