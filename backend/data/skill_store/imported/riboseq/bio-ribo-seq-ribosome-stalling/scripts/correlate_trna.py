#!/usr/bin/env python3
"""Correlate codon occupancy with tRNA abundance."""
import argparse
import json
from scipy import stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--occupancy", required=True, help="TSV with codon and mean_occupancy")
    parser.add_argument("--trna", required=True, help="JSON mapping codon -> tRNA abundance")
    args = parser.parse_args()

    codon_occ = {}
    with open(args.occupancy) as f:
        next(f)
        for line in f:
            parts = line.strip().split("\t")
            codon_occ[parts[0]] = float(parts[1])

    with open(args.trna) as f:
        trna_abundance = json.load(f)

    codons = list(set(codon_occ.keys()) & set(trna_abundance.keys()))
    occ = [codon_occ[c] for c in codons]
    trna = [trna_abundance[c] for c in codons]

    corr, pval = stats.spearmanr(occ, trna)
    print(f"Spearman rho: {corr:.4f}, p-value: {pval:.4g}")


if __name__ == "__main__":
    main()
