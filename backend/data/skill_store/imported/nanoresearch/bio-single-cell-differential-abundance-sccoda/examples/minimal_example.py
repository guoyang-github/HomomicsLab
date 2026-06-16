#!/usr/bin/env python3
"""
Minimal example of scCODA differential compositional analysis.

This example demonstrates a basic two-group comparison using scCODA.
It creates synthetic data and runs the complete analysis workflow.

Requirements:
    pip install sccoda scanpy pandas numpy matplotlib seaborn

Reference:
    Büttner, Ostner et al. (2021). scCODA is a Bayesian model for compositional
    single-cell data analysis. Nature Communications, 12:6876.
"""

import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData

# Add parent directory to path for imports
import sys
sys.path.insert(0, '../scripts/python')

from core_analysis import run_sccoda_analysis
from utils import summarize_results, get_significant_cell_types, export_results


def create_synthetic_data(
    n_cells_per_sample: int = 500,
    n_samples_control: int = 4,
    n_samples_treatment: int = 4,
    random_state: int = 42,
) -> AnnData:
    """Create synthetic single-cell data for demonstration.

    Creates a dataset with:
    - 8 cell types
    - Control samples with baseline proportions
    - Treatment samples with increased Enterocyte and decreased T_cell proportions
    """
    np.random.seed(random_state)

    # Define cell types
    cell_types = [
        "T_cell", "B_cell", "Monocyte", "NK_cell",
        "Enterocyte", "Goblet", "Stem", "TA"
    ]

    # Baseline proportions for control
    control_props = np.array([0.25, 0.15, 0.10, 0.10, 0.20, 0.08, 0.07, 0.05])

    # Treatment proportions (Enterocyte increases, T_cell decreases)
    treatment_props = np.array([0.15, 0.15, 0.10, 0.10, 0.35, 0.08, 0.05, 0.02])

    # Create cell-level data
    all_cells = []
    all_cell_types = []
    all_sample_ids = []
    all_conditions = []

    sample_id = 0

    # Generate control samples
    for i in range(n_samples_control):
        n_cells = n_cells_per_sample + np.random.randint(-50, 50)
        cells = np.random.choice(cell_types, size=n_cells, p=control_props)

        all_cells.extend(range(len(cells)))
        all_cell_types.extend(cells)
        all_sample_ids.extend([f"ctrl_{i}"] * n_cells)
        all_conditions.extend(["control"] * n_cells)
        sample_id += 1

    # Generate treatment samples
    for i in range(n_samples_treatment):
        n_cells = n_cells_per_sample + np.random.randint(-50, 50)
        cells = np.random.choice(cell_types, size=n_cells, p=treatment_props)

        all_cells.extend(range(len(cells)))
        all_cell_types.extend(cells)
        all_sample_ids.extend([f"treat_{i}"] * n_cells)
        all_conditions.extend(["treatment"] * n_cells)
        sample_id += 1

    # Create AnnData
    n_total_cells = len(all_cells)
    n_genes = 100

    # Random expression data (not used for compositional analysis)
    X = np.random.lognormal(3, 1, (n_total_cells, n_genes))

    obs = pd.DataFrame({
        "cell_type": all_cell_types,
        "sample_id": all_sample_ids,
        "condition": all_conditions,
    }, index=[f"cell_{i}" for i in range(n_total_cells)])

    var = pd.DataFrame(index=[f"gene_{i}" for i in range(n_genes)])

    adata = AnnData(X=X, obs=obs, var=var)

    return adata


def main():
    """Run minimal scCODA example."""
    print("=" * 70)
    print("scCODA Minimal Example: Two-group Comparison")
    print("=" * 70)
    print()

    # Step 1: Create synthetic data
    print("Step 1: Creating synthetic data...")
    adata = create_synthetic_data(
        n_cells_per_sample=500,
        n_samples_control=4,
        n_samples_treatment=4,
    )
    print(f"  Created dataset with {adata.n_obs} cells")
    print(f"  Samples: {adata.obs['sample_id'].nunique()}")
    print(f"  Cell types: {adata.obs['cell_type'].nunique()}")
    print()

    # Step 2: Prepare compositional data
    print("Step 2: Preparing compositional data...")

    # Aggregate to sample x cell type counts
    cell_counts = (
        adata.obs.groupby(["sample_id", "cell_type"])
        .size()
        .unstack(fill_value=0)
    )

    # Create sample-level covariates
    covariates = (
        adata.obs.groupby("sample_id")["condition"]
        .first()
        .to_frame()
    )

    # Create scCODA AnnData
    from sccoda.util import cell_composition_data as dat
    sccoda_data = dat.from_pandas(
        cell_counts.join(covariates),
        covariate_columns=["condition"]
    )

    print(f"  Samples: {sccoda_data.n_obs}")
    print(f"  Cell types: {sccoda_data.n_vars}")
    print(f"  Covariates: {list(sccoda_data.obs.columns)}")
    print()

    # Step 3: Run scCODA analysis
    print("Step 3: Running scCODA analysis...")
    print("  (This may take 1-2 minutes)")
    print()

    results = run_sccoda_analysis(
        sccoda_data,
        formula="condition",
        reference_cell_type="automatic",
        num_results=10000,  # Reduced for example (use 20000 for real analysis)
        num_burnin=2500,
        verbose=True,
    )

    print()

    # Step 4: View results
    print("Step 4: Results Summary")
    print("-" * 40)
    print()

    # Print built-in summary
    results.summary()
    print()

    # Step 5: Identify significant changes
    print("Step 5: Significant Cell Type Changes")
    print("-" * 40)

    significant = get_significant_cell_types(results)
    print(f"Significant cell types: {significant}")
    print()

    # Get detailed effect information
    summary = summarize_results(results)
    print(f"Total credible effects: {summary['statistics']['n_credible_effects']}")
    print()

    # Step 6: Export results
    print("Step 6: Exporting Results")
    print("-" * 40)

    export_results(
        results,
        output_dir="output",
        prefix="minimal_example",
        export_summary=True,
        export_effects=True,
        export_diagnostics=True,
    )

    print()
    print("=" * 70)
    print("Analysis complete!")
    print("Results saved to output/ directory")
    print("=" * 70)


if __name__ == "__main__":
    main()
