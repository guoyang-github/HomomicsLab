#!/bin/bash
# Periodicity analysis and P-site offset estimation
# Usage: bash scripts/run_periodicity.sh [PROJECT_DIR] [MIN_LENGTH] [MAX_LENGTH] [P_SITE_OFFSETS_JSON] [OFFSET_MIN] [OFFSET_MAX]

set -euo pipefail

PROJECT_DIR="${1:-riboseq_project}"
MIN_LENGTH="${2:-28}"
MAX_LENGTH="${3:-32}"
P_SITE_OFFSETS_JSON="${4:-{\"28\": 12, \"29\": 12, \"30\": 13, \"31\": 13, \"32\": 14}}"
OFFSET_MIN="${5:-10}"
OFFSET_MAX="${6:-16}"

outdir="$PROJECT_DIR/results/03_periodicity"
mkdir -p "$outdir"

# Build comma-separated length list for RiboCode (expects all individual lengths, not min-max)
lengths=$(seq "$MIN_LENGTH" "$MAX_LENGTH" | paste -sd ',' -)

echo "[5/11] Periodicity analysis..."

while IFS=, read -r sample condition ribo_fastq rna_r1 rna_r2; do
    # Strip UTF-8 BOM if present
    sample="${sample#$'\xEF\xBB\xBF'}"
    [[ "$sample" == "sample" ]] && continue
    [[ -z "$ribo_fastq" ]] && continue

    RiboCode_onestep \
        -g "$PROJECT_DIR/results/00_index/annotation_clean.gtf" \
        -r "$PROJECT_DIR/results/02_ribo_preprocessing/${sample}.sorted.bam" \
        -f "$PROJECT_DIR/results/00_index/genome.fa" \
        -l "$lengths" \
        -o "$outdir/ribocode_validation/${sample}"

    python3 - "$outdir" "$sample" "$PROJECT_DIR" "$MIN_LENGTH" "$MAX_LENGTH" "$P_SITE_OFFSETS_JSON" "$OFFSET_MIN" "$OFFSET_MAX" <<'PY'
import json, os, sys
import numpy as np
import pysam

outdir, sample, project_dir, min_len, max_len, psite_json_str, offset_min_str, offset_max_str = sys.argv[1:9]
os.makedirs(outdir, exist_ok=True)

default_offsets = {"28": 12, "29": 12, "30": 13, "31": 13, "32": 14}
try:
    offsets = json.loads(psite_json_str) if psite_json_str.strip() and psite_json_str != '{}' else {}
except Exception:
    offsets = {}
if not offsets:
    offsets = default_offsets

OFFSET_MIN = int(offset_min_str)
OFFSET_MAX = int(offset_max_str)

bam_path = f"{project_dir}/results/02_ribo_preprocessing/{sample}.sorted.bam"
gtf = f"{project_dir}/results/00_index/annotation_clean.gtf"

from plastid import BAMGenomeArray, FivePrimeMapFactory, GTF2_TranscriptAssembler, GenomicSegment

transcripts = list(GTF2_TranscriptAssembler(gtf))

length_range = range(int(min_len), int(max_len) + 1)
length_offsets = {}
length_scores = {}

for read_len in length_range:
    # Build per-length BAM array using pysam filter
    alignments = BAMGenomeArray(bam_path, mapping=FivePrimeMapFactory())
    # Override fetch to filter by query_length
    # Plastid doesn't natively filter by length, so we use a custom approach:
    # For each offset candidate, count reads at CDS starts that match the length
    best_offset = int(offsets.get(str(read_len), 12))
    best_peak = -1
    best_score = 0.0

    for offset in range(OFFSET_MIN, OFFSET_MAX + 1):
        frame_counts = [0, 0, 0]
        total = 0
        with pysam.AlignmentFile(bam_path, 'rb') as bam:
            for tx in transcripts:
                if tx.cds_start is None:
                    continue
                chrom, start, strand = tx.chrom, tx.cds_start, tx.strand
                # Start codon reference position:
                # + strand: start codon at cds_start (smaller genomic coord)
                # - strand: start codon at cds_end (larger coord, transcription goes right→left)
                start_codon_pos = start if strand == '+' else tx.cds_end
                region_start = max(0, start_codon_pos - 50)
                region_end = start_codon_pos + 50
                for read in bam.fetch(chrom, region_start, region_end):
                    if read.is_unmapped or read.query_length != read_len:
                        continue
                    # 5' end in genome coordinates (independent of transcript strand)
                    pos_5p = read.reference_end if read.is_reverse else read.reference_start
                    if strand == '+':
                        rel_pos = pos_5p - start_codon_pos
                        psite = rel_pos - offset
                    else:
                        rel_pos = start_codon_pos - pos_5p
                        psite = rel_pos + offset
                    if -50 <= psite <= 50:
                        frame = int(psite) % 3
                        frame_counts[frame] += 1
                        total += 1
        if total > 0:
            peak = frame_counts[0]
            score = (frame_counts[0] / total) - ((frame_counts[1] + frame_counts[2]) / 2 / total)
            if peak > best_peak:
                best_peak = peak
                best_offset = offset
                best_score = score

    length_offsets[str(read_len)] = best_offset
    length_scores[str(read_len)] = round(float(best_score), 3)

# Overall periodicity score: weighted mean by read count
overall_score = np.mean(list(length_scores.values())) if length_scores else 0.0
data = {
    "sample": sample,
    "offsets": length_offsets,
    "periodicity_scores_by_length": length_scores,
    "periodicity_score": round(float(overall_score), 3),
    "quality_pass": overall_score > 0.3
}

with open(f"{outdir}/{sample}_psite_offsets.json", "w") as f:
    json.dump(data, f, indent=2)
PY

    echo "  [periodicity] $sample done"
done < "$PROJECT_DIR/samplesheet.csv"

echo "[5/11] Periodicity analysis complete."
