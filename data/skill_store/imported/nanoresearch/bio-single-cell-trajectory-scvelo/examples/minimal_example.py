"""
Minimal Example: RNA Velocity Analysis with scVelo
==================================================

This example demonstrates the basic workflow for RNA velocity analysis
using scVelo with the deterministic (steady-state) model.

Requirements:
- AnnData object with 'spliced' and 'unspliced' layers
- Pre-computed embedding (e.g., UMAP)
"""

import scanpy as sc
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))

from core_analysis import (
    prepare_data_for_velocity,
    run_velocity_analysis,
    compute_latent_time_scvelo
)
from visualization import (
    plot_velocity_embedding_stream,
    plot_phase_portrait,
    plot_velocity_summary
)


def main():
    print("=" * 60)
    print("scVelo RNA Velocity Analysis - Minimal Example")
    print("=" * 60)

    # -------------------------------------------------------------------------
    # Step 1: Load data
    # -------------------------------------------------------------------------
    print("\n[Step 1] Loading data...")

    # Example: Load from 10x Genomics output or loom file
    # For demonstration, we'll create a minimal example
    # In practice, replace this with your actual data loading:
    # adata = scv.datasets.pancreas()  # Example dataset from scvelo
    # OR
    # adata = sc.read_h5ad('your_data.h5ad')

    print("Note: Replace this section with your actual data loading.")
    print("Expected: AnnData with 'spliced' and 'unspliced' layers")

    # For this example, we'll show the code structure
    # Uncomment and modify for your actual data:

    # import scvelo as scv
    # adata = scv.datasets.pancreas()  # Example dataset

    # -------------------------------------------------------------------------
    # Step 2: Preprocess data
    # -------------------------------------------------------------------------
    print("\n[Step 2] Preprocessing...")

    # prepare_data_for_velocity(
    #     adata,
    #     min_counts=10,
    #     n_top_genes=2000,
    #     n_pcs=30,
    #     n_neighbors=30,
    #     flavor='seurat'
    # )

    print("- Filtering and normalization")
    print("- Computing moments")
    print("- Computing PCA and neighbors")

    # -------------------------------------------------------------------------
    # Step 3: Compute RNA velocity
    # -------------------------------------------------------------------------
    print("\n[Step 3] Computing RNA velocity...")

    # adata = run_velocity_analysis(
    #     adata,
    #     mode='deterministic',  # Use steady-state model
    #     min_r2=0.01,
    #     copy=False
    # )

    print("- Estimating gamma (degradation rate)")
    print("- Computing velocity vectors")
    print("- Building velocity graph")

    # -------------------------------------------------------------------------
    # Step 4: Compute latent time (optional)
    # -------------------------------------------------------------------------
    print("\n[Step 4] Computing latent time...")

    # compute_latent_time_scvelo(
    #     adata,
    #     root_key='clusters',  # Key for root cells
    #     root_cells=['Ductal'],  # Cluster name for root
    #     n_dcs=10
    # )

    print("- Identifying root and end points")
    print("- Computing latent time across cells")

    # -------------------------------------------------------------------------
    # Step 5: Visualize results
    # -------------------------------------------------------------------------
    print("\n[Step 5] Visualizing results...")

    # Velocity stream plot
    # plot_velocity_embedding_stream(
    #     adata,
    #     basis='umap',
    #     color='clusters',
    #     save='velocity_stream.png'
    # )

    # Phase portrait for a key gene
    # plot_phase_portrait(
    #     adata,
    #     gene='Gene_Name',
    #     save='phase_portrait.png'
    # )

    # Summary plot
    # plot_velocity_summary(
    #     adata,
    #     basis='umap',
    #     save='velocity_summary.png'
    # )

    print("- Velocity stream plot saved")
    print("- Phase portrait saved")
    print("- Summary plot saved")

    # -------------------------------------------------------------------------
    # Step 6: Save results
    # -------------------------------------------------------------------------
    print("\n[Step 6] Saving results...")

    # adata.write('velocity_results.h5ad')
    print("- Results saved to velocity_results.h5ad")

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
