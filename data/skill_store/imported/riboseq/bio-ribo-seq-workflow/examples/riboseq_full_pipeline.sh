#!/bin/bash
set -euo pipefail
# Complete Ribo-seq analysis pipeline
# TODO: Replace placeholder arguments below with your actual file paths

FASTQ="$1"
RRNA_INDEX="$2"
STAR_INDEX="$3"
ANNOTATION="$4"
OUTPUT_DIR="${5:-riboseq_results}"
ADAPTER="${6:-CTGTAGGCACCATCAAT}"

mkdir -p "${OUTPUT_DIR}"/trimmed "${OUTPUT_DIR}"/aligned "${OUTPUT_DIR}"/plastid

echo "=== Step 1: Adapter Trimming ==="
cutadapt \
    -a "$ADAPTER" \
    --minimum-length 25 \
    --maximum-length 35 \
    -o "${OUTPUT_DIR}/trimmed/trimmed.fastq.gz" \
    "$FASTQ" \
    > "${OUTPUT_DIR}/trimmed/cutadapt_report.txt"

echo "Size distribution after trimming:"
if command -v zcat &> /dev/null; then
    zcat "${OUTPUT_DIR}/trimmed/trimmed.fastq.gz" | \
        awk 'NR%4==2 {print length}' | sort -n | uniq -c
else
    gzip -cd "${OUTPUT_DIR}/trimmed/trimmed.fastq.gz" | \
        awk 'NR%4==2 {print length}' | sort -n | uniq -c
fi

echo "=== Step 2: rRNA Removal ==="
bowtie2 \
    -x "$RRNA_INDEX" \
    -U "${OUTPUT_DIR}/trimmed/trimmed.fastq.gz" \
    --un-gz "${OUTPUT_DIR}/trimmed/non_rrna.fastq.gz" \
    -S /dev/null \
    2> "${OUTPUT_DIR}/trimmed/rrna_removal.log"

echo "rRNA removal stats:"
grep "overall alignment rate" "${OUTPUT_DIR}/trimmed/rrna_removal.log"

echo "=== Step 3: Alignment ==="
STAR \
    --genomeDir "$STAR_INDEX" \
    --readFilesIn "${OUTPUT_DIR}/trimmed/non_rrna.fastq.gz" \
    --readFilesCommand zcat \
    --outFilterMismatchNmax 2 \
    --alignEndsType EndToEnd \
    --outSAMtype BAM SortedByCoordinate \
    --outFileNamePrefix "${OUTPUT_DIR}/aligned/" \
    --runThreadN 8

samtools index "${OUTPUT_DIR}/aligned/Aligned.sortedByCoord.out.bam"

echo "=== Step 4: P-site Calibration (Plastid) ==="
cd "${OUTPUT_DIR}/plastid"

metagene generate \
    "$ANNOTATION" \
    --landmark cds_start \
    --upstream 50 \
    --downstream 100 \
    metagene_cds_start

metagene count \
    metagene_cds_start_rois.txt \
    "${OUTPUT_DIR}/aligned/Aligned.sortedByCoord.out.bam" \
    metagene_profile

psite metagene_profile_metagene_profile.txt psite_offsets.txt \
    --min 25 --max 35

cd -

echo "=== Pipeline Complete ==="
echo "Results in: $OUTPUT_DIR"
echo ""
echo "Key outputs:"
echo "  - Aligned BAM: ${OUTPUT_DIR}/aligned/Aligned.sortedByCoord.out.bam"
echo "  - P-site offsets: ${OUTPUT_DIR}/plastid/psite_offsets.txt"
echo ""
echo "Next steps:"
echo "  - Apply P-site offsets for precise positioning"
echo "  - Calculate translation efficiency (requires paired RNA-seq)"
echo "  - Run ORF detection with RiboCode"
