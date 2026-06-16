#!/bin/bash
# Main orchestrator for the Ribo-seq workflow
# Usage: bash scripts/run_pipeline.sh [SPECIES] [RUN_MODE] [GENOME_FA] [GTF] [RRNA_FA]

set -euo pipefail

SPECIES="${1:-human}"
RUN_MODE="${2:-full}"
GENOME_FA="${3:-genome.fa}"
GTF="${4:-annotation.gtf}"
RRNA_FA="${5:-rrna.fa}"

PROJECT_DIR="riboseq_project"

# Load species config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source <(bash "$SCRIPT_DIR"/generate_species_config.sh "$SPECIES")
export P_SITE_OFFSETS_JSON

case "$RUN_MODE" in
    full)
        bash "$SCRIPT_DIR"/build_indexes.sh "$PROJECT_DIR" "$SPECIES" "$GENOME_FA" "$GTF" "$RRNA_FA" "${STAR_ALIGN_SJDB_OVERHANG:-49}"
        bash "$SCRIPT_DIR"/run_qc_raw.sh "$PROJECT_DIR"
        bash "$SCRIPT_DIR"/preprocess_riboseq.sh "$PROJECT_DIR" "$ADAPTER_SEQ" "$MIN_LENGTH" "$MAX_LENGTH" "${RRNA_TOOL:-bowtie2}"
        bash "$SCRIPT_DIR"/preprocess_rnaseq.sh "$PROJECT_DIR" "${RNA_SEQ_ADAPTER_R1:-AGATCGGAAGAGCACACGTCTGAACTCCAGTCA}" "${RNA_SEQ_ADAPTER_R2:-AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT}"
        bash "$SCRIPT_DIR"/run_periodicity.sh "$PROJECT_DIR" "$MIN_LENGTH" "$MAX_LENGTH" "$P_SITE_OFFSETS_JSON" "${P_SITE_OFFSET_MIN:-10}" "${P_SITE_OFFSET_MAX:-16}"
        bash "$SCRIPT_DIR"/run_differential_occupancy.sh "$PROJECT_DIR"
        bash "$SCRIPT_DIR"/run_differential_te.sh "$PROJECT_DIR"
        bash "$SCRIPT_DIR"/detect_orfs.sh "$PROJECT_DIR" "$MIN_LENGTH" "$MAX_LENGTH"
        Rscript "$SCRIPT_DIR"/quantify_orfs.R \
            "$PROJECT_DIR"/results/00_index/annotation_clean.gtf \
            "$PROJECT_DIR"/results/02_ribo_preprocessing \
            "$PROJECT_DIR"/results/06_orf_quantification
        python3 "$SCRIPT_DIR"/detect_stalling.py \
            --bam-dir "$PROJECT_DIR"/results/02_ribo_preprocessing \
            --gtf "$PROJECT_DIR"/results/00_index/annotation_clean.gtf \
            --psite-dir "$PROJECT_DIR"/results/03_periodicity \
            --outdir "$PROJECT_DIR"/results/07_stalling
        python3 "$SCRIPT_DIR"/generate_metagene_plots.py \
            --bam-dir "$PROJECT_DIR"/results/02_ribo_preprocessing \
            --gtf "$PROJECT_DIR"/results/00_index/annotation_clean.gtf \
            --psite-dir "$PROJECT_DIR"/results/03_periodicity \
            --outdir "$PROJECT_DIR"/results/08_visualization
        bash "$SCRIPT_DIR"/generate_final_report.sh "$PROJECT_DIR"
        ;;
    ribo-only)
        bash "$SCRIPT_DIR"/build_indexes.sh "$PROJECT_DIR" "$SPECIES" "$GENOME_FA" "$GTF" "$RRNA_FA" "${STAR_ALIGN_SJDB_OVERHANG:-49}"
        bash "$SCRIPT_DIR"/run_qc_raw.sh "$PROJECT_DIR"
        bash "$SCRIPT_DIR"/preprocess_riboseq.sh "$PROJECT_DIR" "$ADAPTER_SEQ" "$MIN_LENGTH" "$MAX_LENGTH" "${RRNA_TOOL:-bowtie2}"
        bash "$SCRIPT_DIR"/run_periodicity.sh "$PROJECT_DIR" "$MIN_LENGTH" "$MAX_LENGTH" "$P_SITE_OFFSETS_JSON" "${P_SITE_OFFSET_MIN:-10}" "${P_SITE_OFFSET_MAX:-16}"
        bash "$SCRIPT_DIR"/detect_orfs.sh "$PROJECT_DIR" "$MIN_LENGTH" "$MAX_LENGTH"
        Rscript "$SCRIPT_DIR"/quantify_orfs.R \
            "$PROJECT_DIR"/results/00_index/annotation_clean.gtf \
            "$PROJECT_DIR"/results/02_ribo_preprocessing \
            "$PROJECT_DIR"/results/06_orf_quantification
        python3 "$SCRIPT_DIR"/generate_metagene_plots.py \
            --bam-dir "$PROJECT_DIR"/results/02_ribo_preprocessing \
            --gtf "$PROJECT_DIR"/results/00_index/annotation_clean.gtf \
            --psite-dir "$PROJECT_DIR"/results/03_periodicity \
            --outdir "$PROJECT_DIR"/results/08_visualization
        bash "$SCRIPT_DIR"/generate_final_report.sh "$PROJECT_DIR"
        ;;
    te-only)
        bash "$SCRIPT_DIR"/build_indexes.sh "$PROJECT_DIR" "$SPECIES" "$GENOME_FA" "$GTF" "$RRNA_FA" "${STAR_ALIGN_SJDB_OVERHANG:-49}"
        bash "$SCRIPT_DIR"/preprocess_riboseq.sh "$PROJECT_DIR" "$ADAPTER_SEQ" "$MIN_LENGTH" "$MAX_LENGTH" "${RRNA_TOOL:-bowtie2}"
        bash "$SCRIPT_DIR"/preprocess_rnaseq.sh "$PROJECT_DIR" "${RNA_SEQ_ADAPTER_R1:-AGATCGGAAGAGCACACGTCTGAACTCCAGTCA}" "${RNA_SEQ_ADAPTER_R2:-AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT}"
        bash "$SCRIPT_DIR"/run_periodicity.sh "$PROJECT_DIR" "$MIN_LENGTH" "$MAX_LENGTH" "$P_SITE_OFFSETS_JSON" "${P_SITE_OFFSET_MIN:-10}" "${P_SITE_OFFSET_MAX:-16}"
        bash "$SCRIPT_DIR"/run_differential_occupancy.sh "$PROJECT_DIR"
        bash "$SCRIPT_DIR"/run_differential_te.sh "$PROJECT_DIR"
        bash "$SCRIPT_DIR"/generate_final_report.sh "$PROJECT_DIR"
        ;;
    orf-only)
        bash "$SCRIPT_DIR"/build_indexes.sh "$PROJECT_DIR" "$SPECIES" "$GENOME_FA" "$GTF" "$RRNA_FA" "${STAR_ALIGN_SJDB_OVERHANG:-49}"
        bash "$SCRIPT_DIR"/preprocess_riboseq.sh "$PROJECT_DIR" "$ADAPTER_SEQ" "$MIN_LENGTH" "$MAX_LENGTH" "${RRNA_TOOL:-bowtie2}"
        bash "$SCRIPT_DIR"/run_periodicity.sh "$PROJECT_DIR" "$MIN_LENGTH" "$MAX_LENGTH" "$P_SITE_OFFSETS_JSON" "${P_SITE_OFFSET_MIN:-10}" "${P_SITE_OFFSET_MAX:-16}"
        bash "$SCRIPT_DIR"/detect_orfs.sh "$PROJECT_DIR" "$MIN_LENGTH" "$MAX_LENGTH"
        Rscript "$SCRIPT_DIR"/quantify_orfs.R \
            "$PROJECT_DIR"/results/00_index/annotation_clean.gtf \
            "$PROJECT_DIR"/results/02_ribo_preprocessing \
            "$PROJECT_DIR"/results/06_orf_quantification
        python3 "$SCRIPT_DIR"/generate_metagene_plots.py \
            --bam-dir "$PROJECT_DIR"/results/02_ribo_preprocessing \
            --gtf "$PROJECT_DIR"/results/00_index/annotation_clean.gtf \
            --psite-dir "$PROJECT_DIR"/results/03_periodicity \
            --outdir "$PROJECT_DIR"/results/08_visualization
        bash "$SCRIPT_DIR"/generate_final_report.sh "$PROJECT_DIR"
        ;;
    *)
        echo "Unknown mode: $RUN_MODE"
        exit 1
        ;;
esac
