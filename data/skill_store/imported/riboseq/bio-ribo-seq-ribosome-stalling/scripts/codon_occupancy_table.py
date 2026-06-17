#!/usr/bin/env python3
"""Calculate average occupancy per codon type across all transcripts."""
import argparse
from collections import defaultdict
import numpy as np
from plastid import BAMGenomeArray, GTF2_TranscriptAssembler, FivePrimeMapFactory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bam", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--offset", type=int, default=12)
    parser.add_argument("--out", default="codon_means.tsv")
    args = parser.parse_args()

    alignments = BAMGenomeArray(args.bam, mapping=FivePrimeMapFactory(offset=args.offset))
    transcripts = list(GTF2_TranscriptAssembler(args.gtf))

    codon_reads = defaultdict(list)

    for tx in transcripts:
        if tx.cds_start is None:
            continue
        cds = tx.get_cds()
        cds_seq = str(tx.get_sequence(cds))
        counts = alignments.get_counts(cds)

        if len(counts) != len(cds_seq):
            continue

        phase_offset = cds.start % 3
        for i in range(phase_offset, len(cds_seq) - 2, 3):
            codon = cds_seq[i:i + 3]
            if len(counts) > i + 2:
                codon_reads[codon].append(sum(counts[i:i + 3]))

    codon_means = {codon: float(np.mean(reads)) for codon, reads in codon_reads.items() if reads}

    with open(args.out, "w") as f:
        f.write("codon\tmean_occupancy\n")
        for codon, mean_val in sorted(codon_means.items()):
            f.write(f"{codon}\t{mean_val:.4f}\n")


if __name__ == "__main__":
    main()
