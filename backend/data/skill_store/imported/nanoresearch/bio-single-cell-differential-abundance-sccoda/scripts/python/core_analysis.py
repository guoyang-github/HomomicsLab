"""Core scCODA analysis functions for differential compositional analysis.

This module provides high-level functions to run scCODA analysis on single-cell data,
including data preparation, model fitting, and result extraction.

References:
    Büttner, Ostner et al. (2021). scCODA is a Bayesian model for compositional
    single-cell data analysis. Nature Communications, 12:6876.
"""

import os
import warnings
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData

# Suppress TensorFlow warnings
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"


def run_sccoda_analysis(
    data: AnnData,
    formula: str,
    reference_cell_type: Union[str, int] = "automatic",
    num_results: int = 20000,
    num_burnin: int = 5000,
    num_leapfrog_steps: int = 10,
    step_size: float = 0.01,
    verbose: bool = True,
    automatic_reference_absence_threshold: float = 0.05,
) -> "sccoda.util.result_classes.CAResult":
    """Run scCODA differential compositional analysis.

    This function sets up and runs a scCODA model using Hamiltonian Monte Carlo (HMC)
    sampling to identify cell types with statistically credible changes in abundance.

    Args:
        data: AnnData object with cell counts as data.X and covariates in data.obs.
            This should be created using sccoda.util.cell_composition_data functions.
        formula: R-style formula for covariates (e.g., "condition", "condition + batch").
            Uses patsy syntax for formula specification.
        reference_cell_type: Reference cell type for compositional analysis.
            - "automatic": Select cell type with lowest dispersion present in >90% samples
            - str: Name of cell type column
            - int: Column index (0-based)
        num_results: MCMC chain length (number of samples to generate).
            Default 20000. Increase for better convergence on complex models.
        num_burnin: Number of burn-in iterations to discard.
            Default 5000 (25% of num_results).
        num_leapfrog_steps: Number of leapfrog steps for HMC sampler.
            Default 10. Increase if acceptance rate is too low.
        step_size: Initial step size for HMC sampler.
            Default 0.01. Adjust if acceptance rate is outside 20-80%.
        verbose: Whether to print progress information.
        automatic_reference_absence_threshold: Maximum fraction of zero entries
            for a cell type to be considered as automatic reference candidate.

    Returns:
        CAResult object containing MCMC samples, summary statistics, and effect estimates.

    Raises:
        ImportError: If sccoda is not installed.
        ValueError: If data format is invalid or model specification is incorrect.

    Example:
        >>> from sccoda.util import cell_composition_data as dat
        >>> from core_analysis import run_sccoda_analysis
        >>>
        >>> # Prepare data
        >>> sccoda_data = dat.from_scanpy(adata, "cell_type", "sample_id", covariate_df=covs)
        >>>
        >>> # Run analysis
        >>> results = run_sccoda_analysis(
        ...     sccoda_data,
        ...     formula="condition",
        ...     reference_cell_type="automatic"
        ... )
        >>>
        >>> # View summary
        >>> results.summary()
    """
    try:
        # sccoda >= 0.1.9 uses compositional_analysis
        from sccoda.util import compositional_analysis as mod
    except ImportError:
        try:
            # Fallback for older sccoda versions
            from sccoda.util import comp_ana as mod
        except ImportError:
            raise ImportError(
                "sccoda is required for this analysis. "
                "Install with: pip install sccoda"
            )

    if verbose:
        print(f"Setting up scCODA model...")
        print(f"  Formula: {formula}")
        print(f"  Reference: {reference_cell_type}")
        print(f"  Samples: {data.n_obs}, Cell types: {data.n_vars}")

    # Create model (CompositionalModel in newer sccoda, CompositionalAnalysis in older)
    ModelClass = getattr(mod, "CompositionalModel", getattr(mod, "CompositionalAnalysis", None))
    if ModelClass is None:
        raise ImportError(
            "Could not find CompositionalModel or CompositionalAnalysis in sccoda. "
            "Please check your sccoda version."
        )
    model = ModelClass(
        data,
        formula=formula,
        reference_cell_type=reference_cell_type,
        automatic_reference_absence_threshold=automatic_reference_absence_threshold,
    )

    if verbose:
        print(f"\nRunning MCMC sampling...")
        print(f"  Chain length: {num_results}")
        print(f"  Burn-in: {num_burnin}")

    # Run MCMC sampling
    results = model.sample_hmc(
        num_results=num_results,
        num_burnin=num_burnin,
        num_leapfrog_steps=num_leapfrog_steps,
        step_size=step_size,
        verbose=verbose,
    )

    if verbose:
        print(f"\nMCMC sampling complete!")
        print(f"  Acceptance rate: {results.sampling_stats['acc_rate']:.1%}")
        print(f"  Duration: {results.sampling_stats['duration']:.1f}s")

    return results


def run_complete_analysis(
    adata: AnnData,
    sample_key: str,
    cell_type_key: str,
    condition_key: str,
    covariate_columns: Optional[List[str]] = None,
    reference_cell_type: Union[str, int] = "automatic",
    num_results: int = 20000,
    num_burnin: int = 5000,
    output_dir: Optional[str] = None,
    verbose: bool = True,
) -> Tuple["sccoda.util.result_classes.CAResult", AnnData]:
    """Run complete scCODA analysis pipeline from single-cell data.

    This is a convenience function that handles the entire workflow:
    1. Aggregate cell-level data to sample-level counts
    2. Create scCODA-compatible AnnData
    3. Run MCMC sampling
    4. Optional: Export results

    Args:
        adata: Cell-level AnnData object.
        sample_key: Column in adata.obs containing sample identifiers.
        cell_type_key: Column in adata.obs containing cell type labels.
        condition_key: Column in adata.obs containing condition labels.
        covariate_columns: Additional covariate columns to include.
        reference_cell_type: Reference cell type specification.
        num_results: MCMC chain length.
        num_burnin: Number of burn-in iterations.
        output_dir: Directory to save results (optional).
        verbose: Whether to print progress.

    Returns:
        Tuple of (CAResult, sccoda_data) where sccoda_data is the compositional
        AnnData object used for analysis.

    Example:
        >>> results, sccoda_data = run_complete_analysis(
        ...     adata,
        ...     sample_key="sample_id",
        ...     cell_type_key="cell_type",
        ...     condition_key="condition",
        ...     output_dir="sccoda_results"
        ... )
    """
    from data_preparation import prepare_sccoda_data
    from utils import export_results

    # Prepare data
    if verbose:
        print("=" * 50)
        print("Step 1: Preparing compositional data")
        print("=" * 50)

    sccoda_data = prepare_sccoda_data(
        adata,
        sample_key=sample_key,
        cell_type_key=cell_type_key,
        condition_key=condition_key,
        covariate_columns=covariate_columns,
    )

    # Build formula
    all_covariates = [condition_key]
    if covariate_columns:
        all_covariates.extend(covariate_columns)
    formula = " + ".join(all_covariates)

    if verbose:
        print(f"\nFormula: {formula}")

    # Run analysis
    if verbose:
        print("\n" + "=" * 50)
        print("Step 2: Running scCODA analysis")
        print("=" * 50)

    results = run_sccoda_analysis(
        sccoda_data,
        formula=formula,
        reference_cell_type=reference_cell_type,
        num_results=num_results,
        num_burnin=num_burnin,
        verbose=verbose,
    )

    # Export results if requested
    if output_dir:
        if verbose:
            print("\n" + "=" * 50)
            print("Step 3: Exporting results")
            print("=" * 50)

        export_results(results, output_dir=output_dir, prefix="sccoda")

    if verbose:
        print("\n" + "=" * 50)
        print("Analysis complete!")
        print("=" * 50)

    return results, sccoda_data


def compare_multiple_conditions(
    data: AnnData,
    condition_col: str,
    reference_condition: str,
    reference_cell_type: Union[str, int] = "automatic",
    num_results: int = 20000,
    num_burnin: int = 5000,
    verbose: bool = True,
) -> Dict[str, "sccoda.util.result_classes.CAResult"]:
    """Run pairwise comparisons between a reference and all other conditions.

    Args:
        data: Compositional AnnData object.
        condition_col: Column in data.obs containing conditions.
        reference_condition: Reference condition to compare against.
        reference_cell_type: Reference cell type specification.
        num_results: MCMC chain length.
        num_burnin: Number of burn-in iterations.
        verbose: Whether to print progress.

    Returns:
        Dictionary mapping condition names to CAResult objects.

    Example:
        >>> results = compare_multiple_conditions(
        ...     sccoda_data,
        ...     condition_col="treatment",
        ...     reference_condition="control"
        ... )
        >>> for condition, result in results.items():
        ...     print(f"{condition}: {result.credible_effects().sum()} significant changes")
    """
    conditions = data.obs[condition_col].unique()
    conditions = [c for c in conditions if c != reference_condition]

    results = {}

    for condition in conditions:
        if verbose:
            print(f"\nComparing {condition} vs {reference_condition}...")

        # Subset data
        mask = data.obs[condition_col].isin([reference_condition, condition])
        data_subset = data[mask].copy()

        # Create binary condition variable
        data_subset.obs["comparison"] = (
            data_subset.obs[condition_col] == condition
        ).astype(int)

        # Run analysis
        result = run_sccoda_analysis(
            data_subset,
            formula="comparison",
            reference_cell_type=reference_cell_type,
            num_results=num_results,
            num_burnin=num_burnin,
            verbose=verbose,
        )

        results[condition] = result

    return results


def run_sccoda_with_different_references(
    data: AnnData,
    formula: str,
    reference_cell_types: List[Union[str, int]],
    num_results: int = 20000,
    num_burnin: int = 5000,
    verbose: bool = True,
) -> Dict[Union[str, int], "sccoda.util.result_classes.CAResult"]:
    """Run scCODA with different reference cell types to assess robustness.

    This helps verify that results are not dependent on reference cell type choice.

    Args:
        data: Compositional AnnData object.
        formula: R-style formula for covariates.
        reference_cell_types: List of reference cell types to test.
        num_results: MCMC chain length.
        num_burnin: Number of burn-in iterations.
        verbose: Whether to print progress.

    Returns:
        Dictionary mapping reference cell types to CAResult objects.

    Example:
        >>> results = run_sccoda_with_different_references(
        ...     sccoda_data,
        ...     formula="condition",
        ...     reference_cell_types=["T_cell", "B_cell", "automatic"]
        ... )
        >>> for ref, result in results.items():
        ...     print(f"Reference {ref}: {result.credible_effects().sum()} effects")
    """
    results = {}

    for ref in reference_cell_types:
        if verbose:
            print(f"\nUsing reference: {ref}")

        result = run_sccoda_analysis(
            data,
            formula=formula,
            reference_cell_type=ref,
            num_results=num_results,
            num_burnin=num_burnin,
            verbose=verbose,
        )

        results[ref] = result

    # Compare results
    if verbose and len(results) > 1:
        print("\n" + "=" * 50)
        print("Reference robustness check:")
        print("=" * 50)

        first_result = list(results.values())[0]
        baseline_effects = first_result.credible_effects()

        for ref, result in results.items():
            effects = result.credible_effects()
            agreement = (effects == baseline_effects).mean()
            print(f"  {ref}: {effects.sum()} effects, {agreement:.1%} agreement with first")

    return results
