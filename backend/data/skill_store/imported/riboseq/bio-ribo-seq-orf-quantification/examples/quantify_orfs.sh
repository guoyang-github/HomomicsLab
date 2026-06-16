#!/bin/bash
set -euo pipefail
# Example: Quantify ORF-level counts and run DESeq2
# Usage: bash quantify_orfs.sh [GTF] [BAM_DIR] [OUTDIR]
# TODO: Replace paths below with your actual file paths

GTF="${1:-results/00_index/annotation_clean.gtf}"
BAM_DIR="${2:-results/02_ribo_preprocessing}"
OUTDIR="${3:-results/06_orf_quantification}"

mkdir -p "$OUTDIR"

Rscript ../scripts/quantify_orfs.R "$GTF" "$BAM_DIR" "$OUTDIR"
echo "ORF counts saved to $OUTDIR/orf_counts.tsv"
if [ -f "$OUTDIR/orf_deseq2_results.csv" ]; then
    echo "DESeq2 results saved to $OUTDIR/orf_deseq2_results.csv"
fi
