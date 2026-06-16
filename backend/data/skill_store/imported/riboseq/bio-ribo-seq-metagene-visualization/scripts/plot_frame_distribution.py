#!/usr/bin/env python3
"""Plot reading frame distribution across CDS positions."""
import argparse
import matplotlib.pyplot as plt
from plastid import BAMGenomeArray, GTF2_TranscriptAssembler, FivePrimeMapFactory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bam", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--offset", type=int, default=12)
    parser.add_argument("--out", default="frame_distribution.pdf")
    args = parser.parse_args()

    alignments = BAMGenomeArray(args.bam, mapping=FivePrimeMapFactory(offset=args.offset))
    transcripts = list(GTF2_TranscriptAssembler(args.gtf))

    frame_counts = [0, 0, 0]
    total = 0

    for tx in transcripts:
        if tx.cds_start is None:
            continue
        cds = tx.get_cds()
        counts = alignments.get_counts(cds)
        cds_seq = str(tx.get_sequence(cds))

        if len(counts) != len(cds_seq):
            continue

        # Account for genomic phase of CDS start
        phase_offset = cds.start % 3
        for i, c in enumerate(counts):
            frame = (i + phase_offset) % 3
            frame_counts[frame] += c
            total += c

    fig, ax = plt.subplots(figsize=(6, 5))
    frames = ['Frame 0', 'Frame 1', 'Frame 2']
    if total > 0:
        proportions = [c / total for c in frame_counts]
    else:
        proportions = [0, 0, 0]
    colors = ['#2ecc71', '#f39c12', '#e74c3c']
    ax.bar(frames, proportions, color=colors, edgecolor='black')
    ax.set_ylabel('Proportion of reads')
    ax.set_title('Reading frame distribution in CDS')
    ax.set_ylim(0, 1)
    plt.tight_layout()
    plt.savefig(args.out)
    plt.close()


if __name__ == "__main__":
    main()
