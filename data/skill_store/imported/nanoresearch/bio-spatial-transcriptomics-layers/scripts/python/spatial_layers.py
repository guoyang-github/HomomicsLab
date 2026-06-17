"""Spatial Layer Analysis - Create concentric layers around ROI for gradient analysis."""

import numpy as np
import pandas as pd
import scanpy as sc
from scipy.spatial.distance import cdist
from scipy import stats
from typing import Union, List, Optional, Tuple, Dict
from sklearn.neighbors import NearestNeighbors
import warnings


def create_spatial_layers(
    adata: sc.AnnData,
    roi_definition: Union[str, List[str], np.ndarray],
    roi_type: str = "niche",
    n_layers: int = 3,
    layer_method: str = "distance",
    distance_threshold: Optional[Union[float, List[float]]] = None,
    layer_names: Optional[List[str]] = None,
    buffer_zone: float = 0,
    return_distance: bool = True,
    spatial_key: str = "spatial",
    inplace: bool = True
) -> Optional[sc.AnnData]:
    """
    Create concentric spatial layers around a Region of Interest (ROI).

    This function divides the tissue into concentric layers centered on an ROI,
    enabling analysis of microenvironment gradients (e.g., tumor infiltration zones,
    perineural regions, perivascular niches).

    Parameters
    ----------
    adata : sc.AnnData
        Spatial transcriptomics data with coordinates in adata.obsm[spatial_key]
    roi_definition : str, list, or np.ndarray
        Definition of the center region:
        - roi_type="niche": niche name(s) e.g., "Tumor_core" or ["Tumor_core", "Tumor_margin"]
        - roi_type="cell_type": cell type name(s) e.g., "Cancer_cell"
        - roi_type="mask": boolean array of length n_obs
        - roi_type="coordinates": center coordinates [[x1, y1], [x2, y2], ...]
    roi_type : str, default="niche"
        Type of ROI definition: "niche", "cell_type", "mask", "coordinates"
    n_layers : int, default=3
        Number of layers to create (excluding center/ROI layer)
    layer_method : str, default="distance"
        Method for layer creation:
        - "distance": Euclidean distance from ROI boundary (recommended for Visium)
        - "knn": K-nearest neighbor graph steps (recommended for high-res data)
        - "radius": Fixed radius expansion from ROI center
    distance_threshold : float or list, optional
        Distance thresholds defining layer boundaries:
        - Single float: equal-width layers (e.g., 100 means layers at 0-100, 100-200, 200-300 μm)
        - List: custom boundaries [100, 200, 300] means layers at 0-100, 100-200, 200-300+ μm
        If None, automatically calculated based on data extent
    layer_names : list, optional
        Custom names for layers. If None, uses ["center", "layer_1", "layer_2", ...]
    buffer_zone : float, default=0
        Distance buffer between ROI and first layer (μm). Spots within buffer
        are excluded from analysis to avoid boundary effects.
    return_distance : bool, default=True
        Whether to store distance to ROI in adata.obs
    spatial_key : str, default="spatial"
        Key in adata.obsm containing spatial coordinates
    inplace : bool, default=True
        If True, modify adata in place. If False, return a copy.

    Returns
    -------
    adata : sc.AnnData or None
        Modified AnnData object with added columns:
        - adata.obs['spatial_layer']: Layer assignment
        - adata.obs['distance_to_roi']: Distance to ROI boundary (if return_distance=True)
        - adata.obs['roi_status']: Whether spot is in ROI (True/False)
        - adata.uns['spatial_layers']: Layer statistics and parameters

    Examples
    --------
    >>> # Create 3 layers around tumor core (100μm each)
    >>> create_spatial_layers(
    ...     adata,
    ...     roi_definition="Tumor_core",
    ...     roi_type="niche",
    ...     n_layers=3,
    ...     distance_threshold=100,
    ...     layer_names=["Tumor_core", "Interface", "Stroma", "Distant"]
    ... )

    >>> # Analyze around specific cell type with KNN method
    >>> create_spatial_layers(
    ...     adata,
    ...     roi_definition="Endothelial",
    ...     roi_type="cell_type",
    ...     layer_method="knn",
    ...     n_layers=5
    ... )
    """
    # Handle inplace
    if not inplace:
        adata = adata.copy()

    # Validate inputs
    if spatial_key not in adata.obsm:
        raise ValueError(f"Spatial coordinates not found in adata.obsm['{spatial_key}']")

    coords = adata.obsm[spatial_key]
    if coords.shape[1] < 2:
        raise ValueError("Spatial coordinates must have at least 2 dimensions (x, y)")

    coords_2d = coords[:, :2]  # Use only x, y

    # Parse ROI definition
    roi_mask = _parse_roi_definition(adata, roi_definition, roi_type)

    if roi_mask.sum() == 0:
        raise ValueError("No spots found matching ROI definition")

    # Calculate distances based on method
    if layer_method == "distance":
        distances = _calculate_distance_to_roi(coords_2d, roi_mask)
    elif layer_method == "knn":
        distances = _calculate_knn_distance(adata, roi_mask, spatial_key)
    elif layer_method == "radius":
        distances = _calculate_radius_distance(coords_2d, roi_mask)
    else:
        raise ValueError(f"Unknown layer_method: {layer_method}")

    # Determine layer boundaries
    if distance_threshold is None:
        # Auto-calculate based on data extent
        max_dist = distances[~roi_mask].max() if (~roi_mask).any() else distances.max()
        layer_boundaries = np.linspace(0, max_dist, n_layers + 1)[1:]
    elif isinstance(distance_threshold, (int, float)):
        # Equal-width layers
        layer_boundaries = [distance_threshold * (i + 1) for i in range(n_layers)]
    else:
        # Custom boundaries
        layer_boundaries = list(distance_threshold)
        n_layers = len(layer_boundaries)

    # Assign layers
    layers = _assign_layers(distances, roi_mask, layer_boundaries, buffer_zone)

    # Generate layer names
    if layer_names is None:
        layer_names = ["center"] + [f"layer_{i+1}" for i in range(n_layers)]
    else:
        if len(layer_names) != n_layers + 1:
            warnings.warn(f"layer_names length ({len(layer_names)}) doesn't match n_layers+1 ({n_layers+1}), using defaults")
            layer_names = ["center"] + [f"layer_{i+1}" for i in range(n_layers)]

    # Map layer indices to names
    layer_map = {i: name for i, name in enumerate(layer_names)}
    layer_labels = pd.Series(layers).map(layer_map).fillna("unassigned").values

    # Add to adata
    adata.obs["spatial_layer"] = pd.Categorical(layer_labels, categories=layer_names)
    adata.obs["roi_status"] = roi_mask

    if return_distance:
        adata.obs["distance_to_roi"] = distances

    # Calculate layer statistics
    layer_stats = _calculate_layer_stats(adata, layers, layer_names, distances, roi_mask)

    # Store parameters and stats
    adata.uns["spatial_layers"] = {
        "params": {
            "roi_type": roi_type,
            "roi_definition": roi_definition if isinstance(roi_definition, (str, list)) else "custom_mask",
            "n_layers": n_layers,
            "layer_method": layer_method,
            "distance_threshold": distance_threshold,
            "buffer_zone": buffer_zone,
            "layer_names": layer_names
        },
        "layer_stats": layer_stats
    }

    print(f"Created {n_layers + 1} layers around {roi_mask.sum()} ROI spots")
    print(f"Layer distribution:")
    for name in layer_names:
        count = (layer_labels == name).sum()
        print(f"  {name}: {count} spots")

    if not inplace:
        return adata


def _parse_roi_definition(
    adata: sc.AnnData,
    roi_definition: Union[str, List[str], np.ndarray],
    roi_type: str
) -> np.ndarray:
    """Parse ROI definition and return boolean mask."""

    if roi_type == "mask":
        if not isinstance(roi_definition, np.ndarray):
            roi_definition = np.array(roi_definition)
        if len(roi_definition) != adata.n_obs:
            raise ValueError(f"Mask length ({len(roi_definition)}) doesn't match n_obs ({adata.n_obs})")
        return roi_definition.astype(bool)

    elif roi_type == "niche":
        if "niche" not in adata.obs and "niche_annotated" not in adata.obs:
            raise ValueError("Niche column not found in adata.obs. Run niche clustering first.")

        niche_col = "niche_annotated" if "niche_annotated" in adata.obs else "niche"

        if isinstance(roi_definition, str):
            roi_definition = [roi_definition]

        return adata.obs[niche_col].isin(roi_definition).values

    elif roi_type == "cell_type":
        # Check if cell type is in obs (from mapping) or in deconvolution results
        if isinstance(roi_definition, str):
            roi_definition = [roi_definition]

        # Try to find in obs columns
        for col in adata.obs.columns:
            if adata.obs[col].dtype == object:
                mask = adata.obs[col].isin(roi_definition).values
                if mask.any():
                    return mask

        # Try deconvolution results in obsm
        for key in adata.obsm.keys():
            if "proportion" in key.lower() or "prediction" in key.lower():
                for cell_type in roi_definition:
                    if cell_type in adata.obsm[key].columns:
                        # Consider spot as ROI if cell type proportion > 0.3
                        return (adata.obsm[key][cell_type] > 0.3).values

        raise ValueError(f"Cell type {roi_definition} not found in adata")

    elif roi_type == "coordinates":
        coords = np.array(roi_definition)
        if coords.ndim == 1:
            coords = coords.reshape(1, -1)

        spatial_coords = adata.obsm["spatial"][:, :2]

        # Find spots within 50μm of center coordinates
        distances = cdist(spatial_coords, coords)
        min_dist = distances.min(axis=1)
        return min_dist < 50  # 50μm radius around center

    else:
        raise ValueError(f"Unknown roi_type: {roi_type}")


def _calculate_distance_to_roi(coords: np.ndarray, roi_mask: np.ndarray) -> np.ndarray:
    """Calculate Euclidean distance from each spot to nearest ROI spot."""
    roi_coords = coords[roi_mask]

    if len(roi_coords) == 0:
        return np.full(len(coords), np.inf)

    # Calculate distance to nearest ROI spot
    distances = cdist(coords, roi_coords)
    min_distances = distances.min(axis=1)

    # Set ROI spots to distance 0
    min_distances[roi_mask] = 0

    return min_distances


def _calculate_knn_distance(
    adata: sc.AnnData,
    roi_mask: np.ndarray,
    spatial_key: str
) -> np.ndarray:
    """Calculate distance as number of KNN steps to ROI."""
    import squidpy as sq

    # Build spatial neighbor graph
    sq.gr.spatial_neighbors(adata, n_neighs=6, coord_type="generic", key_added="layer_knn")

    # Convert to numpy array
    adjacency = adata.obsp["layer_knn_connectivities"].toarray()

    # BFS to find shortest path from each spot to ROI
    distances = np.full(adata.n_obs, -1)
    distances[roi_mask] = 0

    current_layer = 0
    current_spots = set(np.where(roi_mask)[0])

    while current_spots and (distances == -1).any():
        next_spots = set()
        for spot in current_spots:
            neighbors = np.where(adjacency[spot])[0]
            for neighbor in neighbors:
                if distances[neighbor] == -1:
                    distances[neighbor] = current_layer + 1
                    next_spots.add(neighbor)

        current_spots = next_spots
        current_layer += 1

    return distances


def _calculate_radius_distance(coords: np.ndarray, roi_mask: np.ndarray) -> np.ndarray:
    """Calculate distance as radius expansion from ROI center."""
    roi_coords = coords[roi_mask]
    center = roi_coords.mean(axis=0)

    distances = np.sqrt(((coords - center) ** 2).sum(axis=1))
    return distances


def _assign_layers(
    distances: np.ndarray,
    roi_mask: np.ndarray,
    layer_boundaries: List[float],
    buffer_zone: float
) -> np.ndarray:
    """Assign each spot to a layer based on distance."""
    n_spots = len(distances)
    layers = np.full(n_spots, -1, dtype=int)  # -1 = unassigned

    # ROI center is layer 0
    layers[roi_mask] = 0

    # Assign layers based on distance
    for i, boundary in enumerate(layer_boundaries):
        if i == 0:
            # First layer: buffer_zone < distance <= first_boundary
            if buffer_zone > 0:
                mask = (~roi_mask) & (distances > buffer_zone) & (distances <= boundary)
            else:
                mask = (~roi_mask) & (distances <= boundary)
        else:
            # Subsequent layers: previous_boundary < distance <= current_boundary
            prev_boundary = layer_boundaries[i - 1]
            mask = (~roi_mask) & (distances > prev_boundary) & (distances <= boundary)

        layers[mask] = i + 1

    # Assign spots beyond last boundary to last layer
    if len(layer_boundaries) > 0:
        last_boundary = layer_boundaries[-1]
        mask = (~roi_mask) & (distances > last_boundary)
        layers[mask] = len(layer_boundaries)

    return layers


def _calculate_layer_stats(
    adata: sc.AnnData,
    layers: np.ndarray,
    layer_names: List[str],
    distances: np.ndarray,
    roi_mask: np.ndarray
) -> Dict:
    """Calculate statistics for each layer."""
    stats = {}

    for i, name in enumerate(layer_names):
        mask = layers == i
        if mask.any():
            stats[name] = {
                "n_spots": int(mask.sum()),
                "mean_distance": float(distances[mask].mean()),
                "min_distance": float(distances[mask].min()),
                "max_distance": float(distances[mask].max()),
                "fraction_of_total": float(mask.sum() / len(layers))
            }

    # Add unassigned stats
    unassigned = (layers == -1).sum()
    if unassigned > 0:
        stats["unassigned"] = {"n_spots": int(unassigned)}

    return stats


def analyze_layer_gradients(
    adata: sc.AnnData,
    layer_key: str = "spatial_layer",
    features: Optional[List[str]] = None,
    feature_type: str = "obs",
    analysis_method: str = "trend",
    reference_layer: str = "center"
) -> pd.DataFrame:
    """
    Analyze feature gradients across spatial layers.

    Parameters
    ----------
    adata : sc.AnnData
        Data with spatial_layer annotations
    layer_key : str, default="spatial_layer"
        Column in adata.obs containing layer assignments
    features : list, optional
        Features to analyze. If None, uses all features of feature_type
    feature_type : str, default="obs"
        Type of features: "obs" (metadata), "var" (genes), or "obsm"
    analysis_method : str, default="trend"
        Analysis method: "trend", "anova", or "correlation"
    reference_layer : str, default="center"
        Reference layer for fold change calculations

    Returns
    -------
    results : pd.DataFrame
        Gradient analysis results with columns:
        - feature: Feature name
        - layer: Layer name
        - mean_value: Mean feature value in layer
        - log2fc: Log2 fold change vs reference
        - trend: "increasing", "decreasing", "peaked", or "stable"
        - pval: Statistical significance (if applicable)
    """
    # Get features
    if features is None:
        if feature_type == "obs":
            features = adata.obs.select_dtypes(include=[np.number]).columns.tolist()
        elif feature_type == "var":
            features = adata.var_names.tolist()[:100]  # Limit to top 100 genes if not specified
        elif feature_type == "obsm":
            features = list(adata.obsm.keys())

    # Get layer order
    if isinstance(adata.obs[layer_key].dtype, pd.CategoricalDtype):
        layer_order = adata.obs[layer_key].cat.categories.tolist()
    else:
        layer_order = adata.obs[layer_key].unique().tolist()

    results = []

    for feature in features:
        # Extract feature values
        if feature_type == "obs":
            if feature not in adata.obs:
                continue
            values = adata.obs[feature].values
        elif feature_type == "var":
            if feature not in adata.var_names:
                continue
            values = adata[:, feature].X.toarray().flatten()
        elif feature_type == "obsm":
            if feature not in adata.obsm:
                continue
            # For multidimensional features, use mean or first component
            values = adata.obsm[feature].mean(axis=1)

        # Calculate per-layer statistics
        layer_values = {}
        for layer in layer_order:
            mask = adata.obs[layer_key] == layer
            if mask.sum() > 0:
                layer_values[layer] = values[mask]

        if reference_layer not in layer_values:
            continue

        ref_mean = np.mean(layer_values[reference_layer])

        for layer in layer_order:
            if layer not in layer_values:
                continue

            layer_data = layer_values[layer]
            layer_mean = np.mean(layer_data)

            # Calculate log2 fold change
            if ref_mean > 0 and layer_mean > 0:
                log2fc = np.log2(layer_mean / ref_mean)
            else:
                log2fc = np.nan

            # Determine trend
            if len(layer_order) > 2:
                trend = _determine_trend(layer_order, layer_values, feature)
            else:
                trend = "N/A"

            # Statistical test
            if layer != reference_layer and analysis_method in ["anova", "ttest"]:
                _, pval = stats.ttest_ind(layer_values[reference_layer], layer_data)
            else:
                pval = np.nan

            results.append({
                "feature": feature,
                "layer": layer,
                "mean_value": layer_mean,
                "log2fc": log2fc,
                "trend": trend,
                "pval": pval
            })

    results_df = pd.DataFrame(results)

    # FDR correction
    if "pval" in results_df.columns and not results_df["pval"].isna().all():
        from statsmodels.stats.multitest import multipletests
        valid_pvals = results_df["pval"].dropna()
        if len(valid_pvals) > 0:
            _, qvals, _, _ = multipletests(valid_pvals, method="fdr_bh")
            results_df.loc[results_df["pval"].notna(), "qval"] = qvals

    return results_df


def _determine_trend(layer_order: List[str], layer_values: Dict, feature: str) -> str:
    """Determine the trend pattern across layers."""
    means = [np.mean(layer_values.get(layer, [0])) for layer in layer_order]

    if all(means[i] <= means[i+1] for i in range(len(means)-1)):
        return "increasing"
    elif all(means[i] >= means[i+1] for i in range(len(means)-1)):
        return "decreasing"
    elif means[0] < means[1] and means[-2] > means[-1]:
        return "peaked"
    elif means[0] > means[1] and means[-2] < means[-1]:
        return "valley"
    else:
        return "variable"


def visualize_spatial_layers(
    adata: sc.AnnData,
    layer_key: str = "spatial_layer",
    color_by: Optional[str] = None,
    show_distance: bool = False,
    figsize: Tuple[int, int] = (15, 5),
    save: Optional[str] = None,
    **kwargs
):
    """
    Visualize spatial layers on tissue.

    Parameters
    ----------
    adata : sc.AnnData
    layer_key : str
        Column containing layer assignments
    color_by : str, optional
        Additional feature to color by (e.g., cell type proportion)
    show_distance : bool
        Whether to show distance to ROI
    figsize : tuple
        Figure size
    save : str, optional
        Path to save figure
    **kwargs
        Additional arguments passed to sq.pl.spatial_scatter
    """
    import matplotlib.pyplot as plt

    n_panels = 2 if show_distance else 1
    if color_by:
        n_panels += 1

    fig, axes = plt.subplots(1, n_panels, figsize=figsize)
    if n_panels == 1:
        axes = [axes]

    # Panel 1: Layer assignment
    sq.pl.spatial_scatter(
        adata,
        color=layer_key,
        ax=axes[0],
        title="Spatial Layers",
        show=False,
        **kwargs
    )

    panel_idx = 1

    # Panel 2: Distance to ROI
    if show_distance and "distance_to_roi" in adata.obs:
        sq.pl.spatial_scatter(
            adata,
            color="distance_to_roi",
            ax=axes[panel_idx],
            title="Distance to ROI (μm)",
            cmap="viridis",
            show=False,
            **kwargs
        )
        panel_idx += 1

    # Panel 3: Additional feature
    if color_by:
        sq.pl.spatial_scatter(
            adata,
            color=color_by,
            ax=axes[panel_idx],
            title=color_by,
            show=False,
            **kwargs
        )

    plt.tight_layout()

    if save:
        plt.savefig(save, dpi=300, bbox_inches="tight")

    plt.show()


def plot_layer_heatmap(
    gradient_results: pd.DataFrame,
    value_col: str = "mean_value",
    normalize: bool = True,
    figsize: Tuple[int, int] = (10, 8),
    save: Optional[str] = None
):
    """
    Plot heatmap of feature values across layers.

    Parameters
    ----------
    gradient_results : pd.DataFrame
        Output from analyze_layer_gradients
    value_col : str
        Column to visualize ("mean_value" or "log2fc")
    normalize : bool
        Whether to z-score normalize features
    figsize : tuple
    save : str, optional
    """
    import matplotlib.pyplot as plt
    import seaborn as sns

    # Pivot to matrix
    pivot = gradient_results.pivot(index="feature", columns="layer", values=value_col)

    # Ensure proper layer order
    layer_order = gradient_results["layer"].unique()
    pivot = pivot.reindex(columns=layer_order)

    # Normalize
    if normalize and value_col == "mean_value":
        pivot = (pivot.T - pivot.mean(axis=1)) / pivot.std(axis=1).T

    # Plot
    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(pivot, cmap="RdBu_r", center=0, ax=ax, annot=True, fmt=".2f")
    ax.set_title(f"Feature Values Across Layers ({value_col})")
    ax.set_xlabel("Layer")
    ax.set_ylabel("Feature")

    if save:
        plt.savefig(save, dpi=300, bbox_inches="tight")

    plt.show()
