#!/usr/bin/env python3
"""Detect ribosome stalling sites from Ribo-seq data."""
import argparse
import glob
import json
import os
import sys
import numpy as np
from plastid import GTF2_TranscriptAssembler, BAMGenomeArray, FivePrimeMapFactory


def get_representative_offset(sample, psite_dir):
    path = os.path.join(psite_dir, f"{sample}_psite_offsets.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"P-site offset file not found: {path}")
    with open(path) as f:
        offsets = json.load(f)["offsets"]
    vals = [int(v) for v in offsets.values()]
    return int(np.median(vals)) if vals else 12


def main():
    parser = argparse.ArgumentParser(description="Detect ribosome stalling sites")
    parser.add_argument("--bam-dir", required=True)
    parser.add_argument("--gtf", required=True)
    parser.add_argument("--psite-dir", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args()

    transcripts = list(GTF2_TranscriptAssembler(args.gtf))
    if not transcripts:
        raise ValueError(f"No transcripts loaded from GTF: {args.gtf}")

    results = []
    for bam in glob.glob(os.path.join(args.bam_dir, "*.sorted.bam")):
        sample = os.path.basename(bam).replace(".sorted.bam", "")
        offset = get_representative_offset(sample, args.psite_dir)
        pause_sites = []

        alignments = BAMGenomeArray(bam, mapping=FivePrimeMapFactory(offset=offset))

        for tx in transcripts:
            if tx.cds_start is None:
                continue
            cds = tx.get_cds()
            counts = alignments.get_counts(cds)
            cds_seq = str(tx.get_sequence(cds))
            if len(cds_seq) < 9 or len(counts) != len(cds_seq):
                continue

            phase_offset = cds.start % 3
            codon_counts = []
            for i in range(phase_offset, len(cds_seq) - 2, 3):
                if len(counts) > i + 2:
                    codon_counts.append(counts[i] + counts[i+1] + counts[i+2])
                else:
                    codon_counts.append(0)

            if len(codon_counts) < 10 or sum(codon_counts) < 100:
                continue

            arr = np.array(codon_counts, dtype=float)
            mean_occ = arr.mean()
            std_occ = arr.std()
            if std_occ == 0:
                continue
            zscores = (arr - mean_occ) / std_occ

            for pos, zscore in enumerate(zscores):
                if zscore > 3.0:
                    pause_sites.append({
                        "transcript": tx.get_name(),
                        "codon_position": pos,
                        "occupancy": int(arr[pos]),
                        "zscore": float(zscore)
                    })

        results.append({
            "sample": sample,
            "offset_used": offset,
            "pause_sites_detected": len(pause_sites),
            "pause_sites": pause_sites
        })

    os.makedirs(args.outdir, exist_ok=True)
    with open(os.path.join(args.outdir, "stalling_summary.json"), "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
