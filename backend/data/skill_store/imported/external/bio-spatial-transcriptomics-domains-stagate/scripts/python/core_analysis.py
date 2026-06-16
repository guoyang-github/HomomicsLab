"""
STAGATE core analysis module for spatial domain identification.

Graph attention autoencoder for spatial transcriptomics clustering,
based on PyTorch Geometric framework.

Author: Yang Guo
Date: 2026-04-03
Version: 1.1.0
"""

import warnings
from typing import Optional, List, Dict, Tuple, Union
import numpy as np
import pandas as pd
import scanpy as sc
from anndata import AnnData
import scipy.sparse as sp
import matplotlib.pyplot as plt


# ============================================================================
# Data Preparation and Spatial Network Construction
# ============================================================================

def prepare_data(
    adata: AnnData,
    min_counts: int = 100,
    n_top_genes: int = 3000,
    normalize: bool = True,
    log1p: bool = True,
) -> AnnData:
    """
    Prepare spatial data for STAGATE analysis.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    min_counts : int, default=100
        Minimum counts per spot
    n_top_genes : int, default=3000
        Number of highly variable genes to select
    normalize : bool, default=True
        Whether to normalize total counts
    log1p : bool, default=True
        Whether to apply log1p transformation

    Returns
    -------
    AnnData
        Prepared data with HVGs selected

    Examples
    --------
    >>> adata = prepare_data(adata, n_top_genes=3000)
    """
    adata = adata.copy()

    # Filter low quality spots
    if 'total_counts' not in adata.obs:
        adata.obs['total_counts'] = np.array(adata.X.sum(axis=1)).flatten()

    n_before = adata.n_obs
    adata = adata[adata.obs['total_counts'] >= min_counts].copy()
    n_after = adata.n_obs

    if n_after < n_before:
        print(f"Filtered {n_before - n_after} spots with < {min_counts} counts")

    if n_after == 0:
        raise ValueError("No spots remaining after filtering!")

    # Normalize
    if normalize:
        sc.pp.normalize_total(adata, target_sum=1e4, inplace=True)
        print("Normalized total counts to 10,000")

    if log1p:
        sc.pp.log1p(adata)
        print("Applied log1p transformation")

    # Select highly variable genes
    # Ensure float dtype for HVG computation (scanpy's seurat flavor modifies in-place)
    if np.issubdtype(adata.X.dtype, np.integer):
        adata.X = adata.X.astype(np.float32)
    sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes, flavor='seurat')
    n_hvg = adata.var.highly_variable.sum()
    print(f"Selected {n_hvg} highly variable genes")

    return adata


def build_spatial_network(
    adata: AnnData,
    rad_cutoff: Optional[float] = None,
    k_cutoff: Optional[int] = None,
    model: str = 'Radius',
    spatial_key: str = 'spatial',
    verbose: bool = True,
) -> None:
    """
    Construct spatial neighbor networks.

    Parameters
    ----------
    adata : AnnData
        Spatial data with coordinates
    rad_cutoff : float, optional
        Radius cutoff when model='Radius' (microns)
    k_cutoff : int, optional
        Number of nearest neighbors when model='KNN'
    model : str, default='Radius'
        Network model: 'Radius' or 'KNN'
    spatial_key : str, default='spatial'
        Key for spatial coordinates in adata.obsm
    verbose : bool, default=True
        Print statistics

    Returns
    -------
    None
        Adds 'Spatial_Net' to adata.uns

    Examples
    --------
    >>> build_spatial_network(adata, rad_cutoff=150, model='Radius')
    >>> build_spatial_network(adata, k_cutoff=10, model='KNN')

    Notes
    -----
    For Visium data with 55μm spots, rad_cutoff=150 connects ~4-6 neighbors.
    """
    try:
        import sklearn.neighbors
    except ImportError:
        raise ImportError("scikit-learn required")

    assert model in ['Radius', 'KNN'], "model must be 'Radius' or 'KNN'"

    if spatial_key not in adata.obsm:
        raise ValueError(f"'{spatial_key}' not found in adata.obsm")

    if model == 'Radius' and rad_cutoff is None:
        raise ValueError("rad_cutoff required for Radius model")
    if model == 'KNN' and k_cutoff is None:
        raise ValueError("k_cutoff required for KNN model")

    if verbose:
        print(f"------Calculating spatial graph (model={model})...")

    # Extract coordinates
    coor = pd.DataFrame(adata.obsm[spatial_key][:, :2])  # Use first 2 dimensions
    coor.index = adata.obs.index
    coor.columns = ['imagerow', 'imagecol']

    # Build network
    if model == 'Radius':
        nbrs = sklearn.neighbors.NearestNeighbors(radius=rad_cutoff).fit(coor)
        distances, indices = nbrs.radius_neighbors(coor, return_distance=True)
        KNN_list = []
        for it in range(indices.shape[0]):
            KNN_list.append(pd.DataFrame(zip([it]*indices[it].shape[0], indices[it], distances[it])))

    elif model == 'KNN':
        nbrs = sklearn.neighbors.NearestNeighbors(n_neighbors=k_cutoff+1).fit(coor)
        distances, indices = nbrs.kneighbors(coor)
        KNN_list = []
        for it in range(indices.shape[0]):
            KNN_list.append(pd.DataFrame(zip([it]*indices.shape[1], indices[it, :], distances[it, :])))

    KNN_df = pd.concat(KNN_list)
    KNN_df.columns = ['Cell1', 'Cell2', 'Distance']

    # Remove self-loops
    Spatial_Net = KNN_df.copy()
    Spatial_Net = Spatial_Net.loc[Spatial_Net['Distance'] > 0]

    # Map back to original indices
    id_cell_trans = dict(zip(range(coor.shape[0]), np.array(coor.index)))
    Spatial_Net['Cell1'] = Spatial_Net['Cell1'].map(id_cell_trans)
    Spatial_Net['Cell2'] = Spatial_Net['Cell2'].map(id_cell_trans)

    if verbose:
        print(f"Graph contains {Spatial_Net.shape[0]} edges, {adata.n_obs} cells.")
        print(f"{Spatial_Net.shape[0]/adata.n_obs:.2f} neighbors per cell on average.")

    adata.uns['Spatial_Net'] = Spatial_Net


def build_3d_spatial_network(
    adata: AnnData,
    rad_cutoff_2d: float,
    rad_cutoff_z: float,
    section_key: str = 'section',
    section_order: Optional[List[str]] = None,
    verbose: bool = True,
) -> None:
    """
    Construct 3D spatial neighbor networks for multiple sections.

    Parameters
    ----------
    adata : AnnData
        Concatenated data from multiple sections
    rad_cutoff_2d : float
        Radius cutoff for within-section neighbors
    rad_cutoff_z : float
        Radius cutoff for between-section neighbors
    section_key : str, default='section'
        Column in adata.obs identifying sections
    section_order : List[str], optional
        Order of sections for Z-axis connections
    verbose : bool, default=True
        Print statistics

    Returns
    -------
    None
        Adds 'Spatial_Net' to adata.uns

    Examples
    --------
    >>> build_3d_spatial_network(adata, rad_cutoff_2d=150, rad_cutoff_z=100,
    ...                          section_key='section', section_order=['1', '2', '3'])

    Notes
    -----
    Creates connections within each section (2D) and between adjacent sections (Z-axis).
    """
    if section_key not in adata.obs:
        raise ValueError(f"'{section_key}' not found in adata.obs")

    if section_order is None:
        section_order = sorted(adata.obs[section_key].unique())

    adata.uns['Spatial_Net_2D'] = pd.DataFrame()
    adata.uns['Spatial_Net_Zaxis'] = pd.DataFrame()

    num_section = len(section_order)

    if verbose:
        print(f'Radius for 2D SNN: {rad_cutoff_2d}')
        print(f'Radius for Z-axis SNN: {rad_cutoff_z}')

    # Build 2D networks for each section
    for section in section_order:
        if verbose:
            print(f'------Calculating 2D SNN of section {section}')

        temp_adata = adata[adata.obs[section_key] == section].copy()
        build_spatial_network(temp_adata, rad_cutoff=rad_cutoff_2d, verbose=False)
        temp_adata.uns['Spatial_Net']['SNN'] = section

        if verbose:
            n_edges = temp_adata.uns['Spatial_Net'].shape[0]
            print(f'Section {section}: {n_edges} edges, {temp_adata.n_obs} cells')

        adata.uns['Spatial_Net_2D'] = pd.concat([adata.uns['Spatial_Net_2D'], temp_adata.uns['Spatial_Net']])

    # Build Z-axis networks between adjacent sections
    for it in range(num_section - 1):
        section_1 = section_order[it]
        section_2 = section_order[it + 1]

        if verbose:
            print(f'------Calculating SNN between sections {section_1} and {section_2}')

        temp_adata = adata[adata.obs[section_key].isin([section_1, section_2])].copy()
        build_spatial_network(temp_adata, rad_cutoff=rad_cutoff_z, verbose=False)

        # Keep only cross-section edges
        spot_section_trans = dict(zip(temp_adata.obs.index, temp_adata.obs[section_key]))
        temp_adata.uns['Spatial_Net']['Section_id_1'] = temp_adata.uns['Spatial_Net']['Cell1'].map(spot_section_trans)
        temp_adata.uns['Spatial_Net']['Section_id_2'] = temp_adata.uns['Spatial_Net']['Cell2'].map(spot_section_trans)

        used_edge = temp_adata.uns['Spatial_Net'].apply(
            lambda x: x['Section_id_1'] != x['Section_id_2'], axis=1)
        temp_adata.uns['Spatial_Net'] = temp_adata.uns['Spatial_Net'].loc[used_edge, ['Cell1', 'Cell2', 'Distance']]
        temp_adata.uns['Spatial_Net']['SNN'] = f'{section_1}-{section_2}'

        if verbose:
            n_edges = temp_adata.uns['Spatial_Net'].shape[0]
            print(f'Between-section: {n_edges} edges')

        adata.uns['Spatial_Net_Zaxis'] = pd.concat([adata.uns['Spatial_Net_Zaxis'], temp_adata.uns['Spatial_Net']])

    # Combine networks
    adata.uns['Spatial_Net'] = pd.concat([adata.uns['Spatial_Net_2D'], adata.uns['Spatial_Net_Zaxis']])

    if verbose:
        total_edges = adata.uns['Spatial_Net'].shape[0]
        print(f'\n3D SNN: {total_edges} edges, {adata.n_obs} cells')
        print(f'{total_edges/adata.n_obs:.2f} neighbors per cell on average')


def plot_network_stats(adata: AnnData) -> plt.Figure:
    """
    Plot statistics of spatial network.

    Parameters
    ----------
    adata : AnnData
        Data with Spatial_Net in uns

    Returns
    -------
    plt.Figure
        Figure object
    """
    if 'Spatial_Net' not in adata.uns:
        raise ValueError("Spatial_Net not found. Run build_spatial_network first.")

    Num_edge = adata.uns['Spatial_Net'].shape[0]
    Mean_edge = Num_edge / adata.shape[0]

    # Count neighbors per cell
    neighbor_counts = adata.uns['Spatial_Net']['Cell1'].value_counts()
    plot_df = neighbor_counts.value_counts() / adata.shape[0]

    fig, ax = plt.subplots(figsize=[4, 3])
    ax.bar(plot_df.index, plot_df.values)
    ax.set_ylabel('Percentage')
    ax.set_xlabel('Number of Neighbors')
    ax.set_title(f'Neighbor Distribution (Mean={Mean_edge:.2f})')

    plt.tight_layout()
    return fig


# ============================================================================
# STAGATE Training
# ============================================================================

def train_stagate(
    adata: AnnData,
    hidden_dims: List[int] = [512, 30],
    n_epochs: int = 1000,
    lr: float = 0.001,
    key_added: str = 'STAGATE',
    gradient_clipping: float = 5.0,
    weight_decay: float = 0.0001,
    random_seed: int = 0,
    save_loss: bool = False,
    save_reconstruction: bool = False,
    verbose: bool = True,
    device: Optional[str] = None,
) -> AnnData:
    """
    Train STAGATE graph attention autoencoder.

    Parameters
    ----------
    adata : AnnData
        Data with Spatial_Net constructed
    hidden_dims : List[int], default=[512, 30]
        Hidden dimensions [encoder_hidden, embedding_dim]
    n_epochs : int, default=1000
        Number of training epochs
    lr : float, default=0.001
        Learning rate
    key_added : str, default='STAGATE'
        Key for storing embeddings in adata.obsm
    gradient_clipping : float, default=5.0
        Gradient clipping value
    weight_decay : float, default=0.0001
        Weight decay for optimizer
    random_seed : int, default=0
        Random seed for reproducibility
    save_loss : bool, default=False
        Save final loss in adata.uns
    save_reconstruction : bool, default=False
        Save reconstructed expression in adata.layers
    verbose : bool, default=True
        Print progress
    device : str, optional
        Device for training ('cuda' or 'cpu'). Auto-detected if None.

    Returns
    -------
    AnnData
        Data with STAGATE embeddings in adata.obsm[key_added]

    Examples
    --------
    >>> build_spatial_network(adata, rad_cutoff=150)
    >>> adata = train_stagate(adata, n_epochs=1000)

    Notes
    -----
    Requires PyTorch and PyTorch Geometric installed.
    Uses GPU if available unless specified otherwise.
    """
    try:
        import torch
        import torch.nn.functional as F
        from tqdm import tqdm
    except ImportError:
        raise ImportError("PyTorch and tqdm required. Install with: pip install torch tqdm")

    if 'Spatial_Net' not in adata.uns:
        raise ValueError("Spatial_Net not found. Run build_spatial_network first.")

    # Set device
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device(device)

    if verbose:
        print(f"Using device: {device}")
        print(f"Training STAGATE for {n_epochs} epochs...")

    # Set random seeds
    import random
    random.seed(random_seed)
    torch.manual_seed(random_seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(random_seed)
    np.random.seed(random_seed)

    # Prepare data
    adata = adata.copy()
    adata.X = sp.csr_matrix(adata.X)

    if 'highly_variable' in adata.var.columns:
        adata_Vars = adata[:, adata.var['highly_variable']]
    else:
        adata_Vars = adata

    if verbose:
        print(f"Input size: {adata_Vars.shape}")

    # Transfer to PyTorch
    data = _transfer_to_pytorch(adata_Vars)
    data = data.to(device)

    # Initialize model
    try:
        from .stagate_model import STAGATE
    except ImportError:
        try:
            from stagate_model import STAGATE
        except ImportError:
            raise ImportError("STAGATE model not found. Ensure stagate_model.py exists.")

    model = STAGATE([data.x.shape[1]] + hidden_dims).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    # Training loop
    model.train()
    for epoch in tqdm(range(1, n_epochs + 1), disable=not verbose):
        optimizer.zero_grad()
        z, out = model(data.x, data.edge_index)
        loss = F.mse_loss(data.x, out)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clipping)
        optimizer.step()

    # Extract embeddings
    model.eval()
    with torch.no_grad():
        z, out = model(data.x, data.edge_index)

    STAGATE_rep = z.cpu().detach().numpy()
    adata.obsm[key_added] = STAGATE_rep

    if save_loss:
        adata.uns[f'{key_added}_loss'] = loss.item()
    if save_reconstruction:
        ReX = out.cpu().detach().numpy()
        ReX[ReX < 0] = 0
        # Align reconstruction to full gene set (model trains on HVGs only)
        ReX_full = np.zeros((adata.n_obs, adata.n_vars))
        if 'highly_variable' in adata.var.columns:
            hvg_idx = np.where(adata.var['highly_variable'].values)[0]
            ReX_full[:, hvg_idx] = ReX
        else:
            ReX_full = ReX
        adata.layers[f'{key_added}_ReX'] = ReX_full

    if verbose:
        print(f"STAGATE embeddings saved to adata.obsm['{key_added}']")
        print(f"Embedding shape: {STAGATE_rep.shape}")

    return adata


def _transfer_to_pytorch(adata: AnnData):
    """
    Convert AnnData to PyTorch Geometric Data.

    Internal helper function.
    """
    try:
        import torch
        from torch_geometric.data import Data
    except ImportError:
        raise ImportError("PyTorch Geometric required. Install with: pip install torch-geometric")

    G_df = adata.uns['Spatial_Net'].copy()
    cells = np.array(adata.obs_names)
    cells_id_tran = dict(zip(cells, range(cells.shape[0])))
    G_df['Cell1'] = G_df['Cell1'].map(cells_id_tran)
    G_df['Cell2'] = G_df['Cell2'].map(cells_id_tran)

    G = sp.coo_matrix((np.ones(G_df.shape[0]), (G_df['Cell1'], G_df['Cell2'])),
                      shape=(adata.n_obs, adata.n_obs))
    G = G + sp.eye(G.shape[0])

    edgeList = np.nonzero(G)

    if isinstance(adata.X, np.ndarray):
        x = torch.FloatTensor(adata.X)
    else:
        # Convert sparse to dense; may use significant memory for large datasets
        x = torch.FloatTensor(np.array(adata.X.toarray()))

    data = Data(
        edge_index=torch.LongTensor(np.array([edgeList[0], edgeList[1]])),
        x=x
    )

    return data


# ============================================================================
# Batch Processing
# ============================================================================

def create_batch_data(
    adata: AnnData,
    num_batch_x: int = 2,
    num_batch_y: int = 2,
    spatial_key: str = 'spatial',
    plot_stats: bool = False,
) -> List[AnnData]:
    """
    Split spatial data into batches for large-scale processing.

    Parameters
    ----------
    adata : AnnData
        Spatial data
    num_batch_x : int, default=2
        Number of batches in X dimension
    num_batch_y : int, default=2
        Number of batches in Y dimension
    spatial_key : str, default='spatial'
        Key for spatial coordinates
    plot_stats : bool, default=False
        Plot batch size distribution

    Returns
    -------
    List[AnnData]
        List of batched AnnData objects

    Examples
    --------
    >>> batch_list = create_batch_data(adata, num_batch_x=3, num_batch_y=3)
    >>> for batch in batch_list:
    ...     batch = train_stagate(batch, n_epochs=500)
    """
    Sp_df = pd.DataFrame(adata.obsm[spatial_key][:, :2])
    Sp_df.index = adata.obs.index
    Sp_df.columns = ['X', 'Y']
    Sp_df = np.array(Sp_df)

    # Calculate batch boundaries
    batch_x_coor = [np.percentile(Sp_df[:, 0], (1/num_batch_x)*x*100) for x in range(num_batch_x+1)]
    batch_y_coor = [np.percentile(Sp_df[:, 1], (1/num_batch_y)*x*100) for x in range(num_batch_y+1)]

    Batch_list = []
    for it_x in range(num_batch_x):
        for it_y in range(num_batch_y):
            min_x = batch_x_coor[it_x]
            max_x = batch_x_coor[it_x+1]
            min_y = batch_y_coor[it_y]
            max_y = batch_y_coor[it_y+1]

            mask = (
                (adata.obsm[spatial_key][:, 0] >= min_x) &
                (adata.obsm[spatial_key][:, 0] <= max_x) &
                (adata.obsm[spatial_key][:, 1] >= min_y) &
                (adata.obsm[spatial_key][:, 1] <= max_y)
            )
            temp_adata = adata[mask].copy()
            Batch_list.append(temp_adata)

    if plot_stats:
        import matplotlib.pyplot as plt
        import seaborn as sns

        f, ax = plt.subplots(figsize=(3, 5))
        plot_df = pd.DataFrame([x.shape[0] for x in Batch_list], columns=['#spots/batch'])
        sns.boxplot(y='#spots/batch', data=plot_df, ax=ax)
        sns.stripplot(y='#spots/batch', data=plot_df, ax=ax, color='red', size=5)
        plt.title('Batch Size Distribution')
        plt.tight_layout()
        plt.show()

    print(f"Created {len(Batch_list)} batches")
    sizes = [b.n_obs for b in Batch_list]
    print(f"Batch sizes: min={min(sizes)}, max={max(sizes)}, mean={np.mean(sizes):.0f}")

    return Batch_list


# ============================================================================
# Clustering Functions
# ============================================================================

def mclust_clustering(
    adata: AnnData,
    n_clusters: int,
    used_obsm: str = 'STAGATE',
    model_names: str = 'EEE',
    random_seed: int = 2020,
    key_added: str = 'mclust',
) -> AnnData:
    """
    Cluster STAGATE embeddings using mclust (R package).

    Parameters
    ----------
    adata : AnnData
        Data with STAGATE embeddings
    n_clusters : int
        Number of clusters
    used_obsm : str, default='STAGATE'
        Key for embeddings in adata.obsm
    model_names : str, default='EEE'
        Model type for mclust (see mclust documentation)
    random_seed : int, default=2020
        Random seed
    key_added : str, default='mclust'
        Key for cluster labels in adata.obs

    Returns
    -------
    AnnData
        Data with cluster labels

    Examples
    --------
    >>> adata = mclust_clustering(adata, n_clusters=7, used_obsm='STAGATE')

    Notes
    -----
    Requires R and rpy2 installed.
    """
    try:
        import rpy2.robjects as robjects
        import rpy2.robjects.numpy2ri
    except ImportError:
        raise ImportError("rpy2 required for mclust. Install with: pip install rpy2")

    try:
        robjects.r.library("mclust")
    except Exception as e:
        raise ImportError(
            f"R package 'mclust' not available. Ensure R and mclust are installed. Error: {e}"
        )

    np.random.seed(random_seed)
    rpy2.robjects.numpy2ri.activate()

    r_random_seed = robjects.r['set.seed']
    r_random_seed(random_seed)
    rmclust = robjects.r['Mclust']

    if used_obsm not in adata.obsm:
        raise ValueError(f"'{used_obsm}' not found in adata.obsm")

    res = rmclust(rpy2.robjects.numpy2ri.numpy2rpy(adata.obsm[used_obsm]), n_clusters, model_names)
    mclust_res = np.array(res[-2])

    adata.obs[key_added] = pd.Categorical(mclust_res.astype('int'))

    print(f"mclust clustering completed: {n_clusters} clusters")
    print(adata.obs[key_added].value_counts().sort_index())

    return adata


def leiden_clustering(
    adata: AnnData,
    resolution: float = 1.0,
    used_obsm: str = 'STAGATE',
    key_added: str = 'stagate_leiden',
    n_neighbors: int = 15,
) -> AnnData:
    """
    Cluster STAGATE embeddings using Leiden algorithm.

    Parameters
    ----------
    adata : AnnData
        Data with STAGATE embeddings
    resolution : float, default=1.0
        Leiden resolution parameter
    used_obsm : str, default='STAGATE'
        Key for embeddings
    key_added : str, default='stagate_leiden'
        Key for cluster labels
    n_neighbors : int, default=15
        Number of neighbors for graph construction

    Returns
    -------
    AnnData
        Data with cluster labels

    Examples
    --------
    >>> adata = leiden_clustering(adata, resolution=0.5, used_obsm='STAGATE')
    """
    if used_obsm not in adata.obsm:
        raise ValueError(f"'{used_obsm}' not found in adata.obsm")

    adata = adata.copy()

    # Build neighbor graph from embeddings
    sc.pp.neighbors(adata, n_neighbors=n_neighbors, use_rep=used_obsm)
    sc.tl.leiden(adata, resolution=resolution, key_added=key_added)

    n_clusters = adata.obs[key_added].nunique()
    print(f"Leiden clustering completed: {n_clusters} clusters (resolution={resolution})")
    print(adata.obs[key_added].value_counts().sort_index())

    return adata


def louvain_clustering(
    adata: AnnData,
    resolution: float = 1.0,
    used_obsm: str = 'STAGATE',
    key_added: str = 'stagate_louvain',
    n_neighbors: int = 15,
) -> AnnData:
    """
    Cluster STAGATE embeddings using Leiden algorithm.
    (Note: scanpy has deprecated sc.tl.louvain in favor of sc.tl.leiden.)

    Parameters
    ----------
    adata : AnnData
        Data with STAGATE embeddings
    resolution : float, default=1.0
        Resolution parameter
    used_obsm : str, default='STAGATE'
        Key for embeddings
    key_added : str, default='stagate_louvain'
        Key for cluster labels
    n_neighbors : int, default=15
        Number of neighbors

    Returns
    -------
    AnnData
        Data with cluster labels
    """
    if used_obsm not in adata.obsm:
        raise ValueError(f"'{used_obsm}' not found in adata.obsm")

    adata = adata.copy()

    sc.pp.neighbors(adata, n_neighbors=n_neighbors, use_rep=used_obsm)
    sc.tl.leiden(adata, resolution=resolution, key_added=key_added)

    n_clusters = adata.obs[key_added].nunique()
    print(f"Leiden clustering completed: {n_clusters} clusters")

    return adata


# ============================================================================
# Result Export and Analysis
# ============================================================================

def export_results(
    adata: AnnData,
    output_dir: str,
    domain_key: str = 'mclust',
    embedding_key: str = 'STAGATE',
) -> None:
    """
    Export STAGATE results to files.

    Parameters
    ----------
    adata : AnnData
        Data with STAGATE results
    output_dir : str
        Output directory path
    domain_key : str, default='mclust'
        Key for domain labels
    embedding_key : str, default='STAGATE'
        Key for embeddings

    Returns
    -------
    None
        Saves files to output_dir
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Export embeddings
        if embedding_key in adata.obsm:
            df_emb = pd.DataFrame(
                adata.obsm[embedding_key],
                index=adata.obs_names,
                columns=[f'STAGATE_{i}' for i in range(adata.obsm[embedding_key].shape[1])]
            )
            emb_path = os.path.join(output_dir, 'stagate_embeddings.csv')
            df_emb.to_csv(emb_path)
            print(f"Saved embeddings to {emb_path}")

        # Export domains
        if domain_key in adata.obs:
            df_domains = adata.obs[[domain_key]].copy()
            domain_path = os.path.join(output_dir, 'stagate_domains.csv')
            df_domains.to_csv(domain_path)
            print(f"Saved domains to {domain_path}")

        # Export spatial coordinates
        if 'spatial' in adata.obsm:
            df_spatial = pd.DataFrame(
                adata.obsm['spatial'],
                index=adata.obs_names,
                columns=['X', 'Y'] if adata.obsm['spatial'].shape[1] == 2 else ['X', 'Y', 'Z']
            )
            coord_path = os.path.join(output_dir, 'spatial_coordinates.csv')
            df_spatial.to_csv(coord_path)

        # Save AnnData
        h5ad_path = os.path.join(output_dir, 'adata_stagate.h5ad')
        adata.write_h5ad(h5ad_path)
        print(f"Saved AnnData to {h5ad_path}")

    except (OSError, IOError) as e:
        raise RuntimeError(f"Failed to export results to {output_dir}: {e}")


def compute_domain_enrichment(
    adata: AnnData,
    domain_key: str = 'mclust',
    group_key: str = 'section',
) -> pd.DataFrame:
    """
    Compute domain enrichment across groups (e.g., sections).

    Parameters
    ----------
    adata : AnnData
        Data with domain labels
    domain_key : str, default='mclust'
        Key for domain labels
    group_key : str, default='section'
        Key for grouping

    Returns
    -------
    pd.DataFrame
        Domain proportion per group
    """
    if domain_key not in adata.obs:
        raise ValueError(f"'{domain_key}' not found in adata.obs")
    if group_key not in adata.obs:
        raise ValueError(f"'{group_key}' not found in adata.obs")

    # Calculate proportions
    df = pd.crosstab(adata.obs[group_key], adata.obs[domain_key], normalize='index')

    return df
