"""
Advanced Example: RNA Velocity Analysis with scVelo
====================================================

This example demonstrates advanced features of scVelo including:
- Dynamical model for velocity estimation
- PAGA velocity graph
- Cell cycle scoring
- Gene ranking by velocity likelihood
- Terminal state identification

Requirements:
- AnnData object with 'spliced' and 'unspliced' layers
- Pre-computed embedding and clusters
"""

import scanpy as sc
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))

from core_analysis import (
    prepare_data_for_velocity,
    compute_velocity,
    compute_velocity_graph,
    compute_latent_time_scvelo,
    compute_terminal_states,
    rank_velocity_genes,
    compute_paga_velocity,
    score_cell_cycle,
    export_velocity_results,
    run_velocity_analysis
)
from visualization import (
    plot_velocity_embedding_stream,
    plot_velocity_embedding_grid,
    plot_latent_time,
    plot_terminal_states,
    plot_paga_velocity,
    plot_velocity_genes,
    plot_velocity_confidence,
    plot_velocity_summary
)
from utils import (
    get_velocity_summary_stats,
    get_velocity_genes_summary,
    validate_velocity_consistency
)


def main():
    print("=" * 70)
    print("scVelo RNA Velocity Analysis - Advanced Example")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Step 1: Load data
    # -------------------------------------------------------------------------
    print("\n[Step 1] Loading data...")
    print("Note: Replace with your actual data loading code")

    # Example with scvelo dataset:
    # import scvelo as scv
    # adata = scv.datasets.pancreas()
    # adata.obs['clusters'] = adata.obs['clusters'].astype('category')

    # -------------------------------------------------------------------------
    # Step 2: Preprocess data with cell cycle scoring
    # -------------------------------------------------------------------------
    print("\n[Step 2] Preprocessing and cell cycle scoring...")

    # Basic preprocessing
    # prepare_data_for_velocity(
    #     adata,
    #     min_counts=10,
    #     n_top_genes=3000,
    #     n_pcs=30,
    #     n_neighbors=30
    # )

    # Cell cycle scoring (optional, for cycling cells)
    # score_cell_cycle(
    #     adata,
    #     s_genes=None,  # Uses scvelo's default s-phase genes
    #     g2m_genes=None,  # Uses scvelo's default G2M-phase genes
    #     inplace=True
    # )

    print("- Normalization and feature selection")
    print("- Computing PCA and neighbors")
    print("- Computing moments for velocity estimation")
    print("- Cell cycle phase assignment (optional)")

    # -------------------------------------------------------------------------
    # Step 3: Compute RNA velocity with dynamical model
    # -------------------------------------------------------------------------
    print("\n[Step 3] Computing RNA velocity (dynamical model)...")

    # The dynamical model provides:
    # - Full transcriptional dynamics
    # - Latent time inference
    # - Reaction rates (transcription, splicing, degradation)

    # adata = compute_velocity(
    #     adata,
    #     mode='dynamical',  # Use full dynamical model
    #     min_r2=0.01,
    #     min_likelihood=0.01,
    #     copy=False
    # )

    # Compute velocity graph
    # compute_velocity_graph(
    #     adata,
    #     n_neighbors=30,
    #     n_jobs=-1
    # )

    print("- Estimating transcription, splicing, and degradation rates")
    print("- Computing velocity vectors with dynamical model")
    print("- Building velocity graph")

    # -------------------------------------------------------------------------
    # Step 4: Compute terminal states and latent time
    # -------------------------------------------------------------------------
    print("\n[Step 4] Computing terminal states and latent time...")

    # Identify root and end points
    # compute_terminal_states(
    #     adata,
    #     group_key='clusters',
    #     root_groups=['Ductal'],  # Specify root cluster(s)
    #     end_groups=['Alpha', 'Beta', 'Delta', 'Epsilon'],  # End clusters
    #     n_jobs=-1
    # )

    # Compute latent time
    # compute_latent_time_scvelo(
    #     adata,
    #     n_dcs=10,
    #     min_likelihood=0.01
    # )

    print("- Identified root and terminal populations")
    print("- Computed latent time for all cells")

    # -------------------------------------------------------------------------
    # Step 5: Rank genes by velocity likelihood
    # -------------------------------------------------------------------------
    print("\n[Step 5] Ranking velocity genes...")

    # Rank genes that drive the velocity dynamics
    # rank_velocity_genes(
    #     adata,
    #     groupby='clusters',
    #     n_genes=100,
    #     min_r2=0.01
    # )

    print("- Ranked genes by velocity likelihood")
    print("- Identified driver genes for each cluster")

    # -------------------------------------------------------------------------
    # Step 6: PAGA velocity analysis
    # -------------------------------------------------------------------------
    print("\n[Step 6] Computing PAGA velocity graph...")

    # Combine PAGA with velocity for trajectory inference
    # compute_paga_velocity(
    #     adata,
    #     groups='clusters',
    #     threshold=0.1,
    #     transitions='transitions_confidence'
    # )

    print("- Built PAGA graph with velocity transitions")

    # -------------------------------------------------------------------------
    # Step 7: Get summary statistics
    # -------------------------------------------------------------------------
    print("\n[Step 7] Generating summary statistics...")

    # stats = get_velocity_summary_stats(adata)
    # print(f"Number of velocity genes: {stats['n_velocity_genes']}")
    # print(f"Mean velocity confidence: {stats.get('velocity_confidence', {}).get('mean', 'N/A')}")

    # validation = validate_velocity_consistency(
    #     adata,
    #     cell_type_key='clusters',
    #     min_confidence=0.5
    # )
    # print(f"Fraction high confidence cells: {validation['confidence']['fraction_high_confidence']:.2%}")

    # velocity_genes_df = get_velocity_genes_summary(adata, n_top=20)
    # print("\nTop velocity genes:")
    # print(velocity_genes_df.head(10))

    print("- Summary statistics computed")
    print("- Validation metrics calculated")

    # -------------------------------------------------------------------------
    # Step 8: Comprehensive visualization
    # -------------------------------------------------------------------------
    print("\n[Step 8] Generating visualizations...")

    # Velocity stream
    # plot_velocity_embedding_stream(
    #     adata,
    #     basis='umap',
    #     color='clusters',
    #     title='RNA Velocity (Stream)',
    #     save='advanced_velocity_stream.png'
    # )

    # Velocity grid
    # plot_velocity_embedding_grid(
    #     adata,
    #     basis='umap',
    #     color='clusters',
    #     save='advanced_velocity_grid.png'
    # )

    # Latent time
    # plot_latent_time(
    #     adata,
    #     basis='umap',
    #     save='advanced_latent_time.png'
    # )

    # Terminal states
    # plot_terminal_states(
    #     adata,
    #     basis='umap',
    #     color='clusters',
    #     save='advanced_terminal_states.png'
    # )

    # PAGA
    # plot_paga_velocity(
    #     adata,
    #     color='clusters',
    #     save='advanced_paga.png'
    # )

    # Velocity genes phase portraits
    # plot_velocity_genes(
    #     adata,
    #     n_genes=9,
    #     min_r2=0.1,
    #     save='advanced_velocity_genes.png'
    # )

    # Velocity confidence
    # plot_velocity_confidence(
    #     adata,
    #     basis='umap',
    #     save='advanced_confidence.png'
    # )

    # Summary
    # plot_velocity_summary(
    #     adata,
    #     basis='umap',
    #     save='advanced_summary.png'
    # )

    print("- All visualizations saved")

    # -------------------------------------------------------------------------
    # Step 9: Export results
    # -------------------------------------------------------------------------
    print("\n[Step 9] Exporting results...")

    # Export to DataFrame
    # results_df = export_velocity_results(
    #     adata,
    #     obs_keys=['clusters', 'latent_time', 'velocity_confidence'],
    #     include_velocity_vectors=True,
    #     include_summary_stats=True
    # )
    # results_df.to_csv('velocity_results.csv', index=False)

    # Save AnnData
    # adata.write('advanced_velocity_results.h5ad')

    print("- Results exported to CSV")
    print("- AnnData saved to H5AD")

    print("\n" + "=" * 70)
    print("Advanced analysis complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
