#!/bin/bash
set -euo pipefail
# Example: Run DESeq2 differential occupancy analysis on Ribo-seq counts
# Usage: bash run_deseq2_example.sh [OUTDIR]

OUTDIR="${1:-results/04_differential}"

# Ensure count matrix exists
if [ ! -f "$OUTDIR/ribo_counts.tsv" ]; then
    echo "Error: $OUTDIR/ribo_counts.tsv not found."
    echo "Run featureCounts first to generate the count matrix."
    exit 1
fi

# Ensure sample conditions file exists
if [ ! -f "$OUTDIR/sample_conditions.tsv" ]; then
    echo "Error: $OUTDIR/sample_conditions.tsv not found."
    echo "Create a TSV file with columns: sample_name  condition"
    exit 1
fi

Rscript ../scripts/run_deseq2_occupancy.R "$OUTDIR"
echo "DESeq2 occupancy results saved to $OUTDIR/deseq2_occupancy_results.csv"
