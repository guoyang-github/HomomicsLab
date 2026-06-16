"""Utility functions for scCODA analysis.

This module provides helper functions for data validation, result interpretation,
and output generation.
"""

import os
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData


def validate_sccoda_data(
    data: AnnData,
    min_samples: int = 4,
    min_cell_types: int = 3,
    min_samples_per_group: int = 2,
    max_zero_proportion: float = 0.5,
) -> Dict[str, any]:
    """Validate data for scCODA analysis.

    Args:
        data: Compositional AnnData object.
        min_samples: Minimum total samples required.
        min_cell_types: Minimum number of cell types required.
        min_samples_per_group: Minimum samples per group.
        max_zero_proportion: Maximum allowed proportion of zero counts.

    Returns:
        Dictionary with validation results and diagnostic information.

    Example:
        >>> validation = validate_sccoda_data(sccoda_data)
        >>> if validation["valid"]:
        ...     print("Data is valid for scCODA analysis")
        ... else:
        ...     print(f"Errors: {validation['errors']}")
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "diagnostics": {},
    }

    n_samples, n_cell_types = data.X.shape
    result["diagnostics"]["n_samples"] = n_samples
    result["diagnostics"]["n_cell_types"] = n_cell_types

    # Check minimum samples
    if n_samples < min_samples:
        result["errors"].append(
            f"Insufficient samples: {n_samples} (minimum {min_samples})"
        )
        result["valid"] = False

    # Check minimum cell types
    if n_cell_types < min_cell_types:
        result["errors"].append(
            f"Insufficient cell types: {n_cell_types} (minimum {min_cell_types})"
        )
        result["valid"] = False

    # Check for zero counts
    zero_proportion = np.mean(data.X == 0)
    result["diagnostics"]["zero_proportion"] = zero_proportion

    if zero_proportion > max_zero_proportion:
        result["warnings"].append(
            f"High proportion of zeros: {zero_proportion:.1%}"
        )

    # Check samples per group for each covariate
    for col in data.obs.columns:
        value_counts = data.obs[col].value_counts()
        min_count = value_counts.min()

        if min_count < min_samples_per_group:
            result["warnings"].append(
                f"Column '{col}' has groups with only {min_count} sample(s)"
            )

        result["diagnostics"][f"{col}_distribution"] = value_counts.to_dict()

    # Check total cells per sample
    total_cells = data.X.sum(axis=1)
    result["diagnostics"]["total_cells"] = {
        "min": int(total_cells.min()),
        "max": int(total_cells.max()),
        "median": float(np.median(total_cells)),
    }

    if total_cells.min() < 10:
        result["warnings"].append(
            f"Some samples have very few cells (min: {int(total_cells.min())})"
        )

    return result


def summarize_results(
    results,
    est_fdr: Optional[float] = None,
    extended: bool = False,
) -> Dict[str, pd.DataFrame]:
    """Generate comprehensive summary of scCODA results.

    Args:
        results: CAResult object from scCODA analysis.
        est_fdr: False discovery rate threshold (if None, uses current setting).
        extended: Whether to include extended diagnostic information.

    Returns:
        Dictionary containing summary dataframes and statistics.

    Example:
        >>> summary = summarize_results(results)
        >>> print(summary["credible_effects"])
        >>> print(summary["statistics"])
    """
    output = {}

    # Get summaries
    if est_fdr is not None:
        results.set_fdr(est_fdr)

    output["intercept_df"] = results.intercept_df
    output["effect_df"] = results.effect_df
    output["credible_effects"] = results.credible_effects()

    # Calculate statistics
    n_credible = output["credible_effects"].sum()
    n_total = len(output["credible_effects"])

    output["statistics"] = {
        "n_samples": results.sampling_stats.get("y_hat", np.zeros((10, 5))).shape[0],
        "n_cell_types": results.sampling_stats.get("y_hat", np.zeros((10, 5))).shape[1],
        "n_credible_effects": int(n_credible),
        "n_total_effects": int(n_total),
        "proportion_significant": float(n_credible / n_total) if n_total > 0 else 0,
        "reference_cell_type": results.model_specs.get("reference"),
        "formula": results.model_specs.get("formula"),
        "acceptance_rate": results.sampling_stats.get("acc_rate"),
        "mcmc_duration": results.sampling_stats.get("duration"),
    }

    if extended:
        output["sampling_stats"] = results.sampling_stats
        output["model_specs"] = results.model_specs

    return output


def get_credible_effects(
    results,
    est_fdr: Optional[float] = None,
) -> pd.Series:
    """Get boolean mask of credible (significant) effects.

    Args:
        results: CAResult object from scCODA analysis.
        est_fdr: False discovery rate threshold (optional).

    Returns:
        Boolean Series indicating which effects are credible.

    Example:
        >>> credible = get_credible_effects(results)
        >>> significant_cell_types = credible[credible].index.tolist()
    """
    return results.credible_effects(est_fdr=est_fdr)


def get_significant_cell_types(
    results,
    covariate: Optional[str] = None,
    est_fdr: Optional[float] = None,
) -> List[str]:
    """Get list of cell types with significant changes.

    Args:
        results: CAResult object from scCODA analysis.
        covariate: Filter by specific covariate (optional).
        est_fdr: False discovery rate threshold (optional).

    Returns:
        List of cell type names with significant changes.

    Example:
        >>> sig_cells = get_significant_cell_types(results, covariate="condition")
        >>> print(f"Significant cell types: {sig_cells}")
    """
    credible = results.credible_effects(est_fdr=est_fdr)

    if covariate is not None:
        credible = credible.loc[credible.index.get_level_values("Covariate") == covariate]

    return credible[credible].index.get_level_values("Cell Type").tolist()


def export_results(
    results,
    output_dir: str,
    prefix: str = "sccoda",
    export_summary: bool = True,
    export_effects: bool = True,
    export_diagnostics: bool = True,
    export_raw: bool = False,
):
    """Export scCODA results to files.

    Args:
        results: CAResult object from scCODA analysis.
        output_dir: Directory to save output files.
        prefix: Prefix for output file names.
        export_summary: Whether to export summary tables.
        export_effects: Whether to export effect details.
        export_diagnostics: Whether to export MCMC diagnostics.
        export_raw: Whether to export raw result object (pickle).

    Example:
        >>> export_results(results, output_dir="results/", prefix="analysis")
    """
    os.makedirs(output_dir, exist_ok=True)

    # Export intercepts
    if export_summary:
        intercept_path = os.path.join(output_dir, f"{prefix}_intercepts.csv")
        results.intercept_df.to_csv(intercept_path)
        print(f"Saved intercepts to {intercept_path}")

    # Export effects
    if export_effects:
        effects_path = os.path.join(output_dir, f"{prefix}_effects.csv")
        results.effect_df.to_csv(effects_path)
        print(f"Saved effects to {effects_path}")

        # Export credible effects
        credible_path = os.path.join(output_dir, f"{prefix}_credible_effects.csv")
        credible = results.credible_effects()
        credible.to_csv(credible_path)
        print(f"Saved credible effects to {credible_path}")

    # Export diagnostics
    if export_diagnostics:
        diag_path = os.path.join(output_dir, f"{prefix}_diagnostics.txt")
        with open(diag_path, "w") as f:
            f.write("MCMC Diagnostics\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Chain length: {results.sampling_stats.get('chain_length')}\n")
            f.write(f"Burn-in: {results.sampling_stats.get('num_burnin')}\n")
            f.write(f"Acceptance rate: {results.sampling_stats.get('acc_rate'):.2%}\n")
            f.write(f"Duration: {results.sampling_stats.get('duration'):.1f}s\n\n")
            f.write(f"Formula: {results.model_specs.get('formula')}\n")
            f.write(f"Reference cell type: {results.model_specs.get('reference')}\n")
            if "threshold_prob" in results.model_specs:
                f.write(f"Inclusion threshold: {results.model_specs.get('threshold_prob'):.3f}\n")
        print(f"Saved diagnostics to {diag_path}")

    # Export raw results
    if export_raw:
        import pickle
        raw_path = os.path.join(output_dir, f"{prefix}_results.pkl")
        with open(raw_path, "wb") as f:
            pickle.dump(results, f)
        print(f"Saved raw results to {raw_path}")


def create_analysis_report(
    results,
    output_file: Optional[str] = None,
    est_fdr: Optional[float] = None,
) -> str:
    """Create a text report of scCODA analysis results.

    Args:
        results: CAResult object from scCODA analysis.
        output_file: Path to save report (if None, returns string).
        est_fdr: False discovery rate threshold (optional).

    Returns:
        Report string (if output_file is None).

    Example:
        >>> report = create_analysis_report(results, output_file="report.txt")
        >>> print(report)
    """
    lines = []
    lines.append("=" * 70)
    lines.append("scCODA Differential Compositional Analysis Report")
    lines.append("=" * 70)
    lines.append("")

    # Model specifications
    lines.append("Model Specifications")
    lines.append("-" * 40)
    lines.append(f"Formula: {results.model_specs.get('formula', 'N/A')}")
    lines.append(f"Reference cell type: {results.model_specs.get('reference', 'N/A')}")
    if "threshold_prob" in results.model_specs:
        lines.append(f"Inclusion threshold: {results.model_specs['threshold_prob']:.3f}")
    lines.append("")

    # MCMC diagnostics
    lines.append("MCMC Diagnostics")
    lines.append("-" * 40)
    lines.append(f"Chain length: {results.sampling_stats.get('chain_length', 'N/A')}")
    lines.append(f"Burn-in samples: {results.sampling_stats.get('num_burnin', 'N/A')}")
    lines.append(f"Acceptance rate: {results.sampling_stats.get('acc_rate', 0):.2%}")
    lines.append(f"Sampling duration: {results.sampling_stats.get('duration', 0):.1f} seconds")
    lines.append("")

    # Data dimensions
    y_hat = results.sampling_stats.get("y_hat")
    if y_hat is not None:
        lines.append("Data Dimensions")
        lines.append("-" * 40)
        lines.append(f"Samples: {y_hat.shape[0]}")
        lines.append(f"Cell types: {y_hat.shape[1]}")
        lines.append("")

    # Significant effects
    lines.append("Significant Effects")
    lines.append("-" * 40)

    credible = results.credible_effects(est_fdr=est_fdr)
    n_significant = credible.sum()
    n_total = len(credible)

    lines.append(f"Total significant effects: {n_significant} / {n_total}")
    lines.append("")

    if n_significant > 0:
        lines.append("Significant cell type changes:")
        lines.append("")

        # Group by covariate
        for covariate in credible.index.get_level_values("Covariate").unique():
            cov_credible = credible.loc[credible.index.get_level_values("Covariate") == covariate]
            sig_for_cov = cov_credible[cov_credible]

            if len(sig_for_cov) > 0:
                lines.append(f"  {covariate}:")

                for idx in sig_for_cov.index:
                    cell_type = idx[1]
                    effect_row = results.effect_df.loc[idx]
                    logfc = effect_row["log2-fold change"]
                    inc_prob = effect_row["Inclusion probability"]

                    direction = "increased" if logfc > 0 else "decreased"
                    lines.append(f"    - {cell_type}: {direction} (log2FC: {logfc:.2f}, "
                               f"inc. prob: {inc_prob:.3f})")
                lines.append("")

    # Effect summary table
    lines.append("")
    lines.append("Effect Summary Table")
    lines.append("-" * 70)
    lines.append(results.effect_df.to_string())
    lines.append("")

    # Join all lines
    report = "\n".join(lines)

    # Save or return
    if output_file:
        with open(output_file, "w") as f:
            f.write(report)
        print(f"Report saved to {output_file}")

    return report


def compare_conditions_pairwise(
    sccoda_data: AnnData,
    condition_col: str,
    reference_condition: str,
    **kwargs
) -> Dict[str, any]:
    """Run pairwise comparisons between reference and all other conditions.

    Args:
        sccoda_data: Compositional AnnData object.
        condition_col: Column containing condition labels.
        reference_condition: Reference condition to compare against.
        **kwargs: Additional arguments passed to run_sccoda_analysis.

    Returns:
        Dictionary with comparison results.

    Example:
        >>> results = compare_conditions_pairwise(
        ...     data, condition_col="treatment", reference_condition="control"
        ... )
    """
    from core_analysis import run_sccoda_analysis

    conditions = sccoda_data.obs[condition_col].unique()
    conditions = [c for c in conditions if c != reference_condition]

    results_dict = {}

    for condition in conditions:
        # Subset data
        mask = sccoda_data.obs[condition_col].isin([reference_condition, condition])
        data_subset = sccoda_data[mask].copy()

        # Create binary comparison variable
        data_subset.obs["comparison"] = (
            data_subset.obs[condition_col] == condition
        ).astype(int)

        # Run analysis
        result = run_sccoda_analysis(
            data_subset,
            formula="comparison",
            **kwargs
        )

        results_dict[condition] = result

    return results_dict


def get_effect_summary_table(
    results_list: Dict[str, any],
    metric: str = "log2-fold change",
) -> pd.DataFrame:
    """Create summary table of effects across multiple comparisons.

    Args:
        results_list: Dictionary mapping condition names to CAResult objects.
        metric: Metric to extract from results.

    Returns:
        DataFrame with conditions as columns and cell types as rows.

    Example:
        >>> summary = get_effect_summary_table(results_dict)
        >>> summary.to_csv("effect_summary.csv")
    """
    summaries = []

    for condition, results in results_list.items():
        effect_df = results.effect_df.reset_index()
        summary = effect_df.set_index("Cell Type")[metric].rename(condition)
        summaries.append(summary)

    return pd.concat(summaries, axis=1)
