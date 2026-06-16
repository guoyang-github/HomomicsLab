#!/bin/bash
# Build a STAR genome index for STARsolo.
# Usage: bash make_index.sh --genome-fasta genome.fa --gtf genes.gtf --output-dir /path/to/index [--threads 16]

set -euo pipefail

THREADS=8

while [[ $# -gt 0 ]]; do
    case "$1" in
        --genome-fasta)
            GENOME_FASTA="$2"
            shift 2
            ;;
        --gtf)
            GTF="$2"
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
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "${GENOME_FASTA:-}" ]] || [[ -z "${GTF:-}" ]] || [[ -z "${OUTPUT_DIR:-}" ]]; then
    echo "Usage: bash make_index.sh \\"
    echo "  --genome-fasta /path/to/genome.fa \\"
    echo "  --gtf /path/to/annotation.gtf \\"
    echo "  --output-dir /path/to/output_index \\"
    echo "  [--threads 16]"
    echo ""
    echo "Example (Human GRCh38):"
    echo "  bash make_index.sh \\"
    echo "    --genome-fasta GRCh38.primary_assembly.genome.fa \\"
    echo "    --gtf gencode.v45.primary_assembly.annotation.gtf \\"
    echo "    --output-dir star_index_GRCh38 \\"
    echo "    --threads 16"
    exit 1
fi

if [[ ! -f "$GENOME_FASTA" ]]; then
    echo "ERROR: Genome FASTA not found: $GENOME_FASTA"
    exit 1
fi

if [[ ! -f "$GTF" ]]; then
    echo "ERROR: GTF not found: $GTF"
    exit 1
fi

# Estimate genome size for sjdbOverhang
genome_size=$(stat --printf="%s" "$GENOME_FASTA" 2>/dev/null || stat -f%z "$GENOME_FASTA" 2>/dev/null || echo 3100000000)

# For typical scRNA-seq with 150bp reads, use 149
READ_LENGTH=149

echo "=== Building STAR Genome Index ==="
echo "Genome: $GENOME_FASTA"
echo "GTF: $GTF"
echo "Output: $OUTPUT_DIR"
echo "Threads: $THREADS"
echo "sjdbOverhang: $READ_LENGTH"
echo ""

mkdir -p "$OUTPUT_DIR"

STAR \
    --runMode genomeGenerate \
    --genomeDir "$OUTPUT_DIR" \
    --genomeFastaFiles "$GENOME_FASTA" \
    --sjdbGTFfile "$GTF" \
    --sjdbOverhang "$READ_LENGTH" \
    --runThreadN "$THREADS"

echo ""
echo "=== Index build complete ==="
echo "Index location: $OUTPUT_DIR"
echo ""
echo "Index size:"
du -sh "$OUTPUT_DIR"
