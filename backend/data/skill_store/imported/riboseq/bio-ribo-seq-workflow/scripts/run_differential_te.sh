#!/bin/bash
# Differential translation efficiency analysis
# Usage: bash scripts/run_differential_te.sh [PROJECT_DIR]

set -euo pipefail

PROJECT_DIR="${1:-riboseq_project}"
outdir="$PROJECT_DIR/results/04_differential"

mkdir -p "$outdir"

echo "[6/11] Differential TE analysis..."

# Generate count matrices
featureCounts -T 8 -t CDS -g gene_id \
  -a "$PROJECT_DIR"/results/00_index/annotation_clean.gtf \
  -o "$outdir"/ribo_counts.tsv \
  "$PROJECT_DIR"/results/02_ribo_preprocessing/*.sorted.bam

featureCounts -T 8 -t exon -g gene_id \
  -a "$PROJECT_DIR"/results/00_index/annotation_clean.gtf \
  -o "$outdir"/rna_counts.tsv \
  "$PROJECT_DIR"/results/02_rna_preprocessing/*.sorted.bam

# Create sample conditions map from samplesheet
awk -F',' 'NR>1 {print $1"\t"$2}' "$PROJECT_DIR/samplesheet.csv" > "$outdir"/sample_conditions.tsv

Rscript "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"/run_differential_te.R "$outdir"

echo "[6/11] Differential TE analysis complete."
