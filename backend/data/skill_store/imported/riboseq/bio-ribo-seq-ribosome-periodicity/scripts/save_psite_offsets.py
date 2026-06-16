#!/usr/bin/env python3
"""Save standardized P-site offset JSON for downstream skills."""
import argparse
import json
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True)
    parser.add_argument("--offsets", required=True, help='JSON dict, e.g. {"28":12,"29":12}')
    parser.add_argument("--score", type=float, default=0.72)
    parser.add_argument("--outdir", default="results/03_periodicity")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    offsets_dict = json.loads(args.offsets)
    data = {
        "sample": args.sample,
        "offsets": {str(k): int(v) for k, v in offsets_dict.items()},
        "periodicity_score": float(args.score),
        "quality_pass": args.score > 0.5
    }
    outpath = os.path.join(args.outdir, f"{args.sample}_psite_offsets.json")
    with open(outpath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {outpath}")


if __name__ == "__main__":
    main()
