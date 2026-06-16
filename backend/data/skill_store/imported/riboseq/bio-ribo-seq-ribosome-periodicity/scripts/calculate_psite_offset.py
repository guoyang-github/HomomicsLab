#!/usr/bin/env python3
"""Determine optimal P-site offset by aggregating signal around start codons."""
import argparse
import numpy as np
from plastid import BAMGenomeArray, FivePrimeMapFactory, GTF2_TranscriptAssembler, GenomicSegment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bam", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--min-offset", type=int, default=10)
    parser.add_argument("--max-offset", type=int, default=15)
    parser.add_argument("--upstream", type=int, default=50)
    parser.add_argument("--downstream", type=int, default=100)
    args = parser.parse_args()

    transcripts = list(GTF2_TranscriptAssembler(args.gtf))
    alignments = BAMGenomeArray(args.bam, mapping=FivePrimeMapFactory())

    profiles = {}
    width = args.upstream + args.downstream
    for offset in range(args.min_offset, args.max_offset + 1):
        alignments.set_mapping(FivePrimeMapFactory(offset=offset))
        profile = []
        for tx in transcripts:
            if tx.cds_start is None:
                continue
            chrom, start, strand = tx.chrom, tx.cds_start, tx.strand
            if strand == '+':
                region = GenomicSegment(chrom, max(0, start - args.upstream), start + args.downstream, strand)
            else:
                region = GenomicSegment(chrom, max(0, start - args.downstream), start + args.upstream, strand)
            counts = alignments.get_counts(region)
            if strand == '-':
                counts = counts[::-1]
            # Pad or truncate to fixed width to avoid ragged arrays
            if len(counts) < width:
                counts = np.pad(counts, (width - len(counts), 0), mode='constant')
            else:
                counts = counts[-width:]
            profile.append(counts)
        if profile:
            profiles[offset] = np.mean(profile, axis=0)
        else:
            profiles[offset] = np.zeros(width)

    best_offset = max(profiles, key=lambda o: profiles[o][args.upstream])
    print(f"Best offset: {best_offset}")
    for o, p in profiles.items():
        peak = p[args.upstream]
        print(f"  offset={o}: peak_at_start={peak:.4f}")


if __name__ == "__main__":
    main()
