#!/bin/bash
# Run FastQC on raw reads
# Usage: bash scripts/run_qc_raw.sh [PROJECT_DIR]

set -euo pipefail

PROJECT_DIR="${1:-riboseq_project}"

echo "[2/11] Running raw QC..."
mkdir -p "$PROJECT_DIR"/results/01_qc/fastqc_raw

while IFS=, read -r sample condition ribo_fastq rna_r1 rna_r2; do
    # Skip header lines (with or without BOM)
    [[ "$sample" == $'\xEF\xBB\xBF'sample ]] && continue
    [[ "$sample" == "sample" ]] && continue
    [[ -z "$ribo_fastq" ]] && continue

    fastqc -o "$PROJECT_DIR"/results/01_qc/fastqc_raw/ "$ribo_fastq"
    if [[ -n "$rna_r1" && -n "$rna_r2" ]]; then
        fastqc -o "$PROJECT_DIR"/results/01_qc/fastqc_raw/ "$rna_r1" "$rna_r2"
    fi
done < "$PROJECT_DIR/samplesheet.csv"

echo "[2/11] Raw QC complete."
