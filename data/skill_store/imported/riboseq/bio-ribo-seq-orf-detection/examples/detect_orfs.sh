#!/bin/bash
set -euo pipefail
# Reference: BioPython 1.83+, DESeq2 1.42+, pandas 2.2+ | Verify API if version differs
# ORF detection from Ribo-seq using RiboCode

BAM="$1"
GTF="$2"
GENOME="$3"
OUTPUT_DIR="${4:-ribocode_output}"

mkdir -p "$OUTPUT_DIR"

echo "ORF detection with RiboCode"
echo "Input: $BAM"

RiboCode_onestep \
    -g "$GTF" \
    -r "$BAM" \
    -f "$GENOME" \
    -l 27,28,29,30 \
    -o "$OUTPUT_DIR" \
    2>&1 | tee "${OUTPUT_DIR}/ribocode.log"

# Summarize results
RESULT_FILE=($OUTPUT_DIR/*_ORF_result.txt)

if [ -f "${RESULT_FILE[0]}" ]; then
    echo ""
    echo "ORF detection complete!"
    echo ""
    echo "ORF counts by type:"
    awk -F'\t' 'NR>1 {types[$7]++} END {for (t in types) print "  "t": "types[t]}' "${RESULT_FILE[0]}"

    TOTAL=$(wc -l < "${RESULT_FILE[0]}")
    echo "Total ORFs: $((TOTAL - 1))"

    echo ""
    echo "Output files:"
    ls -lh "${OUTPUT_DIR}"/*ORF*
else
    echo "No results found. Check ribocode.log for errors."
fi
