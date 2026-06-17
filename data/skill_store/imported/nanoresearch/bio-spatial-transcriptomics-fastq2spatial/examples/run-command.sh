#!/bin/bash
# Example commands for running Space Ranger and Spacemake
# Adjust paths to match your environment.

set -euo pipefail

# ============================================
# Configuration
# ============================================
REF="/path/to/refdata-gex-GRCh38-2020-A"
FASTQ_BASE="/path/to/fastqs"
IMAGE_BASE="/path/to/images"
OUT_BASE="/path/to/results"
THREADS=16
MEMORY=64

# ============================================
# 1. Space Ranger: Single Sample (Brightfield)
# ============================================
spaceranger count \
    --id=PA08 \
    --sample=PA08 \
    --transcriptome="$REF" \
    --fastqs="$FASTQ_BASE/PA08" \
    --image="$IMAGE_BASE/PA08_tissue.tif" \
    --slide=V19L01-041 \
    --area=A1 \
    --localcores="$THREADS" \
    --localmem="$MEMORY"

# ============================================
# 2. Space Ranger: Single Sample (Fluorescence)
# ============================================
spaceranger count \
    --id=PA08_IF \
    --sample=PA08 \
    --transcriptome="$REF" \
    --fastqs="$FASTQ_BASE/PA08" \
    --darkimage="$IMAGE_BASE/PA08_dapi.tif" \
    --slide=V19L01-041 \
    --area=A1 \
    --localcores="$THREADS" \
    --localmem="$MEMORY"

# ============================================
# 3. Space Ranger: With Manual Loupe Alignment
# ============================================
spaceranger count \
    --id=PA08 \
    --sample=PA08 \
    --transcriptome="$REF" \
    --fastqs="$FASTQ_BASE/PA08" \
    --image="$IMAGE_BASE/PA08_tissue.tif" \
    --loupe-alignment="loupe_alignments/PA08_alignment.json" \
    --localcores="$THREADS" \
    --localmem="$MEMORY"

# ============================================
# 4. Space Ranger: Multi-Sample (loop)
# ============================================
while IFS=',' read -r sample_id fastq_dir image_path transcriptome slide area condition; do
    [[ "$sample_id" == "sample_id" ]] && continue
    spaceranger count \
        --id="$sample_id" \
        --sample="$sample_id" \
        --transcriptome="$transcriptome" \
        --fastqs="$fastq_dir" \
        --image="$image_path" \
        --slide="$slide" \
        --area="$area" \
        --localcores="$THREADS" \
        --localmem="$MEMORY"
done < samplesheet-spatial.csv

# ============================================
# 5. Spacemake: Initialize and Run
# ============================================
SPACEMAKE_DIR="/path/to/spacemake_project"

# Initialize project (run once)
bash ../scripts/spacemake/init_project.sh \
    --project-dir "$SPACEMAKE_DIR" \
    --species human \
    --genome-fasta /path/to/GRCh38.fa \
    --gtf /path/to/gencode.v45.annotation.gtf

# Add sample and run
spacemake projects add_sample \
    --project default \
    --sample_id PA08 \
    --R1 "$FASTQ_BASE/PA08/PA08_S1_L001_R1_001.fastq.gz" \
    --R2 "$FASTQ_BASE/PA08/PA08_S1_L001_R2_001.fastq.gz" \
    --species human \
    --puck visium \
    --run_mode visium

spacemake run --cores "$THREADS" --knit --sample_id PA08

# ============================================
# 6. Validate Output
# ============================================
# Check Space Ranger output dimensions
python -c "
import scanpy as sc
adata = sc.read_visium('PA08/outs/')
print(f'PA08: {adata.n_obs} spots x {adata.n_vars} genes')
print(f'Spatial coords shape: {adata.obsm[\"spatial\"].shape}')
"
