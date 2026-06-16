"""Prepare test data for pipeline test cases.

Reads PA08_sc.h5ad and PA12_sc.h5ad from DemoShot, creates:
1. Renamed versions with QC-compatible column names
2. Merged multi-sample object for batch integration tests

Usage:
    python prepare_test_data.py
"""

import anndata as ad
import numpy as np
from pathlib import Path

DATA_DIR = Path("/mnt/c/Users/guoyang/Desktop/DemoShot")
OUT_DIR = Path(__file__).parent


def prepare_single_sample(adata: ad.AnnData, out_path: Path):
    """Rename mito_percent -> pct_counts_mt for pipeline QC compatibility."""
    adata = adata.copy()
    if "mito_percent" in adata.obs.columns:
        adata.obs["pct_counts_mt"] = adata.obs["mito_percent"].astype(float)
    # Ensure counts layer exists for doublet detection
    if "counts" not in adata.layers:
        print(f"  Warning: 'counts' layer missing in {out_path.name}")
    adata.write(out_path)
    print(f"Saved: {out_path} ({adata.n_obs} cells)")


def prepare_merged_multi_sample(out_path: Path):
    """Concatenate PA08 + PA12 for batch integration test."""
    a1 = ad.read_h5ad(DATA_DIR / "PA08_sc.h5ad")
    a2 = ad.read_h5ad(DATA_DIR / "PA12_sc.h5ad")

    # Rename mito_percent for QC compatibility
    for a in [a1, a2]:
        if "mito_percent" in a.obs.columns:
            a.obs["pct_counts_mt"] = a.obs["mito_percent"].astype(float)

    # Concatenate with sample key preserved in obs
    merged = ad.concat([a1, a2], label="sample_id", keys=["PA08", "PA12"], index_unique="-")

    # Ensure unique var names
    merged.var_names_make_unique()

    # Ensure counts layer is preserved (concat should handle this)
    print(f"Layers after concat: {list(merged.layers.keys())}")

    # Write
    merged.write(out_path)
    print(f"Saved merged: {out_path}")
    print(f"  Total cells: {merged.n_obs}")
    print(f"  Samples: {merged.obs['sample_id'].value_counts().to_dict()}")


def main():
    print(f"Reading source data from: {DATA_DIR}")
    print(f"Output directory: {OUT_DIR}\n")

    # Prepare individual samples
    print("=== Preparing single samples ===")
    a1 = ad.read_h5ad(DATA_DIR / "PA08_sc.h5ad")
    prepare_single_sample(a1, OUT_DIR / "PA08_sc_renamed.h5ad")

    a2 = ad.read_h5ad(DATA_DIR / "PA12_sc.h5ad")
    prepare_single_sample(a2, OUT_DIR / "PA12_sc_renamed.h5ad")

    # Prepare merged
    print("\n=== Preparing merged multi-sample ===")
    prepare_merged_multi_sample(OUT_DIR / "PA08_PA12_merged.h5ad")

    print("\n=== Done ===")
    print("Generated files:")
    for f in ["PA08_sc_renamed.h5ad", "PA12_sc_renamed.h5ad", "PA08_PA12_merged.h5ad"]:
        path = OUT_DIR / f
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  {f} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
