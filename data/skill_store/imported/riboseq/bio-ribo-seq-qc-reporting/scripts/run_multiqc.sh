#!/bin/bash
set -euo pipefail
# Aggregate QC reports with MultiQC
# Usage: bash run_multiqc.sh [OUTDIR] [INPUT_DIRS...]

OUTDIR="${1:-results/01_qc}"
shift

INPUTS=()
for d in "$@"; do
  if [ -d "$d" ]; then
    INPUTS+=("$d")
  fi
done

if [ ${#INPUTS[@]} -eq 0 ]; then
  for d in "$OUTDIR"/fastqc_raw/ "$OUTDIR"/fastqc_trimmed/ results/02_ribo_preprocessing/; do
    [ -d "$d" ] && INPUTS+=("$d")
  done
fi

if [ ${#INPUTS[@]} -eq 0 ]; then
  echo "No valid input directories found." >&2
  exit 1
fi

multiqc -f "${INPUTS[@]}" -o "$OUTDIR" -n multiqc_report
