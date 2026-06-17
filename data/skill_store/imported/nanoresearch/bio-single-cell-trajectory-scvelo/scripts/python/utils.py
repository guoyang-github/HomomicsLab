"""
scVelo Utility Module
=====================

Utility functions for RNA velocity analysis including data validation,
parameter optimization, and result processing.
"""

import numpy as np
import pandas as pd
from typing import Optional, Union, List, Dict, Tuple, Any
import warnings


def check_velocity_layers(
    adata,
    spliced_layer: str = 'spliced',
    unspliced_layer: str = 'unspliced',
    raise_error: bool = True
) -> bool:
    """
    Check if required spliced/unspliced layers exist in AnnData.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    spliced_layer : str
        Name of spliced counts layer
    unspliced_layer : str
        Name of unspliced counts layer
    raise_error : bool
        Whether to raise an error if layers are missing

    Returns
    -------
    bool
        True if all required layers exist

    Raises
    ------
    ValueError
        If required layers are missing and raise_error=True
    """
    missing = []

    if spliced_layer not in adata.layers:
        missing.append(spliced_layer)
    if unspliced_layer not in adata.layers:
        missing.append(unspliced_layer)

    if missing:
        msg = f"Missing required layers: {missing}. Available layers: {list(adata.layers.keys())}"
        if raise_error:
            raise ValueError(msg)
        else:
            warnings.warn(msg)
            return False

    return True


def check_velocity_computed(
    adata,
    raise_error: bool = True
) -> bool:
    """
    Check if velocity has been computed in AnnData.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    raise_error : bool
        Whether to raise an error if velocity is not computed

    Returns
    -------
    bool
        True if velocity is computed
    """
    if 'velocity' not in adata.layers:
        if raise_error:
            raise ValueError("Velocity not computed. Run velocity estimation first.")
        return False
    return True


def estimate_min_counts(
    adata,
    spliced_layer: str = 'spliced',
    unspliced_layer: str = 'unspliced',
    percentiles: List[int] = [10, 25, 50]
) -> Dict[str, Any]:
    """
    Estimate minimum count thresholds based on data distribution.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    spliced_layer : str
        Name of spliced counts layer
    unspliced_layer : str
        Name of unspliced counts layer
    percentiles : list
        Percentiles to compute for guidance

    Returns
    -------
    dict
        Dictionary with count statistics
    """
    check_velocity_layers(adata, spliced_layer, unspliced_layer)

    spliced = adata.layers[spliced_layer]
    unspliced = adata.layers[unspliced_layer]

    # Gene-level sums
    spliced_sum = np.array(spliced.sum(axis=0)).flatten()
    unspliced_sum = np.array(unspliced.sum(axis=0)).flatten()

    stats = {
        'spliced': {
            'mean': float(np.mean(spliced_sum)),
            'median': float(np.median(spliced_sum)),
            'std': float(np.std(spliced_sum)),
            'percentiles': {p: float(np.percentile(spliced_sum, p)) for p in percentiles}
        },
        'unspliced': {
            'mean': float(np.mean(unspliced_sum)),
            'median': float(np.median(unspliced_sum)),
            'std': float(np.std(unspliced_sum)),
            'percentiles': {p: float(np.percentile(unspliced_sum, p)) for p in percentiles}
        },
        'recommended_min_counts': max(
            int(np.percentile(unspliced_sum, 10)),
            10
        )
    }

    return stats


def optimize_velocity_params(
    adata,
    n_jobs: int = -1,
    n_values: int = 5
) -> Dict[str, Any]:
    """
    Optimize velocity estimation parameters by grid search.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix (preprocessed)
    n_jobs : int
        Number of parallel jobs (-1 for all cores)
    n_values : int
        Number of values to test for each parameter

    Returns
    -------
    dict
        Dictionary with optimal parameters and scores
    """
    try:
        import scvelo as scv
    except ImportError:
        raise ImportError("scvelo is required for parameter optimization")

    warnings.warn("Parameter optimization can be computationally expensive. "
                  "Consider using on a subset of data first.")

    # Define parameter grid
    min_r2_values = np.linspace(0.01, 0.5, n_values)
    min_r2_adjusted_values = np.linspace(0.01, 0.5, n_values)

    best_score = -np.inf
    best_params = {}

    # Store original velocity genes
    original_velocity_genes = adata.var.get('velocity_genes', pd.Series(False, index=adata.var_names)).copy()

    for min_r2 in min_r2_values:
        for min_r2_adj in min_r2_adjusted_values:
            try:
                # Compute velocity with current parameters
                scv.tl.velocity(
                    adata,
                    min_r2=min_r2,
                    min_r2_adjusted=min_r2_adj,
                    mode='stochastic'
                )

                # Compute velocity graph
                scv.tl.velocity_graph(adata)

                # Evaluate: number of velocity genes and graph connectivity
                n_velocity_genes = adata.var['velocity_genes'].sum()
                graph_connectivity = (adata.uns['velocity_graph'] > 0).sum() / adata.n_obs

                # Score: balance between velocity genes and connectivity
                if n_velocity_genes > 10 and graph_connectivity > 0:
                    score = np.log1p(n_velocity_genes) * graph_connectivity

                    if score > best_score:
                        best_score = score
                        best_params = {
                            'min_r2': min_r2,
                            'min_r2_adjusted': min_r2_adj,
                            'n_velocity_genes': int(n_velocity_genes),
                            'graph_connectivity': float(graph_connectivity),
                            'score': float(score)
                        }
            except Exception:
                continue

    # Restore original velocity genes
    adata.var['velocity_genes'] = original_velocity_genes

    if not best_params:
        warnings.warn("Could not find optimal parameters. Using defaults.")
        return {'min_r2': 0.01, 'min_r2_adjusted': 0.01}

    return best_params


def get_velocity_genes_summary(
    adata,
    n_top: int = 20
) -> pd.DataFrame:
    """
    Get summary of velocity genes.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with velocity genes identified
    n_top : int
        Number of top genes to return

    Returns
    -------
    pd.DataFrame
        DataFrame with velocity gene information
    """
    if 'velocity_genes' not in adata.var.columns:
        raise ValueError("Velocity genes not computed. Run velocity estimation first.")

    velocity_genes = adata.var_names[adata.var['velocity_genes']]

    if len(velocity_genes) == 0:
        warnings.warn("No velocity genes found")
        return pd.DataFrame()

    # Build summary
    summary_data = []

    for gene in velocity_genes[:n_top]:
        gene_info = {'gene': gene}

        # Get R2 if available
        if 'fit_r2' in adata.var.columns:
            gene_info['r2'] = adata.var.loc[gene, 'fit_r2']

        # Get gamma if available
        if 'fit_gamma' in adata.var.columns:
            gene_info['gamma'] = adata.var.loc[gene, 'fit_gamma']

        # Get likelihood if available
        if 'fit_likelihood' in adata.var.columns:
            gene_info['likelihood'] = adata.var.loc[gene, 'fit_likelihood']

        # Get velocity ratio
        if 'fit_velocity_ratio' in adata.var.columns:
            gene_info['velocity_ratio'] = adata.var.loc[gene, 'fit_velocity_ratio']

        summary_data.append(gene_info)

    return pd.DataFrame(summary_data)


def subset_high_velocity_cells(
    adata,
    quantile: float = 0.8,
    inplace: bool = False
):
    """
    Subset AnnData to cells with high velocity magnitude.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with velocity computed
    quantile : float
        Quantile threshold (0-1)
    inplace : bool
        Whether to modify adata in place

    Returns
    -------
    AnnData or None
        Subsetted AnnData if inplace=False
    """
    check_velocity_computed(adata)

    velocity = adata.layers['velocity']
    velocity_magnitude = np.sqrt(np.power(velocity, 2).sum(axis=1))

    threshold = np.quantile(velocity_magnitude, quantile)
    high_velocity_mask = velocity_magnitude >= threshold

    if inplace:
        # This doesn't actually subset in place, but follows scanpy convention
        warnings.warn("Subset operation returns new object. Use inplace=False and assign result.")

    return adata[high_velocity_mask].copy()


def merge_velocity_results(
    adata_original,
    adata_velocity,
    velocity_layers: List[str] = ['velocity', 'velocity_u']
) -> Any:
    """
    Merge velocity results back into original AnnData.

    Parameters
    ----------
    adata_original : AnnData
        Original annotated data matrix
    adata_velocity : AnnData
        AnnData with velocity results
    velocity_layers : list
        List of velocity layers to transfer

    Returns
    -------
    AnnData
        Original AnnData with velocity results added
    """
    adata_merged = adata_original.copy()

    # Transfer velocity layers
    for layer in velocity_layers:
        if layer in adata_velocity.layers:
            adata_merged.layers[layer] = adata_velocity.layers[layer]

    # Transfer velocity-related obs
    velocity_obs = ['velocity_self_transition', 'root_cells', 'end_points',
                    'velocity_confidence', 'latent_time']
    for obs_key in velocity_obs:
        if obs_key in adata_velocity.obs.columns:
            adata_merged.obs[obs_key] = adata_velocity.obs[obs_key]

    # Transfer velocity-related var
    velocity_var = ['velocity_genes', 'fit_r2', 'fit_gamma', 'fit_beta',
                    'fit_likelihood', 'fit_velocity_ratio']
    for var_key in velocity_var:
        if var_key in adata_velocity.var.columns:
            adata_merged.var[var_key] = adata_velocity.var[var_key]

    # Transfer velocity-related uns
    velocity_uns = ['velocyto_params', 'velocity_graph', 'velocity_graph_neg']
    for uns_key in velocity_uns:
        if uns_key in adata_velocity.uns:
            adata_merged.uns[uns_key] = adata_velocity.uns[uns_key]

    return adata_merged


def export_velocity_to_dataframe(
    adata,
    obs_keys: Optional[List[str]] = None,
    layer_keys: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Export velocity results to pandas DataFrame.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with velocity computed
    obs_keys : list, optional
        obs keys to include (defaults to velocity-related)
    layer_keys : list, optional
        layer keys to include

    Returns
    -------
    pd.DataFrame
        DataFrame with velocity results
    """
    if obs_keys is None:
        obs_keys = ['velocity_self_transition', 'root_cells', 'end_points',
                   'velocity_confidence', 'latent_time']
        obs_keys = [k for k in obs_keys if k in adata.obs.columns]

    if layer_keys is None:
        layer_keys = ['velocity', 'velocity_u']
        layer_keys = [k for k in layer_keys if k in adata.layers]

    # Start with cell identifiers
    data = {'cell_id': adata.obs_names}

    # Add obs data
    for key in obs_keys:
        if key in adata.obs.columns:
            data[key] = adata.obs[key].values

    # Add embedding coordinates if available
    for basis in ['umap', 'tsne', 'pca']:
        if f'X_{basis}' in adata.obsm:
            coords = adata.obsm[f'X_{basis}']
            data[f'{basis}_1'] = coords[:, 0]
            data[f'{basis}_2'] = coords[:, 1]
            if coords.shape[1] > 2:
                data[f'{basis}_3'] = coords[:, 2]
            break

    df = pd.DataFrame(data)

    # Note: layer data (velocity vectors) are typically large
    # We export summary statistics instead
    for layer_key in layer_keys:
        layer_data = adata.layers[layer_key]
        df[f'{layer_key}_magnitude'] = np.sqrt(np.power(layer_data, 2).sum(axis=1))
        df[f'{layer_key}_mean'] = np.abs(layer_data).mean(axis=1)
        df[f'{layer_key}_max'] = np.abs(layer_data).max(axis=1)

    return df


def validate_velocity_consistency(
    adata,
    cell_type_key: Optional[str] = None,
    min_confidence: float = 0.5
) -> Dict[str, Any]:
    """
    Validate velocity consistency within and across cell types.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with velocity computed
    cell_type_key : str, optional
        Key for cell type annotations
    min_confidence : float
        Minimum confidence threshold

    Returns
    -------
    dict
        Dictionary with validation metrics
    """
    check_velocity_computed(adata)

    results = {
        'n_cells': adata.n_obs,
        'n_velocity_genes': int(adata.var['velocity_genes'].sum()) if 'velocity_genes' in adata.var.columns else None,
        'velocity_mode': adata.uns.get('velocyto_params', {}).get('mode', 'unknown')
    }

    # Check confidence distribution
    if 'velocity_confidence' in adata.obs.columns:
        confidence = adata.obs['velocity_confidence']
        results['confidence'] = {
            'mean': float(confidence.mean()),
            'median': float(confidence.median()),
            'std': float(confidence.std()),
            'fraction_high_confidence': float((confidence >= min_confidence).mean())
        }

    # Check cell type consistency
    if cell_type_key and cell_type_key in adata.obs.columns:
        cell_types = adata.obs[cell_type_key].unique()
        ct_confidence = {}

        for ct in cell_types:
            mask = adata.obs[cell_type_key] == ct
            if 'velocity_confidence' in adata.obs.columns:
                ct_confidence[ct] = {
                    'mean_confidence': float(adata.obs.loc[mask, 'velocity_confidence'].mean()),
                    'n_cells': int(mask.sum())
                }

        results['cell_type_confidence'] = ct_confidence

    # Check latent time ordering if available
    if 'latent_time' in adata.obs.columns and cell_type_key in adata.obs.columns:
        lt_by_ct = adata.obs.groupby(cell_type_key)['latent_time'].mean().sort_values()
        results['latent_time_progression'] = lt_by_ct.to_dict()

    return results


def get_velocity_summary_stats(
    adata
) -> Dict[str, Any]:
    """
    Get comprehensive summary statistics for velocity analysis.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with velocity computed

    Returns
    -------
    dict
        Dictionary with summary statistics
    """
    stats = {
        'data_shape': {'cells': adata.n_obs, 'genes': adata.n_vars},
        'velocity_params': adata.uns.get('velocyto_params', {})
    }

    # Velocity genes
    if 'velocity_genes' in adata.var.columns:
        stats['n_velocity_genes'] = int(adata.var['velocity_genes'].sum())
        stats['velocity_gene_fraction'] = float(adata.var['velocity_genes'].mean())

    # Latent time
    if 'latent_time' in adata.obs.columns:
        lt = adata.obs['latent_time']
        stats['latent_time'] = {
            'min': float(lt.min()),
            'max': float(lt.max()),
            'mean': float(lt.mean()),
            'std': float(lt.std())
        }

    # Terminal states
    if 'root_cells' in adata.obs.columns:
        stats['n_root_cells'] = int(adata.obs['root_cells'].sum())
    if 'end_points' in adata.obs.columns:
        stats['n_end_points'] = int(adata.obs['end_points'].sum())

    # Confidence
    if 'velocity_confidence' in adata.obs.columns:
        conf = adata.obs['velocity_confidence']
        stats['velocity_confidence'] = {
            'mean': float(conf.mean()),
            'median': float(conf.median()),
            'min': float(conf.min()),
            'max': float(conf.max())
        }

    # Graph connectivity
    if 'velocity_graph' in adata.uns:
        graph = adata.uns['velocity_graph']
        stats['velocity_graph'] = {
            'shape': graph.shape,
            'nonzero_fraction': float((graph > 0).sum() / graph.size),
            'max_value': float(graph.max())
        }

    return stats


def split_by_trajectory_branch(
    adata,
    root_cells: Optional[List[int]] = None,
    n_branches: int = 2
) -> Dict[str, Any]:
    """
    Split cells by trajectory branches based on velocity graph.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with velocity graph computed
    root_cells : list, optional
        Indices of root cells (if None, uses computed root_cells)
    n_branches : int
        Number of branches to identify

    Returns
    -------
    dict
        Dictionary with branch assignments and statistics
    """
    if 'velocity_graph' not in adata.uns:
        raise ValueError("Velocity graph not computed. Run velocity_graph first.")

    if root_cells is None and 'root_cells' in adata.obs.columns:
        root_cells = np.where(adata.obs['root_cells'].values > 0)[0].tolist()

    if not root_cells:
        raise ValueError("No root cells specified or computed")

    # Use graph diffusion to assign cells to branches
    graph = adata.uns['velocity_graph'].toarray()

    # Simple approach: assign based on proximity to roots
    assignments = np.zeros(adata.n_obs, dtype=int)

    for i, root in enumerate(root_cells[:n_branches]):
        # Diffuse from root
        distances = np.zeros(adata.n_obs)
        distances[root] = 1

        # Simple propagation (can be improved with proper diffusion)
        for _ in range(10):  # iterations
            distances = graph.T @ distances + distances
            distances = distances / (distances.sum() + 1e-10)

        if i == 0:
            distances_prev = distances
        else:
            # Assign cells closer to this root
            mask = distances > distances_prev
            assignments[mask] = i
            distances_prev = np.maximum(distances_prev, distances)

    # Create result
    branch_names = [f'branch_{i}' for i in range(n_branches)]
    branch_counts = [int((assignments == i).sum()) for i in range(n_branches)]

    return {
        'branch_assignments': assignments,
        'branch_names': branch_names,
        'branch_counts': branch_counts,
        'root_cells': root_cells
    }
