#!/usr/bin/env python3
"""Generate metagene plots and length distribution figures from Ribo-seq BAMs."""
import argparse
import glob
import json
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pysam
from plastid import BAMGenomeArray, FivePrimeMapFactory, GTF2_TranscriptAssembler, GenomicSegment


def main():
    parser = argparse.ArgumentParser(description="Generate metagene plots")
    parser.add_argument("--bam-dir", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--psite-dir", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    for bam in glob.glob(os.path.join(args.bam_dir, "*.sorted.bam")):
        sample = os.path.basename(bam).replace(".sorted.bam", "")

        # Plot 1: Read length distribution
        lengths = {}
        with pysam.AlignmentFile(bam, 'rb') as f:
            for read in f:
                if not read.is_unmapped:
                    read_len = read.query_length
                    if read_len is not None:
                        lengths[read_len] = lengths.get(read_len, 0) + 1

        fig, ax = plt.subplots(figsize=(8, 5))
        if lengths:
            x = sorted(lengths.keys())
            y = [lengths[k] for k in x]
            ax.bar(x, y, color='steelblue', edgecolor='black')
        else:
            sys.stderr.write(f"Warning: no mapped reads in {bam}\n")
        ax.set_xlabel('Read length (nt)')
        ax.set_ylabel('Count')
        ax.set_title(f'{sample} - Read length distribution')
        fig.savefig(os.path.join(args.outdir, f"{sample}_length_dist.pdf"))
        plt.close(fig)

        # Plot 2: Frame distribution around start codon
        offset_path = os.path.join(args.psite_dir, f"{sample}_psite_offsets.json")
        if not os.path.exists(offset_path):
            raise FileNotFoundError(f"P-site offset file not found: {offset_path}")
        with open(offset_path) as f:
            offsets = json.load(f)["offsets"]
        rep_offset = int(np.median([int(v) for v in offsets.values()])) if offsets else 12

        alignments = BAMGenomeArray(bam, mapping=FivePrimeMapFactory(offset=rep_offset))
        transcripts = list(GTF2_TranscriptAssembler(args.gtf))

        frame_counts = [0, 0, 0]
        total = 0
        for tx in transcripts:
            if tx.cds_start is None:
                continue
            chrom, start, strand = tx.chrom, tx.cds_start, tx.strand
            if strand == '+':
                region = GenomicSegment(chrom, max(0, start - 30), start + 60, strand)
                phase_offset = 30
            else:
                region = GenomicSegment(chrom, max(0, start - 60), start + 30, strand)
                phase_offset = 60
            counts = alignments.get_counts(region)
            if strand == '-':
                counts = counts[::-1]
            for i, c in enumerate(counts):
                if c > 0:
                    frame = (i - phase_offset) % 3
                    frame_counts[frame] += c
                    total += c

        fig, ax = plt.subplots(figsize=(6, 5))
        if total > 0:
            proportions = [c / total for c in frame_counts]
            colors = ['#2ecc71', '#f39c12', '#e74c3c']
            ax.bar(['Frame 0', 'Frame 1', 'Frame 2'], proportions, color=colors, edgecolor='black')
            ax.set_ylim(0, max(proportions) * 1.2 if max(proportions) > 0 else 1)
        ax.set_ylabel('Proportion of reads')
        ax.set_title(f'{sample} - Frame distribution around start codon')
        fig.savefig(os.path.join(args.outdir, f"{sample}_metagene.pdf"))
        plt.close(fig)


if __name__ == "__main__":
    main()
