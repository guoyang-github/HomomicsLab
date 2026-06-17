#!/bin/bash
# Generate final MultiQC report
# Usage: bash scripts/generate_final_report.sh [PROJECT_DIR]

set -euo pipefail

PROJECT_DIR="${1:-riboseq_project}"

echo "[11/11] Final QC report..."

INPUT_DIRS=()
for d in "$PROJECT_DIR"/results/01_qc/fastqc_raw/ \
         "$PROJECT_DIR"/results/02_ribo_preprocessing/ \
         "$PROJECT_DIR"/results/02_rna_preprocessing/; do
  [ -d "$d" ] && INPUT_DIRS+=("$d")
done

if [ ${#INPUT_DIRS[@]} -eq 0 ]; then
  echo "No QC directories found to report." >&2
  exit 1
fi

multiqc -f \
    "${INPUT_DIRS[@]}" \
    -o "$PROJECT_DIR"/results/99_report/ \
    -n multiqc_report

echo "[11/11] Pipeline complete. Report: $PROJECT_DIR/results/99_report/multiqc_report.html"
