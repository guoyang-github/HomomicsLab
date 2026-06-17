#!/usr/bin/env python3
"""PyDESeq2 differential occupancy analysis for Ribo-seq data."""
import argparse
import pandas as pd
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", required=True, help="featureCounts TSV")
    parser.add_argument("--metadata", required=True, help="CSV with 'condition' column")
    parser.add_argument("--contrast", nargs=3, required=True, help="e.g. condition treatment control")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    counts = pd.read_csv(args.counts, sep='\t', comment='#', index_col=0)
    # Select only numeric count columns instead of hard-coding column drop
    counts = counts.select_dtypes(include='number')

    metadata = pd.read_csv(args.metadata, index_col=0)

    dds = DeseqDataSet(counts, metadata, design='~ condition')
    dds.fit_size_factors()
    dds.fit_dispersions()
    dds.fit_LFC()
    res = DeseqStats(dds, contrast=args.contrast)
    res.summary()
    res.results_df.to_csv(args.out)

if __name__ == "__main__":
    main()
