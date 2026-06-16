#!/bin/bash
set -euo pipefail
# Run RiboCode periodicity/validation analysis for one sample
# Usage: bash batch_ribocode.sh [GTF] [BAM] [FASTA] [OUTDIR] [SAMPLE]

GTF="$1"
BAM="$2"
FASTA="$3"
OUTDIR="${4:-results/03_periodicity/ribocode_validation}"
SAMPLE="${5:-sample1}"

mkdir -p "$OUTDIR/$SAMPLE"

RiboCode_onestep \
  -g "$GTF" \
  -r "$BAM" \
  -f "$FASTA" \
  -o "$OUTDIR/$SAMPLE"
