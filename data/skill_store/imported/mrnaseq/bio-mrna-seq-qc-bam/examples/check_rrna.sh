#!/bin/bash
# Reference: NCBI BLAST+ 2.15+, numpy 1.26+, picard 3.1+, pysam 0.22+, samtools 1.19+ | Verify API if version differs
# Check rRNA contamination with SortMeRNA

FASTQ=$1
RRNA_DB=${2:-/path/to/sortmerna/rRNA_databases/smr_v4.3_default_db.fasta}
THREADS=${3:-8}

if [ -z "$FASTQ" ]; then
    echo "Usage: $0 <reads.fastq.gz> [rRNA_db] [threads]"
    exit 1
fi

NAME=$(basename "$FASTQ" .fastq.gz)
NAME=$(basename "$NAME" .fq.gz)

mkdir -p sortmerna_tmp

sortmerna \
    --ref "$RRNA_DB" \
    --reads "$FASTQ" \
    --aligned "${NAME}_rRNA" \
    --other "${NAME}_non_rRNA" \
    --fastx \
    --threads "$THREADS" \
    --workdir sortmerna_tmp

# Approximate read count via '@' header lines (exact for well-formed FASTQ)
total=$(zcat "$FASTQ" 2>/dev/null | grep -c "^@" || cat "$FASTQ" | grep -c "^@")

# SortMeRNA 4.x may produce different output extensions; check several possibilities
rrna=0
for ext in fastq fq fastq.gz fq.gz; do
    if [ -f "${NAME}_rRNA.${ext}" ]; then
        if [[ "$ext" == *.gz ]]; then
            rrna=$(zcat "${NAME}_rRNA.${ext}" | grep -c "^@")
        else
            rrna=$(grep -c "^@" "${NAME}_rRNA.${ext}")
        fi
        break
    fi
done

pct=$(echo "scale=2; $rrna / $total * 100" | bc)

echo "=== rRNA Check: $NAME ==="
echo "Total reads: $total"
echo "rRNA reads: $rrna"
echo "rRNA percentage: ${pct}%"

if [ "$(echo "$pct > 20" | bc -l)" -eq 1 ]; then
    echo "WARNING: High rRNA contamination (>20%)"
elif [ "$(echo "$pct > 10" | bc -l)" -eq 1 ]; then
    echo "NOTE: Moderate rRNA contamination (10-20%)"
else
    echo "OK: rRNA within acceptable range (<10%)"
fi

rm -rf sortmerna_tmp
