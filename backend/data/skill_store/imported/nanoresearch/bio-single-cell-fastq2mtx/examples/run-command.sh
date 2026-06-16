#!/bin/bash
# Example commands for running Cell Ranger and STARsolo
# Adjust paths to match your environment.

set -euo pipefail

# ============================================
# Configuration
# ============================================
REF="/path/to/refdata-gex-GRCh38-2024-A"
STAR_INDEX="/path/to/star_index"
FASTQ_BASE="/path/to/fastqs"
OUT_BASE="/path/to/results"
THREADS=16
MEMORY=64

# ============================================
# 1. Cell Ranger: Single Sample
# ============================================
cellranger count \
    --id=PA08 \
    --sample=PA08 \
    --transcriptome="$REF" \
    --fastqs="$FASTQ_BASE/PA08" \
    --localcores="$THREADS" \
    --localmem="$MEMORY"

# ============================================
# 2. Cell Ranger: Multi-Sample (loop)
# ============================================
while IFS=',' read -r sample_id fastq_dir transcriptome expect_cells condition; do
    [[ "$sample_id" == "sample_id" ]] && continue
    cellranger count \
        --id="$sample_id" \
        --sample="$sample_id" \
        --transcriptome="$transcriptome" \
        --fastqs="$fastq_dir" \
        --localcores="$THREADS" \
        --localmem="$MEMORY"
done < samplesheet-fastq.csv

# ============================================
# 3. STARsolo: Single Sample
# ============================================
bash ../scripts/starsolo/run_starsolo.sh \
    --index "$STAR_INDEX" \
    --r1 "$FASTQ_BASE/PA08"/*_R1_*.fastq.gz \
    --r2 "$FASTQ_BASE/PA08"/*_R2_*.fastq.gz \
    --sample PA08 \
    --output-dir "$OUT_BASE/PA08" \
    --threads "$THREADS"

# ============================================
# 4. Validate Output
# ============================================
# Check Cell Ranger output dimensions
python -c "
import scanpy as sc
adata = sc.read_10x_mtx('PA08/outs/filtered_feature_bc_matrix/')
print(f'PA08: {adata.n_obs} cells x {adata.n_vars} genes')
"
