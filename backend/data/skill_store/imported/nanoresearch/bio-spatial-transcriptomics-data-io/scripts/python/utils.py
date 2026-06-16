"""Utility functions for spatial transcriptomics data loading.

Reference: scanpy 1.10+, anndata 0.10+, pandas 2.2+
"""

import os
from pathlib import Path


SUPPORTED_FORMATS = [
    "visium",
    "visium_h5",
    "xenium",
    "cosmx",
    "merfish",
    "geo_visium",
    "geo_visium_h5",
]


def validate_file_exists(path: str, context: str = "") -> None:
    """Raise FileNotFoundError with context if path does not exist."""
    if not os.path.exists(path):
        msg = f"Path not found"
        if context:
            msg += f" ({context})"
        msg += f": {path}"
        raise FileNotFoundError(msg)
