"""Step 1: Load Data — Single-Cell RNA-seq Pipeline (Python)

Reference: scanpy 1.10+, anndata 0.10+, pandas 2.2+

Supports:
- 10X Cell Ranger output (filtered_feature_bc_matrix/)
- 10X H5 file (.h5)
- SampleSheet CSV (multi-sample)
- GEO non-standard formats (via bio-single-cell-data-io)

Output State: [Raw]
"""

import os
from pathlib import Path

import anndata
import pandas as pd
import scanpy as sc

from _skill_registry import resolve_skill_path, import_skill_module


# ---------------------------------------------------------------------------
# Single-sample loaders
# ---------------------------------------------------------------------------

def load_10x_mtx(data_dir: str) -> sc.AnnData:
    """Load 10X Cell Ranger MTX output."""
    adata = sc.read_10x_mtx(data_dir, var_names="gene_symbols", cache=True)
    adata.var_names_make_unique()
    print(f"Loaded 10X MTX: {adata.n_obs} cells x {adata.n_vars} genes")
    return adata


def load_10x_h5(h5_path: str) -> sc.AnnData:
    """Load 10X H5 file."""
    adata = sc.read_10x_h5(h5_path)
    adata.var_names_make_unique()
    print(f"Loaded 10X H5: {adata.n_obs} cells x {adata.n_vars} genes")
    return adata


def load_h5ad(path: str) -> sc.AnnData:
    """Load existing h5ad file."""
    adata = sc.read_h5ad(path)
    print(f"Loaded h5ad: {adata.n_obs} cells x {adata.n_vars} genes")
    return adata


# ---------------------------------------------------------------------------
# Multi-sample loader via SampleSheet
# ---------------------------------------------------------------------------

def load_from_samplesheet(sheet_path: str, merge: bool = True):
    """Load multi-sample data via SampleSheet.

    Delegates to bio-single-cell-data-io skill via the skill registry.
    Resolution order: env var > registry file > relative fallback.
    """
    _load = import_skill_module("bio-single-cell-data-io", "samplesheet")
    return _load.load_from_samplesheet(sheet_path, merge=merge)


# ---------------------------------------------------------------------------
# Main entry: auto-detect format and load
# ---------------------------------------------------------------------------

def load_data(path: str) -> sc.AnnData:
    """Load single-cell data with automatic format detection.

    Parameters
    ----------
    path : str
        Path to data file, directory, or SampleSheet CSV.

    Returns
    -------
    AnnData with pipeline_state = 'Raw' in uns.
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    path_str = str(path)
    if path_str.endswith(".csv"):
        adata = load_from_samplesheet(path_str, merge=True)
    elif path_str.endswith(".h5"):
        adata = load_10x_h5(path_str)
    elif path_str.endswith(".h5ad"):
        adata = load_h5ad(path_str)
    elif path_obj.is_dir():
        # Check for 10X MTX structure
        mtx_file = path_obj / "matrix.mtx.gz"
        if not mtx_file.exists():
            mtx_file = path_obj / "matrix.mtx"
        if mtx_file.exists():
            adata = load_10x_mtx(str(path_obj))
        else:
            raise ValueError(f"Directory does not contain 10X MTX files: {path}")
    else:
        raise ValueError(f"Unsupported file format: {path}")

    adata.uns["pipeline_state"] = "Raw"
    return adata
