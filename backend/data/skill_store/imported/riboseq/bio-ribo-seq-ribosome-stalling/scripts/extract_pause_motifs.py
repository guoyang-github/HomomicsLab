#!/usr/bin/env python3
"""Extract amino acid context around pause sites."""
import argparse
import json
from Bio.Seq import Seq


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pauses", required=True, help="JSON pause sites")
    parser.add_argument("--sequences", required=True, help="JSON mapping transcript -> nucleotide sequence")
    parser.add_argument("--window", type=int, default=10)
    parser.add_argument("--out", default="pause_motifs.txt")
    args = parser.parse_args()

    with open(args.pauses) as f:
        pause_sites = json.load(f)
    with open(args.sequences) as f:
        sequences = json.load(f)

    motifs = []
    for site in pause_sites:
        tx = site["transcript"]
        pos = site["codon_position"]
        seq = sequences.get(tx, "")
        if len(seq) >= (pos + args.window + 1) * 3:
            start = max(0, (pos - args.window) * 3)
            end = min(len(seq), (pos + args.window + 1) * 3)
            aa_seq = str(Seq(seq[start:end]).translate())
            motifs.append(aa_seq)

    with open(args.out, "w") as f:
        for m in motifs:
            f.write(m + "\n")
    print(f"Extracted {len(motifs)} motifs -> {args.out}")


if __name__ == "__main__":
    main()
