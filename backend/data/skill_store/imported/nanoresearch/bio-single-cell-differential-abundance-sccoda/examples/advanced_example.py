#!/usr/bin/env python3
"""
Advanced example of scCODA differential compositional analysis.

This example demonstrates advanced features of scCODA including:
- Multi-condition analysis
- Batch correction
- Multiple reference cell type comparisons
- Comprehensive visualization
- Robustness checks

Requirements:
    pip install sccoda scanpy pandas numpy matplotlib seaborn

Reference:
    Büttner, Ostner et al. (2021). scCODA is a Bayesian model for compositional
    single-cell data analysis. Nature Communications, 12:6876.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scanpy as sc
from anndata import AnnData

# Add parent directory to path for imports
import sys
sys.path.insert(0, '../scripts/python')

from core_analysis import (
    run_sccoda_analysis,
    run_complete_analysis,
    compare_multiple_conditions,
    run_sccoda_with_different_references,
)
from data_preparation import prepare_sccoda_data, check_data_requirements, get_composition_summary
from visualization import (
    plot_effect_barplot,
    plot_credible_effects,
    plot_fold_changes,
    plot_inclusion_probability,
    plot_composition_summary,
    plot_results_summary,
)
from utils import (
    summarize_results,
    get_significant_cell_types,
    export_results,
    create_analysis_report,
    get_effect_summary_table,
)


def create_advanced_synthetic_data(
    n_cells_per_sample: int = 500,
    random_state: int = 42,
) -> AnnData:
    """Create synthetic data with multiple conditions and batch effects.

    Creates a dataset with:
    - Control (4 samples)
    - Treatment A - increases Enterocyte (4 samples)
    - Treatment B - increases B_cell (4 samples)
    - 2 batches with slight technical variation
    """
    np.random.seed(random_state)

    # Define cell types
    cell_types = [
        "T_cell", "B_cell", "Monocyte", "NK_cell",
        "Enterocyte", "Goblet", "Stem", "TA"
    ]

    # Baseline proportions
    control_props = np.array([0.25, 0.15, 0.10, 0.10, 0.20, 0.08, 0.07, 0.05])

    # Treatment A: Enterocyte increases, T_cell decreases
    treat_a_props = np.array([0.15, 0.15, 0.10, 0.10, 0.35, 0.08, 0.05, 0.02])

    # Treatment B: B_cell increases, Monocyte decreases
    treat_b_props = np.array([0.22, 0.25, 0.05, 0.10, 0.20, 0.08, 0.07, 0.03])

    all_cells = []
    all_cell_types = []
    all_sample_ids = []
    all_conditions = []
    all_batches = []

    sample_id = 0

    # Generate control samples (2 per batch)
    for batch in ["A", "B"]:
        for i in range(2):
            n_cells = n_cells_per_sample + np.random.randint(-50, 50)
            cells = np.random.choice(cell_types, size=n_cells, p=control_props)

            all_cells.extend(range(len(cells)))
            all_cell_types.extend(cells)
            all_sample_ids.extend([f"ctrl_{batch}_{i}"] * n_cells)
            all_conditions.extend(["control"] * n_cells)
            all_batches.extend([batch] * n_cells)

    # Generate Treatment A samples
    for batch in ["A", "B"]:
        for i in range(2):
            n_cells = n_cells_per_sample + np.random.randint(-50, 50)
            cells = np.random.choice(cell_types, size=n_cells, p=treat_a_props)

            all_cells.extend(range(len(cells)))
            all_cell_types.extend(cells)
            all_sample_ids.extend([f"treatA_{batch}_{i}"] * n_cells)
            all_conditions.extend(["treatment_A"] * n_cells)
            all_batches.extend([batch] * n_cells)

    # Generate Treatment B samples
    for batch in ["A", "B"]:
        for i in range(2):
            n_cells = n_cells_per_sample + np.random.randint(-50, 50)
            cells = np.random.choice(cell_types, size=n_cells, p=treat_b_props)

            all_cells.extend(range(len(cells)))
            all_cell_types.extend(cells)
            all_sample_ids.extend([f"treatB_{batch}_{i}"] * n_cells)
            all_conditions.extend(["treatment_B"] * n_cells)
            all_batches.extend([batch] * n_cells)

    # Create AnnData
    n_total_cells = len(all_cells)
    n_genes = 100

    X = np.random.lognormal(3, 1, (n_total_cells, n_genes))

    obs = pd.DataFrame({
        "cell_type": all_cell_types,
        "sample_id": all_sample_ids,
        "condition": all_conditions,
        "batch": all_batches,
    }, index=[f"cell_{i}" for i in range(n_total_cells)])

    var = pd.DataFrame(index=[f"gene_{i}" for i in range(n_genes)])

    adata = AnnData(X=X, obs=obs, var=var)

    return adata


def main():
    """Run advanced scCODA example."""
    print("=" * 70)
    print("scCODA Advanced Example")
    print("=" * 70)
    print()

    # Create output directory
    os.makedirs("output_advanced", exist_ok=True)

    # Step 1: Create synthetic data
    print("Step 1: Creating synthetic data with multiple conditions...")
    adata = create_advanced_synthetic_data(n_cells_per_sample=500)
    print(f"  Total cells: {adata.n_obs}")
    print(f"  Samples: {adata.obs['sample_id'].nunique()}")
    print(f"  Cell types: {adata.obs['cell_type'].nunique()}")
    print(f"  Conditions: {adata.obs['condition'].unique()}")
    print(f"  Batches: {adata.obs['batch'].unique()}")
    print()

    # Step 2: Prepare compositional data
    print("Step 2: Preparing compositional data...")
    sccoda_data = prepare_sccoda_data(
        adata,
        sample_key="sample_id",
        cell_type_key="cell_type",
        condition_key="condition",
        covariate_columns=["batch"],
    )
    print(f"  Samples: {sccoda_data.n_obs}")
    print(f"  Cell types: {sccoda_data.n_vars}")
    print()

    # Step 3: Data quality check
    print("Step 3: Data quality check...")
    checks = check_data_requirements(sccoda_data, verbose=True)
    print()

    if not checks["pass"]:
        print("Data does not meet requirements. Exiting.")
        return

    # Step 4: Composition summary
    print("Step 4: Composition summary...")
    comp_summary = get_composition_summary(sccoda_data)
    print(comp_summary)
    print()

    # Step 5: Visualize composition before analysis
    print("Step 5: Creating composition visualizations...")

    fig = plot_composition_summary(
        sccoda_data,
        groupby="condition",
        kind="stacked",
        save_path="output_advanced/composition_stacked.png",
        show=False,
    )
    plt.close()
    print("  Saved: output_advanced/composition_stacked.png")

    fig = plot_composition_summary(
        sccoda_data,
        groupby="condition",
        kind="box",
        save_path="output_advanced/composition_boxplot.png",
        show=False,
    )
    plt.close()
    print("  Saved: output_advanced/composition_boxplot.png")
    print()

    # Step 6: Analysis 1 - Simple two-group comparison
    print("=" * 70)
    print("Analysis 1: Control vs Treatment A (Simple comparison)")
    print("=" * 70)
    print()

    # Subset data
    mask = sccoda_data.obs["condition"].isin(["control", "treatment_A"])
    data_2group = sccoda_data[mask].copy()

    results_2group = run_sccoda_analysis(
        data_2group,
        formula="condition",
        reference_cell_type="automatic",
        num_results=10000,  # Use 20000 for real analysis
        num_burnin=2500,
        verbose=True,
    )

    # Visualize results
    plot_effect_barplot(
        results_2group,
        save_path="output_advanced/analysis1_effects.png",
        show=False,
    )
    plt.close()

    plot_fold_changes(
        results_2group,
        save_path="output_advanced/analysis1_foldchanges.png",
        show=False,
    )
    plt.close()
    print()

    # Step 7: Analysis 2 - Multi-condition with batch correction
    print("=" * 70)
    print("Analysis 2: Multi-condition with batch correction")
    print("=" * 70)
    print()

    results_multi = run_sccoda_analysis(
        sccoda_data,
        formula="condition + batch",
        reference_cell_type="automatic",
        num_results=10000,
        num_burnin=2500,
        verbose=True,
    )

    # Comprehensive visualization
    plot_results_summary(
        results_multi,
        save_path="output_advanced/analysis2_summary.png",
        show=False,
    )
    plt.close()
    print("  Saved: output_advanced/analysis2_summary.png")
    print()

    # Step 8: Analysis 3 - Pairwise comparisons
    print("=" * 70)
    print("Analysis 3: Pairwise comparisons (each treatment vs control)")
    print("=" * 70)
    print()

    pairwise_results = compare_multiple_conditions(
        sccoda_data,
        condition_col="condition",
        reference_condition="control",
        reference_cell_type="automatic",
        num_results=8000,
        num_burnin=2000,
        verbose=False,
    )

    for condition, result in pairwise_results.items():
        sig_count = result.credible_effects().sum()
        print(f"  {condition} vs control: {sig_count} significant changes")

    # Create summary table
    summary_table = get_effect_summary_table(pairwise_results, metric="log2-fold change")
    summary_table.to_csv("output_advanced/pairwise_summary.csv")
    print("  Saved: output_advanced/pairwise_summary.csv")
    print()

    # Step 9: Analysis 4 - Reference cell type robustness check
    print("=" * 70)
    print("Analysis 4: Reference cell type robustness check")
    print("=" * 70)
    print()

    # Subset for faster computation
    mask = sccoda_data.obs["condition"].isin(["control", "treatment_A"])
    data_subset = sccoda_data[mask].copy()

    ref_results = run_sccoda_with_different_references(
        data_subset,
        formula="condition",
        reference_cell_types=["automatic", "Goblet", "Stem"],
        num_results=8000,
        num_burnin=2000,
        verbose=False,
    )
    print()

    # Step 10: Generate comprehensive report
    print("=" * 70)
    print("Step 10: Generating comprehensive report...")
    print("=" * 70)
    print()

    # Export main results
    export_results(
        results_multi,
        output_dir="output_advanced",
        prefix="main_analysis",
        export_summary=True,
        export_effects=True,
        export_diagnostics=True,
    )

    # Create detailed report
    report = create_analysis_report(
        results_multi,
        output_file="output_advanced/final_report.txt",
    )

    print()
    print("=" * 70)
    print("All analyses complete!")
    print("Results saved to output_advanced/ directory")
    print("=" * 70)


if __name__ == "__main__":
    main()
