#!/bin/bash
set -euo pipefail
# Example: Run PyDESeq2 differential occupancy analysis
# Usage: bash run_pydeseq2_example.sh [COUNTS_TSV] [METADATA_CSV] [OUT_CSV]

COUNTS="${1:-results/04_differential/ribo_counts.tsv}"
METADATA="${2:-results/04_differential/sample_conditions.csv}"
OUT="${3:-results/04_differential/pydeseq2_occupancy_results.csv}"

python3 ../scripts/run_pydeseq2.py \
    --counts "$COUNTS" \
    --metadata "$METADATA" \
    --contrast condition treatment control \
    --out "$OUT"

echo "PyDESeq2 results saved to $OUT"
