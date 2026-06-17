"""Utility functions for single-cell data loading.

Reference: scanpy 1.10+, anndata 0.10+, pandas 2.2+
"""

import os
import re
from pathlib import Path


SUPPORTED_FORMATS = [
    "10x_mtx",
    "10x_h5",
    "geo_mtx",
    "geo_mtx_merged",
    "geo_h5",
    "h5ad",
    "rds",
]


def detect_format_from_path(path: str) -> str:
    """Auto-detect file format from path.

    Returns one of: 10x_mtx, 10x_h5, h5ad, rds, unknown.
    For h5 files, returns 10x_h5 (cannot distinguish from geo_h5 without inspection).
    """
    p = Path(path)

    if p.is_dir():
        has_matrix = any(p.glob("matrix.mtx*"))
        has_features = any(p.glob("features.tsv*")) or any(p.glob("genes.tsv*"))
        has_barcodes = any(p.glob("barcodes.tsv*"))
        if has_matrix and has_features and has_barcodes:
            return "10x_mtx"
        return "unknown"

    ext = p.suffix.lower()
    if ext == ".h5":
        return "10x_h5"
    if ext == ".h5ad":
        return "h5ad"
    if ext == ".rds":
        return "rds"

    return "unknown"


def strip_barcode_suffix(barcodes, suffixes=("-1", "-2")):
    """Strip common barcode suffixes for alignment between MTX and metadata."""
    pattern = re.compile(r"(" + "|".join(suffixes) + r")$")
    return [pattern.sub("", str(b)) for b in barcodes]


def validate_file_exists(path: str, context: str = "") -> None:
    """Raise FileNotFoundError with context if path does not exist."""
    if not os.path.exists(path):
        msg = f"Path not found"
        if context:
            msg += f" ({context})"
        msg += f": {path}"
        raise FileNotFoundError(msg)
