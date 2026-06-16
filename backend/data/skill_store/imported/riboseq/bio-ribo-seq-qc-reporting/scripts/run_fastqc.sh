#!/bin/bash
set -euo pipefail
# Run FastQC on raw and trimmed reads
# Usage: bash run_fastqc.sh [RAW_DIR] [TRIMMED_DIR] [OUTDIR]

RAW_DIR="${1:-raw}"
TRIMMED_DIR="${2:-results/02_ribo_preprocessing}"
OUTDIR="${3:-results/01_qc}"

mkdir -p "$OUTDIR"/fastqc_raw "$OUTDIR"/fastqc_trimmed

shopt -s nullglob
raw_files=("$RAW_DIR"/*.fastq.gz)
trimmed_files=("$TRIMMED_DIR"/*_trimmed.fastq.gz)
shopt -u nullglob

if [ ${#raw_files[@]} -gt 0 ]; then
  fastqc -o "$OUTDIR"/fastqc_raw/ "${raw_files[@]}"
fi

if [ ${#trimmed_files[@]} -gt 0 ]; then
  fastqc -o "$OUTDIR"/fastqc_trimmed/ "${trimmed_files[@]}"
fi
