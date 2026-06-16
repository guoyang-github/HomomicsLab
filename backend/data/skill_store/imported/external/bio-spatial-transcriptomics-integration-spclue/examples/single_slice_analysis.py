"""
Single-Slice Spatial Domain Analysis with spCLUE

This example demonstrates how to use spCLUE to identify spatial domains
in a single tissue section from spatial transcriptomics data.

Author: Claude Code
Date: 2026-04-07
"""

import scanpy as sc
import squidpy as sq
import torch
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from scripts import spCLUE, preprocess, prepare_graph, clustering, fix_seed, refine_label
from sklearn.decomposition import PCA


def run_single_slice_analysis(adata_path, n_clusters=12, output_path=None):
    """
    Run spCLUE analysis on a single slice of spatial transcriptomics data.

    Parameters
    ----------
    adata_path : str
        Path to AnnData file (.h5ad) or 10X Visium directory
    n_clusters : int
        Number of spatial domains to identify
    output_path : str, optional
        Path to save output AnnData

    Returns
    -------
    AnnData
        AnnData with spCLUE embeddings and cluster labels
    """
    # Set random seed for reproducibility
    fix_seed(42)

    # 1. Load data
    print("=" * 50)
    print("Step 1: Loading data")
    print("=" * 50)

    if adata_path.endswith('.h5ad'):
        adata = sc.read_h5ad(adata_path)
    elif os.path.isdir(adata_path):
        # Assume 10X Visium format
        adata = sc.read_visium(adata_path)
    else:
        raise ValueError(f"Unknown data format: {adata_path}")

    print(f"Data shape: {adata.shape}")
    print(f"Spatial coordinates: {adata.obsm['spatial'].shape}")

    # 2. Preprocess data
    print("\n" + "=" * 50)
    print("Step 2: Preprocessing")
    print("=" * 50)

    adata = preprocess(adata, hvgNumber=2000)
    print(f"After HVG selection: {adata.shape}")

    # 3. Apply PCA for dimensionality reduction
    print("\n" + "=" * 50)
    print("Step 3: PCA dimensionality reduction")
    print("=" * 50)

    pca = PCA(n_components=200, random_state=0)
    input_data = pca.fit_transform(adata.X)
    print(f"PCA input shape: {input_data.shape}")

    # 4. Construct multi-view graphs
    print("\n" + "=" * 50)
    print("Step 4: Building multi-view graphs")
    print("=" * 50)

    graph_dict = {
        "spatial": prepare_graph(adata, key="spatial", n_neighbors=12),
        "expr": prepare_graph(adata, key="expr", n_neighbors=12, n_comps=50)
    }
    print(f"Spatial graph shape: {graph_dict['spatial'].shape}")
    print(f"Expression graph shape: {graph_dict['expr'].shape}")

    # 5. Initialize and train spCLUE model
    print("\n" + "=" * 50)
    print("Step 5: Training spCLUE model")
    print("=" * 50)

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    model = spCLUE(
        input_data=input_data,
        graph_dict=graph_dict,
        n_clusters=n_clusters,
        epochs=500,
        device=device,
        learning_rate=0.001,
        weight_decay=0.001,
        dim_input=200,
        dim_hidden=64,
        dim_embed=24,
        graph_corr=0.4,
        dropout=0.5,
        gamma=1,
        beta=1,
        kappa=0.1,
        random_seed=42
    )

    pred_labels, embeddings = model.train()

    # 6. Store results
    print("\n" + "=" * 50)
    print("Step 6: Storing results")
    print("=" * 50)

    adata.obsm['spCLUE'] = embeddings
    adata.obs['pred'] = pred_labels.astype(str)
    print(f"Embeddings shape: {embeddings.shape}")

    # 7. Perform clustering
    print("\n" + "=" * 50)
    print("Step 7: Clustering with mclust")
    print("=" * 50)

    adata = clustering(
        adata,
        n_clusters=n_clusters,
        key='spCLUE',
        cluster_methods='mclust',
        refinement=False
    )

    # 8. Spatial refinement
    print("\n" + "=" * 50)
    print("Step 8: Spatial refinement")
    print("=" * 50)

    refine_label(adata, radius=30, key='mclust', suffix='refined')
    print("Refinement complete")

    # 9. Visualize results
    print("\n" + "=" * 50)
    print("Step 9: Visualization")
    print("=" * 50)

    # Create visualization
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Plot 1: Model predictions
    sq.pl.spatial_scatter(adata, color='pred', ax=axes[0], show=False,
                  title='spCLUE Predictions')

    # Plot 2: mclust clustering
    sq.pl.spatial_scatter(adata, color='mclust', ax=axes[1], show=False,
                  title='Mclust Clustering')

    # Plot 3: Refined clustering
    sq.pl.spatial_scatter(adata, color='mclust_refined', ax=axes[2], show=False,
                  title='Refined Clustering')

    plt.tight_layout()
    plt.savefig('spCLUE_single_slice_results.png', dpi=300, bbox_inches='tight')
    print("Saved visualization to spCLUE_single_slice_results.png")

    # 10. Save output
    if output_path:
        print("\n" + "=" * 50)
        print("Step 10: Saving output")
        print("=" * 50)
        adata.write_h5ad(output_path)
        print(f"Saved to: {output_path}")

    print("\n" + "=" * 50)
    print("Analysis complete!")
    print("=" * 50)

    return adata


def main():
    """Main function for command-line execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Run spCLUE on single-slice spatial transcriptomics data'
    )
    parser.add_argument(
        'input',
        type=str,
        help='Path to input AnnData (.h5ad) or 10X Visium directory'
    )
    parser.add_argument(
        '-n', '--n-clusters',
        type=int,
        default=12,
        help='Number of spatial domains (default: 12)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output path for results (.h5ad)'
    )

    args = parser.parse_args()

    # Run analysis
    adata = run_single_slice_analysis(
        adata_path=args.input,
        n_clusters=args.n_clusters,
        output_path=args.output
    )

    # Print summary
    print("\n" + "=" * 50)
    print("Results Summary")
    print("=" * 50)
    print(f"Number of spots: {adata.n_obs}")
    print(f"Number of genes: {adata.n_vars}")
    print(f"Number of clusters: {adata.obs['mclust'].nunique()}")
    print(f"\nCluster distribution:")
    print(adata.obs['mclust'].value_counts().sort_index())


if __name__ == '__main__':
    main()
