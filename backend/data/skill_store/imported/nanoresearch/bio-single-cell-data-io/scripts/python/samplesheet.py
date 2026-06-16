"""SampleSheet-based single-cell data loading for Scanpy.

Reference: scanpy 1.10+, anndata 0.10+, pandas 2.2+

This module provides:
- read_samplesheet(): validate and read a SampleSheet CSV
- load_from_samplesheet(): load all samples and optionally merge

SampleSheet format (CSV):
    sample_id,file_path,file_format,condition,batch,technology
    PA08,data/PA08/filtered_feature_bc_matrix,10x_mtx,High_NI,Batch1,10x_v3
    PA11,data/PA11/filtered_feature_bc_matrix,10x_mtx,High_NI,Batch1,10x_v3

Required columns: sample_id, file_path, file_format
Optional columns: condition, batch, technology, sex, age, note
"""

from typing import List, Union

import anndata
import pandas as pd
import scanpy as sc

from geo_loaders import load_geo_h5, load_geo_mtx_with_metadata
from utils import SUPPORTED_FORMATS, strip_barcode_suffix, validate_file_exists


def read_samplesheet(sheet_path: str) -> pd.DataFrame:
    """Read and validate a SampleSheet CSV.

    Validation rules:
    - Required columns: sample_id, file_path, file_format
    - sample_id must be unique and non-empty
    - file_path must exist
    - file_format must be in SUPPORTED_FORMATS
    - Warns if batch column missing when n_samples > 1

    Parameters
    ----------
    sheet_path : str
        Path to SampleSheet CSV.

    Returns
    -------
    Validated DataFrame with one row per sample.
    """
    validate_file_exists(sheet_path, "SampleSheet")

    sheet = pd.read_csv(sheet_path)

    # Required columns
    required = {"sample_id", "file_path", "file_format"}
    missing = required - set(sheet.columns)
    if missing:
        raise ValueError(f"SampleSheet missing required columns: {missing}")

    # Unique sample_id
    if sheet["sample_id"].duplicated().any():
        dups = sheet["sample_id"][sheet["sample_id"].duplicated()].unique().tolist()
        raise ValueError(f"Duplicate sample_id found: {dups}")

    # Non-empty sample_id
    empty_ids = sheet["sample_id"].isna() | (sheet["sample_id"].astype(str).str.strip() == "")
    if empty_ids.any():
        raise ValueError("sample_id contains empty or NA values")

    # File existence
    for _, row in sheet.iterrows():
        if not pd.isna(row["file_path"]):
            validate_file_exists(str(row["file_path"]), f"sample '{row['sample_id']}'")

    # Format validation
    invalid_formats = set(sheet["file_format"].dropna()) - set(SUPPORTED_FORMATS)
    if invalid_formats:
        raise ValueError(
            f"Unsupported file_format: {invalid_formats}. "
            f"Supported: {SUPPORTED_FORMATS}"
        )

    # Warn if batch missing with >1 sample
    if len(sheet) > 1 and "batch" not in sheet.columns:
        print(
            "WARNING: Multiple samples detected but 'batch' column not found. "
            "Consider adding batch info for downstream integration."
        )

    return sheet


def load_from_samplesheet(
    sheet_path: str, merge: bool = True, join: str = "outer"
) -> Union[sc.AnnData, List[sc.AnnData]]:
    """Load all samples from a SampleSheet.

    Parameters
    ----------
    sheet_path : str
        Path to SampleSheet CSV.
    merge : bool, default True
        If True and n_samples > 1, concatenate into single AnnData.
        If False, return list of AnnData objects.
    join : str, default "outer"
        Join strategy for concatenation ("outer" or "inner").

    Returns
    -------
    AnnData if merge=True, List[AnnData] if merge=False.

    Notes
    -----
    - Each sample's metadata (condition, batch, technology, etc.) is injected
      into adata.obs.
    - For geo_mtx_merged format, the metadata_csv path is expected to be in
      the same directory as the MTX, named ``<sample_id>_metadata.csv`` or
      specified via a ``metadata_csv`` column in the SampleSheet.
    - Barcode suffixes (e.g. "-1") are automatically stripped when aligning
      merged MTX with metadata.
    """
    sheet = read_samplesheet(sheet_path)

    adata_list = []
    for _, row in sheet.iterrows():
        sample_id = str(row["sample_id"])
        file_path = str(row["file_path"])
        fmt = str(row["file_format"])

        # Route to format-specific loader
        adata = _load_by_format(file_path, fmt, sample_id, row)

        # Inject metadata from SampleSheet optional columns
        for col in ["condition", "batch", "technology", "sex", "age", "note"]:
            if col in row and pd.notna(row[col]):
                adata.obs[col] = row[col]

        adata_list.append(adata)

    # Named list by sample_id
    names = sheet["sample_id"].astype(str).tolist()
    for ad, nm in zip(adata_list, names):
        ad.obs["sample_id"] = nm

    # Single sample: return directly regardless of merge flag
    if len(adata_list) == 1:
        return adata_list[0]

    if not merge:
        return adata_list

    # Concatenate
    adata_merged = anndata.concat(
        adata_list,
        join=join,
        label="sample_id",
        keys=names,
        index_unique="-",
    )

    # Ensure categorical types
    adata_merged.obs["sample_id"] = adata_merged.obs["sample_id"].astype("category")
    for col in ["batch", "condition", "technology"]:
        if col in adata_merged.obs.columns:
            adata_merged.obs[col] = adata_merged.obs[col].astype("category")

    print(
        f"Merged {len(adata_list)} samples: "
        f"{adata_merged.n_obs} cells x {adata_merged.n_vars} genes"
    )

    return adata_merged


def _load_by_format(
    file_path: str, fmt: str, sample_id: str, sheet_row: pd.Series
) -> sc.AnnData:
    """Dispatch to the correct loader based on file_format."""
    if fmt == "10x_mtx":
        adata = sc.read_10x_mtx(file_path, var_names="gene_symbols", cache=False)
        adata.var_names_make_unique()
        return adata

    if fmt == "10x_h5":
        adata = sc.read_10x_h5(file_path)
        adata.var_names_make_unique()
        return adata

    if fmt == "geo_mtx":
        adata = sc.read_10x_mtx(file_path, var_names="gene_symbols", cache=False)
        adata.var_names_make_unique()
        return adata

    if fmt == "geo_mtx_merged":
        # metadata_csv can be specified in SampleSheet or inferred
        metadata_csv = None
        import os

        base = os.path.dirname(file_path)
        if "metadata_csv" in sheet_row and pd.notna(sheet_row["metadata_csv"]):
            metadata_csv = str(sheet_row["metadata_csv"])
            if not os.path.exists(metadata_csv):
                raise FileNotFoundError(
                    f"SampleSheet specifies metadata_csv='{metadata_csv}' but file not found. "
                    f"Check the path or place metadata.csv in {base}"
                )
        else:
            # Try common naming patterns
            candidates = [
                os.path.join(base, f"{sample_id}_metadata.csv"),
                os.path.join(base, "metadata.csv"),
                os.path.join(base, "cell_metadata.csv"),
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    metadata_csv = cand
                    break
        if metadata_csv is None:
            raise ValueError(
                f"geo_mtx_merged requires metadata_csv. "
                f"Add 'metadata_csv' column to SampleSheet or place "
                f"metadata.csv in {base}"
            )
        return load_geo_mtx_with_metadata(
            mtx_dir=file_path,
            metadata_csv=metadata_csv,
            sample_col="sample_id" if "sample_id" in pd.read_csv(metadata_csv, nrows=0).columns else "sample",
        )

    if fmt == "geo_h5":
        return load_geo_h5(file_path, sample_id=sample_id)

    if fmt == "h5ad":
        adata = sc.read_h5ad(file_path)
        if "sample_id" not in adata.obs.columns:
            adata.obs["sample_id"] = sample_id
        return adata

    if fmt == "rds":
        raise ValueError(
            f"Cannot load RDS file '{file_path}' in Python. "
            f"Use R workflow or convert to h5ad first."
        )

    raise ValueError(f"Unsupported format: {fmt}")
