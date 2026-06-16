#!/usr/bin/env python3
"""Aggregate P-site offsets and periodicity scores across samples into a summary figure."""
import argparse
import json
import numpy as np
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsons", nargs='+', required=True)
    parser.add_argument("--out", default="results/01_qc/periodicity_summary.pdf")
    args = parser.parse_args()

    offsets = {}
    scores = {}
    for psite_file in args.jsons:
        with open(psite_file) as f:
            data = json.load(f)
        sample = data['sample']
        offsets[sample] = data['offsets']
        scores[sample] = data['periodicity_score']

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    samples = list(offsets.keys())
    lengths = sorted({k for v in offsets.values() for k in v.keys()})
    offset_matrix = np.array([[offsets[s].get(str(l), np.nan) for l in lengths] for s in samples])

    im = axes[0].imshow(offset_matrix, aspect='auto', cmap='viridis')
    axes[0].set_xticks(range(len(lengths)))
    axes[0].set_xticklabels(lengths)
    axes[0].set_yticks(range(len(samples)))
    axes[0].set_yticklabels(samples)
    axes[0].set_xlabel('Read length (nt)')
    axes[0].set_title('P-site offsets')
    plt.colorbar(im, ax=axes[0])

    axes[1].bar(samples, [scores[s] for s in samples], color='coral')
    axes[1].axhline(0.5, color='red', linestyle='--', label='Quality threshold')
    axes[1].set_ylabel('Periodicity score')
    axes[1].set_title('3-nt periodicity quality')
    axes[1].legend()
    plt.setp(axes[1].xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()
    plt.savefig(args.out)
    plt.close()


if __name__ == "__main__":
    main()
