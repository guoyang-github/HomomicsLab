#!/bin/bash
# Project setup for Ribo-seq workflow
# Usage: bash scripts/project_setup.sh [PROJECT_DIR] [SPECIES] [RUN_MODE]

set -euo pipefail

PROJECT_DIR="${1:-riboseq_project}"
SPECIES="${2:-human}"
RUN_MODE="${3:-full}"

mkdir -p "$PROJECT_DIR"/results/{00_index,01_qc,02_ribo_preprocessing,02_rna_preprocessing,03_periodicity,04_differential,05_orf_detection,06_orf_quantification,07_stalling,08_visualization,99_report}

# Load species parameters (from species-templates skill)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source <(bash "$SCRIPT_DIR"/generate_species_config.sh "$SPECIES")

echo "=== Ribo-seq Pipeline ==="
echo "Species: $SPECIES"
echo "Mode: $RUN_MODE"
echo "Adapter: ${ADAPTER_SEQ:-CTGTAGGCACCATCAAT}"
echo "Footprint size: ${MIN_LENGTH:-28}-${MAX_LENGTH:-32} nt"
