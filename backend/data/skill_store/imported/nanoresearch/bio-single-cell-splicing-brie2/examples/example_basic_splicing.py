#!/usr/bin/env python
"""
Basic BRIE2 Splicing Analysis Example

This example demonstrates the basic workflow for analyzing alternative splicing
in single-cell RNA-seq data using BRIE2.
"""

import numpy as np
import pandas as pd
import scanpy as sc

# Import BRIE2 wrapper functions
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

from core_analysis import (
    run_brie_count,
    run_brie_quant,
    filter_splicing_data,
    get_psi_values,
    get_significant_events,
)
from visualization import (
    plot_psi_distribution,
    plot_psi_heatmap,
    plot_volcano,
)
from utils import (
    load_brie_data,
    export_results,
    summarize_splicing_results,
)


def main():
    """Run basic splicing analysis workflow."""

    print("=" * 60)
    print("BRIE2 Basic Splicing Analysis Example")
    print("=" * 60)

    # Note: This example assumes you have already run brie-count
    # and have a count matrix in h5ad format.

    # For demonstration, we'll create a mock AnnData structure
    # In practice, you would load: adata = load_brie_data('brie_count.h5ad')

    print("\n1. Creating mock data (in practice, load from brie-count output)")
    n_cells = 200
    n_events = 100

    # Create mock count data
    isoform1 = np.random.poisson(10, (n_cells, n_events))
    isoform2 = np.random.poisson(5, (n_cells, n_events))
    ambiguous = np.random.poisson(2, (n_cells, n_events))

    adata = sc.AnnData(
        X=np.zeros((n_cells, n_events)),  # Will be filled with PSI
        obs=pd.DataFrame({
            'cell_id': [f'cell_{i}' for i in range(n_cells)],
            'cell_type': np.random.choice(['Type_A', 'Type_B', 'Type_C'], n_cells)
        }, index=[f'cell_{i}' for i in range(n_cells)]),
        var=pd.DataFrame({
            'GeneID': [f'gene_{i}' for i in range(n_events)],
            'GeneName': [f'Gene{i}' for i in range(n_events)]
        }, index=[f'event_{i}' for i in range(n_events)])
    )
    adata.layers['isoform1'] = isoform1
    adata.layers['isoform2'] = isoform2
    adata.layers['ambiguous'] = ambiguous

    print(f"   Created data: {n_cells} cells x {n_events} events")

    # Step 2: Filter data
    print("\n2. Filtering splicing data")
    adata_filtered = filter_splicing_data(
        adata,
        min_counts=50,
        min_counts_uniq=10,
        min_cells_uniq=20,
        min_MIF_uniq=0.001
    )
    print(f"   After filtering: {adata_filtered.n_vars} events")

    # Step 3: Quantification
    print("\n3. Running BRIE2 quantification")
    print("   Note: This requires brie to be installed")
    print("   Skipping actual quantification in this example")

    # In practice:
    # adata_quant = run_brie_quant(adata_filtered)

    # Mock PSI values for demonstration
    psi = np.random.beta(2, 2, (n_cells, adata_filtered.n_vars))
    adata_filtered.X = psi
    adata_filtered.layers['psi'] = psi

    print(f"   PSI range: {psi.min():.3f} - {psi.max():.3f}")
    print(f"   PSI mean: {psi.mean():.3f}")

    # Step 4: Get PSI values
    print("\n4. Extracting PSI values")
    psi_df = get_psi_values(adata_filtered, with_confidence=False)
    print(f"   PSI matrix shape: {psi_df.shape}")
    print(f"   First few cells x events:")
    print(psi_df.iloc[:3, :3])

    # Step 5: Summarize results
    print("\n5. Summary statistics")
    summary = summarize_splicing_results(adata_filtered, groupby='cell_type')
    print(f"   Cells: {summary['n_cells']}")
    print(f"   Events: {summary['n_events']}")
    print(f"   Mean PSI: {summary['psi_mean']:.3f}")
    print(f"   Variable events: {summary.get('variable_events', 'N/A')}")

    # Step 6: Visualization
    print("\n6. Creating visualizations")

    # PSI distribution
    fig = plot_psi_distribution(
        adata_filtered,
        n_events=6,
        figsize=(15, 8)
    )
    fig.savefig('psi_distribution_example.pdf', dpi=150, bbox_inches='tight')
    print("   Saved: psi_distribution_example.pdf")

    # PSI heatmap
    fig = plot_psi_heatmap(
        adata_filtered,
        n_events=30,
        groupby='cell_type',
        figsize=(12, 8)
    )
    fig.savefig('psi_heatmap_example.pdf', dpi=150, bbox_inches='tight')
    print("   Saved: psi_heatmap_example.pdf")

    # Step 7: Export results
    print("\n7. Exporting results")
    # In practice:
    # outputs = export_results(adata_filtered, 'output_dir', prefix='example')
    print("   Would export to: output_dir/example_*.tsv")

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
