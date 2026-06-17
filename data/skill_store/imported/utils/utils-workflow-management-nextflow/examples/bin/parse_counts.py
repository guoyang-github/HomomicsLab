#!/usr/bin/env python3
"""
Parse and filter raw count matrix for downstream DESeq2 analysis.
Designed for Nextflow: single-task execution, parameterized I/O.
"""

import argparse
import sys
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(
        description="Filter low-expression genes from count matrix"
    )
    parser.add_argument("--input", required=True, help="Input count matrix (CSV)")
    parser.add_argument("--outprefix", required=True, help="Output file prefix")
    parser.add_argument(
        "--min-cpm", type=float, default=1.0,
        help="Minimum CPM threshold for filtering (default: 1.0)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Load data
    try:
        counts = pd.read_csv(args.input, index_col=0)
    except FileNotFoundError:
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to read input: {e}", file=sys.stderr)
        sys.exit(1)

    # Filter: keep genes with CPM > min_cpm in at least 2 samples
    cpm = counts.div(counts.sum(axis=0), axis=1) * 1e6
    keep = (cpm > args.min_cpm).sum(axis=1) >= 2
    filtered = counts.loc[keep, :]

    # Write output with prefix for uniqueness in parallel execution
    output_path = f"{args.outprefix}.filtered_counts.csv"
    filtered.to_csv(output_path)

    print(f"Filtered counts written to: {output_path}")
    print(f"Genes retained: {len(filtered)} / {len(counts)}")


if __name__ == "__main__":
    main()
