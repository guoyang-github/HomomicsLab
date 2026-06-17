#!/usr/bin/env python3
"""Plot gene-body ribosome occupancy heatmap for top expressed genes."""
import argparse
import numpy as np
import matplotlib.pyplot as plt
from plastid import BAMGenomeArray, FivePrimeMapFactory, GTF2_TranscriptAssembler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bam", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--offset", type=int, default=12)
    parser.add_argument("--n-genes", type=int, default=100)
    parser.add_argument("--bins", type=int, default=50)
    parser.add_argument("--out", default="genebody_heatmap.pdf")
    args = parser.parse_args()

    alignments = BAMGenomeArray(args.bam, mapping=FivePrimeMapFactory(offset=args.offset))
    transcripts = list(GTF2_TranscriptAssembler(args.gtf))

    tx_with_cds = [tx for tx in transcripts if tx.cds_start is not None]

    tx_counts = []
    for tx in tx_with_cds:
        cds = tx.get_cds()
        total = alignments.get_counts(cds).sum()
        tx_counts.append(total)

    top_indices = np.argsort(tx_counts)[-args.n_genes:]
    top_tx = [tx_with_cds[i] for i in top_indices]

    matrix = []
    for tx in top_tx:
        cds = tx.get_cds()
        counts = alignments.get_counts(cds)

        if len(counts) < args.bins:
            continue

        x_old = np.linspace(0, 1, len(counts))
        x_new = np.linspace(0, 1, args.bins)
        binned = np.interp(x_new, x_old, counts)
        if binned.sum() > 0:
            binned = binned / binned.sum()
        matrix.append(binned)

    matrix = np.array(matrix)
    peak_pos = np.argmax(matrix, axis=1)
    matrix = matrix[np.argsort(peak_pos)]

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(matrix, aspect='auto', cmap='YlOrRd', interpolation='nearest')
    ax.set_xlabel('Gene body position (binned)')
    ax.set_ylabel('Genes (sorted by peak)')
    ax.set_title('Ribosome occupancy gene-body heatmap')
    plt.colorbar(im, ax=ax, label='Normalized density')
    plt.tight_layout()
    plt.savefig(args.out)
    plt.close()


if __name__ == "__main__":
    main()
