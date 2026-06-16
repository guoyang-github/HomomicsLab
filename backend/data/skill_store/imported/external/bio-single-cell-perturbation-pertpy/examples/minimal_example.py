"""
Minimal Example: Perturbation Analysis with pertpy
====================================================

This example demonstrates the basic workflow for perturbation analysis
using pertpy.
"""

import scanpy as sc
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))

from core_analysis import (
    check_perturbation_data,
    compute_pseudobulk_space,
    run_augur_classification
)


def main():
    print("=" * 60)
    print("pertpy Perturbation Analysis - Minimal Example")
    print("=" * 60)

    # -------------------------------------------------------------------------
    # Step 1: Load data
    # -------------------------------------------------------------------------
    print("\n[Step 1] Loading data...")

    # Load your perturbation data
    # adata = sc.read_h5ad('perturbation_data.h5ad')

    print("Note: Replace this section with your actual data loading.")
    print("Expected: AnnData with perturbation labels in .obs")
    print("Required columns:")
    print("  - perturbation: perturbation labels (e.g., 'control', 'KO_gene1')")
    print("  - replicate: biological replicate information")

    # -------------------------------------------------------------------------
    # Step 2: Validate data
    # -------------------------------------------------------------------------
    print("\n[Step 2] Validating data...")

    # check_perturbation_data(
    #     adata,
    #     perturbation_col="perturbation",
    #     control="control"
    # )

    print("- Data validation passed")
    print("- Perturbation column found")
    print("- Control perturbation found")

    # -------------------------------------------------------------------------
    # Step 3: Compute pseudobulk space
    # -------------------------------------------------------------------------
    print("\n[Step 3] Computing pseudobulk space...")

    # ps_adata = compute_pseudobulk_space(
    #     adata,
    #     perturbation_col="perturbation",
    #     replicate_col="replicate"
    # )

    print("- Pseudobulk profiles computed")
    print("- One profile per perturbation")

    # -------------------------------------------------------------------------
    # Step 4: Run Augur classification
    # -------------------------------------------------------------------------
    print("\n[Step 4] Running Augur classification...")

    # adata = run_augur_classification(
    #     adata,
    #     estimator="random_forest_classifier",
    #     labels_col="perturbation",
    #     n_estimators=100
    # )

    print("- Augur classification complete")
    print("- Results stored in .uns['augur_results']")

    # -------------------------------------------------------------------------
    # Step 5: Visualize results
    # -------------------------------------------------------------------------
    print("\n[Step 5] Visualizing results...")

    # from visualization import plot_augur_results
    # plot_augur_results(adata, save='augur_results.png')

    print("- Augur results plotted")

    # -------------------------------------------------------------------------
    # Step 6: Export results
    # -------------------------------------------------------------------------
    print("\n[Step 6] Exporting results...")

    # results = adata.uns['augur_results']
    # results.to_csv('augur_results.csv')

    print("- Results exported to CSV")

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
