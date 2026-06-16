"""GEO-specific loaders for non-standard single-cell data formats.

Reference: scanpy 1.10+, anndata 0.10+, pandas 2.2+

Handles common GEO patterns:
- Merged MTX + separate metadata CSV
- GEO H5 files (same API as 10X H5)
"""

import pandas as pd
import scanpy as sc

from utils import strip_barcode_suffix, validate_file_exists


def load_geo_mtx_with_metadata(
    mtx_dir: str,
    metadata_csv: str,
    sample_col: str = "sample",
    barcode_col: str = None,
    var_names: str = "gene_symbols",
) -> sc.AnnData:
    """Load a GEO merged MTX matrix with a separate metadata CSV.

    Common GEO pattern: all cells in one MTX directory, metadata CSV maps
    barcodes to samples and other cell-level metadata.

    Parameters
    ----------
    mtx_dir : str
        Directory containing matrix.mtx[.gz], features.tsv[.gz], barcodes.tsv[.gz].
    metadata_csv : str
        CSV with cell metadata. Index or `barcode_col` should be cell barcodes.
    sample_col : str
        Column in metadata indicating sample origin.
    barcode_col : str, optional
        If metadata index is not barcode, specify column name containing barcodes.
        The column will be set as index internally.
    var_names : str
        Use 'gene_symbols' or 'gene_ids' for variable names.

    Returns
    -------
    AnnData with sample info and all metadata columns in .obs.
    """
    validate_file_exists(mtx_dir, "MTX directory")
    validate_file_exists(metadata_csv, "metadata CSV")

    adata = sc.read_10x_mtx(mtx_dir, var_names=var_names, cache=False)

    # Load metadata
    if barcode_col is not None:
        meta = pd.read_csv(metadata_csv)
        meta = meta.set_index(barcode_col)
    else:
        meta = pd.read_csv(metadata_csv, index_col=0)

    # Align barcodes: exact match first
    common = adata.obs_names.intersection(meta.index)

    # If no overlap, try stripping suffixes (e.g. "-1" from Cell Ranger)
    if len(common) == 0:
        stripped = strip_barcode_suffix(adata.obs_names)
        common = pd.Index(stripped).intersection(meta.index)
        if len(common) > 0:
            adata.obs_names = stripped

    if len(common) == 0:
        raise ValueError(
            f"No barcodes overlap between MTX and metadata. "
            f"MTX example: {adata.obs_names[0]}, Meta example: {meta.index[0]}"
        )

    adata = adata[common].copy()
    meta = meta.loc[common]

    # Add all metadata columns to obs
    for col in meta.columns:
        if col in adata.obs.columns and col != sample_col:
            print(f"WARNING: Column '{col}' already exists in adata.obs, overwriting with metadata value")
        adata.obs[col] = meta[col]

    # Ensure var_names are unique after loading
    adata.var_names_make_unique()

    print(
        f"Loaded {adata.n_obs} cells x {adata.n_vars} genes from GEO MTX. "
        f"Samples: {dict(adata.obs[sample_col].value_counts())}"
    )

    return adata


def load_geo_h5(h5_path: str, sample_id: str = None) -> sc.AnnData:
    """Load a GEO H5 file.

    GEO H5 files use the same format as 10X Cell Ranger H5.
    This is a thin wrapper around sc.read_10x_h5 for clarity.

    Parameters
    ----------
    h5_path : str
        Path to .h5 file.
    sample_id : str, optional
        If provided, add to adata.obs['sample_id'].

    Returns
    -------
    AnnData
    """
    validate_file_exists(h5_path, "H5 file")

    adata = sc.read_10x_h5(h5_path)
    adata.var_names_make_unique()

    if sample_id is not None:
        adata.obs["sample_id"] = sample_id

    print(f"Loaded {adata.n_obs} cells x {adata.n_vars} genes from GEO H5")
    return adata
