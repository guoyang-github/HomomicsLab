#!/bin/bash
# Batch runner for Space Ranger count across a SampleSheet.
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
    echo "  sample_id,fastq_dir,image_path,transcriptome,slide,area,condition"
    exit 1
fi

echo "=== Space Ranger Batch Run ==="
echo "SampleSheet: $SAMPLESHEET"
echo "Cores per job: $CORES"
echo "Memory per job: ${MEMORY}GB"
echo ""

# Read and skip header
tail -n +2 "$SAMPLESHEET" | while IFS=',' read -r sample_id fastq_dir image_path transcriptome slide area condition; do
    # Trim whitespace
    sample_id=$(echo "$sample_id" | xargs)
    fastq_dir=$(echo "$fastq_dir" | xargs)
    image_path=$(echo "$image_path" | xargs)
    transcriptome=$(echo "$transcriptome" | xargs)
    slide=$(echo "$slide" | xargs)
    area=$(echo "$area" | xargs)

    if [[ -z "$sample_id" ]]; then
        continue
    fi

    echo "----------------------------------------"
    echo "Processing sample: $sample_id"
    echo "  FASTQ dir: $fastq_dir"
    echo "  Image: $image_path"
    echo "  Transcriptome: $transcriptome"
    echo "  Slide: $slide"
    echo "  Area: $area"

    if [[ ! -d "$fastq_dir" ]]; then
        echo "  WARNING: FASTQ directory not found, skipping."
        continue
    fi

    if [[ ! -f "$image_path" ]]; then
        echo "  WARNING: Image file not found, skipping."
        continue
    fi

    # Build args
    IMAGE_ARG=""
    if [[ "$image_path" == *dapi* ]] || [[ "$image_path" == *DAPI* ]] || [[ "$image_path" == *dark* ]]; then
        IMAGE_ARG="--darkimage=$image_path"
    else
        IMAGE_ARG="--image=$image_path"
    fi

    SLIDE_ARG=""
    if [[ -n "$slide" ]] && [[ "$slide" != "slide" ]]; then
        SLIDE_ARG="--slide=$slide"
    fi

    AREA_ARG=""
    if [[ -n "$area" ]] && [[ "$area" != "area" ]]; then
        AREA_ARG="--area=$area"
    fi

    # Run spaceranger
    spaceranger count \
        --id="$sample_id" \
        --sample="$sample_id" \
        --transcriptome="$transcriptome" \
        --fastqs="$fastq_dir" \
        "$IMAGE_ARG" \
        $SLIDE_ARG \
        $AREA_ARG \
        --localcores="$CORES" \
        --localmem="$MEMORY"

    echo "  Done: $sample_id"
done

echo ""
echo "=== All samples processed ==="
