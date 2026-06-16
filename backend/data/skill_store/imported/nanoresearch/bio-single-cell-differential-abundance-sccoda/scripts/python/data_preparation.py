"""Data preparation functions for scCODA analysis.

This module provides functions to convert single-cell data into the compositional
format required by scCODA, including validation and quality checks.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData


def prepare_sccoda_data(
    adata: AnnData,
    sample_key: str,
    cell_type_key: str,
    condition_key: Optional[str] = None,
    covariate_columns: Optional[List[str]] = None,
) -> AnnData:
    """Prepare compositional data from single-cell AnnData.

    This function aggregates cell-level data to sample-level cell counts,
    creating an AnnData object suitable for scCODA analysis.

    Args:
        adata: Cell-level AnnData object.
        sample_key: Column in adata.obs containing sample identifiers.
        cell_type_key: Column in adata.obs containing cell type labels.
        condition_key: Column in adata.obs containing condition labels (optional).
        covariate_columns: Additional covariate columns to include (optional).

    Returns:
        Compositional AnnData with samples as observations and cell types as variables.

    Raises:
        ValueError: If required columns are missing or data is invalid.

    Example:
        >>> sccoda_data = prepare_sccoda_data(
        ...     adata,
        ...     sample_key="sample_id",
        ...     cell_type_key="cell_type",
        ...     condition_key="treatment"
        ... )
        >>> print(sccoda_data)
        AnnData object with n_obs × n_vars = 10 × 8
            obs: 'condition'
    """
    # Check required columns
    if sample_key not in adata.obs.columns:
        raise ValueError(f"Column '{sample_key}' not found in adata.obs")
    if cell_type_key not in adata.obs.columns:
        raise ValueError(f"Column '{cell_type_key}' not found in adata.obs")

    # Aggregate counts
    cell_counts = (
        adata.obs.groupby([sample_key, cell_type_key]).size()
        .unstack(fill_value=0)
    )

    # Build covariate DataFrame
    covariate_cols = []
    if condition_key:
        covariate_cols.append(condition_key)
    if covariate_columns:
        covariate_cols.extend(covariate_columns)

    if covariate_cols:
        # Get unique samples with their covariates
        covariates = (
            adata.obs.groupby(sample_key)[covariate_cols]
            .first()
            .reindex(cell_counts.index)
        )
    else:
        covariates = pd.DataFrame(index=cell_counts.index)

    # Create AnnData
    var_df = pd.DataFrame(index=cell_counts.columns)
    var_df["n_cells"] = cell_counts.sum(axis=0)

    sccoda_data = AnnData(
        X=cell_counts.values.astype("float64"),
        obs=covariates,
        var=var_df,
    )

    return sccoda_data


def check_data_requirements(
    data: AnnData,
    min_samples_per_group: int = 2,
    min_cell_types: int = 3,
    max_zero_proportion: float = 0.5,
    verbose: bool = True,
) -> Dict[str, any]:
    """Check if data meets requirements for scCODA analysis.

    Args:
        data: Compositional AnnData object.
        min_samples_per_group: Minimum samples required per group.
        min_cell_types: Minimum number of cell types required.
        max_zero_proportion: Maximum allowed proportion of zero counts.
        verbose: Whether to print diagnostic information.

    Returns:
        Dictionary with diagnostic information and pass/fail status.

    Example:
        >>> checks = check_data_requirements(sccoda_data)
        >>> if not checks["pass"]:
        ...     print("Data does not meet requirements")
    """
    results = {
        "pass": True,
        "warnings": [],
        "errors": [],
        "diagnostics": {},
    }

    n_samples, n_cell_types = data.X.shape
    results["diagnostics"]["n_samples"] = n_samples
    results["diagnostics"]["n_cell_types"] = n_cell_types

    # Check minimum cell types
    if n_cell_types < min_cell_types:
        results["errors"].append(
            f"Too few cell types: {n_cell_types} (minimum {min_cell_types})"
        )
        results["pass"] = False

    # Check for zero counts
    zero_proportion = np.mean(data.X == 0)
    results["diagnostics"]["zero_proportion"] = zero_proportion

    if zero_proportion > max_zero_proportion:
        results["warnings"].append(
            f"High proportion of zeros: {zero_proportion:.1%} "
            f"(threshold: {max_zero_proportion:.1%})"
        )

    # Check samples per group if condition column exists
    for col in data.obs.columns:
        value_counts = data.obs[col].value_counts()
        min_count = value_counts.min()

        if min_count < min_samples_per_group:
            results["warnings"].append(
                f"Column '{col}' has groups with only {min_count} sample(s) "
                f"(recommended: >= {min_samples_per_group})"
            )

        results["diagnostics"][f"{col}_distribution"] = value_counts.to_dict()

    # Check total cells per sample
    total_cells = data.X.sum(axis=1)
    results["diagnostics"]["total_cells"] = {
        "min": int(total_cells.min()),
        "max": int(total_cells.max()),
        "median": float(np.median(total_cells)),
    }

    if total_cells.min() < 10:
        results["warnings"].append(
            f"Some samples have very few cells (min: {int(total_cells.min())})"
        )

    # Print summary
    if verbose:
        print("Data Requirements Check:")
        print("=" * 40)
        print(f"Samples: {n_samples}")
        print(f"Cell types: {n_cell_types}")
        print(f"Zero proportion: {zero_proportion:.1%}")
        print(f"Total cells per sample: {int(total_cells.min())} - {int(total_cells.max())}")

        if results["errors"]:
            print("\nErrors:")
            for error in results["errors"]:
                print(f"  ❌ {error}")

        if results["warnings"]:
            print("\nWarnings:")
            for warning in results["warnings"]:
                print(f"  ⚠️  {warning}")

        if results["pass"] and not results["warnings"]:
            print("\n✅ All checks passed!")

    return results


def from_cell_counts_df(
    cell_counts: pd.DataFrame,
    covariates: Optional[pd.DataFrame] = None,
    covariate_columns: Optional[List[str]] = None,
) -> AnnData:
    """Create scCODA AnnData from cell counts DataFrame.

    Args:
        cell_counts: DataFrame with samples as rows and cell types as columns.
        covariates: DataFrame with sample-level covariates (optional).
        covariate_columns: List of column names that are covariates
            (alternative to providing separate covariates DataFrame).

    Returns:
        Compositional AnnData object.

    Example:
        >>> counts = pd.DataFrame({
        ...     'T_cell': [100, 150, 120],
        ...     'B_cell': [50, 60, 55],
        ... }, index=['S1', 'S2', 'S3'])
        >>> covs = pd.DataFrame({
        ...     'condition': ['ctrl', 'treat', 'treat']
        ... }, index=['S1', 'S2', 'S3'])
        >>> data = from_cell_counts_df(counts, covs)
    """
    if covariate_columns:
        # Extract covariates from cell_counts
        covariates = cell_counts[covariate_columns]
        cell_counts_only = cell_counts.drop(columns=covariate_columns)
    elif covariates is not None:
        cell_counts_only = cell_counts
    else:
        covariates = pd.DataFrame(index=cell_counts.index)
        cell_counts_only = cell_counts

    # Ensure indices match
    if not covariates.index.equals(cell_counts_only.index):
        raise ValueError("Indices of cell_counts and covariates must match")

    # Create AnnData
    var_df = pd.DataFrame(index=cell_counts_only.columns)
    var_df["n_cells"] = cell_counts_only.sum(axis=0)

    return AnnData(
        X=cell_counts_only.values.astype("float64"),
        obs=covariates,
        var=var_df,
    )


def subset_sccoda_data(
    data: AnnData,
    samples: Optional[List[str]] = None,
    cell_types: Optional[List[str]] = None,
) -> AnnData:
    """Subset scCODA data by samples and/or cell types.

    Args:
        data: Compositional AnnData object.
        samples: List of sample IDs to keep (optional).
        cell_types: List of cell types to keep (optional).

    Returns:
        Subsetted AnnData object.

    Example:
        >>> subset = subset_sccoda_data(
        ...     data,
        ...     samples=["S1", "S2"],
        ...     cell_types=["T_cell", "B_cell"]
        ... )
    """
    data_sub = data.copy()

    if samples is not None:
        sample_mask = data_sub.obs.index.isin(samples)
        data_sub = data_sub[sample_mask]

    if cell_types is not None:
        cell_type_mask = data_sub.var.index.isin(cell_types)
        data_sub = data_sub[:, cell_type_mask]

    return data_sub


def merge_sccoda_datasets(
    datasets: List[AnnData],
    merge_on: Optional[List[str]] = None,
) -> AnnData:
    """Merge multiple scCODA datasets.

    Args:
        datasets: List of compositional AnnData objects.
        merge_on: List of column names to include in merged obs
            (if None, uses intersection of all obs columns).

    Returns:
        Merged AnnData object.

    Example:
        >>> merged = merge_sccoda_datasets([data1, data2, data3])
    """
    # Get common cell types
    common_cell_types = set(datasets[0].var.index)
    for data in datasets[1:]:
        common_cell_types &= set(data.var.index)
    common_cell_types = list(common_cell_types)

    if len(common_cell_types) == 0:
        raise ValueError("No common cell types found across datasets")

    # Get common covariates if not specified
    if merge_on is None:
        common_cols = set(datasets[0].obs.columns)
        for data in datasets[1:]:
            common_cols &= set(data.obs.columns)
        merge_on = list(common_cols)

    # Subset and concatenate
    subsetted = []
    for data in datasets:
        data_sub = data[:, common_cell_types].copy()
        subsetted.append(data_sub)

    # Concatenate (compatible with anndata >= 0.10)
    try:
        import anndata as ad
        merged = ad.concat(
            subsetted,
            label="dataset",
            index_unique="-",
        )
    except (ImportError, AttributeError):
        # Fallback for anndata < 0.10
        merged = AnnData.concatenate(
            *subsetted,
            batch_key="dataset",
            index_unique="-",
        )

    return merged


def get_composition_summary(data: AnnData) -> pd.DataFrame:
    """Get summary statistics of cell type compositions.

    Args:
        data: Compositional AnnData object.

    Returns:
        DataFrame with composition statistics per cell type.

    Example:
        >>> summary = get_composition_summary(data)
        >>> print(summary)
    """
    # Calculate relative abundances
    rel_abun = data.X / data.X.sum(axis=1, keepdims=True)

    summary = pd.DataFrame({
        "total_count": data.X.sum(axis=0).astype(int),
        "mean_proportion": rel_abun.mean(axis=0),
        "std_proportion": rel_abun.std(axis=0),
        "min_proportion": rel_abun.min(axis=0),
        "max_proportion": rel_abun.max(axis=0),
        "zero_samples": (data.X == 0).sum(axis=0),
    }, index=data.var.index)

    summary["cv"] = summary["std_proportion"] / summary["mean_proportion"]

    return summary
