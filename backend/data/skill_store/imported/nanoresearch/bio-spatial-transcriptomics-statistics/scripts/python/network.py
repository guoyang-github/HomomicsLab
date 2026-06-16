"""
Network Analysis for Spatial Transcriptomics

This module provides network-based analysis methods for spatial data:
- Centrality measures: Identify important nodes in the spatial network
- Network properties: Global network statistics
- Interaction matrices: Cell-type specific connectivity patterns

Methods:
    - Degree Centrality: Local connectivity of spots
    - Closeness Centrality: Proximity to all other spots
    - Betweenness Centrality: Bridge-like importance
    - Network Efficiency: Global communication efficiency
"""

import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Tuple, Union
import warnings


def extract_adjacency_matrix(
    adata,
    n_neighbors: int = 6,
    method: str = 'knn'
) -> np.ndarray:
    """
    Extract spatial adjacency matrix from AnnData.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    n_neighbors : int, default=6
        Number of neighbors
    method : str, default='knn'
        Method to construct adjacency ('knn' or 'radius')

    Returns
    -------
    np.ndarray
        Adjacency matrix (n_obs x n_obs)

    Example
    -------
    >>> adjacency = extract_adjacency_matrix(adata, n_neighbors=6)
    >>> print(f"Network has {adjacency.sum() / 2} edges")
    """
    from sklearn.neighbors import kneighbors_graph, radius_neighbors_graph

    coords = adata.obsm['spatial']

    if method == 'knn':
        adjacency = kneighbors_graph(coords, n_neighbors=n_neighbors, mode='connectivity')
    elif method == 'radius':
        # Estimate radius from k-th neighbor distance
        from sklearn.neighbors import NearestNeighbors
        nbrs = NearestNeighbors(n_neighbors=n_neighbors + 1).fit(coords)
        distances, _ = nbrs.kneighbors(coords)
        radius = np.median(distances[:, -1])
        adjacency = radius_neighbors_graph(coords, radius=radius, mode='connectivity')
    else:
        raise ValueError(f"Unknown method: {method}")

    # Make symmetric (undirected graph)
    adjacency = np.maximum(adjacency, adjacency.T)

    return adjacency


def compute_degree_centrality(adjacency: np.ndarray) -> np.ndarray:
    """
    Compute degree centrality for each node.

    Degree centrality is the number of connections a node has,
    normalized by the maximum possible connections.

    Parameters
    ----------
    adjacency : np.ndarray
        Adjacency matrix

    Returns
    -------
    np.ndarray
        Degree centrality scores (0-1 scale)

    Example
    -------
    >>> adjacency = extract_adjacency_matrix(adata)
    >>> centrality = compute_degree_centrality(adjacency)
    >>> print(f"Most connected node: {centrality.argmax()}")
    """
    n = adjacency.shape[0]
    degrees = np.array(adjacency.sum(axis=1)).flatten()
    max_degree = n - 1  # Maximum possible degree

    return degrees / max_degree


def compute_closeness_centrality(adjacency: np.ndarray) -> np.ndarray:
    """
    Compute closeness centrality for each node.

    Closeness centrality measures how close a node is to all other nodes
    in the network. Higher values indicate nodes that can reach others
    more quickly.

    Parameters
    ----------
    adjacency : np.ndarray
        Adjacency matrix

    Returns
    -------
    np.ndarray
        Closeness centrality scores

    References
    ----------
    Freeman, L.C. (1978). Centrality in social networks conceptual clarification.
    Social Networks, 1(3), 215-239.

    Example
    -------
    >>> adjacency = extract_adjacency_matrix(adata)
    >>> centrality = compute_closeness_centrality(adjacency)
    >>> print(f"Most central node: {centrality.argmax()}")
    """
    from scipy.sparse import csgraph

    # Convert to distance matrix (1 for connected, inf for unconnected)
    n = adjacency.shape[0]
    distances = csgraph.shortest_path(adjacency, directed=False, unweighted=True)

    # Handle infinite distances (disconnected components)
    distances[np.isinf(distances)] = n  # Use max distance for disconnected

    # Closeness = (n-1) / sum of distances to all other nodes
    with np.errstate(divide='ignore'):
        closeness = (n - 1) / distances.sum(axis=1)

    return closeness


def compute_betweenness_centrality(
    adjacency: np.ndarray,
    normalized: bool = True
) -> np.ndarray:
    """
    Compute betweenness centrality for each node.

    Betweenness centrality measures how often a node lies on the shortest
    path between other nodes. High betweenness indicates "bridge" nodes
    that connect different parts of the network.

    Parameters
    ----------
    adjacency : np.ndarray
        Adjacency matrix
    normalized : bool, default=True
        Whether to normalize by (n-1)*(n-2) for directed networks
        or (n-1)*(n-2)/2 for undirected

    Returns
    -------
    np.ndarray
        Betweenness centrality scores

    References
    ----------
    Freeman, L.C. (1977). A set of measures of centrality based on betweenness.
    Sociometry, 40(1), 35-41.

    Example
    -------
    >>> adjacency = extract_adjacency_matrix(adata)
    >>> centrality = compute_betweenness_centrality(adjacency)
    >>> print(f"Top bridge node: {centrality.argmax()}")
    """
    try:
        import networkx as nx
    except ImportError:
        raise ImportError("networkx is required for betweenness centrality")

    # Convert to networkx graph
    G = nx.from_numpy_array(adjacency)

    # Compute betweenness
    betweenness = nx.betweenness_centrality(G, normalized=normalized)

    return np.array([betweenness[i] for i in range(len(betweenness))])


def compute_centrality_scores(
    adata,
    n_neighbors: int = 6,
    methods: List[str] = ['degree', 'closeness', 'betweenness']
) -> pd.DataFrame:
    """
    Compute multiple centrality measures for spatial network.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    n_neighbors : int, default=6
        Number of neighbors for network construction
    methods : list, default=['degree', 'closeness', 'betweenness']
        List of centrality methods to compute

    Returns
    -------
    pd.DataFrame
        DataFrame with centrality scores for each spot

    Example
    -------
    >>> centrality = compute_centrality_scores(adata, methods=['degree', 'betweenness'])
    >>> print(centrality.head())
           degree  betweenness
    spot_0   0.12       0.0234
    spot_1   0.08       0.0012
    """
    # Build adjacency matrix
    adjacency = extract_adjacency_matrix(adata, n_neighbors)

    results = pd.DataFrame(index=adata.obs_names)

    if 'degree' in methods:
        results['degree'] = compute_degree_centrality(adjacency)

    if 'closeness' in methods:
        results['closeness'] = compute_closeness_centrality(adjacency)

    if 'betweenness' in methods:
        results['betweenness'] = compute_betweenness_centrality(adjacency)

    return results


def compute_spatial_centrality(
    adata,
    gene: Optional[str] = None,
    layer: Optional[str] = None,
    n_neighbors: int = 6,
    percentile: float = 90.0
) -> pd.DataFrame:
    """
    Compute spatial centrality weighted by gene expression.

    This combines network centrality with expression values to identify
    "functionally central" spots that are both well-connected and highly
    expressed for a gene of interest.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    gene : str, optional
        Gene to weight by. If None, uses unweighted centrality.
    layer : str, optional
        Layer to use for expression
    n_neighbors : int, default=6
        Number of neighbors
    percentile : float, default=90.0
        Percentile threshold for high centrality spots

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - spot_id: Spot identifier
        - degree: Degree centrality
        - expression: Expression value (if gene specified)
        - weighted_centrality: Expression * degree
        - is_hub: Whether spot is in top percentile

    Example
    -------
    >>> # Find hub spots for a specific gene
    >>> centrality = compute_spatial_centrality(adata, gene='GeneA', percentile=95)
    >>> hubs = centrality[centrality['is_hub']]
    """
    # Get base centrality
    base_centrality = compute_centrality_scores(
        adata, n_neighbors, methods=['degree']
    )

    results = pd.DataFrame({
        'spot_id': adata.obs_names,
        'degree': base_centrality['degree'].values
    })

    # Add expression weighting if gene specified
    if gene is not None:
        if gene not in adata.var_names:
            raise ValueError(f"Gene '{gene}' not found")

        if layer is not None:
            X = adata.layers[layer]
        else:
            X = adata.X

        if hasattr(X, 'toarray'):
            X = X.toarray()

        expression = X[:, adata.var_names.get_loc(gene)]
        results['expression'] = expression

        # Weighted centrality
        results['weighted_centrality'] = results['degree'] * expression
    else:
        results['weighted_centrality'] = results['degree']

    # Identify hubs
    threshold = np.percentile(results['weighted_centrality'], percentile)
    results['is_hub'] = results['weighted_centrality'] >= threshold

    return results


def compute_clustering_coefficient(adjacency: np.ndarray) -> np.ndarray:
    """
    Compute local clustering coefficient for each node.

    Clustering coefficient measures the degree to which nodes in a network
    tend to cluster together. High values indicate tightly knit neighborhoods.

    Parameters
    ----------
    adjacency : np.ndarray
        Adjacency matrix

    Returns
    -------
    np.ndarray
        Clustering coefficients (0-1 scale)

    References
    ----------
    Watts, D.J., & Strogatz, S.H. (1998). Collective dynamics of 'small-world' networks.
    Nature, 393(6684), 440-442.

    Example
    -------
    >>> adjacency = extract_adjacency_matrix(adata)
    >>> cc = compute_clustering_coefficient(adjacency)
    >>> print(f"Mean clustering: {cc.mean():.3f}")
    """
    try:
        import networkx as nx
    except ImportError:
        raise ImportError("networkx is required for clustering coefficient")

    G = nx.from_numpy_array(adjacency)
    clustering = nx.clustering(G)

    return np.array([clustering[i] for i in range(len(clustering))])


def compute_network_efficiency(adjacency: np.ndarray) -> Dict:
    """
    Compute global network efficiency metrics.

    Network efficiency measures how efficiently information can be exchanged
    across the network.

    Parameters
    ----------
    adjacency : np.ndarray
        Adjacency matrix

    Returns
    -------
    dict
        Dictionary with:
        - global_efficiency: Average inverse path length
        - local_efficiency: Average efficiency of local neighborhoods
        - connected_components: Number of connected components
        - largest_component_size: Size of largest component
        - density: Edge density of network

    References
    ----------
    Latora, V., & Marchiori, M. (2001). Efficient behavior of small-world networks.
    Physical Review Letters, 87(19), 198701.

    Example
    -------
    >>> adjacency = extract_adjacency_matrix(adata)
    >>> efficiency = compute_network_efficiency(adjacency)
    >>> print(f"Global efficiency: {efficiency['global_efficiency']:.3f}")
    """
    try:
        import networkx as nx
    except ImportError:
        raise ImportError("networkx is required for network efficiency")

    G = nx.from_numpy_array(adjacency)

    # Global efficiency
    try:
        global_eff = nx.global_efficiency(G)
    except:
        global_eff = np.nan

    # Local efficiency
    try:
        local_eff = nx.local_efficiency(G)
    except:
        local_eff = np.nan

    # Connected components
    components = list(nx.connected_components(G))
    n_components = len(components)
    largest_component_size = max(len(c) for c in components) if components else 0

    # Density
    density = nx.density(G)

    return {
        'global_efficiency': global_eff,
        'local_efficiency': local_eff,
        'connected_components': n_components,
        'largest_component_size': largest_component_size,
        'density': density
    }


def compute_network_properties(
    adata,
    n_neighbors: int = 6
) -> Dict:
    """
    Compute comprehensive network properties for spatial data.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    n_neighbors : int, default=6
        Number of neighbors

    Returns
    -------
    dict
        Dictionary containing:
        - efficiency: Global efficiency metrics
        - clustering: Mean clustering coefficient
        - degree_stats: Degree distribution statistics
        - diameter: Network diameter (if connected)

    Example
    -------
    >>> props = compute_network_properties(adata, n_neighbors=6)
    >>> print(f"Network density: {props['efficiency']['density']:.3f}")
    >>> print(f"Mean clustering: {props['clustering']['mean']:.3f}")
    """
    adjacency = extract_adjacency_matrix(adata, n_neighbors)

    # Efficiency
    efficiency = compute_network_efficiency(adjacency)

    # Clustering
    clustering = compute_clustering_coefficient(adjacency)
    clustering_stats = {
        'mean': clustering.mean(),
        'std': clustering.std(),
        'min': clustering.min(),
        'max': clustering.max(),
        'median': np.median(clustering)
    }

    # Degree statistics
    degrees = np.array(adjacency.sum(axis=1)).flatten()
    degree_stats = {
        'mean': degrees.mean(),
        'std': degrees.std(),
        'min': degrees.min(),
        'max': degrees.max(),
        'median': np.median(degrees)
    }

    # Diameter (only if connected)
    try:
        import networkx as nx
        G = nx.from_numpy_array(adjacency)
        if nx.is_connected(G):
            diameter = nx.diameter(G)
        else:
            diameter = np.inf
    except:
        diameter = np.nan

    return {
        'efficiency': efficiency,
        'clustering': clustering_stats,
        'degree_stats': degree_stats,
        'diameter': diameter
    }


def compute_interaction_matrix(
    adata,
    cluster_key: str = 'cell_type',
    n_neighbors: int = 6,
    metric: str = 'connectivity'
) -> pd.DataFrame:
    """
    Compute cell-type interaction matrix based on spatial adjacency.

    This quantifies how often different cell types are adjacent in space,
    revealing preferential spatial associations.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    cluster_key : str, default='cell_type'
        Column containing cluster labels
    n_neighbors : int, default=6
        Number of neighbors for adjacency
    metric : str, default='connectivity'
        Metric to compute ('connectivity', 'mean_centrality', 'interaction_strength')

    Returns
    -------
    pd.DataFrame
        Interaction matrix (cell_types x cell_types)

    Example
    -------
    >>> interactions = compute_interaction_matrix(adata, cluster_key='cell_type')
    >>> print(interactions.loc['Macrophage', 'T_cell'])
    """
    if cluster_key not in adata.obs.columns:
        raise ValueError(f"Column '{cluster_key}' not found in adata.obs")

    # Get adjacency and clusters
    adjacency = extract_adjacency_matrix(adata, n_neighbors)
    clusters = adata.obs[cluster_key].astype('category')
    categories = clusters.cat.categories.tolist()

    n_categories = len(categories)
    interaction_matrix = np.zeros((n_categories, n_categories))

    for i, cat_i in enumerate(categories):
        mask_i = clusters == cat_i
        indices_i = np.where(mask_i)[0]

        for j, cat_j in enumerate(categories):
            mask_j = clusters == cat_j

            if metric == 'connectivity':
                # Count edges between categories
                count = 0
                for idx in indices_i:
                    neighbors = adjacency[idx].nonzero()[1]
                    count += mask_j.iloc[neighbors].sum()
                interaction_matrix[i, j] = count

            elif metric == 'mean_centrality':
                # Average centrality of cat_j neighbors of cat_i
                degrees = np.array(adjacency.sum(axis=1)).flatten()
                neighbor_degrees = []
                for idx in indices_i:
                    neighbors = adjacency[idx].nonzero()[1]
                    neighbor_degrees.extend(degrees[neighbors][mask_j.iloc[neighbors]])
                interaction_matrix[i, j] = np.mean(neighbor_degrees) if neighbor_degrees else 0

    # Normalize by row (source) to get proportions
    if metric == 'connectivity':
        row_sums = interaction_matrix.sum(axis=1, keepdims=True)
        interaction_matrix = interaction_matrix / (row_sums + 1e-10)

    return pd.DataFrame(
        interaction_matrix,
        index=categories,
        columns=categories
    )


def analyze_network_structure(
    adata,
    cluster_key: str = 'cell_type',
    n_neighbors: int = 6,
    compute_centralities: bool = True
) -> Dict:
    """
    Comprehensive network structure analysis.

    Parameters
    ----------
    adata : AnnData
        Spatial transcriptomics data
    cluster_key : str, default='cell_type'
        Column containing cluster labels
    n_neighbors : int, default=6
        Number of neighbors
    compute_centralities : bool, default=True
        Whether to compute centrality for each spot

    Returns
    -------
    dict
        Complete network analysis results including:
        - properties: Global network properties
        - centralities: Per-spot centrality scores (if requested)
        - interaction_matrix: Cell-type interaction matrix
        - cluster_centrality: Average centrality per cluster

    Example
    -------
    >>> results = analyze_network_structure(adata, cluster_key='cell_type')
    >>> print(results['properties']['efficiency'])
    """
    print("Computing network properties...")
    properties = compute_network_properties(adata, n_neighbors)

    print("Computing interaction matrix...")
    interactions = compute_interaction_matrix(adata, cluster_key, n_neighbors)

    results = {
        'properties': properties,
        'interaction_matrix': interactions
    }

    if compute_centralities:
        print("Computing centrality scores...")
        centralities = compute_centrality_scores(
            adata, n_neighbors, methods=['degree', 'closeness', 'betweenness']
        )
        results['centralities'] = centralities

        # Average centrality by cluster
        if cluster_key in adata.obs.columns:
            centralities_with_cluster = centralities.copy()
            centralities_with_cluster[cluster_key] = adata.obs[cluster_key].values
            cluster_centrality = centralities_with_cluster.groupby(cluster_key).mean()
            results['cluster_centrality'] = cluster_centrality

    return results
