"""
Niche Clustering Example

Cluster spatial transcriptomics spots into niches based on cell type proportions
from deconvolution. Supports both KMeans (composition-only) and Leiden
(with spatial constraint) clustering methods.

Prerequisites:
    - Spatial data with deconvolution results in adata.obsm
    - scanpy, squidpy, scikit-learn, leidenalg
"""

import scanpy as sc
import squidpy as sq
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import warnings


def cluster_niches_by_proportions(
    adata,
    proportions_key='cell_type_proportions',
    n_clusters=12,
    use_spatial_constraint=True,
    n_neighbors=6,
    random_state=42
):
    """
    Cluster spatial niches based on cell type proportions.

    Parameters
    ----------
    adata : AnnData
        Spatial data with deconvolution results in obsm
    proportions_key : str
        Key in adata.obsm containing cell type proportions
    n_clusters : int
        Number of niche clusters (for KMeans method)
    use_spatial_constraint : bool
        Whether to include spatial coordinates in clustering (Leiden)
    n_neighbors : int
        Number of spatial neighbors (Visium default: 6)
    random_state : int
        Random seed for reproducibility

    Returns
    -------
    adata : AnnData with niche assignments in adata.obs['niche']
    niche_composition : DataFrame of niche x cell_type composition
    """
    # Validate proportions exist
    if proportions_key not in adata.obsm:
        available = list(adata.obsm.keys())
        raise ValueError(f"'{proportions_key}' not found. Available: {available}")

    proportions = adata.obsm[proportions_key]
    if hasattr(proportions, 'columns'):
        cell_types = proportions.columns.tolist()
        prop_values = proportions.values
    else:
        cell_types = [f"CellType_{i}" for i in range(proportions.shape[1])]
        prop_values = proportions

    print(f"Clustering {adata.n_obs} spots with {len(cell_types)} cell types")
    print(f"Cell types: {cell_types}")

    # PCA on proportions for dimensionality reduction
    n_components = min(10, len(cell_types) - 1, adata.n_obs - 1)
    if n_components < 2:
        n_components = min(5, len(cell_types))

    pca = PCA(n_components=n_components, random_state=random_state)
    prop_pca = pca.fit_transform(prop_values)
    print(f"PCA explained variance: {pca.explained_variance_ratio_.sum():.2%}")

    if use_spatial_constraint:
        print("Using Leiden clustering with spatial constraint...")

        # Build spatial neighbor graph
        sq.gr.spatial_neighbors(adata, n_neighs=n_neighbors)

        # Normalize spatial coordinates to [0, 1]
        coords = adata.obsm['spatial']
        coords_range = coords.max(axis=0) - coords.min(axis=0)
        coords_normalized = (coords - coords.min(axis=0)) / (coords_range + 1e-8)

        # Combine proportion PCA with normalized spatial coordinates
        combined_features = np.hstack([prop_pca, coords_normalized])
        adata.obsm['X_niche_pca'] = combined_features

        # Build nearest neighbors graph using combined features
        sc.pp.neighbors(
            adata,
            use_rep='X_niche_pca',
            n_neighbors=30,
            key_added='niche_neighbors'
        )

        # Leiden clustering
        sc.tl.leiden(
            adata,
            neighbors_key='niche_neighbors',
            key_added='niche',
            random_state=random_state
        )

        n_found = adata.obs['niche'].nunique()
        print(f"Leiden clustering found {n_found} niches")

    else:
        print(f"Using KMeans clustering with k={n_clusters}...")

        # KMeans on proportions only
        kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
        adata.obs['niche'] = kmeans.fit_predict(prop_pca).astype(str)

        print(f"KMeans clustering assigned {n_clusters} niches")

    # Calculate niche composition (mean proportions per niche)
    proportions_df = pd.DataFrame(
        prop_values,
        index=adata.obs_names,
        columns=cell_types
    )
    proportions_df['niche'] = adata.obs['niche'].values

    niche_composition = proportions_df.groupby('niche')[cell_types].mean()
    niche_sizes = proportions_df['niche'].value_counts().sort_index()

    print("\nNiche sizes:")
    print(niche_sizes)

    # Store results
    adata.uns['niche_composition'] = niche_composition
    adata.uns['niche_sizes'] = niche_sizes.to_dict()

    return adata, niche_composition


def visualize_niches(adata, niche_key='niche', title='Spatial Niches'):
    """
    Visualize niche spatial distribution.

    Parameters
    ----------
    adata : AnnData
        Spatial data with niche assignments
    niche_key : str
        Column in adata.obs containing niche labels
    title : str
        Plot title
    """
    import matplotlib.pyplot as plt

    n_niches = adata.obs[niche_key].nunique()
    palette = sc.pl.palettes.default_102[:n_niches]

    fig, ax = plt.subplots(figsize=(10, 8))
    sq.pl.spatial_scatter(
        adata,
        color=niche_key,
        title=title,
        palette=palette,
        ax=ax,
        show=False
    )
    plt.tight_layout()
    return fig


def plot_niche_heatmap(niche_composition, title='Niche Cell Type Composition'):
    """
    Create heatmap of cell type composition per niche.

    Parameters
    ----------
    niche_composition : DataFrame
        Niche x cell_type composition matrix
    title : str
        Plot title

    Returns
    -------
    fig : matplotlib Figure
    """
    import matplotlib.pyplot as plt
    import seaborn as sns

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.heatmap(
        niche_composition.T,
        cmap='YlOrRd',
        annot=True,
        fmt='.2f',
        cbar_kws={'label': 'Mean Proportion'},
        ax=ax
    )
    ax.set_title(title)
    ax.set_xlabel('Niche')
    ax.set_ylabel('Cell Type')
    plt.tight_layout()
    return fig


# Example usage
if __name__ == "__main__":
    # Load your spatial data with deconvolution results
    # adata = sc.read_h5ad('your_spatial_data.h5ad')

    # Example: Cluster niches using spatial constraint
    # adata, niche_comp = cluster_niches_by_proportions(
    #     adata,
    #     proportions_key='cell_type_proportions',
    #     n_clusters=10,
    #     use_spatial_constraint=True,
    #     n_neighbors=6
    # )

    # Example: Cluster without spatial constraint (KMeans)
    # adata, niche_comp = cluster_niches_by_proportions(
    #     adata,
    #     proportions_key='cell_type_proportions',
    #     n_clusters=8,
    #     use_spatial_constraint=False
    # )

    # Visualize results
    # fig1 = visualize_niches(adata, title='Tissue Microenvironment Niches')
    # fig1.savefig('niche_spatial_map.png', dpi=300, bbox_inches='tight')

    # fig2 = plot_niche_heatmap(niche_comp)
    # fig2.savefig('niche_composition_heatmap.png', dpi=300, bbox_inches='tight')

    print("Niche clustering example loaded successfully!")
    print("\nTo use:")
    print("1. Load your spatial data with deconvolution results")
    print("2. Call cluster_niches_by_proportions()")
    print("3. Visualize with visualize_niches() and plot_niche_heatmap()")
