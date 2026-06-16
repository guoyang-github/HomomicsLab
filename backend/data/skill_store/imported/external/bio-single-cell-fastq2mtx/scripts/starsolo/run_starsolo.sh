#!/bin/bash
# Wrapper script to run STARsolo with 10x-compatible output.
# Usage: bash run_starsolo.sh --index /path/to/index --r1 R1.fastq.gz --r2 R2.fastq.gz --sample NAME --output-dir out/ [--threads 16]

set -euo pipefail

# Default values
THREADS=8
SOLO_FEATURES="Gene"
SOLO_UMI_LEN=12
SOLO_CB_LEN=16

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --index)
            INDEX="$2"
            shift 2
            ;;
        --r1)
            R1_FILES="$2"
            shift 2
            ;;
        --r2)
            R2_FILES="$2"
            shift 2
            ;;
        --sample)
            SAMPLE="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --threads)
            THREADS="$2"
            shift 2
            ;;
        --solo-features)
            SOLO_FEATURES="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required args
if [[ -z "${INDEX:-}" ]] || [[ -z "${R1_FILES:-}" ]] || [[ -z "${R2_FILES:-}" ]] || [[ -z "${SAMPLE:-}" ]] || [[ -z "${OUTPUT_DIR:-}" ]]; then
    echo "Usage: bash run_starsolo.sh \\"
    echo "  --index /path/to/star_index \\"
    echo "  --r1 'R1.fastq.gz [R1_L002.fastq.gz ...]' \\"
    echo "  --r2 'R2.fastq.gz [R2_L002.fastq.gz ...]' \\"
    echo "  --sample SAMPLE_NAME \\"
    echo "  --output-dir /path/to/output \\"
    echo "  [--threads 16] [--solo-features Gene]"
    exit 1
fi

# Resolve whitelist based on chemistry (default: 10x v3)
# Common whitelist paths
WHITELIST=""
if command -v cellranger &> /dev/null; then
    # Try to find whitelist from cellranger installation
    CELLRANGER_DIR=$(dirname "$(which cellranger)")
    POSSIBLE_WL="$CELLRANGER_DIR/../lib/python/cellranger/barcodes/737K-august-2016.txt"
    if [[ -f "$POSSIBLE_WL" ]]; then
        WHITELIST="$POSSIBLE_WL"
    fi
fi

# Fallback: try to find in current environment
if [[ -z "$WHITELIST" ]]; then
    for path in \
        "737K-august-2016.txt" \
        "3M-february-2018.txt" \
        "/opt/10x/barcodes/737K-august-2016.txt"; do
        if [[ -f "$path" ]]; then
            WHITELIST="$path"
            break
        fi
    done
fi

if [[ -z "$WHITELIST" ]]; then
    echo "WARNING: Could not find 10x barcode whitelist. STARsolo will use --soloCBmatchWLtype 1MM_multi_pseudocounts without explicit whitelist."
    echo "For best results, download the whitelist from 10x Genomics:"
    echo "  wget https://teichlab.github.io/scg_lib_structs/data/737K-august-2016.txt"
    WL_ARG=""
else
    echo "Using whitelist: $WHITELIST"
    WL_ARG="--soloCBwhitelist $WHITELIST"
fi

mkdir -p "$OUTPUT_DIR"

echo "=== STARsolo Run ==="
echo "Sample: $SAMPLE"
echo "Index: $INDEX"
echo "R1: $R1_FILES"
echo "R2: $R2_FILES"
echo "Output: $OUTPUT_DIR"
echo "Threads: $THREADS"
echo "Features: $SOLO_FEATURES"
echo ""

# Detect if input is gzipped
READ_FILES_COMMAND="cat"
if [[ "$R2_FILES" == *.gz ]]; then
    READ_FILES_COMMAND="zcat"
fi

# Run STARsolo
# Note: --readFilesIn expects cDNA (R2) first, then barcode (R1)
STAR \
    --genomeDir "$INDEX" \
    --readFilesIn $R2_FILES $R1_FILES \
    --readFilesCommand "$READ_FILES_COMMAND" \
    --soloType CB_UMI_Simple \
    --soloFeatures "$SOLO_FEATURES" \
    --soloUMIlen "$SOLO_UMI_LEN" \
    --soloCBlen "$SOLO_CB_LEN" \
    $WL_ARG \
    --soloCBmatchWLtype 1MM_multi_pseudocounts \
    --soloUMIdedup 1MM_CR \
    --outFileNamePrefix "$OUTPUT_DIR/" \
    --outSAMtype BAM SortedByCoordinate \
    --outBAMsortingThreadN "$THREADS" \
    --runThreadN "$THREADS"

# Reorganize output to match Cell Ranger structure
echo ""
echo "Reorganizing output to 10x-compatible format..."

SOLO_DIR="$OUTPUT_DIR/Solo.out/${SOLO_FEATURES}"
if [[ -d "$SOLO_DIR/filtered" ]]; then
    mkdir -p "$OUTPUT_DIR/filtered_feature_bc_matrix"
    cp "$SOLO_DIR/filtered/barcodes.tsv.gz" "$OUTPUT_DIR/filtered_feature_bc_matrix/" 2>/dev/null || \
        cp "$SOLO_DIR/filtered/barcodes.tsv" "$OUTPUT_DIR/filtered_feature_bc_matrix/" && \
        gzip "$OUTPUT_DIR/filtered_feature_bc_matrix/barcodes.tsv"
    cp "$SOLO_DIR/filtered/features.tsv.gz" "$OUTPUT_DIR/filtered_feature_bc_matrix/" 2>/dev/null || \
        cp "$SOLO_DIR/filtered/features.tsv" "$OUTPUT_DIR/filtered_feature_bc_matrix/" && \
        gzip "$OUTPUT_DIR/filtered_feature_bc_matrix/features.tsv"
    cp "$SOLO_DIR/filtered/matrix.mtx.gz" "$OUTPUT_DIR/filtered_feature_bc_matrix/" 2>/dev/null || \
        cp "$SOLO_DIR/filtered/matrix.mtx" "$OUTPUT_DIR/filtered_feature_bc_matrix/" && \
        gzip "$OUTPUT_DIR/filtered_feature_bc_matrix/matrix.mtx"
    echo "Created: $OUTPUT_DIR/filtered_feature_bc_matrix/"
fi

if [[ -d "$SOLO_DIR/raw" ]]; then
    mkdir -p "$OUTPUT_DIR/raw_feature_bc_matrix"
    cp "$SOLO_DIR/raw/barcodes.tsv.gz" "$OUTPUT_DIR/raw_feature_bc_matrix/" 2>/dev/null || \
        cp "$SOLO_DIR/raw/barcodes.tsv" "$OUTPUT_DIR/raw_feature_bc_matrix/" && \
        gzip "$OUTPUT_DIR/raw_feature_bc_matrix/barcodes.tsv"
    cp "$SOLO_DIR/raw/features.tsv.gz" "$OUTPUT_DIR/raw_feature_bc_matrix/" 2>/dev/null || \
        cp "$SOLO_DIR/raw/features.tsv" "$OUTPUT_DIR/raw_feature_bc_matrix/" && \
        gzip "$OUTPUT_DIR/raw_feature_bc_matrix/features.tsv"
    cp "$SOLO_DIR/raw/matrix.mtx.gz" "$OUTPUT_DIR/raw_feature_bc_matrix/" 2>/dev/null || \
        cp "$SOLO_DIR/raw/matrix.mtx" "$OUTPUT_DIR/raw_feature_bc_matrix/" && \
        gzip "$OUTPUT_DIR/raw_feature_bc_matrix/matrix.mtx"
    echo "Created: $OUTPUT_DIR/raw_feature_bc_matrix/"
fi

echo ""
echo "=== STARsolo complete: $SAMPLE ==="
echo "Summary: $OUTPUT_DIR/Solo.out/${SOLO_FEATURES}/Summary.csv"
