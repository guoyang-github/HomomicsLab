#!/usr/bin/env python3
"""Calculate ribosome occupancy per codon from Ribo-seq BAM and annotation."""
import argparse
import json
from collections import defaultdict
from plastid import BAMGenomeArray, GTF2_TranscriptAssembler, FivePrimeMapFactory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bam", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--offset", type=int, default=12)
    parser.add_argument("--out", default="codon_occupancy.json")
    args = parser.parse_args()

    alignments = BAMGenomeArray(args.bam, mapping=FivePrimeMapFactory(offset=args.offset))
    transcripts = list(GTF2_TranscriptAssembler(args.gtf))

    codon_counts = defaultdict(dict)

    for tx in transcripts:
        if tx.cds_start is None:
            continue
        cds = tx.get_cds()
        cds_seq = str(tx.get_sequence(cds))
        position_counts = alignments.get_counts(cds)

        if len(position_counts) != len(cds_seq):
            continue

        phase_offset = cds.start % 3
        for i in range(phase_offset, len(cds_seq) - 2, 3):
            codon_pos = (i - phase_offset) // 3
            if len(position_counts) > i + 2:
                total = int(position_counts[i] + position_counts[i + 1] + position_counts[i + 2])
            else:
                total = 0
            codon_counts[tx.get_name()][codon_pos] = total

    with open(args.out, "w") as f:
        json.dump(dict(codon_counts), f, indent=2)


if __name__ == "__main__":
    main()
