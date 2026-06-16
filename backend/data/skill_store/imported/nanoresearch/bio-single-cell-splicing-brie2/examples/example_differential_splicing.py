#!/usr/bin/env python
"""
Differential Splicing Analysis with BRIE2

This example demonstrates how to perform differential alternative splicing (DAS)
analysis between cell groups using BRIE2.
"""

import numpy as np
import pandas as pd
import scanpy as sc
import matplotlib.pyplot as plt

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'python'))

from core_analysis import (
    run_brie_quant,
    filter_splicing_data,
    get_psi_values,
    get_significant_events,
    compare_cell_groups,
)
from visualization import (
    plot_psi_distribution,
    plot_volcano,
    plot_psi_trajectory,
    plot_splicing_summary,
)
from utils import (
    prepare_cell_features,
    export_results,
    summarize_splicing_results,
)


def main():
    """Run differential splicing analysis workflow."""

    print("=" * 60)
    print("BRIE2 Differential Splicing Analysis Example")
    print("=" * 60)

    # Create mock data with cell type structure
    print("\n1. Creating mock data with cell type structure")
    n_cells = 300
    n_events = 150

    # Define cell types
    cell_types = np.random.choice(['Neuron', 'Glial', 'Stem'], n_cells)

    # Create event-specific PSI patterns
    psi = np.zeros((n_cells, n_events))

    for i in range(n_events):
        base_psi = np.random.uniform(0.2, 0.8)

        for j, ct in enumerate(cell_types):
            if ct == 'Neuron':
                # Neurons have higher PSI for some events
                offset = 0.2 if i < 30 else -0.1
            elif ct == 'Glial':
                offset = -0.1 if i < 30 else 0.15
            else:  # Stem
                offset = 0.0

            psi[j, i] = np.clip(base_psi + offset + np.random.normal(0, 0.1), 0, 1)

    # Create AnnData
    adata = sc.AnnData(
        X=psi,
        obs=pd.DataFrame({
            'cell_id': [f'cell_{i}' for i in range(n_cells)],
            'cell_type': cell_types,
            'pseudotime': np.random.uniform(0, 1, n_cells)
        }, index=[f'cell_{i}' for i in range(n_cells)]),
        var=pd.DataFrame({
            'GeneID': [f'gene_{i}' for i in range(n_events)],
            'GeneName': [f'Gene{i}' for i in range(n_events)]
        }, index=[f'event_{i}' for i in range(n_events)])
    )

    # Add mock count layers
    adata.layers['isoform1'] = np.random.poisson(10, (n_cells, n_events))
    adata.layers['isoform2'] = np.random.poisson(5, (n_cells, n_events))
    adata.layers['ambiguous'] = np.random.poisson(2, (n_cells, n_events))
    adata.layers['psi'] = psi

    print(f"   Data: {n_cells} cells x {n_events} events")
    print(f"   Cell types: {dict(zip(*np.unique(cell_types, return_counts=True)))}")

    # Step 2: Prepare cell features
    print("\n2. Preparing cell features for differential analysis")
    cell_features, feature_names = prepare_cell_features(
        adata,
        features='cell_type',
        encode_categorical=True
    )
    print(f"   Features: {feature_names}")
    print(f"   Feature matrix shape: {cell_features.shape}")

    # Step 3: Compare cell groups
    print("\n3. Comparing cell groups")
    comparison_results = compare_cell_groups(
        adata,
        group_key='cell_type',
        group1='Neuron',
        group2='Glial'
    )
    print(f"   Compared {len(comparison_results)} events")
    print(f"   Top differential events:")
    print(comparison_results.sort_values('pvalue').head()[['event', 'delta_psi', 'pvalue']])

    # Step 4: Visualizations
    print("\n4. Creating visualizations")

    # PSI distribution by cell type
    fig = plot_psi_distribution(
        adata,
        events=['event_0', 'event_1', 'event_2'],
        figsize=(15, 4)
    )
    fig.savefig('das_psi_distribution.pdf', dpi=150, bbox_inches='tight')
    print("   Saved: das_psi_distribution.pdf")

    # Volcano plot
    fig = plot_volcano(
        comparison_results,
        x_col='delta_psi',
        y_col='pvalue',
        q_threshold=0.05,
        effect_threshold=0.1,
        figsize=(10, 8)
    )
    fig.savefig('das_volcano_plot.pdf', dpi=150, bbox_inches='tight')
    print("   Saved: das_volcano_plot.pdf")

    # PSI trajectory
    fig = plot_psi_trajectory(
        adata,
        events=['event_0', 'event_1', 'event_2'],
        pseudotime_key='pseudotime',
        figsize=(15, 4)
    )
    fig.savefig('das_psi_trajectory.pdf', dpi=150, bbox_inches='tight')
    print("   Saved: das_psi_trajectory.pdf")

    # Splicing summary
    fig = plot_splicing_summary(
        adata,
        groupby='cell_type',
        n_events=10,
        figsize=(14, 10)
    )
    fig.savefig('das_splicing_summary.pdf', dpi=150, bbox_inches='tight')
    print("   Saved: das_splicing_summary.pdf")

    # Step 5: Export results
    print("\n5. Exporting results")
    # In practice with real BRIE2 output:
    # outputs = export_results(adata, 'das_output', prefix='differential')
    print("   Would export:")
    print("   - das_output/differential_results.h5ad")
    print("   - das_output/differential_psi.tsv")
    print("   - das_output/differential_stats.tsv")

    # Step 6: Summary
    print("\n6. Analysis summary")
    sig_events = comparison_results[comparison_results['qvalue'] < 0.05]
    print(f"   Significant events (q<0.05): {len(sig_events)}")
    if len(sig_events) > 0:
        print(f"   Largest ΔPSI: {sig_events['delta_psi'].abs().max():.3f}")
        print(f"   Most significant: {sig_events.sort_values('qvalue').iloc[0]['event']}")

    print("\n" + "=" * 60)
    print("Differential splicing analysis complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
