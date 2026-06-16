#!/bin/bash
# Batch runner for Cell Ranger count across a SampleSheet.
# Usage: bash run_count.sh samplesheet.csv [--cores N] [--mem N]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAMPLESHEET=""
CORES=16
MEMORY=64

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --cores)
            CORES="$2"
            shift 2
            ;;
        --mem)
            MEMORY="$2"
            shift 2
            ;;
        *)
            if [[ -z "$SAMPLESHEET" ]]; then
                SAMPLESHEET="$1"
            fi
            shift
            ;;
    esac
done

if [[ -z "$SAMPLESHEET" ]] || [[ ! -f "$SAMPLESHEET" ]]; then
    echo "Usage: bash run_count.sh samplesheet.csv [--cores N] [--mem N]"
    echo ""
    echo "SampleSheet CSV format:"
    echo "  sample_id,fastq_dir,transcriptome,expect_cells,condition"
    exit 1
fi

echo "=== Cell Ranger Batch Run ==="
echo "SampleSheet: $SAMPLESHEET"
echo "Cores per job: $CORES"
echo "Memory per job: ${MEMORY}GB"
echo ""

# Read and skip header
tail -n +2 "$SAMPLESHEET" | while IFS=',' read -r sample_id fastq_dir transcriptome expect_cells condition; do
    # Trim whitespace
    sample_id=$(echo "$sample_id" | xargs)
    fastq_dir=$(echo "$fastq_dir" | xargs)
    transcriptome=$(echo "$transcriptome" | xargs)

    if [[ -z "$sample_id" ]]; then
        continue
    fi

    echo "----------------------------------------"
    echo "Processing sample: $sample_id"
    echo "  FASTQ dir: $fastq_dir"
    echo "  Transcriptome: $transcriptome"

    if [[ ! -d "$fastq_dir" ]]; then
        echo "  WARNING: FASTQ directory not found, skipping."
        continue
    fi

    # Build optional args
    OPT_ARGS=""
    if [[ -n "${expect_cells:-}" ]] && [[ "$expect_cells" != "expect_cells" ]]; then
        expect_cells=$(echo "$expect_cells" | xargs)
        if [[ -n "$expect_cells" ]]; then
            OPT_ARGS="$OPT_ARGS --expect-cells=$expect_cells"
        fi
    fi

    # Run cellranger
    cellranger count \
        --id="$sample_id" \
        --sample="$sample_id" \
        --transcriptome="$transcriptome" \
        --fastqs="$fastq_dir" \
        --localcores="$CORES" \
        --localmem="$MEMORY" \
        $OPT_ARGS

    echo "  Done: $sample_id"
done

echo ""
echo "=== All samples processed ==="
