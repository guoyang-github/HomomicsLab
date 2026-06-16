"""Step 1: Load Spatial Data — Spatial Transcriptomics Pipeline (Python)

Reference: scanpy 1.10+, squidpy 1.3+, anndata 0.10+

Supports:
- 10X Visium (Space Ranger output)
- 10X Xenium
- AnnData h5ad (resume)
- SampleSheet CSV (multi-sample)

Output State: [Raw]
"""

import os
from pathlib import Path

import anndata
import pandas as pd
import scanpy as sc
import squidpy as sq

from _skill_registry import resolve_skill_path, import_skill_module


def load_visium(data_dir: str) -> sc.AnnData:
    """Load 10X Visium Space Ranger output."""
    adata = sc.read_visium(data_dir)
    adata.var_names_make_unique()
    print(f"Loaded Visium: {adata.n_obs} spots x {adata.n_vars} genes")
    return adata


def load_xenium(data_dir: str) -> sc.AnnData:
    """Load 10X Xenium output."""
    adata = sq.read.xenium(data_dir)
    adata.var_names_make_unique()
    print(f"Loaded Xenium: {adata.n_obs} cells x {adata.n_vars} genes")
    return adata


def load_h5ad(path: str) -> sc.AnnData:
    """Load existing h5ad file."""
    adata = sc.read_h5ad(path)
    print(f"Loaded h5ad: {adata.n_obs} spots x {adata.n_vars} genes")
    return adata


def load_from_samplesheet(sheet_path: str, merge: bool = True):
    """Load multi-sample spatial data via SampleSheet.

    Delegates to bio-spatial-transcriptomics-data-io skill.
    """
    _load = import_skill_module("bio-spatial-transcriptomics-data-io", "samplesheet")
    return _load.load_from_samplesheet(sheet_path, merge=merge)


def load_spatial_data(path: str) -> sc.AnnData:
    """Load spatial transcriptomics data with automatic format detection.

    Parameters
    ----------
    path : str
        Path to data file, directory, or SampleSheet CSV.

    Returns
    -------
    AnnData with pipeline_state = 'Raw' in uns and spatial coords in obsm['spatial'].
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    path_str = str(path)
    if path_str.endswith(".csv"):
        adata = load_from_samplesheet(path_str, merge=True)
    elif path_str.endswith(".h5ad"):
        adata = load_h5ad(path_str)
    elif path_obj.is_dir():
        # Auto-detect Visium vs Xenium
        if (path_obj / "spatial").exists() or (path_obj / "tissue_positions_list.csv").exists():
            adata = load_visium(str(path_obj))
        elif (path_obj / "cells.parquet").exists() or (path_obj / "cell_feature_matrix.h5").exists():
            adata = load_xenium(str(path_obj))
        else:
            raise ValueError(f"Directory does not contain recognized spatial data: {path}")
    else:
        raise ValueError(f"Unsupported file format: {path}")

    # Validate spatial coordinates
    if "spatial" not in adata.obsm:
        import warnings
        warnings.warn("Spatial coordinates not found in adata.obsm['spatial']. "
                      "Some spatial analyses may not work.")

    adata.uns["pipeline_state"] = "Raw"
    return adata
