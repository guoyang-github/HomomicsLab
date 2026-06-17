#!/bin/bash
set -euo pipefail
# Example: Run QC pipeline for Ribo-seq data
# Usage: bash run_qc.sh [PROJECT_DIR]
# TODO: Replace paths below with your actual file paths

PROJECT_DIR="${1:-riboseq_project}"
OUTDIR="$PROJECT_DIR/results/01_qc"
BAM_DIR="$PROJECT_DIR/results/02_ribo_preprocessing"
PSITE_DIR="$PROJECT_DIR/results/03_periodicity"

mkdir -p "$OUTDIR"/fastqc_raw "$OUTDIR"/fastqc_trimmed "$OUTDIR"/length_distributions

bash ../scripts/run_fastqc.sh raw "$BAM_DIR" "$OUTDIR"
bash ../scripts/run_multiqc.sh "$OUTDIR" \
  "$OUTDIR"/fastqc_raw/ \
  "$OUTDIR"/fastqc_trimmed/ \
  "$BAM_DIR"

# Summarize periodicity and mapping stats
python3 ../scripts/generate_qc_summary.py \
  --samplesheet "$PROJECT_DIR/samplesheet.csv" \
  --flagstat-dir "$BAM_DIR" \
  --psite-dir "$PSITE_DIR" \
  --out "$OUTDIR/qc_summary.csv"

echo "QC report saved to $OUTDIR"
