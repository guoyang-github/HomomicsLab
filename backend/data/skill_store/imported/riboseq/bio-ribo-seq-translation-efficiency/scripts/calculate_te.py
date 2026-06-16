#!/usr/bin/env python3
"""Calculate translation efficiency per gene from Ribo-seq and mRNA-seq BAMs."""
import argparse
import numpy as np
import pandas as pd
from plastid import BAMGenomeArray, GTF2_TranscriptAssembler, FivePrimeMapFactory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ribo-bam", required=True)
    parser.add_argument("--rna-bam", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--out", default="te_values.csv")
    args = parser.parse_args()

    transcripts = list(GTF2_TranscriptAssembler(args.gtf))
    ribo = BAMGenomeArray(args.ribo_bam, mapping=FivePrimeMapFactory())
    rna = BAMGenomeArray(args.rna_bam, mapping=FivePrimeMapFactory())

    results = []
    for tx in transcripts:
        if tx.cds_start is None:
            continue
        cds = tx.get_cds()
        ribo_counts = int(ribo.get_counts(cds).sum())
        rna_counts = int(rna.get_counts(tx).sum())

        cds_length = sum(len(seg) for seg in cds)
        tx_length = tx.get_length()

        ribo_rpk = ribo_counts / (cds_length / 1000)
        rna_rpk = rna_counts / (tx_length / 1000)
        te = ribo_rpk / rna_rpk if rna_rpk > 0 else np.nan

        gene_id = tx.attr.get('gene_id', tx.get_name()) if hasattr(tx, 'attr') else tx.get_name()
        results.append({
            'gene': gene_id,
            'transcript': tx.get_name(),
            'ribo_counts': ribo_counts,
            'rna_counts': rna_counts,
            'te': te
        })

    pd.DataFrame(results).to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
