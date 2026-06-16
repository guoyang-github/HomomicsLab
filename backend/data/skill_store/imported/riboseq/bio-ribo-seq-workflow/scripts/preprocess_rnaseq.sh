#!/bin/bash
# Preprocess mRNA-seq reads for TE analysis
# Usage: bash scripts/preprocess_rnaseq.sh [PROJECT_DIR] [ADAPTER_R1] [ADAPTER_R2]

set -euo pipefail

PROJECT_DIR="${1:-riboseq_project}"
ADAPTER_R1="${2:-AGATCGGAAGAGCACACGTCTGAACTCCAGTCA}"
ADAPTER_R2="${3:-AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT}"
outdir="$PROJECT_DIR/results/02_rna_preprocessing"

mkdir -p "$outdir"/counts

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

echo "[4/11] Preprocessing mRNA-seq..."

while IFS=, read -r sample condition ribo_fastq rna_r1 rna_r2; do
    # Strip UTF-8 BOM if present
    sample="${sample#$'\xEF\xBB\xBF'}"
    [[ "$sample" == "sample" ]] && continue
    [[ -z "$rna_r1" ]] && continue
    [[ -z "$rna_r2" ]] && continue

    cutadapt \
        -a "$ADAPTER_R1" \
        -A "$ADAPTER_R2" \
        -m 20 \
        -o "$outdir/${sample}_R1_trimmed.fastq.gz" \
        -p "$outdir/${sample}_R2_trimmed.fastq.gz" \
        "$rna_r1" "$rna_r2"

    bowtie2 -x "$PROJECT_DIR/results/00_index/bowtie2_rrna/rrna" \
        -1 "$outdir/${sample}_R1_trimmed.fastq.gz" \
        -2 "$outdir/${sample}_R2_trimmed.fastq.gz" \
        --un-conc-gz "$outdir/${sample}_trimmed.fastq.gz" \
        -S /dev/null -p 8

    # Bowtie2 outputs ${prefix}.1.gz and ${prefix}.2.gz; rename for consistency
    mv "$outdir/${sample}_trimmed.fastq.1.gz" "$outdir/${sample}_trimmed.1.fastq.gz" || true
    mv "$outdir/${sample}_trimmed.fastq.2.gz" "$outdir/${sample}_trimmed.2.fastq.gz" || true

    STAR --runMode alignReads \
        --genomeDir "$PROJECT_DIR/results/00_index/star_genome/" \
        --readFilesIn "$outdir/${sample}_trimmed.1.fastq.gz" \
                    "$outdir/${sample}_trimmed.2.fastq.gz" \
        --readFilesCommand zcat \
        --outFilterMultimapNmax 20 \
        --outFilterMismatchNmax 2 \
        --alignIntronMin 20 \
        --alignIntronMax 1000000 \
        --outSAMtype BAM SortedByCoordinate \
        --outFileNamePrefix "$outdir/${sample}_"

    mv "$outdir/${sample}_Aligned.sortedByCoord.out.bam" "$outdir/${sample}.sorted.bam"
    samtools index "$outdir/${sample}.sorted.bam"
    samtools flagstat "$outdir/${sample}.sorted.bam" > "$outdir/${sample}.flagstat"

    echo "  [rna] $sample done"
done < "$PROJECT_DIR/samplesheet.csv"

echo "[4/11] mRNA-seq preprocessing complete."
