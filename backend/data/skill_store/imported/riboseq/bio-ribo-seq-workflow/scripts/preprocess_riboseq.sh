#!/bin/bash
# Preprocess Ribo-seq reads
# Usage: bash scripts/preprocess_riboseq.sh [PROJECT_DIR] [ADAPTER] [MIN_LENGTH] [MAX_LENGTH] [RRNA_TOOL]
#   RRNA_TOOL: bowtie2 (default) or sortmerna

set -euo pipefail

PROJECT_DIR="${1:-riboseq_project}"
ADAPTER_SEQ="${2:-CTGTAGGCACCATCAAT}"
MIN_LENGTH="${3:-28}"
MAX_LENGTH="${4:-32}"
RRNA_TOOL="${5:-bowtie2}"

outdir="$PROJECT_DIR/results/02_ribo_preprocessing"
mkdir -p "$outdir"

# Validate required indexes exist
STAR_INDEX="$PROJECT_DIR/results/00_index/star_genome"
RRNA_INDEX="$PROJECT_DIR/results/00_index/bowtie2_rrna/rrna"
for req in "$STAR_INDEX/SA" "$RRNA_INDEX".1.bt2; do
    if [[ ! -e "$req" ]]; then
        echo "Error: Required index not found: $req" >&2
        echo "Run build_indexes.sh first." >&2
        exit 1
    fi
done

echo "[3/11] Preprocessing Ribo-seq (rRNA tool: $RRNA_TOOL)..."

while IFS=, read -r sample condition ribo_fastq rna_r1 rna_r2; do
    # Strip UTF-8 BOM if present
    sample="${sample#$'\xEF\xBB\xBF'}"
    [[ "$sample" == "sample" ]] && continue
    [[ -z "$ribo_fastq" ]] && continue

    cutadapt -a "$ADAPTER_SEQ" -m 20 -M 40 \
        -o "$outdir/${sample}_trimmed.fastq.gz" "$ribo_fastq"

    cutadapt -m "$MIN_LENGTH" -M "$MAX_LENGTH" \
        -o "$outdir/${sample}_size_selected.fastq.gz" \
        "$outdir/${sample}_trimmed.fastq.gz"

    if [[ "$RRNA_TOOL" == "sortmerna" ]]; then
        # SortMeRNA requires pre-built indices or reference databases
        # Assumes rRNA_databases/ exists with SILVA reference files
        sortmerna \
            --ref "$PROJECT_DIR"/rRNA_databases/silva-bac-16s-id90.fasta \
            --ref "$PROJECT_DIR"/rRNA_databases/silva-euk-18s-id95.fasta \
            --ref "$PROJECT_DIR"/rRNA_databases/silva-euk-28s-id98.fasta \
            --reads "$outdir/${sample}_size_selected.fastq.gz" \
            --aligned "$outdir/${sample}_rRNA_reads" \
            --other "$outdir/${sample}_non_rRNA_reads" \
            --fastx \
            --threads 8 2>/dev/null || {
                echo "Warning: SortMeRNA failed for $sample, falling back to bowtie2" >&2
                bowtie2 -x "$PROJECT_DIR/results/00_index/bowtie2_rrna/rrna" \
                    -U "$outdir/${sample}_size_selected.fastq.gz" \
                    --un-gz "$outdir/${sample}_non_rRNA.fastq.gz" \
                    -S /dev/null -p 8
            }
        mv "$outdir/${sample}_non_rRNA_reads.fq.gz" "$outdir/${sample}_non_rRNA.fastq.gz" 2>/dev/null || true
    else
        bowtie2 -x "$PROJECT_DIR/results/00_index/bowtie2_rrna/rrna" \
            -U "$outdir/${sample}_size_selected.fastq.gz" \
            --un-gz "$outdir/${sample}_non_rRNA.fastq.gz" \
            -S /dev/null -p 8
    fi

    STAR --runMode alignReads \
        --genomeDir "$PROJECT_DIR/results/00_index/star_genome/" \
        --readFilesIn "$outdir/${sample}_non_rRNA.fastq.gz" \
        --readFilesCommand zcat \
        --outFilterMultimapNmax 1 \
        --outFilterMismatchNmax 2 \
        --alignIntronMax 1 \
        --outSAMtype BAM SortedByCoordinate \
        --outFileNamePrefix "$outdir/${sample}_"

    mv "$outdir/${sample}_Aligned.sortedByCoord.out.bam" "$outdir/${sample}.sorted.bam"
    samtools index "$outdir/${sample}.sorted.bam"
    samtools flagstat "$outdir/${sample}.sorted.bam" > "$outdir/${sample}.flagstat"

    echo "  [ribo] $sample done"
done < "$PROJECT_DIR/samplesheet.csv"

echo "[3/11] Ribo-seq preprocessing complete."
