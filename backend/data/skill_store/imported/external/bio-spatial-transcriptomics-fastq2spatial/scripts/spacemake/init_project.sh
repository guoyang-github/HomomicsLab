#!/bin/bash
# Initialize a Spacemake project with a species reference.
# Usage: bash init_project.sh --project-dir /path/to/project --species human --genome-fasta genome.fa --gtf genes.gtf [--threads 16]

set -euo pipefail

THREADS=8

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-dir)
            PROJECT_DIR="$2"
            shift 2
            ;;
        --species)
            SPECIES="$2"
            shift 2
            ;;
        --genome-fasta)
            GENOME_FASTA="$2"
            shift 2
            ;;
        --gtf)
            GTF="$2"
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

if [[ -z "${PROJECT_DIR:-}" ]] || [[ -z "${SPECIES:-}" ]] || [[ -z "${GENOME_FASTA:-}" ]] || [[ -z "${GTF:-}" ]]; then
    echo "Usage: bash init_project.sh \\"
    echo "  --project-dir /path/to/project \\"
    echo "  --species human \\"
    echo "  --genome-fasta /path/to/genome.fa \\"
    echo "  --gtf /path/to/annotation.gtf \\"
    echo "  [--threads 16]"
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

echo "=== Initializing Spacemake Project ==="
echo "Project directory: $PROJECT_DIR"
echo "Species: $SPECIES"
echo "Genome: $GENOME_FASTA"
echo "GTF: $GTF"
echo "Threads: $THREADS"
echo ""

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Initialize spacemake if not already initialized
if [[ ! -f "$PROJECT_DIR/config.yaml" ]]; then
    echo "Running spacemake init..."
    spacemake init \
        --dropseq_tools /dev/null \
        --root_dir "$PROJECT_DIR"
else
    echo "Spacemake already initialized."
fi

# Add species to config
echo "Adding species $SPECIES..."
spacemake config add_species \
    --name "$SPECIES" \
    --reference "$GENOME_FASTA" \
    --annotation "$GTF"

# Download/create STAR index via spacemake
echo "Creating STAR index (this may take 1-2 hours)..."
spacemake config create_index \
    --species "$SPECIES" \
    --threads "$THREADS"

echo ""
echo "=== Spacemake project initialized ==="
echo "Project directory: $PROJECT_DIR"
echo ""
echo "Next steps:"
echo "  1. Add samples: spacemake projects add_sample --project default --sample_id SAMPLE ..."
echo "  2. Run pipeline: spacemake run --cores $THREADS"
