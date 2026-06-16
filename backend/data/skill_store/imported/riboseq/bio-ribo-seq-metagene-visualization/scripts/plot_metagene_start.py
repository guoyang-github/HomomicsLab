#!/usr/bin/env python3
"""Plot metagene profile around start codons."""
import argparse
import sys
import numpy as np
import matplotlib.pyplot as plt
from plastid import BAMGenomeArray, FivePrimeMapFactory, GTF2_TranscriptAssembler, GenomicSegment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bam", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--offset", type=int, default=12)
    parser.add_argument("--upstream", type=int, default=50)
    parser.add_argument("--downstream", type=int, default=100)
    parser.add_argument("--out", default="metagene_start.pdf")
    args = parser.parse_args()

    alignments = BAMGenomeArray(args.bam, mapping=FivePrimeMapFactory(offset=args.offset))
    transcripts = list(GTF2_TranscriptAssembler(args.gtf))

    profile = np.zeros(args.upstream + args.downstream)
    counts = 0

    for tx in transcripts:
        if tx.cds_start is None:
            continue
        chrom, strand, start = tx.chrom, tx.strand, tx.cds_start
        if strand == '+':
            region = GenomicSegment(chrom, start - args.upstream, start + args.downstream, strand)
            positions = np.arange(-args.upstream, args.downstream)
        else:
            region = GenomicSegment(chrom, start - args.downstream, start + args.upstream, strand)
            positions = np.arange(-args.downstream, args.upstream)

        counts_array = alignments.get_counts(region)
        if strand == '-':
            counts_array = counts_array[::-1]

        # Pad or truncate to match expected length
        expected_len = len(positions)
        if len(counts_array) < expected_len:
            counts_array = np.pad(counts_array, (expected_len - len(counts_array), 0), mode='constant')
        else:
            counts_array = counts_array[-expected_len:]

        profile += counts_array
        counts += 1

    if counts == 0:
        sys.exit("Error: No transcripts with cds_start found.")

    profile = profile / counts

    fig, ax = plt.subplots(figsize=(10, 5))

    for frame in range(3):
        frame_positions = positions[np.mod(positions, 3) == frame]
        frame_counts = profile[np.mod(positions, 3) == frame]
        ax.bar(frame_positions, frame_counts, alpha=0.7, label=f'Frame {frame}')

    ax.axvline(0, color='red', linestyle='--')
    ax.set_xlabel('Position relative to start codon (nt)')
    ax.set_ylabel('Normalized read density')
    ax.set_title('Metagene profile around start codon')
    ax.legend()
    plt.tight_layout()
    plt.savefig(args.out)
    plt.close()


if __name__ == "__main__":
    main()
