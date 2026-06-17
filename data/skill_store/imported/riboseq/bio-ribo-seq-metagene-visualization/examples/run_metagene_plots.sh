#!/bin/bash
set -euo pipefail
# Example: Generate metagene and frame-distribution plots
# Usage: bash run_metagene_plots.sh [SAMPLE] [BAM] [GTF] [OUTDIR]
# TODO: Replace paths below with your actual file paths

SAMPLE="${1:-sample1}"
BAM="${2:-results/02_ribo_preprocessing/sample1.sorted.bam}"
GTF="${3:-results/00_index/annotation_clean.gtf}"
OUTDIR="${4:-results/08_visualization}"

mkdir -p "$OUTDIR"

python3 ../scripts/plot_metagene_start.py \
  --bam "$BAM" \
  --gtf "$GTF" \
  --out "$OUTDIR/${SAMPLE}_metagene_start_codon.pdf"

python3 ../scripts/plot_frame_distribution.py \
  --bam "$BAM" \
  --gtf "$GTF" \
  --out "$OUTDIR/${SAMPLE}_frame_distribution.pdf"

python3 ../scripts/plot_genebody_heatmap.py \
  --bam "$BAM" \
  --gtf "$GTF" \
  --n-genes 100 \
  --out "$OUTDIR/${SAMPLE}_genebody_heatmap.pdf"

echo "Metagene plots saved to $OUTDIR"
