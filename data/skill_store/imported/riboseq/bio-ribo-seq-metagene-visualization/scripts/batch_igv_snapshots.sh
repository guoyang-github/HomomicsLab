#!/bin/bash
set -euo pipefail
# Generate IGV batch snapshot script
# Usage: bash scripts/batch_igv_snapshots.sh [GENOME] [BED] [BAM_DIR] [OUTDIR]

GENOME="$1"
BED="$2"
BAM_DIR="$3"
OUTDIR="${4:-results/08_visualization/igv_snapshots}"

mkdir -p "$OUTDIR"

cat > "$OUTDIR/igv_batch.txt" <<EOF
new
genome $GENOME
snapshotDirectory $OUTDIR
EOF

while read -r chrom start end gene strand; do
  win_start=$(( start > 500 ? start - 500 : 0 ))
  win_end=$(( end + 500 ))
  echo "goto ${chrom}:${win_start}-${win_end}" >> "$OUTDIR/igv_batch.txt"

  for bam in "$BAM_DIR"/*.sorted.bam; do
    echo "load $bam" >> "$OUTDIR/igv_batch.txt"
  done

  echo "snapshot ${gene}.png" >> "$OUTDIR/igv_batch.txt"
done < "$BED"

echo "IGV batch script written to $OUTDIR/igv_batch.txt"
echo "Run: xvfb-run igv.sh -b $OUTDIR/igv_batch.txt"
