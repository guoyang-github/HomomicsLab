"""
Multi-Slice Integration with spCLUE

This example demonstrates how to use spCLUE for integrating multiple
spatial transcriptomics slices with batch correction.

Author: Claude Code
Date: 2026-04-07
"""

import scanpy as sc
import anndata as ad
import torch
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from scripts import spCLUE, preprocess, prepare_graph, clustering, fix_seed, batch_refine_label
from sklearn.decomposition import PCA


def run_multi_slice_integration(adata_paths, slice_names, n_clusters=12,
                                 output_path=None, batch_key='batch'):
    """
    Run spCLUE multi-slice integration with batch correction.

    Parameters
    ----------
    adata_paths : list
        List of paths to AnnData files
    slice_names : list
        List of slice names (same length as adata_paths)
    n_clusters : int
        Number of spatial domains
    output_path : str, optional
        Path to save output
    batch_key : str
        Key for batch information in obs

    Returns
    -------
    AnnData
        Integrated AnnData with batch-corrected embeddings
    """
    # Set random seed
    fix_seed(42)

    assert len(adata_paths) == len(slice_names), \
        "Number of paths must match number of slice names"

    # 1. Load and concatenate data
    print("=" * 50)
    print("Step 1: Loading and concatenating data")
    print("=" * 50)

    adata_list = []
    for path, name in zip(adata_paths, slice_names):
        print(f"Loading {name} from {path}")
        adata = sc.read_h5ad(path) if path.endswith('.h5ad') else sc.read_visium(path)
        adata.obs[batch_key] = name
        adata_list.append(adata)

    # Concatenate
    adata_combined = ad.concat(adata_list, label=batch_key, keys=slice_names)
    print(f"\nCombined data shape: {adata_combined.shape}")
    print(f"Batches: {adata_combined.obs[batch_key].unique()}")

    # 2. Preprocess
    print("\n" + "=" * 50)
    print("Step 2: Preprocessing")
    print("=" * 50)

    adata_combined = preprocess(adata_combined, hvgNumber=2000)
    print(f"After HVG selection: {adata_combined.shape}")

    # 3. Apply PCA
    print("\n" + "=" * 50)
    print("Step 3: PCA dimensionality reduction")
    print("=" * 50)

    pca = PCA(n_components=200, random_state=0)
    input_data = pca.fit_transform(adata_combined.X)
    print(f"PCA input shape: {input_data.shape}")

    # 4. Create batch list
    print("\n" + "=" * 50)
    print("Step 4: Creating batch labels")
    print("=" * 50)

    batch_list = adata_combined.obs[batch_key].astype('category').cat.codes.values
    print(f"Number of batches: {len(np.unique(batch_list))}")

    # 5. Build graphs
    print("\n" + "=" * 50)
    print("Step 5: Building multi-view graphs")
    print("=" * 50)

    graph_dict = {
        "spatial": prepare_graph(adata_combined, key="spatial", n_neighbors=12),
        "expr": prepare_graph(adata_combined, key="expr", n_neighbors=12, n_comps=50)
    }
    print(f"Graph shapes: spatial={graph_dict['spatial'].shape}, expr={graph_dict['expr'].shape}")

    # 6. Initialize and train model with batch correction
    print("\n" + "=" * 50)
    print("Step 6: Training spCLUE with batch correction")
    print("=" * 50)

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Enable batch training for large datasets
    batch_train = adata_combined.n_obs > 20000
    print(f"Batch training: {batch_train} (n_obs={adata_combined.n_obs})")

    model = spCLUE(
        input_data=input_data,
        graph_dict=graph_dict,
        n_clusters=n_clusters,
        batch_list=batch_list,
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
        batch_train=batch_train,
        random_seed=42
    )

    _, embeddings = model.trainBatch()

    # 7. Store results
    print("\n" + "=" * 50)
    print("Step 7: Storing results")
    print("=" * 50)

    adata_combined.obsm['spCLUE'] = embeddings
    print(f"Embeddings shape: {embeddings.shape}")

    # 8. Clustering
    print("\n" + "=" * 50)
    print("Step 8: Clustering")
    print("=" * 50)

    adata_combined = clustering(
        adata_combined,
        n_clusters=n_clusters,
        key='spCLUE',
        cluster_methods='mclust',
        refinement=False
    )

    # 9. Batch-aware spatial refinement
    print("\n" + "=" * 50)
    print("Step 9: Batch-aware spatial refinement")
    print("=" * 50)

    batch_refine_label(adata_combined, radius=30, key='mclust',
                       suffix='refined', batch_key=batch_key)
    print("Refinement complete")

    # 10. Visualization
    print("\n" + "=" * 50)
    print("Step 10: Visualization")
    print("=" * 50)

    # Create UMAP for visualization
    sc.pp.neighbors(adata_combined, use_rep='spCLUE')
    sc.tl.umap(adata_combined)

    # Plot UMAP
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    sc.pl.umap(adata_combined, color=batch_key, ax=axes[0], show=False,
               title='Batch Distribution')
    sc.pl.umap(adata_combined, color='mclust', ax=axes[1], show=False,
               title='Integrated Clusters')
    plt.tight_layout()
    plt.savefig('spCLUE_integration_umap.png', dpi=300, bbox_inches='tight')
    print("Saved UMAP to spCLUE_integration_umap.png")

    # Plot spatial distribution for each slice
    n_slices = len(slice_names)
    fig, axes = plt.subplots(n_slices, 3, figsize=(18, 6 * n_slices))

    for i, name in enumerate(slice_names):
        adata_slice = adata_combined[adata_combined.obs[batch_key] == name]

        if n_slices == 1:
            ax_row = axes
        else:
            ax_row = axes[i]

        sq.pl.spatial_scatter(adata_slice, color=batch_key, ax=ax_row[0], show=False,
                      title=f'{name} - Batch')
        sq.pl.spatial_scatter(adata_slice, color='mclust', ax=ax_row[1], show=False,
                      title=f'{name} - Clusters')
        sq.pl.spatial_scatter(adata_slice, color='mclust_refined', ax=ax_row[2], show=False,
                      title=f'{name} - Refined')

    plt.tight_layout()
    plt.savefig('spCLUE_integration_spatial.png', dpi=300, bbox_inches='tight')
    print("Saved spatial plots to spCLUE_integration_spatial.png")

    # 11. Save output
    if output_path:
        print("\n" + "=" * 50)
        print("Step 11: Saving output")
        print("=" * 50)
        adata_combined.write_h5ad(output_path)
        print(f"Saved to: {output_path}")

    print("\n" + "=" * 50)
    print("Integration complete!")
    print("=" * 50)

    return adata_combined


def main():
    """Main function for command-line execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Run spCLUE multi-slice integration'
    )
    parser.add_argument(
        'inputs',
        nargs='+',
        help='Paths to input AnnData files'
    )
    parser.add_argument(
        '-n', '--names',
        nargs='+',
        required=True,
        help='Names for each slice (same order as inputs)'
    )
    parser.add_argument(
        '-c', '--n-clusters',
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

    if len(args.inputs) != len(args.names):
        raise ValueError("Number of inputs must match number of names")

    # Run integration
    adata = run_multi_slice_integration(
        adata_paths=args.inputs,
        slice_names=args.names,
        n_clusters=args.n_clusters,
        output_path=args.output
    )

    # Print summary
    print("\n" + "=" * 50)
    print("Integration Summary")
    print("=" * 50)
    print(f"Total spots: {adata.n_obs}")
    print(f"Total genes: {adata.n_vars}")
    print(f"Number of slices: {adata.obs['batch'].nunique()}")
    print(f"Number of clusters: {adata.obs['mclust'].nunique()}")
    print(f"\nBatch distribution:")
    print(adata.obs['batch'].value_counts())
    print(f"\nCluster distribution:")
    print(adata.obs['mclust'].value_counts().sort_index())


if __name__ == '__main__':
    main()
