#!/usr/bin/env python3
"""Find codon positions with significantly elevated ribosome occupancy (Z-score)."""
import argparse
import json
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--occupancy", required=True, help="JSON from get_codon_occupancy.py")
    parser.add_argument("--zscore", type=float, default=3.0)
    parser.add_argument("--out", default="pause_sites.json")
    args = parser.parse_args()

    with open(args.occupancy) as f:
        codon_occupancy = json.load(f)

    pause_sites = []
    for tx, occupancy in codon_occupancy.items():
        if not occupancy:
            continue
        positions = sorted(occupancy.keys(), key=int)
        values = np.array([occupancy[p] for p in positions])
        if len(values) < 10 or values.sum() < 100:
            continue
        mean_occ = values.mean()
        std_occ = values.std()
        if std_occ == 0:
            continue
        zscores = (values - mean_occ) / std_occ
        for idx, zscore in enumerate(zscores):
            if zscore > args.zscore:
                pause_sites.append({
                    "transcript": tx,
                    "codon_position": int(positions[idx]),
                    "occupancy": int(values[idx]),
                    "zscore": float(zscore)
                })

    with open(args.out, "w") as f:
        json.dump(pause_sites, f, indent=2)
    print(f"Found {len(pause_sites)} pause sites -> {args.out}")


if __name__ == "__main__":
    main()
