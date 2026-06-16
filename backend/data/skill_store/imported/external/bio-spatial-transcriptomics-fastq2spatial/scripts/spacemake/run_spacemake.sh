#!/bin/bash
# Batch runner for Spacemake across a SampleSheet.
# Usage: bash run_spacemake.sh --project-dir /path/to/project --samplesheet samples.csv [--cores 16]

set -euo pipefail

CORES=16

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-dir)
            PROJECT_DIR="$2"
            shift 2
            ;;
        --samplesheet)
            SAMPLESHEET="$2"
            shift 2
            ;;
        --cores)
            CORES="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "${PROJECT_DIR:-}" ]] || [[ -z "${SAMPLESHEET:-}" ]] || [[ ! -f "$SAMPLESHEET" ]]; then
    echo "Usage: bash run_spacemake.sh \\"
    echo "  --project-dir /path/to/spacemake_project \\"
    echo "  --samplesheet samples.csv \\"
    echo "  [--cores 16]"
    echo ""
    echo "SampleSheet CSV format:"
    echo "  sample_id,R1,R2,species,puck,run_mode,condition"
    exit 1
fi

if [[ ! -f "$PROJECT_DIR/config.yaml" ]]; then
    echo "ERROR: Spacemake project not initialized. Run init_project.sh first."
    exit 1
fi

echo "=== Spacemake Batch Run ==="
echo "Project directory: $PROJECT_DIR"
echo "SampleSheet: $SAMPLESHEET"
echo "Cores: $CORES"
echo ""

# Read and skip header
tail -n +2 "$SAMPLESHEET" | while IFS=',' read -r sample_id R1 R2 species puck run_mode condition; do
    # Trim whitespace
    sample_id=$(echo "$sample_id" | xargs)
    R1=$(echo "$R1" | xargs)
    R2=$(echo "$R2" | xargs)
    species=$(echo "$species" | xargs)
    puck=$(echo "$puck" | xargs)
    run_mode=$(echo "$run_mode" | xargs)

    if [[ -z "$sample_id" ]]; then
        continue
    fi

    echo "----------------------------------------"
    echo "Adding sample: $sample_id"
    echo "  R1: $R1"
    echo "  R2: $R2"
    echo "  Species: $species"
    echo "  Puck: $puck"
    echo "  Run mode: $run_mode"

    if [[ ! -f "$R1" ]]; then
        echo "  WARNING: R1 file not found, skipping."
        continue
    fi

    if [[ ! -f "$R2" ]]; then
        echo "  WARNING: R2 file not found, skipping."
        continue
    fi

    # Add sample to spacemake
    spacemake projects add_sample \
        --project default \
        --sample_id "$sample_id" \
        --R1 "$R1" \
        --R2 "$R2" \
        --species "$species" \
        --puck "$puck" \
        --run_mode "$run_mode"

echo "  Added: $sample_id"
done

echo ""
echo "Running Spacemake pipeline..."
cd "$PROJECT_DIR"
spacemake run --cores "$CORES" --knit

echo ""
echo "=== Spacemake pipeline complete ==="
echo "Output directory: $PROJECT_DIR/projects/default/processed_data/"
