#!/usr/bin/env python3
"""Calculate 3-nucleotide periodicity score from metagene around start codons."""
import argparse
import numpy as np
from plastid import BAMGenomeArray, FivePrimeMapFactory, GTF2_TranscriptAssembler, GenomicSegment


def calculate_periodicity(bam_path, annotation_file, psite_offset=12, upstream=50, downstream=100):
    transcripts = list(GTF2_TranscriptAssembler(annotation_file))
    alignments = BAMGenomeArray(bam_path, mapping=FivePrimeMapFactory(offset=psite_offset))

    frame_counts = {0: 0, 1: 0, 2: 0}
    total = 0

    for tx in transcripts:
        if tx.cds_start is None:
            continue
        chrom, start, strand = tx.chrom, tx.cds_start, tx.strand
        if strand == '+':
            region = GenomicSegment(chrom, max(0, start - upstream), start + downstream, strand)
            phase_offset = upstream
        else:
            region = GenomicSegment(chrom, max(0, start - downstream), start + upstream, strand)
            phase_offset = downstream
        counts = alignments.get_counts(region)
        if strand == '-':
            counts = counts[::-1]

        for i, c in enumerate(counts):
            if c > 0:
                frame = (i - phase_offset) % 3
                frame_counts[frame] += c
                total += c

    if total == 0:
        return 0.0

    frame0_fraction = frame_counts[0] / total
    other_mean = (frame_counts[1] + frame_counts[2]) / 2 / total
    return frame0_fraction - other_mean


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bam", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--offset", type=int, default=12)
    args = parser.parse_args()

    score = calculate_periodicity(args.bam, args.gtf, args.offset)
    print(f"Periodicity score: {score:.4f}")


if __name__ == "__main__":
    main()
