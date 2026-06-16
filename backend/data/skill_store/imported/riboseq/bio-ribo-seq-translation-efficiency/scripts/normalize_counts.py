#!/usr/bin/env python3
"""Normalize count matrix to TPM or RPKM and compute log2 TE matrix."""
import argparse
import numpy as np
import pandas as pd


def normalize_counts(counts_df, method='tpm'):
    if method == 'tpm':
        rpk = counts_df.div(counts_df['length'] / 1000, axis=0)
        scale = rpk.sum(axis=0) / 1e6
        tpm = rpk.div(scale, axis=1)
        return tpm
    elif method == 'rpkm':
        total = counts_df.sum(axis=0)
        rpm = counts_df / total * 1e6
        rpkm = rpm.div(counts_df['length'] / 1000, axis=0)
        return rpkm
    else:
        raise ValueError("method must be 'tpm' or 'rpkm'")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ribo", required=True)
    parser.add_argument("--rna", required=True)
    parser.add_argument("--method", default='tpm')
    parser.add_argument("--out", default='te_matrix.csv')
    args = parser.parse_args()

    ribo = pd.read_csv(args.ribo, index_col=0)
    rna = pd.read_csv(args.rna, index_col=0)

    ribo_norm = normalize_counts(ribo, args.method)
    rna_norm = normalize_counts(rna, args.method)

    common = ribo_norm.index.intersection(rna_norm.index)
    ribo_norm = ribo_norm.loc[common]
    rna_norm = rna_norm.loc[common]

    te = np.log2((ribo_norm + 0.1) / (rna_norm + 0.1))
    te.to_csv(args.out)


if __name__ == "__main__":
    main()
