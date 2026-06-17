#!/usr/bin/env python3
"""Plot read length distribution from aligned BAM."""
import argparse
import os
from collections import Counter
import pysam
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bam", required=True)
    parser.add_argument("--sample", required=True)
    parser.add_argument("--outdir", default="results/01_qc/length_distributions")
    args = parser.parse_args()

    lengths = Counter()
    with pysam.AlignmentFile(args.bam, 'rb') as bam:
        for read in bam:
            if not read.is_unmapped:
                lengths[read.query_length] += 1

    os.makedirs(args.outdir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(lengths.keys(), lengths.values(), color='steelblue', edgecolor='black')
    ax.set_xlabel('Read length (nt)')
    ax.set_ylabel('Count')
    ax.set_title(f'{args.sample} - Ribo-seq length distribution')
    ax.axvspan(28, 32, alpha=0.2, color='green', label='Expected footprint')
    ax.legend()
    plt.tight_layout()
    outpath = os.path.join(args.outdir, f'{args.sample}_length_dist.pdf')
    plt.savefig(outpath)
    plt.close()


if __name__ == "__main__":
    main()
